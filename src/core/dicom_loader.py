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
import os
import threading
import time
import warnings
from collections.abc import Callable
from pathlib import Path

import pydicom
from pydicom.errors import InvalidDicomError
from PySide6.QtWidgets import QApplication

from core.multiframe_handler import get_frame_count, is_multiframe
from core.sr_sop_classes import (
    is_structured_report_dataset,
    structured_report_storage_label,
)

_MAIN_THREAD_ID = threading.main_thread().ident


def _is_main_thread() -> bool:
    """Return True if the caller is on the main (UI) thread."""
    return threading.current_thread().ident == _MAIN_THREAD_ID

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
            file_start_time = time.time()

            # Notify start of loading
            if progress_callback:
                progress_callback(f"Loading {filename}...", None, None)
                # Process events to allow timer to start and UI to update
                if _is_main_thread():
                    QApplication.processEvents()

            # Validate file before attempting to load pixel data
            validation_start = time.time()
            is_valid, error_msg = self.validate_dicom_file(file_path)
            validation_time = time.time() - validation_start

            if not is_valid:
                # `validate_dicom_file()` returns `Optional[str]`, but `failed_files` is
                # typed as `List[Tuple[str, str]]`, so normalize `None` to a string.
                error_msg_str = error_msg if error_msg is not None else "Unknown validation error"
                print(f"Validation failed for {os.path.basename(file_path)}: {error_msg_str}")
                self.failed_files.append((file_path, error_msg_str))
                return None

            # Check for cancellation after validation
            if self._cancelled:
                return None

            # Suppress excess padding warnings - these are informational and pydicom handles them automatically
            # The warnings don't cause errors, but we suppress them to reduce noise
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='.*excess padding.*', category=UserWarning)

                # Process events before blocking read operation to allow timer to fire
                if _is_main_thread():
                    QApplication.processEvents()

                # Check file size if defer_size is specified
                read_start = time.time()
                if defer_size is not None:
                    file_size = os.path.getsize(file_path)
                    if file_size > defer_size:
                        # Use defer_size parameter to defer pixel data loading
                        file_size_mb = file_size / (1024 * 1024)
                        defer_size_mb = defer_size / (1024 * 1024)
                        # Notify that pixel data loading is being deferred
                        if progress_callback:
                            progress_callback(
                                f"Deferring pixel data loading for {filename} ({file_size_mb:.1f} MB > {defer_size_mb:.0f} MB threshold)",
                                None,
                                None
                            )
                            if _is_main_thread():
                                QApplication.processEvents()
                        dataset = pydicom.dcmread(file_path, force=True, defer_size=defer_size)
                    else:
                        dataset = pydicom.dcmread(file_path, force=True)
                else:
                    # Attempt to read the file as DICOM
                    dataset = pydicom.dcmread(file_path, force=True)
                read_time = time.time() - read_start

            if is_structured_report_dataset(dataset):
                dataset._no_pixel_reason = "structured_report"
                dataset._structured_report_label = structured_report_storage_label(str(getattr(dataset, "SOPClassUID", "") or ""))

            # Track compression info for debugging
            compression_type = None
            pixel_load_time = 0

            # Check compression type (for all files, not just multi-frame)
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                # List of compressed transfer syntaxes
                compressed_syntaxes = {
                    '1.2.840.10008.1.2.4': 'RLE Lossless',
                    '1.2.840.10008.1.2.4.50': 'JPEG Baseline',
                    '1.2.840.10008.1.2.4.51': 'JPEG Extended',
                    '1.2.840.10008.1.2.4.57': 'JPEG Lossless',
                    '1.2.840.10008.1.2.4.70': 'JPEG Lossless',
                    '1.2.840.10008.1.2.4.80': 'JPEG-LS Lossless',
                    '1.2.840.10008.1.2.4.81': 'JPEG-LS Lossy',
                    '1.2.840.10008.1.2.4.90': 'JPEG 2000 Lossless',
                    '1.2.840.10008.1.2.4.91': 'JPEG 2000',
                }
                if transfer_syntax in compressed_syntaxes:
                    compression_type = compressed_syntaxes[transfer_syntax]

            # Detect multi-frame files (for informational purposes)
            # The actual frame splitting will be done in the organizer
            if is_multiframe(dataset):
                num_frames = get_frame_count(dataset)
                dataset._num_frames = num_frames
                dataset._is_multiframe = True

                # Debug logging for multi-frame files (only if verbose)
                # Commented out to reduce noise - uncomment if needed for debugging
                # print(f"\n=== MULTI-FRAME DEBUG ===")
                # print(f"File: {os.path.basename(file_path)}")
                # print(f"Frames: {num_frames}")
                # print(f"Dimensions: {getattr(dataset, 'Rows', 'N/A')} x {getattr(dataset, 'Columns', 'N/A')}")
                # print(f"Bits Allocated: {getattr(dataset, 'BitsAllocated', 'N/A')}")
                # print(f"Transfer Syntax: {transfer_syntax}")

                # For Enhanced Multi-frame DICOMs, pre-load pixel array to ensure correct 3D shape
                # This is necessary because Enhanced Multi-frame files may not expose pixel data
                # correctly if accessed later after the dataset has been manipulated
                if hasattr(dataset, 'PerFrameFunctionalGroupsSequence'):
                    # Notify about frame loading
                    if progress_callback:
                        progress_callback(f"Loading {num_frames} frames from {filename}...", None, num_frames)
                        # Process events before blocking operation to allow timer to fire
                        if _is_main_thread():
                            QApplication.processEvents()

                    # Check for cancellation before expensive pixel array loading
                    if self._cancelled:
                        return None

                    # Check estimated memory requirement before loading
                    rows = int(getattr(dataset, 'Rows', 512))
                    cols = int(getattr(dataset, 'Columns', 512))
                    bits_allocated = int(getattr(dataset, 'BitsAllocated', 16))
                    bytes_per_pixel = bits_allocated // 8
                    samples_per_pixel = int(getattr(dataset, 'SamplesPerPixel', 1))
                    estimated_memory_mb = (num_frames * rows * cols * samples_per_pixel * bytes_per_pixel) / (1024 * 1024)

                    # Skip pre-loading if estimated size is very large (>200MB) to avoid memory pressure
                    # The pixel array will be loaded on-demand later when needed
                    if estimated_memory_mb > 200:
                        # Don't pre-load, but mark as multi-frame
                        dataset._num_frames = num_frames
                        dataset._is_multiframe = True
                    else:
                        try:
                            pixel_load_start = time.time()
                            pixel_array = dataset.pixel_array
                            pixel_load_time = time.time() - pixel_load_start
                            # Cache the pixel array in the dataset for later access
                            dataset._cached_pixel_array = pixel_array
                            # Notify completion
                            if progress_callback:
                                progress_callback(f"Loaded {num_frames} frames from {filename}", num_frames, num_frames)
                        except Exception as e:
                            error_msg = str(e)
                            is_compression_error, classified_message = _classify_pixel_data_error(
                                dataset, error_msg
                            )

                            if is_compression_error:
                                error_detail = (
                                    f"{classified_message} "
                                    f"Install optional dependencies: pip install pylibjpeg pyjpegls"
                                )
                                # Only show error message once per file
                                if file_path not in self._compression_error_files:
                                    self._compression_error_files.add(file_path)
                                    print(f"[LOADER] Compression Error: {file_path}")
                                    print(f"  {error_detail}")
                                    print(f"  Error: {error_msg[:200]}")
                                # Add to failed files with descriptive message
                                self.failed_files.append((file_path, error_detail))
                                return None
                            else:
                                print(
                                    f"[LOADER] Warning: Failed to pre-load pixel array: "
                                    f"{classified_message}"
                                )

            else:
                dataset._num_frames = 1
                dataset._is_multiframe = False

            # Log timing breakdown for slow files
            total_time = time.time() - file_start_time
            if total_time > 0.5:  # Log breakdown for files taking > 0.5s
                timing_parts = [f"Total {total_time:.3f}s"]
                if validation_time > 0.05:
                    timing_parts.append(f"validation: {validation_time:.3f}s")
                if read_time > 0.05:
                    timing_parts.append(f"read: {read_time:.3f}s")
                if pixel_load_time > 0.05:
                    timing_parts.append(f"pixel_load: {pixel_load_time:.3f}s")
                # Always show compression type for slow files to help diagnose
                if compression_type:
                    timing_parts.append(f"compressed: {compression_type}")
                else:
                    timing_parts.append("uncompressed")
                # print(f"[LOAD DEBUG] {filename}: {' | '.join(timing_parts)}")

            return dataset

        except MemoryError as e:
            error_msg = (
                f"Memory error: File too large to load. "
                f"Try closing other applications or use a system with more memory. "
                f"Error: {e!s}"
            )
            self.failed_files.append((file_path, error_msg))
            return None
        except InvalidDicomError as e:
            self.failed_files.append((file_path, f"Invalid DICOM file: {e!s}"))
            return None
        except OSError as e:
            # Handle file system errors (file not found, permission denied, etc.)
            self.failed_files.append((file_path, f"File system error: {e!s}"))
            return None
        except Exception as e:
            error_msg_str = str(e)
            is_compression_error, classified_message = _classify_pixel_data_error(
                dataset if 'dataset' in locals() else None,
                error_msg_str,
            )

            if is_compression_error:
                error_msg = (
                    f"{classified_message} "
                    f"Install optional dependencies: pip install pylibjpeg pyjpegls"
                )
                # Only show error message once per file
                if file_path not in self._compression_error_files:
                    self._compression_error_files.add(file_path)
                    print(f"[LOADER] Compression Error: {file_path}")
                    print(f"  {error_msg}")
                    print(f"  Error: {error_msg_str[:200]}")
            else:
                error_msg = f"Error reading file: {classified_message}"
            # Include error type for debugging
            error_type = type(e).__name__
            if error_type not in error_msg:
                error_msg = f"{error_type}: {error_msg}"
            self.failed_files.append((file_path, error_msg))
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

