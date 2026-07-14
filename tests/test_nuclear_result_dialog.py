"""
Qt tests for the nuclear QC result dialog.

Verifies the per-frame table is populated for a successful run and that a failed
run shows errors instead of a table. Uses the session ``qapp`` fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QTableWidget

from gui.dialogs.nuclear_result_dialog import NuclearResultDialog
from qa.analysis_types import QAResult

pytestmark = pytest.mark.qt

_FRAMES = {
    "Frame 1": {
        "ufov_integral_uniformity": 2.377,
        "ufov_differential_uniformity": 1.838,
        "cfov_integral_uniformity": 2.377,
        "cfov_differential_uniformity": 1.728,
    },
    "Frame 2": {
        "ufov_integral_uniformity": 2.55,
        "ufov_differential_uniformity": 1.90,
        "cfov_integral_uniformity": 2.50,
        "cfov_differential_uniformity": 1.80,
    },
}


_FOURBAR_RESULTS = {
    "x_fwhm": 7.66,
    "y_fwhm": 7.60,
    "x_fwtm": 13.96,
    "y_fwtm": 13.85,
    "x_measured_pixel_size": 1.043,
    "y_measured_pixel_size": 1.040,
    "x_pixel_size_difference": 1.049,
    "y_pixel_size_difference": 0.714,
}


def _success_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="nuclear_planar_uniformity",
        metrics={"analysis_class": "PlanarUniformity", "frame_count": 2, "frames": _FRAMES},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "PlanarUniformity",
            "analysis_parameters": {"ufov_ratio": 0.95},
            "vanilla_equivalent": True,
        },
    )


def _fourbar_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="nuclear_four_bar_resolution",
        metrics={"analysis_class": "FourBarResolution", "results": _FOURBAR_RESULTS},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "FourBarResolution",
            "analysis_parameters": {"separation_mm": 100.0, "roi_width_mm": 10.0},
            "vanilla_equivalent": True,
        },
    )


def test_result_dialog_shows_one_row_per_frame(qapp) -> None:
    dlg = NuclearResultDialog(_success_result(), title="Nuclear Medicine QC")
    tables = dlg.findChildren(QTableWidget)
    assert len(tables) == 1
    table = tables[0]
    assert table.rowCount() == 2
    assert table.columnCount() == 5  # Frame + 4 metrics
    assert table.item(0, 0).text() == "Frame 1"
    # UFOV integral for frame 1 formatted to 3 decimals.
    assert table.item(0, 1).text() == "2.377"
    dlg.deleteLater()


def test_result_dialog_failure_shows_errors_not_table(qapp) -> None:
    failed = QAResult(
        success=False,
        analysis_type="nuclear_planar_uniformity",
        errors=["PlanarUniformity analysis failed: phantom not found"],
        pylinac_analysis_profile={"module": "pylinac.nuclear"},
    )
    dlg = NuclearResultDialog(failed, title="Nuclear Medicine QC")
    assert dlg.findChildren(QTableWidget) == []
    # CSV is disabled for a failed run (no frames); JSON still allowed.
    assert dlg._csv_btn.isEnabled() is False
    dlg.deleteLater()


def test_export_json_button_writes_file(qapp, tmp_path) -> None:
    import json

    out = str(tmp_path / "out.json")
    statuses: list[str] = []
    dlg = NuclearResultDialog(
        _success_result(),
        title="Nuclear Medicine QC",
        app_version="9.9.9",
        prompt_save_path=lambda *a, **k: out,
        on_status=statuses.append,
    )
    dlg._export_json()
    doc = json.loads(Path(out).read_text(encoding="utf-8"))
    assert doc["run"]["nuclear_analysis_class"] == "PlanarUniformity"
    assert statuses and "Saved QA JSON" in statuses[-1]
    dlg.deleteLater()


def test_export_csv_button_writes_file(qapp, tmp_path) -> None:
    out = str(tmp_path / "out.csv")
    dlg = NuclearResultDialog(
        _success_result(),
        title="Nuclear Medicine QC",
        prompt_save_path=lambda *a, **k: out,
    )
    dlg._export_csv()
    text = Path(out).read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("frame,")
    assert "Frame 1" in text and "Frame 2" in text
    dlg.deleteLater()


def test_export_cancelled_when_no_path(qapp) -> None:
    """Returning an empty path (user cancelled) must not write or crash."""
    dlg = NuclearResultDialog(
        _success_result(),
        title="Nuclear Medicine QC",
        prompt_save_path=lambda *a, **k: "",
    )
    dlg._export_json()  # no exception, no file
    dlg.deleteLater()


def test_figure_button_disabled_without_input_path(qapp) -> None:
    # _success_result() has no input_path in its profile/inputs.
    dlg = NuclearResultDialog(_success_result(), title="Nuclear Medicine QC")
    assert dlg._fig_btn.isEnabled() is False
    dlg.deleteLater()


def test_figure_button_enabled_with_input_path(qapp) -> None:
    dlg = NuclearResultDialog(
        _success_result(),
        title="Nuclear Medicine QC",
        inputs={"input_path": "planar.dcm"},
    )
    assert dlg._fig_btn.isEnabled() is True
    dlg.deleteLater()


_QUADRANTS = {
    "1": {"mtf": 0.647, "fwhm": 2.956, "lpmm": 0.118, "spacing": 4.23},
    "2": {"mtf": 0.468, "fwhm": 2.931, "lpmm": 0.157, "spacing": 3.18},
    "3": {"mtf": 0.304, "fwhm": 2.933, "lpmm": 0.197, "spacing": 2.54},
    "4": {"mtf": 0.202, "fwhm": 2.835, "lpmm": 0.236, "spacing": 2.12},
}


def _quadrant_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="nuclear_quadrant_resolution",
        metrics={"analysis_class": "QuadrantResolution", "quadrants": _QUADRANTS},
        pylinac_version="3.43.2",
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "QuadrantResolution",
            "analysis_parameters": {"bar_widths": [4.23, 3.18, 2.54, 2.12]},
            "vanilla_equivalent": True,
        },
    )


def test_quadrant_result_renders_quadrant_table(qapp) -> None:
    dlg = NuclearResultDialog(_quadrant_result(), title="Nuclear Medicine QC")
    tables = dlg.findChildren(QTableWidget)
    assert len(tables) == 1
    table = tables[0]
    assert table.columnCount() == 5  # Quadrant + 4 metrics
    assert table.rowCount() == 4
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 1).text() == "0.647"  # MTF
    dlg.deleteLater()


def test_quadrant_export_csv_is_per_quadrant(qapp, tmp_path) -> None:
    out = str(tmp_path / "quad.csv")
    dlg = NuclearResultDialog(
        _quadrant_result(),
        title="Nuclear Medicine QC",
        prompt_save_path=lambda *a, **k: out,
    )
    dlg._export_csv()
    lines = Path(out).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "quadrant,mtf,fwhm,lpmm,spacing"
    assert lines[1].startswith("1,0.647")
    dlg.deleteLater()


_SPHERES = {
    "1": {"x": 78.5, "y": 58.5, "z": 13.0, "radius": 4.6, "mean": 633.9,
          "mean_contrast": 35.8, "max_contrast": 72.3},
    "2": {"x": 69.7, "y": 47.4, "z": 14.0, "radius": 3.9, "mean": 828.8,
          "mean_contrast": 23.6, "max_contrast": 52.9},
}


def _contrast_result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="nuclear_tomographic_contrast",
        metrics={
            "analysis_class": "TomographicContrast",
            "spheres": _SPHERES,
            "uniformity_baseline": 1341.28,
        },
        pylinac_version="3.43.2",
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "TomographicContrast",
            "vanilla_equivalent": True,
        },
    )


def test_contrast_result_renders_sphere_table(qapp) -> None:
    dlg = NuclearResultDialog(_contrast_result(), title="Nuclear Medicine QC")
    tables = dlg.findChildren(QTableWidget)
    assert len(tables) == 1
    table = tables[0]
    assert table.columnCount() == 8  # Sphere + 7 metrics
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 1).text() == "78.500"  # x
    dlg.deleteLater()


def test_contrast_export_csv_is_per_sphere(qapp, tmp_path) -> None:
    out = str(tmp_path / "spheres.csv")
    dlg = NuclearResultDialog(
        _contrast_result(),
        title="Nuclear Medicine QC",
        prompt_save_path=lambda *a, **k: out,
    )
    dlg._export_csv()
    lines = Path(out).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "sphere,x,y,z,radius,mean,mean_contrast,max_contrast"
    assert lines[1].startswith("1,78.5")
    dlg.deleteLater()


def test_fourbar_result_renders_kv_table(qapp) -> None:
    dlg = NuclearResultDialog(_fourbar_result(), title="Nuclear Medicine QC")
    tables = dlg.findChildren(QTableWidget)
    assert len(tables) == 1
    table = tables[0]
    assert table.columnCount() == 2  # Metric, Value
    assert table.rowCount() == len(_FOURBAR_RESULTS)
    assert table.item(0, 0).text() == "x_fwhm"
    assert table.item(0, 1).text() == "7.660"
    # CSV/figure enabled for flat results too (figure needs input_path).
    assert dlg._csv_btn.isEnabled() is True
    dlg.deleteLater()


def test_fourbar_export_csv_is_flat(qapp, tmp_path) -> None:
    out = str(tmp_path / "fourbar.csv")
    dlg = NuclearResultDialog(
        _fourbar_result(),
        title="Nuclear Medicine QC",
        prompt_save_path=lambda *a, **k: out,
    )
    dlg._export_csv()
    lines = Path(out).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "metric,value"
    assert "x_fwhm,7.66" in lines[1]
    dlg.deleteLater()


def test_figure_button_disabled_for_non_plottable_class(qapp) -> None:
    # SimpleSensitivity (not in _PLOTTABLE_CLASSES) must not offer Save Figure,
    # even with frames/results and an input path.
    result = QAResult(
        success=True,
        analysis_type="nuclear_simple_sensitivity",
        metrics={"analysis_class": "SimpleSensitivity", "results": {"sensitivity_mbq": 244.1}},
        pylinac_analysis_profile={
            "module": "pylinac.nuclear",
            "nuclear_analysis_class": "SimpleSensitivity",
        },
    )
    dlg = NuclearResultDialog(
        result, title="Nuclear Medicine QC", inputs={"input_path": "phantom.dcm"}
    )
    assert dlg._csv_btn.isEnabled() is True
    assert dlg._fig_btn.isEnabled() is False
    dlg.deleteLater()


def test_export_figure_invokes_renderer(qapp, tmp_path, monkeypatch) -> None:
    import qa.pylinac_nuclear_plots as plots

    out = str(tmp_path / "fig.png")
    calls: dict = {}

    def _fake_render(input_path, *, analysis_class, analyze_kwargs, out_path):
        calls.update(
            input_path=input_path, analysis_class=analysis_class, out_path=out_path
        )
        return [out_path]

    monkeypatch.setattr(plots, "render_nuclear_figures", _fake_render)

    statuses: list[str] = []
    dlg = NuclearResultDialog(
        _success_result(),
        title="Nuclear Medicine QC",
        inputs={"input_path": "planar.dcm"},
        prompt_save_path=lambda *a, **k: out,
        on_status=statuses.append,
    )
    dlg._export_figure()
    assert calls["input_path"] == "planar.dcm"
    assert calls["analysis_class"] == "PlanarUniformity"
    assert statuses and "Saved figure" in statuses[-1]
    dlg.deleteLater()
