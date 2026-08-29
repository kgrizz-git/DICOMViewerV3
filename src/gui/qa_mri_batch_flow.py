"""
Multi-series ACR MRI Large (pylinac) batch flow — menu entry to summary.

Mirrors the CT batch flow in ``open_acr_ct_batch_analysis`` /
``start_ct_batch_worker`` but for MRI: series selection
(``prompt_mri_batch_series_selection``) → shared MRI options
(``prompt_acr_mri_options``) → ``stamp_mri_batch_options`` (drops compare) →
``QAMRIBatchWorker`` → N-of-M progress → cancel calls ``worker.cancel()`` →
minimal non-modal summary (labels + success/fail) that keeps temp dirs alive
until destroy.

This module is the public entry called by ``dialog_actions`` so
``QAAppFacade`` does **not** grow past its grandfathered line cap. The facade
owns no MRI-batch methods.

Inputs:
    - App duck-type with ``main_window``, ``dicom_organizer``, ``file_dialog``,
      ``config_manager``, ``_file_series_coordinator.get_file_path_for_dataset``,
      ``_mri_batch_result_dialog`` slot, ``update_status``.

Outputs:
    - UI dialogs, worker thread, minimal summary dialog.

Requirements:
    - Same Qt / pydicom / qa package stack as the main application.
    - ``QAMRIBatchWorker`` + ``ACRMBatchResult`` (not compare-mode
      ``QABatchWorker`` / ``MRIBatchResult``).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressDialog,
    QVBoxLayout,
)

from gui.dialogs.acr_mri_qa_dialog import prompt_acr_mri_options
from gui.dialogs.acr_mri_series_selection_dialog import (
    prompt_mri_batch_series_selection,
    stamp_mri_batch_options,
)
from qa.analysis_types import ACRMBatchResult
from qa.worker import QAMRIBatchWorker
from version import __version__ as APP_VERSION


def open_acr_mri_batch_analysis(app: Any) -> None:
    """
    Open the multi-series ACR MRI Large (pylinac) batch flow (P4-M3).

    Prompts a checkbox-list MR series selection (plus "Add folder..."),
    collects one shared MRI options set applied to every selected series,
    then runs ``QAMRIBatchWorker`` and shows a minimal batch summary. No
    per-series modal -- all failures are collected into the final dialog.

    ``compare_request`` from ``prompt_acr_mri_options`` is **ignored** (OQ-7:
    no compare in batch). The single-run MRI options dialog still offers
    compare; the batch path drops it.
    """
    selection = prompt_mri_batch_series_selection(
        app.main_window,
        app.dicom_organizer,
        app._file_series_coordinator.get_file_path_for_dataset,
        open_folder=lambda: app.file_dialog.open_folder(app.main_window),
    )
    if selection is None:
        return
    requests, labels = selection

    cm = app.config_manager
    lc_method_default = cm.get_acr_mri_low_contrast_method()
    lc_vis_default = cm.get_acr_mri_low_contrast_visibility_threshold()
    lc_sanity_default = cm.get_acr_mri_low_contrast_visibility_sanity_multiplier()
    vanilla_def = cm.get_acr_qa_vanilla_pylinac()
    embed_def = cm.get_acr_qa_embed_module_images_in_xlsx()
    mri_opts = prompt_acr_mri_options(
        app.main_window,
        low_contrast_method=lc_method_default,
        low_contrast_visibility_threshold=lc_vis_default,
        low_contrast_visibility_sanity_multiplier=lc_sanity_default,
        vanilla_pylinac_default=vanilla_def,
        embed_module_images_default=embed_def,
    )
    if mri_opts is None:
        return
    (echo_number, check_uid, origin_slice, mri_scan_tol, lc_method, lc_vis,
     lc_sanity, _compare_request, mri_vanilla, mri_embed) = mri_opts
    cm.set_acr_qa_vanilla_pylinac(mri_vanilla)
    cm.set_acr_qa_embed_module_images_in_xlsx(mri_embed)
    cm.set_acr_mri_low_contrast_method(lc_method)
    cm.set_acr_mri_low_contrast_visibility_threshold(lc_vis)
    cm.set_acr_mri_low_contrast_visibility_sanity_multiplier(lc_sanity)

    stamped = stamp_mri_batch_options(
        requests,
        echo_number=echo_number,
        check_uid=check_uid,
        origin_slice=origin_slice,
        scan_extent_tolerance_mm=float(mri_scan_tol),
        vanilla_pylinac=mri_vanilla,
        embed_module_images_in_xlsx=mri_embed,
        low_contrast_method=lc_method,
        low_contrast_visibility_threshold=float(lc_vis),
        low_contrast_visibility_sanity_multiplier=float(lc_sanity),
    )

    _start_acr_mri_series_batch_worker(app, stamped, labels)


def _start_acr_mri_series_batch_worker(
    app: Any,
    requests: list[Any],
    labels: list[str],
) -> None:
    """
    Launch a ``QAMRIBatchWorker`` for a multi-series ACR MRI Large batch.

    Shows an N-of-M progress dialog updated on ``series_completed``, then a
    minimal batch summary on ``batch_result_ready``. Cancel calls
    ``worker.cancel()`` (best-effort: in-flight series finishes; completed
    series are kept). Temp dirs are owned by the worker and cleaned up when
    the summary dialog is destroyed (or immediately when the batch is empty).
    """
    total = len(requests)
    progress = QProgressDialog(
        f"Running ACR MRI batch analysis (0 of {total})...",
        "Cancel",
        0,
        total,
        app.main_window,
    )
    progress.setWindowTitle("ACR MRI Phantom Analysis — Batch")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setWindowFlags(progress.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    progress.show()
    progress.activateWindow()
    progress.raise_()

    worker = QAMRIBatchWorker(requests, labels, app_version=APP_VERSION)
    app._qa_mri_batch_worker = worker

    def on_cancel() -> None:
        worker.cancel()
        app.main_window.update_status(
            "ACR MRI batch analysis cancelled (best-effort); finishing in-flight series."
        )

    progress.canceled.connect(on_cancel)

    def on_series_completed(done: int, total_: int, _result: Any) -> None:
        progress.setValue(done)
        progress.setLabelText(f"Running ACR MRI batch analysis ({done} of {total_})...")

    def on_batch_result(batch: ACRMBatchResult) -> None:
        progress.close()
        _show_acr_mri_batch_summary(app, worker, batch)

    worker.series_completed.connect(on_series_completed)
    worker.batch_result_ready.connect(on_batch_result)
    worker.finished.connect(progress.close)
    worker.start()


def _cleanup_batch_temp_dirs(worker: QAMRIBatchWorker) -> None:
    """Release worker-owned image and module-image temp dirs (idempotent-safe)."""
    worker.image_temp_dir.cleanup()
    module_dir = getattr(worker, "module_images_temp_dir", None)
    if module_dir is not None:
        module_dir.cleanup()


def _show_acr_mri_batch_summary(
    app: Any,
    worker: QAMRIBatchWorker,
    batch: ACRMBatchResult,
) -> None:
    """
    Show a minimal non-modal batch summary (one label + success/fail per
    series). Keeps the worker's ``image_temp_dir`` (and
    ``module_images_temp_dir`` when embed is on) alive for the dialog's life;
    cleaned up in ``on_destroyed``. An empty batch (all cancelled before any
    series ran) cleans up immediately and shows nothing.
    """
    if not batch.run_results:
        _cleanup_batch_temp_dirs(worker)
        return

    if app._mri_batch_result_dialog is not None:
        app._mri_batch_result_dialog.close()
        app._mri_batch_result_dialog = None

    def on_dialog_destroyed(*_args: Any) -> None:
        app._mri_batch_result_dialog = None
        _cleanup_batch_temp_dirs(worker)

    dialog = _create_mri_batch_result_dialog(
        app.main_window,
        batch,
        on_destroyed=on_dialog_destroyed,
    )
    app._mri_batch_result_dialog = dialog
    dialog.activateWindow()
    dialog.raise_()
    dialog.show()


def _create_mri_batch_result_dialog(
    parent: Any,
    batch: ACRMBatchResult,
    *,
    on_destroyed: Any,
) -> QDialog:
    """
    Build a minimal non-modal MRI batch summary dialog: one row per series
    with the display label and success/fail status. Export buttons land in
    P4-M4; this scaffold keeps temp dirs alive until ``on_destroyed``.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("ACR MRI Phantom Analysis — Batch Summary")
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    dialog.setMinimumWidth(480)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.destroyed.connect(on_destroyed)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("ACR MRI batch complete. One row per series:"))

    for label, result in zip(batch.run_labels, batch.run_results, strict=True):
        status = "Success" if result.success else "Failed"
        row = QLabel(f"  {label}: {status}")
        layout.addWidget(row)

    layout.addStretch()
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    return dialog
