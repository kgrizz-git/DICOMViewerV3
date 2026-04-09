"""
Non-modal ACR MRI compare-results dialog (pylinac batch / compare mode).

Built by ``QAAppFacade.show_mri_compare_result_dialog`` after ``QABatchWorker``
emits ``MRIBatchResult``. Layout: metrics × runs table, full warnings/errors
text, **Save comparison JSON**, optional **Open PDF**, **Close**. Deliberately
**not** ``WindowStaysOnTop`` so an external PDF viewer can take focus without
fighting this window.

Inputs:
    - Parent widget, ``MRIBatchResult``, callbacks for JSON export and PDF open.

Outputs:
    - Configured ``QDialog`` (caller stores reference, ``WA_DeleteOnClose``).

Requirements:
    - PySide6 widgets; ``qa.analysis_types.MRIBatchResult``.
"""

from __future__ import annotations

from typing import Callable, List, Optional

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

from qa.analysis_types import MRIBatchResult


def create_mri_compare_result_dialog(
    parent: Optional[QWidget],
    batch: MRIBatchResult,
    *,
    on_save_json_clicked: Callable[[], None],
    on_open_pdf: Optional[Callable[[str], None]] = None,
    on_destroyed: Optional[Callable[..., None]] = None,
) -> QDialog:
    """
    Build the compare summary dialog (plan section 1.6 table layout).

    Args:
        parent: Owning window (typically ``app.main_window``).
        batch: Completed batch with parallel ``run_configs`` / ``run_results``.
        on_save_json_clicked: Invoked when **Save comparison JSON** is pressed.
        on_open_pdf: If set, **Open PDF** calls ``on_open_pdf(combined_pdf_path)``.
        on_destroyed: Optional slot for ``dialog.destroyed`` (e.g. clear app ref).

    Returns:
        Non-modal ``QDialog``; caller should ``show()`` and retain ref if needed.
    """
    configs = batch.run_configs
    results = batch.run_results
    n = len(configs)

    dialog = QDialog(parent)
    dialog.setWindowTitle("ACR MRI Phantom Analysis — Compare Results")
    dialog.setModal(False)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    if on_destroyed is not None:
        dialog.destroyed.connect(on_destroyed)

    outer = QVBoxLayout(dialog)
    outer.addWidget(QLabel("Comparison table — one column per run (see plan section 1.6)."))

    row_labels = [
        "Status",
        "Low contrast score",
        "Vanilla equivalent",
        "Contrast method",
        "Visibility threshold",
        "Sanity multiplier",
        "Warnings (summary)",
    ]
    n_rows = len(row_labels)
    table = QTableWidget(n_rows, n)
    table.setHorizontalHeaderLabels([c.label for c in configs])
    table.setVerticalHeaderLabels(row_labels)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    for col, (cfg, r) in enumerate(zip(configs, results)):
        prof = r.pylinac_analysis_profile or {}
        vanilla = "Yes" if prof.get("vanilla_equivalent", True) else "No"
        lc_score = (
            str(r.metrics.get("low_contrast_score", "N/A")) if r.success else "N/A"
        )
        if r.warnings:
            wsum = "; ".join(r.warnings[:3])
            if len(r.warnings) > 3:
                wsum += " …"
        else:
            wsum = "—"

        column_values = [
            "OK" if r.success else "FAILED",
            lc_score,
            vanilla,
            cfg.low_contrast_method,
            f"{cfg.low_contrast_visibility_threshold:.6f}",
            f"{cfg.low_contrast_visibility_sanity_multiplier:.3f}",
            wsum,
        ]
        for row, text in enumerate(column_values):
            table.setItem(row, col, QTableWidgetItem(text))

    outer.addWidget(table)

    combined_pdf: Optional[str] = None
    if results and results[0].pdf_report_path:
        combined_pdf = results[0].pdf_report_path

    detail_lines: List[str] = []
    if combined_pdf:
        detail_lines.append(f"Combined PDF: {combined_pdf}")
    else:
        detail_lines.append("Combined PDF: not generated")
    detail_lines.append("")
    for cfg, r in zip(configs, results):
        if r.warnings:
            detail_lines.append(f"{cfg.label} — warnings:")
            for w in r.warnings:
                detail_lines.append(f"  • {w}")
        if r.errors:
            detail_lines.append(f"{cfg.label} — errors:")
            for e in r.errors:
                detail_lines.append(f"  • {e}")

    details = QTextEdit()
    details.setReadOnly(True)
    details.setPlainText("\n".join(detail_lines))
    details.setMinimumHeight(120)
    outer.addWidget(QLabel("Warnings and errors (full)"))
    outer.addWidget(details)

    btn_row = QHBoxLayout()
    save_json_btn = QPushButton("Save comparison JSON…")
    save_json_btn.clicked.connect(on_save_json_clicked)
    btn_row.addWidget(save_json_btn)
    if combined_pdf and on_open_pdf is not None:
        open_pdf_btn = QPushButton("Open PDF")
        # QPushButton.clicked emits ``checked: bool`` — do not use ``lambda p=path`` or
        # ``p`` is overwritten by that argument and becomes a bool at runtime.
        open_pdf_btn.clicked.connect(
            lambda *_args, pdf=combined_pdf: on_open_pdf(pdf)
        )
        btn_row.addWidget(open_pdf_btn)
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dialog.close)
    btn_row.addWidget(close_btn)
    btn_row.addStretch()
    outer.addLayout(btn_row)

    if not all(r.success for r in results):
        dialog.setWindowTitle(dialog.windowTitle() + " (one or more runs failed)")

    dialog.resize(min(920, 240 + n * 130), 540)
    return dialog
