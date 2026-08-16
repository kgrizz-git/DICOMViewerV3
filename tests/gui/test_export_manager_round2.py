"""Bounded synthetic coverage for ExportManager orchestration paths."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset

from gui import export_manager as export_manager_module
from gui.export_manager import ExportManager, ExportSelectedRequest, ExportSliceRequest


def _dataset(instance: int = 1, photometric: str = "MONOCHROME2") -> Dataset:
    dataset = Dataset()
    dataset.PatientID = "SYNTHETIC"
    dataset.StudyDate = "20260101"
    dataset.StudyDescription = "Synthetic Study"
    dataset.SeriesNumber = 2
    dataset.SeriesDescription = "Synthetic Series"
    dataset.InstanceNumber = instance
    dataset.PhotometricInterpretation = photometric
    return dataset


def test_path_selection_sanitizes_metadata_and_sorts_instances(tmp_path: Path) -> None:
    selected = {
        ("study", "series", 1): _dataset(2),
        ("study", "series", 0): _dataset(1),
    }
    selected["study", "series", 0].PatientID = "SYNTH/01"
    selected["study", "series", 0].StudyDescription = "Synthetic: Study"

    paths = ExportManager.get_export_paths_for_selection(selected, str(tmp_path), "PNG")

    assert [Path(path).name for path in paths] == ["Instance_0001.png", "Instance_0002.png"]
    assert "SYNTH_01" in paths[0]
    assert "Synthetic__Study" in paths[0]


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(0.5, 1.0), (1.0, 1.0), (2.0, 1.5), (4.0, 1.5)],
)
def test_scale_and_annotation_sizes_follow_export_limits(requested: float, expected: float) -> None:
    assert ExportManager._effective_scale_for_image(5000, 5000, requested) == expected
    assert ExportManager.export_line_thickness_pixels(50, 512, 512, requested) >= 1
    assert ExportManager.export_text_size_pixels(50, 512, 512, requested) >= 8


def test_photometric_wrapper_no_longer_inverts_monochrome1() -> None:
    image = Image.fromarray(np.array([[0, 100]], dtype=np.uint8), mode="L")
    dataset = _dataset(photometric="MONOCHROME1")

    result = ExportManager.process_image_by_photometric_interpretation(image, dataset)

    assert np.array_equal(np.asarray(result), np.array([[0, 100]], dtype=np.uint8))


class _Progress:
    def __init__(self, *_args) -> None:
        self.values: list[int] = []
        self.closed = False

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration) -> None:
        pass

    def wasCanceled(self) -> bool:
        return False

    def setValue(self, value: int) -> None:
        self.values.append(value)

    def close(self) -> None:
        self.closed = True


@pytest.mark.qt
def test_export_selected_groups_and_delegates_sorted_synthetic_items(monkeypatch, tmp_path: Path, qapp) -> None:
    progress = _Progress()
    monkeypatch.setattr(export_manager_module, "QProgressDialog", lambda *args: progress)
    calls: list[ExportSliceRequest] = []
    manager = ExportManager()

    def fake_export_slice(request: ExportSliceRequest) -> tuple[bool, tuple[float, float] | None]:
        calls.append(request)
        return (True, (4.0, 2.0) if request.slice_index == 0 else None)

    monkeypatch.setattr(manager, "export_slice", fake_export_slice)
    selected = {
        ("study", "series", 1): _dataset(2),
        ("study", "series", 0): _dataset(1),
    }

    result = manager.export_selected(
        ExportSelectedRequest(selected, str(tmp_path), "PNG", export_scale=4.0)
    )

    assert result == (2, [("Instance_0001.png", 4.0, 2.0)])
    assert [call.slice_index for call in calls] == [0, 1]
    assert progress.values == [1, 2]
    assert progress.closed


def test_export_slice_writes_scaled_image_and_renders_requested_overlays(
    monkeypatch, tmp_path: Path
) -> None:
    dataset = _dataset()
    output = tmp_path / "synthetic.png"
    render_requests = []
    source = Image.new("L", (4, 2), 80)
    monkeypatch.setattr(export_manager_module.DICOMProcessor, "dataset_to_image", lambda *args, **kwargs: source)
    monkeypatch.setattr(
        export_manager_module._er,
        "process_image_by_photometric_interpretation",
        lambda image, _dataset: image,
    )

    def fake_render(request):
        render_requests.append(request)
        return request.image.convert("RGB")

    monkeypatch.setattr(export_manager_module._er, "render_overlays_and_rois", fake_render)

    result = ExportManager().export_slice(
        ExportSliceRequest(dataset, str(output), "PNG", include_overlays=True, export_scale=2.0)
    )

    assert result == (True, None)
    assert Image.open(output).size == (8, 4)
    assert render_requests[0].coordinate_scale == 2.0
    assert render_requests[0].image.size == (8, 4)


def test_export_slice_returns_controlled_failure_when_image_conversion_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        export_manager_module.DICOMProcessor,
        "dataset_to_image",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic conversion failure")),
    )

    result = ExportManager().export_slice(
        ExportSliceRequest(_dataset(), str(tmp_path / "unused.png"), "PNG")
    )

    assert result == (False, None)


class _SavableDataset:
    def __init__(self) -> None:
        self.saved_to: str | None = None

    def save_as(self, path: str) -> None:
        self.saved_to = path


def test_export_slice_dicom_control_path_saves_without_native_io(tmp_path: Path) -> None:
    dataset = _SavableDataset()
    output = tmp_path / "synthetic.dcm"

    result = ExportManager().export_slice(ExportSliceRequest(dataset, str(output), "DICOM"))

    assert result == (True, None)
    assert dataset.saved_to == str(output)
