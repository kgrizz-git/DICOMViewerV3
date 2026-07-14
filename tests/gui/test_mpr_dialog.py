"""Unit tests for gui.dialogs.mpr_dialog."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QMessageBox

from core.slice_geometry import SlicePlane
from gui.dialogs.mpr_dialog import MprDialog, MprRequest


def _dataset(
    *,
    rows: int = 128,
    cols: int = 96,
    pixel_spacing: tuple[float, float] = (0.8, 1.2),
    slice_thickness: float = 2.5,
) -> Dataset:
    ds = Dataset()
    ds.Rows = rows
    ds.Columns = cols
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    return ds


def _plane(normal: tuple[float, float, float]) -> SlicePlane:
    n = np.array(normal, dtype=float)
    if abs(float(np.dot(n, np.array([1.0, 0.0, 0.0])))) < 0.9:
        ref = np.array([1.0, 0.0, 0.0])
    else:
        ref = np.array([0.0, 1.0, 0.0])
    row = np.cross(n, ref)
    row /= np.linalg.norm(row)
    col = np.cross(n, row)
    col /= np.linalg.norm(col)
    return SlicePlane(origin=np.zeros(3), row_cosine=row, col_cosine=col, row_spacing=1.0, col_spacing=1.0)


@pytest.fixture
def loaded_series() -> dict[str, dict[str, Any]]:
    return {
        "series-a": {
            "description": "CT Abdomen",
            "modality": "CT",
            "n_slices": 12,
            "study_uid": "1.2.840.1.123456789",
            "datasets": [_dataset(), _dataset()],
        },
        "series-b": {
            "description": "MR Brain",
            "modality": "MR",
            "n_slices": 4,
            "study_uid": "9.8.7.6",
            "datasets": [_dataset(pixel_spacing=(1.5, 1.5), slice_thickness=3.0)],
        },
    }


def test_initial_population_defaults_and_series_change(qapp, loaded_series, monkeypatch):
    availability = {"series-a": True, "series-b": False}

    def _available(datasets):
        return availability["series-a"] if datasets is loaded_series["series-a"]["datasets"] else availability["series-b"]

    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", _available)

    dialog = MprDialog(loaded_series, initial_series_key="series-b")

    assert dialog._series_combo.count() == 2
    assert dialog._current_series_key() == "series-b"
    assert dialog._spacing_spin.value() == 1.5
    assert dialog._thickness_spin.value() == 3.0
    assert dialog._combine_slice_combo.currentData() == 4
    assert dialog._combine_mode_combo.currentData() == "none"
    assert dialog._combine_thickness_label.text() == ""
    assert dialog._geometry_warning.isHidden() is False
    assert dialog._button_box_ok() is not None
    assert dialog._button_box_ok().isEnabled() is False
    assert "Study: 9.8.7.6..." in dialog._series_info_label.text()

    dialog._series_combo.setCurrentIndex(0)

    assert dialog._current_series_key() == "series-a"
    assert dialog._spacing_spin.value() == 0.8
    assert dialog._thickness_spin.value() == 2.5
    assert dialog._geometry_warning.isHidden() is True
    assert dialog._button_box_ok().isEnabled() is True
    assert "Slices: 2" in dialog._series_info_label.text()
    assert "≈ 128×128 px/slice × 6 slices" in dialog._estimate_label.text()


def test_orientation_toggle_and_combine_visibility(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    dialog = MprDialog(loaded_series)

    assert dialog._custom_widget.isHidden() is True
    dialog._radio_custom.setChecked(True)
    assert dialog._custom_widget.isHidden() is False

    dialog._combine_mode_combo.setCurrentIndex(dialog._combine_mode_combo.findData("none"))
    assert dialog._combine_slice_widget.isHidden() is True
    assert dialog._combine_thickness_label.text() == ""

    dialog._combine_mode_combo.setCurrentIndex(dialog._combine_mode_combo.findData("mip"))
    dialog._combine_slice_combo.setCurrentIndex(dialog._combine_slice_combo.findData(8))
    dialog._thickness_spin.setValue(1.75)
    dialog._update_combine_thickness_hint()

    assert dialog._combine_slice_widget.isHidden() is False
    assert "≈ 14.00 mm along normal" in dialog._combine_thickness_label.text()


def test_resolve_output_plane_standard_and_custom(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    standard = {
        "axial": _plane((0.0, 0.0, 1.0)),
        "coronal": _plane((0.0, 1.0, 0.0)),
        "sagittal": _plane((1.0, 0.0, 0.0)),
    }
    monkeypatch.setattr(MprDialog, "_get_standard_planes", staticmethod(lambda: standard))
    dialog = MprDialog(loaded_series)

    plane, label = dialog._resolve_output_plane()
    assert plane is standard["axial"]
    assert label == "Axial"

    dialog._radio_coronal.setChecked(True)
    plane, label = dialog._resolve_output_plane()
    assert plane is standard["coronal"]
    assert label == "Coronal"

    dialog._radio_sagittal.setChecked(True)
    plane, label = dialog._resolve_output_plane()
    assert plane is standard["sagittal"]
    assert label == "Sagittal"

    dialog._radio_custom.setChecked(True)
    dialog._nx_edit.setText("0")
    dialog._ny_edit.setText("3")
    dialog._nz_edit.setText("4")
    plane, label = dialog._resolve_output_plane()

    assert plane is not None
    assert label == "Custom (0.00,3.00,4.00)"
    np.testing.assert_allclose(plane.normal, np.array([0.0, 0.6, 0.8]))
    assert plane.row_spacing == dialog._spacing_spin.value()
    assert plane.col_spacing == dialog._spacing_spin.value()
    assert abs(float(np.dot(plane.row_cosine, plane.normal))) < 1e-6
    assert abs(float(np.dot(plane.col_cosine, plane.normal))) < 1e-6


def test_resolve_output_plane_invalid_custom_inputs_warn(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    dialog = MprDialog(loaded_series)
    dialog._radio_custom.setChecked(True)

    dialog._nx_edit.setText("bad")
    plane, label = dialog._resolve_output_plane()
    assert plane is None
    assert label == ""
    assert warnings[-1] == "Custom normal vector must be three numeric values."

    dialog._nx_edit.setText("0")
    dialog._ny_edit.setText("0")
    dialog._nz_edit.setText("0")
    plane, label = dialog._resolve_output_plane()
    assert plane is None
    assert label == ""
    assert warnings[-1] == "Custom normal vector must be non-zero."


def test_on_ok_warns_for_missing_series_or_datasets(qapp, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)

    dialog = MprDialog({})
    dialog._on_ok()
    assert warnings[-1] == "No series selected."

    dialog = MprDialog({"empty": {"description": "x", "modality": "CT", "n_slices": 0, "datasets": []}})
    dialog._on_ok()
    assert warnings[-1] == "Selected series has no datasets."


def test_on_ok_warns_when_geometry_unavailable(qapp, loaded_series, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: False)

    dialog = MprDialog(loaded_series)
    dialog._on_ok()

    assert "lacks required DICOM spatial metadata" in warnings[-1]


def test_empty_selection_helpers_and_button_lookup_fallback(qapp):
    dialog = MprDialog({})

    assert dialog._current_series_key() is None
    dialog._on_series_changed(-1)
    assert dialog._series_info_label.text() == ""
    assert dialog._geometry_warning.isHidden() is True

    def monkeypatch_buttonless():
        return None
    assert monkeypatch_buttonless is not None  # keep linters quiet about branch-only test
    original_find_children = dialog.findChildren
    dialog.findChildren = lambda *args, **kwargs: []  # type: ignore[method-assign]
    try:
        assert dialog._button_box_ok() is None
    finally:
        dialog.findChildren = original_find_children  # type: ignore[method-assign]


def test_on_ok_returns_when_output_plane_resolution_fails(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    dialog = MprDialog(loaded_series)
    emitted: list[MprRequest] = []
    dialog.mpr_requested.connect(emitted.append)
    monkeypatch.setattr(dialog, "_resolve_output_plane", lambda: (None, ""))

    dialog._on_ok()

    assert emitted == []
    assert dialog.result() != dialog.DialogCode.Accepted


def test_on_ok_emits_request_for_none_combine_mode(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    plane = _plane((0.0, 0.0, 1.0))
    monkeypatch.setattr(MprDialog, "_get_standard_planes", staticmethod(lambda: {"axial": plane, "coronal": plane, "sagittal": plane}))

    dialog = MprDialog(loaded_series)
    dialog._combine_mode_combo.setCurrentIndex(dialog._combine_mode_combo.findData("none"))
    emitted: list[MprRequest] = []
    dialog.mpr_requested.connect(emitted.append)

    dialog._on_ok()

    assert dialog.result() == dialog.DialogCode.Accepted
    assert len(emitted) == 1
    req = emitted[0]
    assert req.series_key == "series-a"
    assert req.datasets is loaded_series["series-a"]["datasets"]
    assert req.output_plane is plane
    assert req.output_spacing_mm == 0.8
    assert req.output_thickness_mm == 2.5
    assert req.interpolation == "linear"
    assert req.combine_mode == "none"
    assert req.combine_slice_count == 4
    assert req.slab_thickness_mm == 0.0
    assert req.orientation_label == "Axial"


def test_combine_slice_text_fallbacks_default_to_four(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    plane = _plane((0.0, 0.0, 1.0))
    monkeypatch.setattr(MprDialog, "_get_standard_planes", staticmethod(lambda: {"axial": plane, "coronal": plane, "sagittal": plane}))

    dialog = MprDialog(loaded_series)
    dialog._combine_mode_combo.setCurrentIndex(dialog._combine_mode_combo.findData("mip"))
    monkeypatch.setattr(dialog._combine_slice_combo, "currentData", lambda: None)
    monkeypatch.setattr(dialog._combine_slice_combo, "currentText", lambda: "bad")

    dialog._update_combine_thickness_hint()
    assert "≈ 10.00 mm along normal" in dialog._combine_thickness_label.text()

    emitted: list[MprRequest] = []
    dialog.mpr_requested.connect(emitted.append)
    dialog._on_ok()

    assert emitted[0].combine_slice_count == 4
    assert emitted[0].slab_thickness_mm == pytest.approx(10.0)


def test_on_ok_normalizes_combine_slice_count_and_interpolation(qapp, loaded_series, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    plane = _plane((0.0, 1.0, 0.0))
    monkeypatch.setattr(MprDialog, "_get_standard_planes", staticmethod(lambda: {"axial": plane, "coronal": plane, "sagittal": plane}))

    dialog = MprDialog(loaded_series)
    dialog._combine_mode_combo.setCurrentIndex(dialog._combine_mode_combo.findData("mip"))
    dialog._combine_slice_combo.addItem("5", 5)
    dialog._combine_slice_combo.setCurrentIndex(dialog._combine_slice_combo.findData(5))
    dialog._thickness_spin.setValue(1.3)
    dialog._interp_combo.setCurrentIndex(dialog._interp_combo.findData("cubic"))
    emitted: list[MprRequest] = []
    dialog.mpr_requested.connect(emitted.append)

    dialog._on_ok()

    req = emitted[0]
    assert req.combine_mode == "mip"
    assert req.combine_slice_count == 4
    assert req.slab_thickness_mm == pytest.approx(5.2)
    assert req.interpolation == "cubic"


def test_update_estimate_handles_missing_dimensions(qapp, monkeypatch):
    monkeypatch.setattr("gui.dialogs.mpr_dialog.MprVolume.available", lambda datasets: True)
    bad = Dataset()
    dialog = MprDialog({"bad": {"description": "bad", "modality": "CT", "n_slices": 1, "datasets": [bad]}})

    assert dialog._estimate_label.text() == ""


def test_perpendicular_axes_handles_near_parallel_reference():
    normal = np.array([1.0, 0.0, 0.0])
    row, col = MprDialog._perpendicular_axes(normal)

    np.testing.assert_allclose(np.linalg.norm(row), 1.0)
    np.testing.assert_allclose(np.linalg.norm(col), 1.0)
    assert abs(float(np.dot(row, normal))) < 1e-6
    assert abs(float(np.dot(col, normal))) < 1e-6
    assert abs(float(np.dot(row, col))) < 1e-6
