"""Focused ExportManager path-planning and anonymize-selection helpers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pydicom.dataset import Dataset

from gui import export_manager as export_manager_module
from gui.export_manager import ExportManager, ExportSliceRequest
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
    assert "_MIP_4slices" in paths[0]


def test_preview_png_studies_single_slice_series_omits_projection_token(tmp_path: Path) -> None:
    """Single-slice series: preview must not claim _MIP_/_AIP_/_MINIP_ when studies is present."""
    study_uid, series_uid = "st", "se"
    d0 = _ds("1.2.3.1")
    items = {(study_uid, series_uid, 0): d0}
    studies = {study_uid: {series_uid: [d0]}}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "PNG",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
        studies=studies,
    )
    assert len(paths) == 1
    base = paths[0].replace("\\", "/").upper()
    assert "_MIP_" not in base
    assert "_AIP_" not in base
    assert "_MINIP_" not in base


def test_preview_png_last_slice_thin_slab_omits_projection_token(tmp_path: Path) -> None:
    study_uid, series_uid = "st", "se"
    slices = [_ds(f"1.2.3.{i}") for i in range(10)]
    items = {(study_uid, series_uid, 9): slices[9]}
    studies = {study_uid: {series_uid: slices}}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "PNG",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
        studies=studies,
    )
    assert len(paths) == 1
    assert "_MIP_" not in paths[0]


def test_png_preview_matches_disk_name_when_studies_missing(tmp_path: Path) -> None:
    """Without studies, PNG preview and the written name both omit the projection token.

    DICOM preview still keeps the legacy suffix (see the one-item DICOM test).
    """
    from gui.export_paths import png_jpg_projection_filename_for_disk

    items = {("st", "se", 0): _ds()}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "PNG",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
    )
    assert len(paths) == 1
    assert "_MIP_" not in paths[0]
    assert png_jpg_projection_filename_for_disk(
        True, "PNG", None, "st", "se", 0, 4
    ) is False


def test_preview_buildable_png_also_lists_single_slice_fallback(tmp_path: Path) -> None:
    """A buildable slab can still be written as one slice if rendering returns nothing."""
    study_uid, series_uid = "st", "se"
    slices = [_ds(f"1.2.3.{i}") for i in range(10)]
    items = {(study_uid, series_uid, 0): slices[0]}
    studies = {study_uid: {series_uid: slices}}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "PNG",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
        studies=studies,
    )
    assert len(paths) == 2
    assert any("_MIP_4slices" in path for path in paths)
    assert any(path.endswith("Instance_0001.png") for path in paths)


def test_preview_png_early_slice_keeps_projection_token_when_slab_ok(tmp_path: Path) -> None:
    study_uid, series_uid = "st", "se"
    slices = [_ds(f"1.2.3.{i}") for i in range(10)]
    items = {(study_uid, series_uid, 0): slices[0]}
    studies = {study_uid: {series_uid: slices}}
    paths = ExportManager.get_export_paths_for_selection(
        items,
        str(tmp_path),
        "PNG",
        projection_enabled=True,
        projection_type="mip",
        projection_slice_count=4,
        studies=studies,
    )
    assert any("_MIP_4slices" in path for path in paths)
    assert any(path.endswith("Instance_0001.png") for path in paths)


def test_export_slice_png_rewrites_path_when_projection_returns_none(monkeypatch, tmp_path: Path) -> None:
    """Fallback single-slice write uses basename without _TYPE_Nslices when rasterize returns None."""
    study_uid, series_uid = "st", "se"
    slices = [_ds("1.2.3.1"), _ds("1.2.3.2")]
    studies = {study_uid: {series_uid: slices}}
    proj_path = tmp_path / "SYNTH01" / "20260101-Synthetic_Study" / "2-Synthetic_Series" / (
        "Instance_0001_MIP_4slices.png"
    )
    proj_path.parent.mkdir(parents=True)
    monkeypatch.setattr(
        export_manager_module._er, "create_projection_for_export", lambda *a, **k: None
    )
    monkeypatch.setattr(
        export_manager_module.DICOMProcessor,
        "dataset_to_image",
        lambda *a, **k: Image.new("L", (4, 4), 200),
    )
    monkeypatch.setattr(
        export_manager_module._er,
        "process_image_by_photometric_interpretation",
        lambda image, _dataset: image,
    )
    ok, _ = ExportManager().export_slice(
        ExportSliceRequest(
            slices[0],
            str(proj_path),
            "PNG",
            study_uid=study_uid,
            series_uid=series_uid,
            slice_index=0,
            projection_enabled=True,
            projection_type="mip",
            projection_slice_count=4,
            studies=studies,
            single_slice_export_basename="Instance_0001.png",
        )
    )
    assert ok
    assert not proj_path.exists()
    assert (proj_path.parent / "Instance_0001.png").exists()


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
