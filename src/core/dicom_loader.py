"""
DICOM File Loader

This module handles loading DICOM files from various sources including:
- Single files
- Multiple files
- Directories (with recursive search)
- Files regardless of extension

When loading a folder, the following are excluded from being tried as DICOM:
- .DS_Store (macOS folder metadata)
- VERSION / DICOMDIR / LOCKFILE sentinel files that do not contain image/SR payloads
- Files whose name starts with ~$ (e.g. Office temporary/lock files)

Inputs:
    - File paths (single or multiple)
    - Directory paths
    - File objects
    
Outputs:
    - List of successfully loaded DICOM datasets
    - List of files that failed to load (with error messages)
    
Requirements:
    - pydicom library for DICOM file reading
    - pathlib for path handling
    - os for file system operations
"""

import gc
import logging
import os
import threading
import time
import warnings
from collections.abc import Callable
from pathlib import Path

import pydicom
from pydicom.errors import InvalidDicomError
from PySide6.QtWidgets import QApplication

from core.dicom_loader_file import (
    build_compression_install_error_detail,
    build_generic_load_error_message,
    build_memory_error_message,
    format_defer_pixel_data_message,
    format_multiframe_load_complete_message,
    format_multiframe_load_start_message,
    normalize_validation_error,
    preload_enhanced_multiframe_pixels,
)
from core.multiframe_handler import get_frame_count, is_multiframe
from core.sr_sop_classes import (
    is_structured_report_dataset,
    structured_report_storage_label,
)
from utils.privacy import safe_event_fields

_MAIN_THREAD_ID = threading.main_thread().ident
_logger = logging.getLogger(__name__)


def _is_main_thread() -> bool:
    """Return True if the caller is on the main (UI) thread."""
    return threading.current_thread().ident == _MAIN_THREAD_ID


def _process_events_if_main_thread() -> None:
    """Pump Qt events on the main thread so progress UI stays responsive."""
    if _is_main_thread():
        QApplication.processEvents()


def _notify_file_load_progress(
    progress_callback: Callable[[str, int | None, int | None], None] | None,
    message: str,
    current_frames: int | None = None,
    total_frames: int | None = None,
) -> None:
    """Invoke load-file progress callback and process Qt events on the main thread."""
    if progress_callback:
        progress_callback(message, current_frames, total_frames)
        _process_events_if_main_thread()


def _read_dicom_dataset(
    file_path: str,
    defer_size: int | None,
    filename: str,
    progress_callback: Callable[[str, int | None, int | None], None] | None,
) -> tuple[pydicom.Dataset, float]:
    """
    Read a DICOM dataset with optional defer_size branching.

    Returns:
        Tuple of (dataset, read_time_seconds).
    """
    read_start = time.time()
    if defer_size is not None:
        file_size = os.path.getsize(file_path)
        if file_size > defer_size:
            file_size_mb = file_size / (1024 * 1024)
            defer_size_mb = defer_size / (1024 * 1024)
            _notify_file_load_progress(
                progress_callback,
                format_defer_pixel_data_message(filename, file_size_mb, defer_size_mb),
            )
            dataset = pydicom.dcmread(file_path, force=True, defer_size=defer_size)
        else:
            dataset = pydicom.dcmread(file_path, force=True)
    else:
        dataset = pydicom.dcmread(file_path, force=True)
    return dataset, time.time() - read_start


def _annotate_structured_report(dataset: pydicom.Dataset) -> None:
    """Tag structured-report datasets that carry no image pixels."""
    if is_structured_report_dataset(dataset):
        dataset._no_pixel_reason = "structured_report"
        dataset._structured_report_label = structured_report_storage_label(
            str(getattr(dataset, "SOPClassUID", "") or "")
        )


