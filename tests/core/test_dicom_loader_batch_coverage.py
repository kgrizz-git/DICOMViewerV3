"""Coverage tests for DICOM loader validation and batch-loading paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from core import dicom_loader as loader_module
from core.dicom_loader import DICOMLoader


def test_validate_dicom_file_handles_multiframe_metadata_and_padding(
    monkeypatch,
) -> None:
    """Validation accepts safe inputs and rejects malformed multiframe payloads."""
    loader = DICOMLoader()
    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 2_000_000)

    enhanced = Dataset()
    enhanced.PerFrameFunctionalGroupsSequence = []
    monkeypatch.setattr(
        loader_module.pydicom, "dcmread", lambda *_args, **_kwargs: enhanced
    )
    assert loader.validate_dicom_file("enhanced.dcm") == (True, None)

    missing_dimensions = Dataset()
    missing_dimensions.NumberOfFrames = "2"
    monkeypatch.setattr(
        loader_module.pydicom,
        "dcmread",
        lambda *_args, **_kwargs: missing_dimensions,
    )
    assert loader.validate_dicom_file("missing-dimensions.dcm") == (
        False,
        "Multi-frame file missing Rows/Columns tags",
    )

    padded = Dataset()
    padded.NumberOfFrames = "2"
    padded.Rows = 1
    padded.Columns = 1
    padded.BitsAllocated = 16
    padded.PixelData = b"x" * 20
    monkeypatch.setattr(
        loader_module.pydicom, "dcmread", lambda *_args, **_kwargs: padded
    )
    is_valid, message = loader.validate_dicom_file("padded.dcm")
    assert is_valid is False
    assert message is not None and "excessive padding" in message

    valid = Dataset()
    valid.NumberOfFrames = "2"
    valid.Rows = 1
    valid.Columns = 1
    valid.BitsAllocated = 16
    valid.PixelData = b"x" * 4
    monkeypatch.setattr(
        loader_module.pydicom, "dcmread", lambda *_args, **_kwargs: valid
    )
    assert loader.validate_dicom_file("valid.dcm") == (True, None)


def test_validate_dicom_file_skips_small_files_and_reports_read_error(
    monkeypatch,
) -> None:
    loader = DICOMLoader()
    dcmread = MagicMock()
    monkeypatch.setattr(loader_module.pydicom, "dcmread", dcmread)
    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 10)
    assert loader.validate_dicom_file("small.dcm") == (True, None)
    dcmread.assert_not_called()

    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 2_000_000)
    monkeypatch.setattr(
        loader_module.pydicom,
        "dcmread",
        MagicMock(side_effect=ValueError("bad metadata")),
    )
    is_valid, message = loader.validate_dicom_file("bad.dcm")
    assert is_valid is False
    assert message == "Validation failed: bad metadata"


def test_read_dicom_dataset_defers_large_files_and_reports_progress(
    monkeypatch,
) -> None:
    dataset = Dataset()
    dcmread = MagicMock(return_value=dataset)
    progress = MagicMock()
    monkeypatch.setattr(loader_module.pydicom, "dcmread", dcmread)
    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 2 * 1024 * 1024)
    monkeypatch.setattr(loader_module.time, "time", MagicMock(side_effect=(10.0, 10.5)))

    result, duration = loader_module._read_dicom_dataset(
        "large.dcm",
        1024 * 1024,
        "large.dcm",
        progress,
    )

    assert result is dataset
    assert duration == 0.5
    dcmread.assert_called_once_with("large.dcm", force=True, defer_size=1024 * 1024)
    assert "Deferring pixel data" in progress.call_args.args[0]


def test_finalize_multiframe_metadata_handles_single_cancelled_and_completed_paths(
    monkeypatch,
) -> None:
    loader = DICOMLoader()
    dataset = Dataset()
    progress = MagicMock()

    monkeypatch.setattr(loader_module, "is_multiframe", lambda _dataset: False)
    assert loader_module._finalize_multiframe_metadata(
        loader, dataset, "one.dcm", "one.dcm", progress
    ) == (0.0, False)
    assert dataset._num_frames == 1
    assert dataset._is_multiframe is False
    progress.assert_not_called()

    multi = Dataset()
    multi.PerFrameFunctionalGroupsSequence = []
    monkeypatch.setattr(loader_module, "is_multiframe", lambda _dataset: True)
    monkeypatch.setattr(loader_module, "get_frame_count", lambda _dataset: 3)
    loader.cancel()
    assert loader_module._finalize_multiframe_metadata(
        loader, multi, "cancelled.dcm", "cancelled.dcm", progress
    ) == (0.0, True)
    progress.assert_called_once()
    assert progress.call_args.args[1:] == (None, 3)

    loader.reset_cancellation()
    progress.reset_mock()
    preloader = MagicMock(return_value=(0.25, False))
    monkeypatch.setattr(loader_module, "preload_enhanced_multiframe_pixels", preloader)
    assert loader_module._finalize_multiframe_metadata(
        loader, multi, "complete.dcm", "complete.dcm", progress
    ) == (0.25, False)
    assert multi._num_frames == 3
    assert multi._is_multiframe is True
    preloader.assert_called_once()
    assert progress.call_count == 2
    assert progress.call_args_list[0].args[1:] == (None, 3)
    assert progress.call_args_list[1].args[1:] == (3, 3)


def test_record_generic_load_exception_deduplicates_compression_failures(
    monkeypatch,
) -> None:
    loader = DICOMLoader()
    dataset = Dataset()
    monkeypatch.setattr(
        loader_module,
        "_classify_pixel_data_error",
        lambda _dataset, _message: (True, "decode unavailable"),
    )

    loader_module._record_load_file_generic_exception(
        loader, "compressed.dcm", dataset, RuntimeError("decode")
    )
    loader_module._record_load_file_generic_exception(
        loader, "compressed.dcm", dataset, RuntimeError("decode")
    )

    assert loader._compression_error_files == {"compressed.dcm"}
    assert len(loader.failed_files) == 2
    assert all(
        "decode unavailable" in message for _path, message in loader.failed_files
    )


def test_load_file_records_validation_failure_and_successful_dataset(
    monkeypatch,
) -> None:
    loader = DICOMLoader()
    monkeypatch.setattr(loader, "validate_dicom_file", lambda _path: (False, None))
    assert loader.load_file("invalid.dcm") is None
    assert loader.failed_files == [("invalid.dcm", "Unknown validation error")]

    loader.clear()
    dataset = Dataset()
    monkeypatch.setattr(loader, "validate_dicom_file", lambda _path: (True, None))
    monkeypatch.setattr(
        loader_module,
        "_read_dicom_dataset",
        lambda *_args, **_kwargs: (dataset, 0.0),
    )
    monkeypatch.setattr(
        loader_module,
        "_finalize_multiframe_metadata",
        lambda *_args, **_kwargs: (0.0, False),
    )

    assert loader.load_file("good.dcm") is dataset
    assert loader.failed_files == []


def test_load_files_collects_successes_defers_messages_and_reports_final_progress(
    monkeypatch,
) -> None:
    loader = DICOMLoader()
    first, third = Dataset(), Dataset()
    outcomes = iter((first, None, third))
    progress_events: list[tuple[int, int, str]] = []

    def load_file(path: str, **kwargs):
        callback = kwargs["progress_callback"]
        assert callback is not None
        callback(f"Deferring pixel data for {path}", None, None)
        return next(outcomes)

    monkeypatch.setattr(loader, "load_file", load_file)
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)

    loaded = loader.load_files(
        ["one.dcm", "two.dcm", "three.dcm"],
        progress_callback=lambda current, total, name: progress_events.append(
            (current, total, name)
        ),
    )

    assert loaded == [first, third]
    assert loader.get_attempted_file_count() == 3
    assert progress_events[0] == (1, 3, "one.dcm")
    assert (1, 3, "Deferring pixel data for one.dcm") in progress_events
    assert progress_events[-1] == (2, 3, "")


def test_load_files_stops_when_a_load_cancels_the_operation(monkeypatch) -> None:
    loader = DICOMLoader()

    def cancelling_load(*_args, **_kwargs):
        loader.cancel()
        return Dataset()

    monkeypatch.setattr(loader, "load_file", cancelling_load)
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)

    loaded = loader.load_files(["one.dcm", "two.dcm"])

    assert len(loaded) == 1
    assert loader.get_attempted_file_count() == 2


def test_load_directory_filters_known_non_dicom_files_and_supports_nonrecursive_scan(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "slice.dcm").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("not dicom")
    (tmp_path / ".DS_Store").write_bytes(b"")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "unnamed").write_bytes(b"")

    loader = DICOMLoader()
    seen_paths: list[str] = []
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)
    monkeypatch.setattr(
        loader,
        "load_file",
        lambda path, **_kwargs: seen_paths.append(path) or Dataset(),
    )

    loaded = loader.load_directory(str(tmp_path), recursive=False)

    assert len(loaded) == 1
    assert seen_paths == [str(tmp_path / "slice.dcm")]
    assert loader.get_attempted_file_count() == 1
    assert loader.get_extension_skipped_count() == 2


def test_load_directory_rejects_missing_directory() -> None:
    loader = DICOMLoader()

    assert loader.load_directory("does-not-exist") == []
    assert loader.get_failed_files() == [
        ("does-not-exist", "Directory does not exist or is not a directory")
    ]
