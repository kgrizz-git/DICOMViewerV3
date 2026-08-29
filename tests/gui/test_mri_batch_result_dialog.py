"""Tests for create_mri_batch_result_dialog factory (P4-M4)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton, QTableWidget

from gui.dialogs.mri_batch_result_dialog import create_mri_batch_result_dialog
from qa.analysis_types import ACRMBatchResult, QAResult


def _batch(*, fail_second: bool = False) -> ACRMBatchResult:
    r0 = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 42.5},
        warnings=["w1"],
    )
    r1 = QAResult(
        success=not fail_second,
        analysis_type="acr_mri_large",
        metrics={},
        errors=["x"] if fail_second else [],
    )
    return ACRMBatchResult(run_results=[r0, r1], run_labels=["Series A", "Series B"])


@pytest.mark.qt
def test_one_row_per_series_with_lc_score(qapp) -> None:
    dlg = create_mri_batch_result_dialog(
        None,
        _batch(),
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
        on_save_csv_clicked=lambda: None,
    )
    table = dlg.findChildren(QTableWidget)[0]
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "Series A"
    assert table.item(0, 1).text() == "OK"
    assert table.item(0, 2).text() == "42.500"
    assert table.item(1, 1).text() == "OK"


@pytest.mark.qt
def test_export_buttons_fire_callbacks(qapp) -> None:
    xlsx: list[int] = []
    json_clicks: list[int] = []
    csv: list[int] = []
    dlg = create_mri_batch_result_dialog(
        None,
        _batch(),
        on_save_xlsx_clicked=lambda: xlsx.append(1),
        on_save_json_clicked=lambda: json_clicks.append(1),
        on_save_csv_clicked=lambda: csv.append(1),
    )
    buttons = {b.text(): b for b in dlg.findChildren(QPushButton)}
    assert "Export XLSX…" in buttons
    assert "Export JSON…" in buttons
    assert "Export CSV…" in buttons
    buttons["Export XLSX…"].click()
    buttons["Export JSON…"].click()
    buttons["Export CSV…"].click()
    assert xlsx == [1]
    assert json_clicks == [1]
    assert csv == [1]


@pytest.mark.qt
def test_failed_series_updates_title(qapp) -> None:
    dlg = create_mri_batch_result_dialog(
        None,
        _batch(fail_second=True),
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
        on_save_csv_clicked=lambda: None,
    )
    assert "one or more series failed" in dlg.windowTitle()


@pytest.mark.qt
def test_missing_lc_score_blank(qapp) -> None:
    """A run with no low_contrast_score metric leaves the LC cell blank."""
    dlg = create_mri_batch_result_dialog(
        None,
        _batch(),
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
        on_save_csv_clicked=lambda: None,
    )
    table = dlg.findChildren(QTableWidget)[0]
    # Second run has empty metrics -> no LC score.
    assert table.item(1, 2).text() == ""


@pytest.mark.qt
def test_zero_lc_score_renders_as_zero(qapp) -> None:
    """A numeric LC score of 0 must render as 0.000, not a blank cell."""
    zero = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 0},
    )
    batch = ACRMBatchResult(run_results=[zero], run_labels=["Zero LC"])
    dlg = create_mri_batch_result_dialog(
        None,
        batch,
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
        on_save_csv_clicked=lambda: None,
    )
    table = dlg.findChildren(QTableWidget)[0]
    assert table.item(0, 2).text() == "0.000"