def _finalize_multiframe_metadata(
    loader: "DICOMLoader",
    dataset: pydicom.Dataset,
    file_path: str,
    filename: str,
    progress_callback: Callable[[str, int | None, int | None], None] | None,
) -> tuple[float, bool]:
    """
    Apply multi-frame metadata and optionally pre-load enhanced multi-frame pixels.

    Returns:
        ``(pixel_load_time_seconds, should_abort_load)``.
    """
    if not is_multiframe(dataset):
        dataset._num_frames = 1
        dataset._is_multiframe = False
        return 0.0, False

    num_frames = get_frame_count(dataset)
    dataset._num_frames = num_frames
    dataset._is_multiframe = True

    if not hasattr(dataset, "PerFrameFunctionalGroupsSequence"):
        return 0.0, False

    _notify_file_load_progress(
        progress_callback,
        format_multiframe_load_start_message(filename, num_frames),
        total_frames=num_frames,
    )

    if loader._cancelled:
        return 0.0, True

    pixel_load_time, should_abort = preload_enhanced_multiframe_pixels(
        dataset,
        file_path,
        num_frames,
        classify_pixel_data_error=_classify_pixel_data_error,
        compression_error_files=loader._compression_error_files,
        failed_files=loader.failed_files,
        on_compression_decode_failed=lambda exc: _logger.warning(
            "DICOM compression decode failed",
            extra=safe_event_fields("dicom.decode", error=exc),
        ),
        on_pixel_preload_failed=lambda exc: _logger.warning(
            "DICOM pixel pre-load failed",
            extra=safe_event_fields("dicom.pixel_preload", error=exc),
        ),
    )
    if should_abort:
        return pixel_load_time, True

    if pixel_load_time > 0:
        _notify_file_load_progress(
            progress_callback,
            format_multiframe_load_complete_message(filename, num_frames),
            current_frames=num_frames,
            total_frames=num_frames,
        )
    return pixel_load_time, False


def _record_load_file_generic_exception(
    loader: "DICOMLoader",
    file_path: str,
    dataset: pydicom.Dataset | None,
    exc: Exception,
) -> None:
    """Classify and append a generic ``load_file`` exception to ``failed_files``."""
    error_msg_str = str(exc)
    is_compression_error, classified_message = _classify_pixel_data_error(dataset, error_msg_str)

    if is_compression_error:
        error_msg = build_compression_install_error_detail(classified_message)
        if file_path not in loader._compression_error_files:
            loader._compression_error_files.add(file_path)
            _logger.warning(
                "DICOM compression decode failed",
                extra=safe_event_fields("dicom.decode", error=exc),
            )
    else:
        error_msg = build_generic_load_error_message(classified_message, type(exc).__name__)
    loader.failed_files.append((file_path, error_msg))

# Default defer size: 250MB - files larger than this will defer pixel data loading
# This balances fast initial load with responsive slice navigation
DEFAULT_DEFER_SIZE = 262144000  # 250 MB in bytes

# Basename patterns to skip when loading a folder as DICOM (system/temp files, not DICOM)
_SKIP_BASENAMES = frozenset({
    ".ds_store",  # macOS folder metadata
    "version",
    "dicomdir",
    "lockfile",
})
_SKIP_BASENAME_PREFIX = "~$"  # Office/temp lock files (e.g. ~$document.docx)

# Extensions to skip (never attempt as DICOM). Lowercase. DICOM often uses .dcm or no extension.
_SKIP_EXTENSIONS = frozenset({
    "pdf", "png", "jpg", "jpeg", "mp3", "m4a", "epub", "txt", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "rtf", "py", "md", "csv", "json", "xml", "html", "htm", "zip", "exe", "dll",
    "bat", "sh", "js", "ts", "jsx", "tsx", "vb", "java", "c", "cpp", "h", "hpp", "rs", "go",
    "swift", "kt", "rb", "php", "mov", "avi", "mp4", "wav", "wmv", "gif", "bmp", "tiff", "tif",
    "ico", "webp", "svg",
})


