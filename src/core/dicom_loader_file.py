"""
Pure helpers for single-file DICOM loading (Sonar S3776 slice).

Extracted from ``DICOMLoader.load_file`` so the loader method stays thin
orchestration. Inputs are paths, datasets, and scalar metadata; outputs are
labels, messages, and timing fragments with no Qt or loader instance state.

Requirements:
    - pydicom (for type hints on Dataset only at call sites)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pydicom

# Transfer-syntax UID → human-readable compression label (subset used for timing logs).
COMPRESSED_TRANSFER_SYNTAX_LABELS: dict[str, str] = {
    "1.2.840.10008.1.2.5": "RLE Lossless",
    "1.2.840.10008.1.2.4.50": "JPEG Baseline",
    "1.2.840.10008.1.2.4.51": "JPEG Extended",
    "1.2.840.10008.1.2.4.57": "JPEG Lossless",
    "1.2.840.10008.1.2.4.70": "JPEG Lossless",
    "1.2.840.10008.1.2.4.80": "JPEG-LS Lossless",
    "1.2.840.10008.1.2.4.81": "JPEG-LS Lossy",
    "1.2.840.10008.1.2.4.90": "JPEG 2000 Lossless",
    "1.2.840.10008.1.2.4.91": "JPEG 2000",
}

# Skip pre-loading enhanced multi-frame pixel arrays above this estimate (MB).
ENHANCED_MULTIFRAME_PRELOAD_MAX_MB = 200.0

# Log timing breakdown when total load exceeds this threshold (seconds).
SLOW_LOAD_LOG_THRESHOLD_SEC = 0.5

# Include a phase in the timing breakdown when it exceeds this threshold (seconds).
SLOW_LOAD_PHASE_THRESHOLD_SEC = 0.05


def compression_label_from_transfer_syntax(transfer_syntax: str) -> str | None:
    """Return the compression label for a transfer-syntax UID, or None if uncompressed/unknown."""
    return COMPRESSED_TRANSFER_SYNTAX_LABELS.get(transfer_syntax)


def compression_label_from_dataset(dataset: pydicom.Dataset) -> str | None:
    """Return compression label from dataset file_meta.TransferSyntaxUID when present."""
    file_meta = getattr(dataset, "file_meta", None)
    if file_meta is None or not hasattr(file_meta, "TransferSyntaxUID"):
        return None
    return compression_label_from_transfer_syntax(str(file_meta.TransferSyntaxUID))


def normalize_validation_error(error_msg: str | None) -> str:
    """Normalize optional validation error text for ``failed_files`` tuples."""
    return error_msg if error_msg is not None else "Unknown validation error"


def format_defer_pixel_data_message(
    filename: str,
    file_size_mb: float,
    defer_size_mb: float,
) -> str:
    """Status message when pixel data loading is deferred for a large file."""
    return (
        f"Deferring pixel data loading for {filename} "
        f"({file_size_mb:.1f} MB > {defer_size_mb:.0f} MB threshold)"
    )


def format_multiframe_load_start_message(filename: str, num_frames: int) -> str:
    """Progress message when pre-loading frames from an enhanced multi-frame file."""
    return f"Loading {num_frames} frames from {filename}..."


def format_multiframe_load_complete_message(filename: str, num_frames: int) -> str:
    """Progress message after enhanced multi-frame pixel pre-load completes."""
    return f"Loaded {num_frames} frames from {filename}"


def estimate_multiframe_memory_mb(
    num_frames: int,
    rows: int,
    cols: int,
    bits_allocated: int = 16,
    samples_per_pixel: int = 1,
) -> float:
    """Estimate decoded multi-frame pixel buffer size in megabytes."""
    bytes_per_pixel = bits_allocated // 8
    return (num_frames * rows * cols * samples_per_pixel * bytes_per_pixel) / (1024 * 1024)


def should_skip_enhanced_multiframe_preload(estimated_memory_mb: float) -> bool:
    """Return True when pre-load should be skipped to avoid memory pressure."""
    return estimated_memory_mb > ENHANCED_MULTIFRAME_PRELOAD_MAX_MB


def build_slow_load_timing_parts(
    total_time: float,
    validation_time: float,
    read_time: float,
    pixel_load_time: float,
    compression_type: str | None,
) -> list[str]:
    """
    Assemble timing breakdown fragments for slow-file debug logging.

    The caller may join these with ``' | '``; production code keeps the log
    commented out but preserves the assembly for future diagnostics.
    """
    if total_time <= SLOW_LOAD_LOG_THRESHOLD_SEC:
        return []

    timing_parts = [f"Total {total_time:.3f}s"]
    if validation_time > SLOW_LOAD_PHASE_THRESHOLD_SEC:
        timing_parts.append(f"validation: {validation_time:.3f}s")
    if read_time > SLOW_LOAD_PHASE_THRESHOLD_SEC:
        timing_parts.append(f"read: {read_time:.3f}s")
    if pixel_load_time > SLOW_LOAD_PHASE_THRESHOLD_SEC:
        timing_parts.append(f"pixel_load: {pixel_load_time:.3f}s")
    if compression_type:
        timing_parts.append(f"compressed: {compression_type}")
    else:
        timing_parts.append("uncompressed")
    return timing_parts


def build_compression_install_error_detail(classified_message: str) -> str:
    """Return a user-facing compression failure without package-install advice."""
    return classified_message


def build_generic_load_error_message(classified_message: str, error_type: str) -> str:
    """Format a non-compression load exception for ``failed_files``."""
    error_msg = f"Error reading file: {classified_message}"
    if error_type not in error_msg:
        error_msg = f"{error_type}: {error_msg}"
    return error_msg


def build_memory_error_message(exc: BaseException) -> str:
    """Format MemoryError for ``failed_files``."""
    return (
        f"Memory error: File too large to load. "
        f"Try closing other applications or use a system with more memory. "
        f"Error: {exc!s}"
    )


def preload_enhanced_multiframe_pixels(
    dataset: pydicom.Dataset,
    file_path: str,
    num_frames: int,
    *,
    classify_pixel_data_error: Callable[[Any, str], tuple[bool, str]],
    compression_error_files: set[str],
    failed_files: list[tuple[str, str]],
    on_compression_decode_failed: Callable[[BaseException], None],
    on_pixel_preload_failed: Callable[[BaseException], None],
) -> tuple[float, bool]:
    """
    Pre-load and cache ``pixel_array`` for enhanced multi-frame datasets.

    Returns:
        ``(pixel_load_time_seconds, should_abort_load)`` where ``should_abort_load``
        is True when a compression decode failure should fail the whole ``load_file``.
    """
    rows = int(getattr(dataset, "Rows", 512))
    cols = int(getattr(dataset, "Columns", 512))
    bits_allocated = int(getattr(dataset, "BitsAllocated", 16))
    samples_per_pixel = int(getattr(dataset, "SamplesPerPixel", 1))
    estimated_memory_mb = estimate_multiframe_memory_mb(
        num_frames, rows, cols, bits_allocated, samples_per_pixel
    )

    if should_skip_enhanced_multiframe_preload(estimated_memory_mb):
        dataset._num_frames = num_frames
        dataset._is_multiframe = True
        return 0.0, False

    import time

    pixel_load_start = time.time()
    try:
        pixel_array = dataset.pixel_array
    except Exception as exc:
        error_msg = str(exc)
        is_compression_error, classified_message = classify_pixel_data_error(dataset, error_msg)
        if is_compression_error:
            error_detail = build_compression_install_error_detail(classified_message)
            if file_path not in compression_error_files:
                compression_error_files.add(file_path)
                on_compression_decode_failed(exc)
            failed_files.append((file_path, error_detail))
            return 0.0, True
        on_pixel_preload_failed(exc)
        return 0.0, False

    pixel_load_time = time.time() - pixel_load_start
    dataset._cached_pixel_array = pixel_array
    return pixel_load_time, False
