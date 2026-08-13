"""Round-two synthetic coverage for deterministic DICOM loader control paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from core import dicom_loader as loader_module
from core.dicom_loader import DICOMLoader


def test_finalize_multiframe_metadata_sets_metadata_without_preload(monkeypatch) -> None:
    """Multiframe datasets without enhanced frame groups do not preload pixels."""
    dataset = Dataset()
    loader = DICOMLoader()
    monkeypatch.setattr(loader_module, "is_multiframe", lambda _dataset: True)
    monkeypatch.setattr(loader_module, "get_frame_count", lambda _dataset: 4)
    preloader = MagicMock()
    monkeypatch.setattr(loader_module, "preload_enhanced_multiframe_pixels", preloader)

    assert loader_module._finalize_multiframe_metadata(
        loader, dataset, "synthetic.dcm", "synthetic.dcm", None
    ) == (0.0, False)
    assert dataset._num_frames == 4
    assert dataset._is_multiframe is True
    preloader.assert_not_called()


def test_record_generic_load_exception_formats_noncompression_failure() -> None:
    """Non-compression exceptions retain their type and classified message."""
    loader = DICOMLoader()
    dataset = Dataset()

    loader_module._record_load_file_generic_exception(
        loader, "synthetic.dcm", dataset, ValueError("metadata is invalid")
    )

    assert loader.failed_files == [
        ("synthetic.dcm", "ValueError: Error reading file: metadata is invalid")
    ]
    assert loader._compression_error_files == set()


def test_classify_pixel_data_error_handles_non_sr_and_unknown_messages() -> None:
    """Pixel absence is distinct from decoder errors, while unknown text is unchanged."""
    dataset = Dataset()
    dataset.Modality = "CT"

    is_compression, missing_message = loader_module._classify_pixel_data_error(
        dataset,
        "One of Pixel Data, Float Pixel Data or Double Float Pixel Data must be present",
    )
    assert is_compression is False
    assert missing_message == "DICOM object does not contain Pixel Data."

    is_compression, original_message = loader_module._classify_pixel_data_error(
        dataset, "unexpected synthetic failure"
    )
    assert is_compression is False
    assert original_message == "unexpected synthetic failure"


def test_validate_dicom_file_uses_tmp_path_and_handles_numeric_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    """Large synthetic multiframe metadata is accepted when pixel padding is safe."""
    file_path = tmp_path / "synthetic.dcm"
    file_path.write_bytes(b"synthetic")
    dataset = Dataset()
    dataset.NumberOfFrames = "2"
    dataset.Rows = 2
    dataset.Columns = 2
    dataset.BitsAllocated = 16
    dataset.PixelData = b"x" * 16
    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 2_000_000)
    dcmread = MagicMock(return_value=dataset)
    monkeypatch.setattr(loader_module.pydicom, "dcmread", dcmread)

    assert DICOMLoader().validate_dicom_file(str(file_path)) == (True, None)
    dcmread.assert_called_once_with(str(file_path), stop_before_pixels=True, force=True)


def test_validate_dicom_file_reports_conversion_failure(monkeypatch, tmp_path: Path) -> None:
    """Validation converts malformed frame metadata into a user-facing failure."""
    file_path = tmp_path / "malformed.dcm"
    file_path.write_bytes(b"synthetic")
    dataset = Dataset()
    object.__setattr__(dataset, "NumberOfFrames", "not-a-number")
    monkeypatch.setattr(loader_module.os.path, "getsize", lambda _path: 2_000_000)
    monkeypatch.setattr(loader_module.pydicom, "dcmread", lambda *_args, **_kwargs: dataset)

    valid, message = DICOMLoader().validate_dicom_file(str(file_path))

    assert valid is False
    assert message == "Validation failed: invalid literal for int() with base 10: 'not-a-number'"


def test_load_files_passes_defer_size_and_handles_unexpected_load_error(monkeypatch) -> None:
    """Batch loading records safety-net exceptions and uses the default defer size."""
    loader = DICOMLoader()
    first = Dataset()
    calls: list[tuple[str, int | None]] = []

    def load_file(path: str, *, defer_size: int | None, progress_callback):
        del progress_callback
        calls.append((path, defer_size))
        if path == "broken.dcm":
            raise RuntimeError("synthetic batch failure")
        return first

    monkeypatch.setattr(loader, "load_file", load_file)
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)

    assert loader.load_files(["good.dcm", "broken.dcm"]) == [first]
    assert calls == [
        ("good.dcm", loader_module.DEFAULT_DEFER_SIZE),
        ("broken.dcm", loader_module.DEFAULT_DEFER_SIZE),
    ]
    assert loader.failed_files == [
        ("broken.dcm", "RuntimeError: Unexpected error loading file: synthetic batch failure")
    ]


def test_load_files_empty_input_reports_no_progress(monkeypatch) -> None:
    """An empty batch resets state without invoking a final progress callback."""
    loader = DICOMLoader()
    callback = MagicMock()
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)

    assert loader.load_files([], progress_callback=callback) == []
    assert loader.get_attempted_file_count() == 0
    callback.assert_not_called()


def test_load_directory_recurses_and_tracks_extension_skips(monkeypatch, tmp_path: Path) -> None:
    """Recursive directory loading sends only eligible synthetic paths to load_file."""
    top_level = tmp_path / "top.dcm"
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    nested_file = nested_dir / "unnamed"
    skipped = tmp_path / "notes.txt"
    for path in (top_level, nested_file, skipped):
        path.write_bytes(b"synthetic")
    loader = DICOMLoader()
    seen: list[str] = []
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)
    monkeypatch.setattr(
        loader,
        "load_file",
        lambda path, **_kwargs: seen.append(path) or Dataset(),
    )

    loaded = loader.load_directory(str(tmp_path), recursive=True)

    assert len(loaded) == 2
    assert seen == [str(top_level), str(nested_file)]
    assert loader.get_attempted_file_count() == 2
    assert loader.get_extension_skipped_count() == 1


def test_load_directory_cancellation_stops_before_next_candidate(monkeypatch, tmp_path: Path) -> None:
    """Directory cancellation prevents later candidates from being loaded."""
    first = tmp_path / "first.dcm"
    second = tmp_path / "second.dcm"
    first.write_bytes(b"synthetic")
    second.write_bytes(b"synthetic")
    loader = DICOMLoader()
    seen: list[str] = []
    monkeypatch.setattr(loader_module, "_is_main_thread", lambda: False)

    def cancel_after_first(path: str, **_kwargs):
        seen.append(path)
        loader.cancel()
        return Dataset()

    monkeypatch.setattr(loader, "load_file", cancel_after_first)

    assert len(loader.load_directory(str(tmp_path), recursive=False)) == 1
    assert seen == [str(first)]