def _classify_pixel_data_error(dataset, error_msg: str) -> tuple[bool, str]:
    """Classify pixel-data failures for more accurate user-facing messages."""
    lowered = error_msg.lower()

    if (
        "one of pixel data, float pixel data or double float pixel data must be present"
        in lowered
    ):
        modality = getattr(dataset, "Modality", None)
        sop_class_uid = getattr(dataset, "SOPClassUID", None)
        if modality == "SR":
            return (
                False,
                f"DICOM Structured Report (SR) objects do not contain image pixels. "
                f"SOPClassUID={sop_class_uid}"
            )
        return False, "DICOM object does not contain Pixel Data."

    is_compression_error = (
        "pylibjpeg-libjpeg" in lowered or
        "missing required dependencies" in lowered or
        "unable to decode" in lowered or
        "decoder" in lowered
    )
    if is_compression_error:
        return True, "Compressed DICOM pixel data cannot be decoded."

    return False, error_msg


def _should_skip_path(path: str | Path) -> bool:
    """
    Return True if this path should not be tried as DICOM (system/temp files or known non-DICOM extensions).
    """
    p = Path(path) if isinstance(path, str) else path
    name = p.name
    if not name:
        return True
    if name.lower() in _SKIP_BASENAMES:
        return True
    if name.startswith(_SKIP_BASENAME_PREFIX):
        return True
    ext = p.suffix
    return bool(ext and ext.lstrip(".").lower() in _SKIP_EXTENSIONS)


def _should_skip_file_for_dicom(path: Path) -> bool:
    """
    Return True if this path should not be tried as DICOM when loading a folder.
    Excludes system/temp files and known non-DICOM extensions.
    """
    return _should_skip_path(path)


def should_skip_path_for_dicom(path: str | Path) -> bool:
    """
    Public API: return True if this path should be skipped for DICOM loading (handler uses this to filter file lists).
    """
    return _should_skip_path(path)


