"""
Multi-series ACR MRI Large (pylinac) batch flow — menu entry to summary.

Mirrors the CT batch flow in ``open_acr_ct_batch_analysis`` /
``start_ct_batch_worker`` but for MRI: series selection
(``prompt_mri_batch_series_selection``) → shared MRI options
(``prompt_acr_mri_options`` with compare hidden, OQ-7) →
``stamp_mri_batch_options`` → slice/folder preflight (same helpers as
single-run MRI, one Yes/No confirm) → ``QAMRIBatchWorker`` → N-of-M
progress → cancel calls ``worker.cancel()`` → minimal non-modal summary
(labels + success/fail) that keeps temp dirs alive until destroy.

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

from dataclasses import replace
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from gui.dialogs.acr_mri_qa_dialog import prompt_acr_mri_options
from gui.dialogs.acr_mri_series_selection_dialog import (
    prompt_mri_batch_series_selection,
    stamp_mri_batch_options,
)
from gui.dialogs.mri_batch_result_dialog import create_mri_batch_result_dialog
from gui.qa_mri_batch_export import (
    save_mri_batch_csv,
    save_mri_batch_json,
    save_mri_batch_xlsx,
)
from qa.analysis_types import ACRMBatchResult, QARequest
from qa.preflight import collect_slice_position_warnings
from qa.worker import QAMRIBatchWorker
from version import __version__ as APP_VERSION

# Same folder-input text as ``QAAppFacade.build_preflight_warnings``.
_FOLDER_GEOMETRY_WARNING = (
    "Slice geometry was not verified from DICOM tags (folder input). "
    "Ensure axial stack order matches what pylinac expects."
)


def open_acr_mri_batch_analysis(app: Any) -> None:
    """
    Open the multi-series ACR MRI Large (pylinac) batch flow (P4-M3).

    Prompts a checkbox-list MR series selection (plus "Add folder..."),
    collects one shared MRI options set applied to every selected series,
    then runs ``QAMRIBatchWorker`` and shows a minimal batch summary. No
    per-series modal -- all failures are collected into the final dialog.

    Compare is hidden in the batch options dialog (OQ-7: no compare in
    batch). After stamp, the same slice-geometry / folder preflight as
    single-run MRI runs once for the whole selection; cancel returns
    without starting the worker.
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
        allow_compare=False,
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
    combined, per_request = collect_mri_batch_preflight_warnings(
        app.dicom_organizer, stamped, labels
    )
    if not user_confirms_mri_batch_preflight(app.main_window, combined):
        return
    stamped = [
        replace(req, preflight_warnings=list(warns))
        for req, warns in zip(stamped, per_request, strict=True)
    ]

    _start_acr_mri_series_batch_worker(app, stamped, labels)


def _lookup_series_datasets(organizer: Any, request: QARequest) -> list[Any]:
    """Return in-memory datasets for a loaded series, or ``[]`` if unknown."""
    studies = getattr(organizer, "studies", None)
    if not isinstance(studies, dict):
        return []
    series_map = studies.get(request.study_uid, {})
    if not isinstance(series_map, dict):
        return []
    datasets = series_map.get(request.series_uid, [])
    if not isinstance(datasets, list):
        return []
    return list(datasets)


def collect_mri_batch_preflight_warnings(
    organizer: Any,
    requests: list[QARequest],
    labels: list[str],
) -> tuple[list[str], list[list[str]]]:
    """
    Build per-request preflight strings plus a flattened confirm-dialog list.

    Folder rows get the same unverified-geometry text as single-run MRI.
    Loaded series run ``collect_slice_position_warnings`` on organizer
    datasets looked up by ``(study_uid, series_uid)``. The confirm dialog
    prefixes each line with the series label; stored ``preflight_warnings``
    stay unprefixed because the batch summary/exports already scope by label.
    """
    per_request: list[list[str]] = []
    combined: list[str] = []
    for req, label in zip(requests, labels, strict=True):
        raw: list[str] = []
        if req.folder_path:
            raw.append(_FOLDER_GEOMETRY_WARNING)
        else:
            datasets = _lookup_series_datasets(organizer, req)
            if datasets:
                raw.extend(collect_slice_position_warnings(datasets))
        per_request.append(list(raw))
        combined.extend(f"{label}: {warning}" for warning in raw)
    return combined, per_request


def user_confirms_mri_batch_preflight(parent: Any, warnings: list[str]) -> bool:
    """
    If warnings exist, show them and return True only if the user continues.

    Matches ``QAAppFacade.user_confirms_preflight`` (Yes/No, default No).
    """
    if not warnings:
        return True
    text = "Preflight warnings:\n\n- " + "\n- ".join(warnings)
    text += "\n\nContinue with analysis?"
    box = QMessageBox(parent)
    box.setWindowTitle("QA preflight")
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.setWindowFlags(box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    box.activateWindow()
    box.raise_()
    return box.exec() == int(QMessageBox.StandardButton.Yes)


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

    previous = app._mri_batch_result_dialog
    if previous is not None:
        previous.close()

    dialog = create_mri_batch_result_dialog(
        app.main_window,
        batch,
        on_save_xlsx_clicked=lambda: save_mri_batch_xlsx(app, batch),
        on_save_json_clicked=lambda: save_mri_batch_json(app, batch),
        on_save_csv_clicked=lambda: save_mri_batch_csv(app, batch),
    )

    def on_dialog_destroyed(*_args: Any) -> None:
        # WA_DeleteOnClose can defer this callback until after a replacement
        # dialog is already in the slot; only clear when it still points here.
        if app._mri_batch_result_dialog is dialog:
            app._mri_batch_result_dialog = None
        _cleanup_batch_temp_dirs(worker)

    dialog.destroyed.connect(on_dialog_destroyed)
    app._mri_batch_result_dialog = dialog
    dialog.activateWindow()
    dialog.raise_()
    dialog.show()
