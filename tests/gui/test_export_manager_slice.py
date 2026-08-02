"""Focused ExportManager path-planning and anonymize-selection helpers."""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import Dataset

from gui.export_manager import ExportManager
from utils.deep_anonymizer import DeepAnonymizerOptions


def _ds(sop: str = "1.2.840.10008.10.20.0.1") -> Dataset:
    ds = Dataset()
    ds.SOPInstanceUID = sop
    ds.PatientID = "SYNTH01"
    ds.PatientName = "Synthetic^Patient"
    ds.Modality = "CT"
    ds.SeriesDescription = "Axial"
    return ds


def test_get_export_paths_for_png_selection(tmp_path: Path) -> None:
    items = {
        ("st", "se", 0): _ds("1.2.3.1"),
        ("st", "se", 1): _ds("1.2.3.2"),
    }
    paths = ExportManager.get_export_paths_for_selection(
        items, str(tmp_path), "PNG"
    )
    assert len(paths) == 2
    assert all(p.lower().endswith(".png") for p in paths)
    assert all(str(tmp_path) in p for p in paths)


def test_get_export_paths_dicom_and_projection_suffix(tmp_path: Path) -> None:
    items = {("st", "se", 0): _ds()}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "DICOM",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
    )
    assert len(paths) == 1
    assert paths[0].lower().endswith(".dcm")
    assert "mip" in paths[0].lower() or "4" in paths[0]


def test_build_deep_anonymized_selection_preserves_keys() -> None:
    items = {
        ("st", "se", 0): _ds("1.2.3.10"),
        ("st", "se", 1): _ds("1.2.3.11"),
    }
    out = ExportManager.build_deep_anonymized_selection(
        items, DeepAnonymizerOptions.standard_share()
    )
    assert set(out.keys()) == set(items.keys())
    for key, anon in out.items():
        assert anon is not items[key]
        assert getattr(anon, "PatientID", None) != "SYNTH01"
        assert str(getattr(anon, "PatientName", "")) != "Synthetic^Patient"


def test_scale_and_thickness_delegates() -> None:
    assert ExportManager._effective_scale_for_image(64, 64, 2.0) == 2.0
    assert ExportManager.export_line_thickness_pixels(50, 512, 512, 1.0) >= 1
    assert ExportManager.export_text_size_pixels(50, 512, 512, 1.0) >= 8
