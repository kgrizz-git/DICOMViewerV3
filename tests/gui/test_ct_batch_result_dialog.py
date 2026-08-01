"""Tests for create_ct_batch_result_dialog factory."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton, QTableWidget

from gui.dialogs.ct_batch_result_dialog import create_ct_batch_result_dialog
from qa.analysis_types import CTBatchResult, QAResult


def _batch(*, fail_second: bool = False) -> CTBatchResult:
    r0 = QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={
            "low_contrast_cnr": {
                "object_rois": [{"mean": 10.0}, {"mean": 14.0}],
                "background_mean": 2.0,
                "background_std": 1.5,
                "cnr": 4.0,
            }
        },
        warnings=["w1"],
    )
    r1 = QAResult(
        success=not fail_second,
        analysis_type="acr_ct",
        metrics={},
        errors=["x"] if fail_second else [],
    )
    return CTBatchResult(run_results=[r0, r1], run_labels=["Series A", "Series B"])


@pytest.mark.qt
def test_one_row_per_series_with_cnr_cells(qapp) -> None:
    dlg = create_ct_batch_result_dialog(
        None,
        _batch(),
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
    )
    table = dlg.findChildren(QTableWidget)[0]
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "Series A"
    assert table.item(0, 1).text() == "OK"
    assert table.item(0, 2).text() == "12.000"  # mean of 10 and 14
    assert table.item(0, 5).text() == "4.000"


@pytest.mark.qt
def test_export_buttons_fire_callbacks(qapp) -> None:
    xlsx: list[int] = []
    json_clicks: list[int] = []
    dlg = create_ct_batch_result_dialog(
        None,
        _batch(),
        on_save_xlsx_clicked=lambda: xlsx.append(1),
        on_save_json_clicked=lambda: json_clicks.append(1),
    )
    buttons = {b.text(): b for b in dlg.findChildren(QPushButton)}
    buttons["Export XLSX…"].click()
    buttons["Export JSON…"].click()
    assert xlsx == [1]
    assert json_clicks == [1]


@pytest.mark.qt
def test_failed_series_updates_title(qapp) -> None:
    dlg = create_ct_batch_result_dialog(
        None,
        _batch(fail_second=True),
        on_save_xlsx_clicked=lambda: None,
        on_save_json_clicked=lambda: None,
    )
    assert "one or more series failed" in dlg.windowTitle()
