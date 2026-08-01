"""Tests for create_mri_compare_result_dialog factory."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QPushButton, QTableWidget

from gui.dialogs.mri_compare_result_dialog import create_mri_compare_result_dialog
from qa.analysis_types import LcRunConfig, MRIBatchResult, QAResult


def _batch(*, success_second: bool = True, with_pdf: bool = False) -> MRIBatchResult:
    r0 = QAResult(
        success=True,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 10},
        warnings=["warn-a", "warn-b", "warn-c", "warn-d"],
        pylinac_analysis_profile={"vanilla_equivalent": False},
    )
    if with_pdf:
        r0.pdf_report_path = "/tmp/fake-combined.pdf"  # NOSONAR - fixture path only
    r1 = QAResult(
        success=success_second,
        analysis_type="acr_mri_large",
        metrics={"low_contrast_score": 8},
        errors=[] if success_second else ["boom"],
        pylinac_analysis_profile={"vanilla_equivalent": True},
    )
    return MRIBatchResult(
        run_configs=[
            LcRunConfig("Run A", "Weber", 0.001, 3.0),
            LcRunConfig("Run B", "Michelson", 0.0009, 2.5),
        ],
        run_results=[r0, r1],
    )


@pytest.mark.qt
def test_table_columns_and_status_cells(qapp) -> None:
    dlg = create_mri_compare_result_dialog(
        None, _batch(), on_save_json_clicked=lambda: None
    )
    tables = dlg.findChildren(QTableWidget)
    assert len(tables) == 1
    table = tables[0]
    assert table.columnCount() == 2
    assert table.horizontalHeaderItem(0).text() == "Run A"
    assert table.item(0, 0).text() == "OK"
    assert table.item(2, 0).text() == "No"  # vanilla_equivalent False
    assert "…" in table.item(6, 0).text()  # warnings truncated


@pytest.mark.qt
def test_save_json_and_open_pdf_callbacks(qapp) -> None:
    saved: list[int] = []
    opened: list[str] = []
    dlg = create_mri_compare_result_dialog(
        None,
        _batch(with_pdf=True),
        on_save_json_clicked=lambda: saved.append(1),
        on_open_pdf=lambda path: opened.append(path),
    )
    buttons = {b.text(): b for b in dlg.findChildren(QPushButton)}
    assert "Save comparison JSON…" in buttons
    assert "Open PDF" in buttons
    buttons["Save comparison JSON…"].click()
    buttons["Open PDF"].click()
    assert saved == [1]
    assert opened == ["/tmp/fake-combined.pdf"]


@pytest.mark.qt
def test_failed_run_updates_window_title(qapp) -> None:
    dlg = create_mri_compare_result_dialog(
        None, _batch(success_second=False), on_save_json_clicked=lambda: None
    )
    assert "one or more runs failed" in dlg.windowTitle()
