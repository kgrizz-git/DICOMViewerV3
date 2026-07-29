"""
Unit tests for Feature 3 — XLSX export (``qa.qa_xlsx_export``).

Covers ``build_qa_workbook`` via an in-memory openpyxl round-trip (single and
multi-row), the Pillow-missing degradation path (Images sheet skipped, note
cell added to Summary), the Qt-free import guarantee, and the transient
``analyzed_image_path`` leak guard shared with the JSON/CSV builders.
"""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

import openpyxl
import pytest
from openpyxl.utils.units import pixels_to_EMU

from qa import qa_xlsx_export
from qa.analysis_types import QAResult
from qa.qa_export import build_metrics_csv, build_single_run_document
from qa.qa_xlsx_export import build_qa_workbook

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def _result(
    *,
    series_uid: str = "1.2.3",
    success: bool = True,
    cnr_details: dict | None = None,
    warnings: list[str] | None = None,
    analyzed_image_path: str | None = None,
) -> QAResult:
    metrics: dict = {"input_count": 5, "vanilla_pylinac": False}
    if cnr_details is not None:
        metrics["low_contrast_cnr"] = cnr_details
    return QAResult(
        success=success,
        analysis_type="acr_ct",
        metrics=metrics,
        warnings=warnings or [],
        errors=[] if success else ["boom"],
        study_uid="1.2.3.study",
        series_uid=series_uid,
        modality="CT",
        num_images=5,
        pylinac_version="3.43.2",
        analyzed_image_path=analyzed_image_path,
    )


_CNR_DETAILS = {
    "cnr": 4.5,
    "object_rois": [{"mean": 100.0, "pixel_value": 100.0, "contrast_to_noise": 3.0}],
    "background": {"means": [10.0], "stds": [2.0], "mean": 10.0, "std": 2.0},
}


def _save_and_reload(wb: openpyxl.Workbook) -> openpyxl.Workbook:
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return openpyxl.load_workbook(buffer)


def test_single_row_workbook_round_trip() -> None:
    result = _result(cnr_details=_CNR_DETAILS, warnings=["w1"])
    wb = build_qa_workbook([result], labels=["Series A"], app_version="9.9.9")
    reloaded = _save_and_reload(wb)

    assert reloaded.sheetnames[:2] == ["Summary", "Detail"]
    summary = reloaded["Summary"]
    header = [c.value for c in summary[1]]
    assert header[0] == "Series/Run ID"
    row2 = [c.value for c in summary[2]]
    assert row2[0] == "Series A"
    assert row2[1] == 100.0  # object ROI mean
    assert row2[2] == 10.0  # background mean
    assert row2[3] == 2.0  # background std
    assert row2[4] == 4.5  # cnr
    assert row2[5] == "success"
    assert row2[6] == "w1"

    detail = reloaded["Detail"]
    detail_values = [c.value for row in detail.iter_rows() for c in row]
    assert "Series A" in detail_values
    assert "low_contrast_cnr.cnr" in detail_values


def test_multi_row_workbook_round_trip() -> None:
    results = [
        _result(series_uid="1.1", cnr_details=_CNR_DETAILS),
        _result(series_uid="1.2", success=False),
    ]
    wb = build_qa_workbook(results)  # no labels -> falls back to series_uid
    reloaded = _save_and_reload(wb)

    summary = reloaded["Summary"]
    ids = [row[0].value for row in summary.iter_rows(min_row=2, max_row=3)]
    assert ids == ["1.1", "1.2"]
    statuses = [row[5].value for row in summary.iter_rows(min_row=2, max_row=3)]
    assert statuses == ["success", "failed"]


def test_labels_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        build_qa_workbook([_result(), _result(series_uid="1.4")], labels=["only one"])


def test_no_analyzed_image_skips_images_sheet_with_note() -> None:
    result = _result(cnr_details=_CNR_DETAILS, analyzed_image_path=None)
    wb = build_qa_workbook([result])
    reloaded = _save_and_reload(wb)

    assert "Images" not in reloaded.sheetnames
    summary_values = [c.value for row in reloaded["Summary"].iter_rows() for c in row]
    assert any(
        isinstance(v, str) and "Images sheet skipped" in v for v in summary_values
    )