class DICOMLoader:
    """
    Handles loading DICOM files from various sources.
    
    Supports:
    - Single file loading
    - Multiple file loading
    - Recursive directory scanning
    - Extension-agnostic file loading (attempts to load all files as DICOM)
    """

    def __init__(self):
        """Initialize the DICOM loader."""
        self.loaded_files: list[pydicom.Dataset] = []
        self.failed_files: list[tuple[str, str]] = []  # (path, error_message)
        self._compression_error_files: set[str] = set()  # Track files that have shown compression errors
        self._cancelled: bool = False  # Flag to track cancellation request
        self.attempted_file_count: int = 0  # Set at start of load_files/load_directory for status bar
        self.extension_skipped_count: int = 0  # Files skipped by extension (handler or directory scan)

    def get_attempted_file_count(self) -> int:
        """Return the number of files attempted in the last load (for status bar 'X files processed')."""
        return getattr(self, "attempted_file_count", 0)

    def set_extension_skipped_count(self, count: int) -> None:
        """Set the number of files skipped by extension before load (handler sets this when filtering file list)."""
        self.extension_skipped_count = count

    def get_extension_skipped_count(self) -> int:
        """Return the number of files skipped by extension in the last load (directory scan or handler filter)."""
        return getattr(self, "extension_skipped_count", 0)

    def validate_dicom_file(self, file_path: str) -> tuple[bool, str | None]:
        """
        Validate DICOM file before loading pixel data.
        
        Checks for issues that might cause crashes:
        - Excessive padding in multi-frame files
        - Missing required tags
        - Corrupted or malformed data
        
        Note: Enhanced Multi-frame DICOMs (with PerFrameFunctionalGroupsSequence)
        are skipped from validation as they don't expose PixelData when loaded
        with stop_before_pixels=True.
        
        For small files (< 1MB), validation is skipped to improve loading speed,
        as these files are unlikely to have padding issues.
        
        Args:
            file_path: Path to DICOM file
            
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file appears safe to load, False otherwise
            - error_message: Description of the problem if not valid, None if valid
        """
        try:
            # Skip validation for small files (< 1MB) to improve loading speed
            # Small files are unlikely to have the padding issues we're checking for
            file_size = os.path.getsize(file_path)
            if file_size < 1048576:  # 1 MB
                return True, None

            # Read metadata only, no pixel data
            ds = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)

            # Skip validation for Enhanced Multi-frame DICOMs
            # These files use PerFrameFunctionalGroupsSequence and store pixel data
            # differently - they cannot be validated using stop_before_pixels
            if hasattr(ds, 'PerFrameFunctionalGroupsSequence'):
                # print(f"[VALIDATION] Skipping validation for Enhanced Multi-frame DICOM: {os.path.basename(file_path)}")
                return True, None

            # Check for multi-frame
            num_frames = getattr(ds, 'NumberOfFrames', None)
            if num_frames and int(num_frames) > 1:
                # Validate required tags for multi-frame
                if not hasattr(ds, 'Rows') or not hasattr(ds, 'Columns'):
                    return False, "Multi-frame file missing Rows/Columns tags"

                # Calculate expected pixel data size
                rows = int(ds.Rows)
                cols = int(ds.Columns)
                frames = int(num_frames)
                bits_allocated = int(getattr(ds, 'BitsAllocated', 16))
                bytes_per_pixel = bits_allocated // 8

                expected_size = rows * cols * frames * bytes_per_pixel

                # Check if pixel data element exists and get its length
                if hasattr(ds, 'PixelData'):
                    actual_size = len(ds.PixelData)
                    padding_ratio = (actual_size - expected_size) / actual_size if actual_size > 0 else 0

                    # Warn if excessive padding (>50%)
                    if padding_ratio > 0.5:
                        return False, (
                            f"Multi-frame file has excessive padding ({padding_ratio*100:.1f}%). "
                            f"This may indicate corruption or unsupported format. "
                            f"Expected {expected_size:,} bytes but found {actual_size:,} bytes."
                        )

            return True, None
        except Exception as e:
            return False, f"Validation failed: {e!s}"

    def cancel(self) -> None:
        """Set cancellation flag to stop loading operations."""
        self._cancelled = True

    def reset_cancellation(self) -> None:
        """Reset cancellation flag to allow new loading operations."""
        self._cancelled = False

    def is_cancelled(self) -> bool:
        """Check if loading has been cancelled.
        
        Returns:
            True if cancellation has been requested, False otherwise
        """
        return self._cancelled

    def load_file(self, file_path: str, defer_size: int | None = None,
                  progress_callback: Callable[[str, int | None, int | None], None] | None = None) -> pydicom.Dataset | None:
        """
        Load a single DICOM file.
        
        Args:
            file_path: Path to the DICOM file
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Default None means load all data immediately.
            progress_callback: Optional callback function for progress updates.
                              Signature: (message: str, current_frames: Optional[int], total_frames: Optional[int]) -> None
            
        Returns:
            pydicom.Dataset if successful, None otherwise
        """
        dataset = None  # bound up-front so the except handler can reference it
        try:
            filename = os.path.basename(file_path)

            _notify_file_load_progress(progress_callback, f"Loading {filename}...")

            is_valid, error_msg = self.validate_dicom_file(file_path)

            if not is_valid:
                _logger.warning(
                    "DICOM validation failed",
                    extra=safe_event_fields("dicom.validate"),
                )
                self.failed_files.append((file_path, normalize_validation_error(error_msg)))
                return None

            if self._cancelled:
                return None

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='.*excess padding.*', category=UserWarning)
                _process_events_if_main_thread()
                dataset, _ = _read_dicom_dataset(
                    file_path, defer_size, filename, progress_callback
                )

            _annotate_structured_report(dataset)

            _, should_abort = _finalize_multiframe_metadata(
                self, dataset, file_path, filename, progress_callback
            )
            if should_abort:
                return None

            return dataset

        except MemoryError as e:
            self.failed_files.append((file_path, build_memory_error_message(e)))
            return None
        except InvalidDicomError as e:
            self.failed_files.append((file_path, f"Invalid DICOM file: {e!s}"))
            return None
        except OSError as e:
            self.failed_files.append((file_path, f"File system error: {e!s}"))
            return None
        except Exception as e:
            _record_load_file_generic_exception(
                self,
                file_path,
                dataset if 'dataset' in locals() else None,
                e,
            )
            return None

    def load_files(self, file_paths: list[str], defer_size: int | None = None,
                   progress_callback: Callable[[int, int, str], None] | None = None) -> list[pydicom.Dataset]:
        """
        Load multiple DICOM files.
        
        Args:
            file_paths: List of file paths to load
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Defaults to DEFAULT_DEFER_SIZE (1MB) if None.
            progress_callback: Optional callback function called during loading.
                              Signature: (current: int, total: int, filename: str) -> None
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        # Use default defer size if not specified
        if defer_size is None:
            defer_size = DEFAULT_DEFER_SIZE

        self.loaded_files = []
        self.failed_files = []
        # extension_skipped_count is left as set by handler when it filtered the file list (if any)

        total_files = len(file_paths)
        self.attempted_file_count = total_files

        last_update_time = time.time()
        update_interval = 0.05  # Update every 50ms

        # Debugging: Track loading performance

        # print(f"[LOAD DEBUG] Starting load of {total_files} files (defer_size={defer_size/1024/1024:.1f}MB)")

        # Reset cancellation flag at start of loading
        self._cancelled = False

        # Disable GC during the loading loop to avoid blocking the UI thread
        gc.disable()

        for idx, file_path in enumerate(file_paths):
            # Check for cancellation at start of each iteration
            if self._cancelled:
                break

            # Call progress callback with throttling (every 5 files or 50ms)
            if progress_callback and (idx % 5 == 0 or time.time() - last_update_time >= update_interval):
                filename = os.path.basename(file_path)
                progress_callback(idx + 1, total_files, filename)
                last_update_time = time.time()
                # Process events more frequently to keep UI responsive
                if _is_main_thread():
                    QApplication.processEvents()

            # Check for cancellation again after processing events
            if self._cancelled:
                break

            try:
                # For single file loading, pass a progress callback that formats messages
                file_progress_callback = None
                if total_files == 1 and progress_callback:
                    def single_file_progress(message: str, current_frames: int | None, total_frames: int | None) -> None:
                        # Format message for single file case - pass message as filename parameter
                        # This handles both loading messages and defer messages
                        progress_callback(1, 1, message)
                    file_progress_callback = single_file_progress
                elif progress_callback:
                    # For multiple files, create a callback that can handle defer messages
                    def multi_file_progress(message: str, current_frames: int | None, total_frames: int | None, idx: int = idx) -> None:
                        # idx is bound per iteration so the closure cannot drift if the
                        # callback is ever invoked outside the current loop pass.
                        # If message starts with "Deferring", show it as a status message
                        if message.startswith("Deferring"):
                            # Pass the defer message as the filename parameter so it shows in status bar
                            progress_callback(idx + 1, total_files, message)
                        # Otherwise, it's a normal loading message which is handled by the main progress callback
                    file_progress_callback = multi_file_progress

                # Check for cancellation before loading file
                if self._cancelled:
                    break

                dataset = self.load_file(file_path, defer_size=defer_size, progress_callback=file_progress_callback)
                if dataset is not None:
                    self.loaded_files.append(dataset)


                    # Keep UI responsive every 50 files (GC deferred to after loop)
                    if len(self.loaded_files) % 50 == 0 and _is_main_thread():
                        QApplication.processEvents()

            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {e!s}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))

        # Re-enable GC; schedule deferred collection only on the main thread
        gc.enable()
        if _is_main_thread():
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, gc.collect)

        # Final progress update (use actual loaded count so cancel shows correct number)
        if progress_callback and total_files > 0:
            progress_callback(len(self.loaded_files), total_files, "")


        return self.loaded_files

    def load_directory(self, directory_path: str, recursive: bool = True, defer_size: int | None = None,
                      progress_callback: Callable[[int, int, str], None] | None = None) -> list[pydicom.Dataset]:
        """
        Load all DICOM files from a directory.
        
        Args:
            directory_path: Path to the directory
            recursive: If True, search subdirectories recursively
            defer_size: Optional size threshold (in bytes) for deferring pixel data loading.
                       If file size exceeds this, pixel data will be loaded on-demand.
                       Defaults to DEFAULT_DEFER_SIZE (1MB) if None.
            progress_callback: Optional callback function called during loading.
                              Signature: (current: int, total: int, filename: str) -> None
            
        Returns:
            List of successfully loaded DICOM datasets
        """
        # Use default defer size if not specified
        if defer_size is None:
            defer_size = DEFAULT_DEFER_SIZE

        self.loaded_files = []
        self.failed_files = []

        dir_path = Path(directory_path)

        if not dir_path.exists() or not dir_path.is_dir():
            self.failed_files.append((directory_path, "Directory does not exist or is not a directory"))
            return []

        # Get all files in directory (and subdirectories if recursive).
        # Exclude system/temp files that are never DICOM (e.g. .DS_Store, ~$*).
        if recursive:
            candidates = [p for p in dir_path.rglob('*') if p.is_file()]
        else:
            candidates = [p for p in dir_path.iterdir() if p.is_file()]
        file_paths = [str(p) for p in candidates if not _should_skip_file_for_dicom(p)]
        # print(f"[LOAD DEBUG] Scanned directory in {scan_time:.2f}s, found {len(file_paths)} files")

        total_files = len(file_paths)
        self.attempted_file_count = total_files
        self.extension_skipped_count = len(candidates) - len(file_paths)

        last_update_time = time.time()
        update_interval = 0.05  # Update every 50ms

        # Debugging: Track loading performance

        # print(f"[LOAD DEBUG] Starting load of {total_files} files (defer_size={defer_size/1024/1024:.1f}MB)")

        # Reset cancellation flag at start of loading
        self._cancelled = False

        # Disable GC during the loading loop to avoid blocking the UI thread
        gc.disable()

        # Attempt to load each file as DICOM (regardless of extension)
        for idx, file_path in enumerate(file_paths):
            # Check for cancellation at start of each iteration
            if self._cancelled:
                break

            # Call progress callback with throttling (every 5 files or 50ms)
            if progress_callback and (idx % 5 == 0 or time.time() - last_update_time >= update_interval):
                filename = os.path.basename(file_path)
                progress_callback(idx + 1, total_files, filename)
                last_update_time = time.time()
                # Note: processEvents is now called inside progress_callback with throttling

            # Check for cancellation again after processing events
            if self._cancelled:
                break

            try:
                # Create progress callback wrapper for load_file
                file_progress_callback = None
                if progress_callback:
                    def multi_file_progress(message: str, current_frames: int | None, total_frames: int | None, idx: int = idx) -> None:
                        # idx is bound per iteration so the closure cannot drift if the
                        # callback is ever invoked outside the current loop pass.
                        # If message starts with "Deferring", show it as a status message
                        if message.startswith("Deferring"):
                            # Pass the defer message as the filename parameter so it shows in status bar
                            progress_callback(idx + 1, total_files, message)
                        # Otherwise, it's a normal loading message which is handled by the main progress callback
                    file_progress_callback = multi_file_progress

                # Check for cancellation before loading file
                if self._cancelled:
                    break

                dataset = self.load_file(file_path, defer_size=defer_size, progress_callback=file_progress_callback)
                if dataset is not None:
                    self.loaded_files.append(dataset)


                    # Keep UI responsive every 50 files (GC deferred to after loop)
                    if len(self.loaded_files) % 50 == 0 and _is_main_thread():
                        QApplication.processEvents()

            except Exception as e:
                # Additional safety net for unexpected errors
                error_msg = f"Unexpected error loading file: {e!s}"
                error_type = type(e).__name__
                if error_type not in error_msg:
                    error_msg = f"{error_type}: {error_msg}"
                self.failed_files.append((file_path, error_msg))

        # Re-enable GC; schedule deferred collection only on the main thread
        gc.enable()
        if _is_main_thread():
            from PySide6.QtCore import QTimer
            QTimer.singleShot(500, gc.collect)

        # Final progress update (use actual loaded count so cancel shows correct number)
        if progress_callback and total_files > 0:
            progress_callback(len(self.loaded_files), total_files, "")


        return self.loaded_files

    def get_failed_files(self) -> list[tuple[str, str]]:
        """
        Get list of files that failed to load with error messages.
        
        Returns:
            List of tuples (file_path, error_message)
        """
        return self.failed_files.copy()

    def clear(self) -> None:
        """Clear loaded files and failed files lists."""
        self.loaded_files = []
        self.failed_files = []
