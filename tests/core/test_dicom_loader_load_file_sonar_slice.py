"""
Characterization tests for single-file DICOM load helpers (Sonar S3776 slice).

Covers pure helpers extracted from ``DICOMLoader.load_file`` into
``core.dicom_loader_file``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from core.dicom_loader_file import (
    COMPRESSED_TRANSFER_SYNTAX_LABELS,
    build_compression_install_error_detail,
    build_generic_load_error_message,
    build_memory_error_message,
    build_slow_load_timing_parts,
    compression_label_from_dataset,
    compression_label_from_transfer_syntax,
    estimate_multiframe_memory_mb,
    format_defer_pixel_data_message,
    format_multiframe_load_complete_message,
    format_multiframe_load_start_message,
    normalize_validation_error,
    preload_enhanced_multiframe_pixels,
    should_skip_enhanced_multiframe_preload,
)


def test_compression_label_from_transfer_syntax_known_and_unknown() -> None:
    assert compression_label_from_transfer_syntax("1.2.840.10008.1.2.4.50") == "JPEG Baseline"
    assert compression_label_from_transfer_syntax("1.2.840.10008.1.2.1") is None
    assert len(COMPRESSED_TRANSFER_SYNTAX_LABELS) == 9


def test_compression_label_from_dataset_uses_file_meta() -> None:
    dataset = MagicMock()
    dataset.file_meta.TransferSyntaxUID = "1.2.840.10008.1.2.4.91"
    assert compression_label_from_dataset(dataset) == "JPEG 2000"

    bare = MagicMock(spec=[])
    assert compression_label_from_dataset(bare) is None


def test_normalize_validation_error() -> None:
    assert normalize_validation_error("bad padding") == "bad padding"
    assert normalize_validation_error(None) == "Unknown validation error"


def test_format_defer_and_multiframe_messages() -> None:
    assert "Deferring pixel data" in format_defer_pixel_data_message("study.dcm", 512.0, 250.0)
    assert format_multiframe_load_start_message("study.dcm", 12) == "Loading 12 frames from study.dcm..."
    assert format_multiframe_load_complete_message("study.dcm", 12) == "Loaded 12 frames from study.dcm"


def test_estimate_multiframe_memory_mb_and_preload_threshold() -> None:
    # 2 frames, 512x512, 16-bit mono => 1 MB
    assert estimate_multiframe_memory_mb(2, 512, 512, 16, 1) == pytest.approx(1.0)
    assert should_skip_enhanced_multiframe_preload(199.9) is False
    assert should_skip_enhanced_multiframe_preload(200.1) is True


def test_build_slow_load_timing_parts_thresholds() -> None:
    assert build_slow_load_timing_parts(0.4, 0.1, 0.1, 0.1, None) == []
    parts = build_slow_load_timing_parts(0.6, 0.1, 0.02, 0.0, "JPEG Baseline")
    assert parts[0].startswith("Total ")
    assert "validation: 0.100s" in parts
    assert "read:" not in parts
    assert parts[-1] == "compressed: JPEG Baseline"

    uncompressed = build_slow_load_timing_parts(0.6, 0.0, 0.1, 0.0, None)
    assert uncompressed[-1] == "uncompressed"


def test_build_error_messages() -> None:
    detail = build_compression_install_error_detail("Compressed DICOM pixel data cannot be decoded.")
    assert detail == "Compressed DICOM pixel data cannot be decoded."
    assert "pip install" not in detail
    assert build_generic_load_error_message("read failed", "RuntimeError") == (
        "RuntimeError: Error reading file: read failed"
    )
    assert "Memory error" in build_memory_error_message(MemoryError("out of ram"))


def test_preload_enhanced_multiframe_pixels_skips_large_estimate() -> None:
    dataset = MagicMock()
    dataset.Rows = 4096
    dataset.Columns = 4096
    dataset.BitsAllocated = 16
    dataset.SamplesPerPixel = 1
    pixel_array_mock = PropertyMock()
    type(dataset).pixel_array = pixel_array_mock

    pixel_time, should_abort = preload_enhanced_multiframe_pixels(
        dataset,
        "/tmp/large.dcm",
        num_frames=64,
        classify_pixel_data_error=lambda _ds, _msg: (False, _msg),
        compression_error_files=set(),
        failed_files=[],
        on_compression_decode_failed=lambda _exc: None,
        on_pixel_preload_failed=lambda _exc: None,
    )

    assert pixel_time == 0.0
    assert should_abort is False
    assert dataset._num_frames == 64
    assert dataset._is_multiframe is True
    pixel_array_mock.assert_not_called()


def test_preload_enhanced_multiframe_pixels_compression_failure_aborts() -> None:
    dataset = MagicMock()
    dataset.Rows = 64
    dataset.Columns = 64
    dataset.BitsAllocated = 16
    dataset.SamplesPerPixel = 1
    type(dataset).pixel_array = PropertyMock(
        side_effect=RuntimeError("unable to decode"),
    )

    failed: list[tuple[str, str]] = []
    compression_seen: set[str] = set()
    decode_calls: list[BaseException] = []

    pixel_time, should_abort = preload_enhanced_multiframe_pixels(
        dataset,
        "/tmp/bad.dcm",
        num_frames=2,
        classify_pixel_data_error=lambda _ds, msg: (True, "Compressed DICOM pixel data cannot be decoded."),
        compression_error_files=compression_seen,
        failed_files=failed,
        on_compression_decode_failed=lambda exc: decode_calls.append(exc),
        on_pixel_preload_failed=lambda _exc: None,
    )

    assert pixel_time == 0.0
    assert should_abort is True
    assert failed
    assert "/tmp/bad.dcm" in compression_seen
    assert len(decode_calls) == 1