def test_pillow_missing_skips_images_sheet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Simulate a Pillow-less environment via the module's availability guard
    (real Pillow import failure would require uninstalling the dependency).
    """
    png_path = tmp_path / "analyzed.png"
    png_path.write_bytes(b"not a real png but path exists")
    result = _result(cnr_details=_CNR_DETAILS, analyzed_image_path=str(png_path))

    monkeypatch.setattr(qa_xlsx_export, "_PILLOW_AVAILABLE", False)
    wb = build_qa_workbook([result])
    reloaded = _save_and_reload(wb)

    assert "Images" not in reloaded.sheetnames
    summary_values = [c.value for row in reloaded["Summary"].iter_rows() for c in row]
    assert any(
        isinstance(v, str) and "Pillow is not available" in v for v in summary_values
    )
    # Rest of the workbook still writes.
    assert reloaded["Detail"].max_row > 1


def test_images_sheet_deterministic_dimensions_and_stride(tmp_path: Path) -> None:
    """Verify image dimensions are set to 480x480 and row stride is 34 rows per run."""
    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("Pillow is not installed")

    img_path1 = tmp_path / "img1.png"
    img_path2 = tmp_path / "img2.png"
    PILImage.new("RGB", (200, 100), color="red").save(img_path1)
    PILImage.new("RGB", (300, 300), color="blue").save(img_path2)

    res1 = _result(series_uid="1.1", analyzed_image_path=str(img_path1))
    res2 = _result(series_uid="1.2", analyzed_image_path=str(img_path2))

    workbook = build_qa_workbook([res1, res2], labels=["Run 1", "Run 2"])
    reloaded = _save_and_reload(workbook)
    assert "Images" in reloaded.sheetnames
    ws = reloaded["Images"]

    # Cell positions for labels
    assert ws.cell(row=1, column=1).value == "Run 1"
    # Row 1 (label) -> row 2 (image) -> row += 34 -> row 36 (label 2)
    assert ws.cell(row=36, column=1).value == "Run 2"

    assert len(ws._images) == 2
    expected_extent = pixels_to_EMU(480)
    actual_anchors = [
        (image.anchor._from.row, image.anchor.ext.width, image.anchor.ext.height)
        for image in ws._images
    ]
    assert actual_anchors == [
        (1, expected_extent, expected_extent),
        (36, expected_extent, expected_extent),
    ]

def test_module_has_no_qt_import() -> None:
    """
    Static check: qa_xlsx_export.py must not import any Qt package, so it
    stays usable from headless/batch contexts (see module boundary in the
    plan: qa_export.py / qa_xlsx_export.py are both Qt-free).
    """
    source = (_SRC_ROOT / "qa" / "qa_xlsx_export.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    qt_markers = ("PySide6", "PyQt5", "PyQt6", "PySide2")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not any(marker in alias.name for marker in qt_markers)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not any(marker in node.module for marker in qt_markers)


def test_module_not_already_imported_qt() -> None:
    """qa_xlsx_export must be importable without pulling in a Qt binding."""
    for mod_name in list(sys.modules):
        if mod_name.startswith(("PySide6", "PyQt5", "PyQt6", "PySide2")):
            pytest.skip("A Qt binding is already imported in this test session.")
    import qa.qa_xlsx_export  # noqa: F401

    assert not any(m.startswith(("PySide6", "PyQt5", "PyQt6", "PySide2")) for m in sys.modules)


def test_analyzed_image_path_does_not_leak_into_json_or_csv() -> None:
    """
    Regression guard for the F3 leak-safety claim: the transient
    QAResult.analyzed_image_path field must never appear in the JSON or CSV
    single-run exports (both name their fields explicitly).
    """
    secret_path = "/tmp/definitely-not-in-exports/analyzed_image_abc123.png"
    result = _result(cnr_details=_CNR_DETAILS, analyzed_image_path=secret_path)

    doc = build_single_run_document(result, app_version="9.9.9", inputs={})
    assert secret_path not in repr(doc)

    csv_text = build_metrics_csv(result)
    assert secret_path not in csv_text
