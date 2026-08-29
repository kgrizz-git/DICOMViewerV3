"""
Non-modal ACR MRI Large batch-results dialog (pylinac batch, P4-M4).

Built by ``gui.qa_mri_batch_flow._show_acr_mri_batch_summary`` after
``QAMRIBatchWorker`` emits ``ACRMBatchResult``. Layout mirrors
``ct_batch_result_dialog.py`` (factory shape, ``QTableWidget`` +
export-button row, window chrome), but the semantics are MRI: **one row per
series**, columns are the series label, status, the low-contrast (LC) score
when present (the MRI analogue of the CT CNR block), and warnings.

Inputs:
    - Parent widget, ``ACRMBatchResult``, callbacks for XLSX/JSON/CSV export.

Outputs:
    - Configured ``QDialog`` (caller stores reference, ``WA_DeleteOnClose``).

Requirements:
    - PySide6 widgets; ``qa.analysis_types.ACRMBatchResult``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from qa.analysis_types import ACRMBatchResult

_COLUMN_HEADERS = (
    "Series/Run",
    "Status",
    "LC Score",
    "Warnings",
)


def _lc_score_value(result: Any) -> str:
    """
    Pull the low-contrast score for a table row (MRI analogue of the CT CNR
    block). Reads ``metrics["low_contrast_score"]`` with ``.get()``; any
    missing/non-numeric key degrades to a blank cell.
    """
    score = result.metrics.get("low_contrast_score")
    if isinstance(score, (int, float)):
        return f"{score:.3f}"
    return ""


def create_mri_batch_result_dialog(
    parent: QWidget | None,
    batch: ACRMBatchResult,
    *,
    on_save_xlsx_clicked: Callable[[], None],
    on_save_json_clicked: Callable[[], None],
    on_save_csv_clicked: Callable[[], None],
    on_destroyed: Callable[..., None] | None = None,
) -> QDialog:
    """
    Build the batch summary dialog: one row per series.

    Args:
        parent: Owning window (typically ``app.main_window``).
        batch: Completed batch with parallel ``run_results`` / ``run_labels``.
        on_save_xlsx_clicked: Invoked when **Export XLSX** is pressed; caller
            calls ``qa.qa_xlsx_export.build_qa_workbook`` directly (OQ-9).
        on_save_json_clicked: Invoked when **Export JSON** is pressed.
        on_save_csv_clicked: Invoked when **Export CSV** is pressed; caller
            writes ``build_batch_metrics_csv`` (full flatten, one row per series).
        on_destroyed: Optional slot for ``dialog.destroyed`` (e.g. clear app
            ref).

    Returns:
        Non-modal ``QDialog``; caller should ``show()`` and retain a ref.
    """
    results = batch.run_results
    labels = batch.run_labels
    n = len(results)

    dialog = QDialog(parent)
    dialog.setWindowTitle("ACR MRI Phantom Analysis — Batch Results")
    dialog.setModal(False)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if on_destroyed is not None:
        dialog.destroyed.connect(on_destroyed)

    outer = QVBoxLayout(dialog)
    outer.addWidget(
        QLabel(f"Batch summary — {n} series (one row per series; see plan Feature 4).")
    )

    table = QTableWidget(n, len(_COLUMN_HEADERS))
    table.setHorizontalHeaderLabels(list(_COLUMN_HEADERS))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)

    for row, (label, result) in enumerate(zip(labels, results, strict=True)):
        lc_score = _lc_score_value(result)
        status = "OK" if result.success else "FAILED"
        if result.warnings:
            wsum = "; ".join(result.warnings[:3])
            if len(result.warnings) > 3:
                wsum += " …"
        else:
            wsum = "—"
        column_values = [label, status, lc_score, wsum]
        for col, text in enumerate(column_values):
            table.setItem(row, col, QTableWidgetItem(text))

    outer.addWidget(table)

    detail_lines: list[str] = []
    for label, result in zip(labels, results, strict=True):
        if result.warnings:
            detail_lines.append(f"{label} — warnings:")
            for w in result.warnings:
                detail_lines.append(f"  • {w}")
        if result.errors:
            detail_lines.append(f"{label} — errors:")
            for e in result.errors:
                detail_lines.append(f"  • {e}")

    details = QTextEdit()
    details.setReadOnly(True)
    details.setPlainText("\n".join(detail_lines))
    details.setMinimumHeight(120)
    outer.addWidget(QLabel("Warnings and errors (full)"))
    outer.addWidget(details)

    btn_row = QHBoxLayout()
    save_xlsx_btn = QPushButton("Export XLSX…")
    save_xlsx_btn.clicked.connect(on_save_xlsx_clicked)
    btn_row.addWidget(save_xlsx_btn)
    save_json_btn = QPushButton("Export JSON…")
    save_json_btn.clicked.connect(on_save_json_clicked)
    btn_row.addWidget(save_json_btn)
    save_csv_btn = QPushButton("Export CSV…")
    save_csv_btn.setToolTip("Full flatten, one row per series.")
    save_csv_btn.clicked.connect(on_save_csv_clicked)
    btn_row.addWidget(save_csv_btn)
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.close)
    btn_row.addWidget(close_btn)
    btn_row.addStretch()
    outer.addLayout(btn_row)

    if not all(r.success for r in results):
        dialog.setWindowTitle(dialog.windowTitle() + " (one or more series failed)")

    dialog.resize(min(1100, 320 + n * 40), 560)
    return dialog
