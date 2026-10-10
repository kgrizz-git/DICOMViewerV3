"""File -> Save MPR as DICOM flow for ``MprController``.

Prompts for an output folder and export options, then writes one DICOM file
per plane of the focused pane's MPR stack with progress and cancel. Pure UI
orchestration over ``core.mpr_dicom_export``; it reads the focused pane's
display adapter and never touches the session/view registry.
"""

from __future__ import annotations

import copy
import os
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMessageBox,
    QProgressDialog,
)

from core.mpr_builder import MprResult
from core.mpr_dicom_export import (
    MprDicomExportError,
    MprDicomExportOptions,
    write_mpr_series,
)

_TITLE_SAVE_MPR_DICOM = "Save MPR as DICOM"


def prompt_save_mpr_as_dicom(controller: Any) -> None:
    """
    Save the focused subwindow's MPR stack as a new DICOM series (File menu).

    Requires a completed ``MprResult`` on the focused pane. Prompts for an
    output root folder (mirrors export path memory), then a small options
    dialog, then writes one file per plane with progress / cancel.
    """
    from gui.dialogs.mpr_dicom_save_dialog import MprDicomSaveDialog

    app = controller._app
    mw = app.main_window
    ctx = _save_mpr_resolve_export_context(controller, mw)
    if ctx is None:
        return
    data, result, template = ctx

    output_root = _save_mpr_pick_output_root(controller, mw)
    if output_root is None:
        return

    orient = str(data.get("mpr_orientation", "") or "")
    opt_dialog = MprDicomSaveDialog(parent=mw, orientation_label=orient)
    if opt_dialog.exec() != QDialog.DialogCode.Accepted:
        return
    opts: MprDicomExportOptions = opt_dialog.build_options(orient)
    _save_mpr_write_series(mw, output_root, result, template, opts)

def _save_mpr_resolve_export_context(controller: Any, mw
) -> tuple[dict[str, Any], Any, Any] | None:
    """Validate focused MPR pane and resolve export template dataset."""
    app = controller._app
    idx = app.get_focused_subwindow_index()
    data = app.subwindow_data.get(idx, {})
    if not data.get("is_mpr"):
        QMessageBox.information(
            mw,
            _TITLE_SAVE_MPR_DICOM,
            "The focused window is not an MPR view.\n"
            "Create an MPR in a pane and focus it, then try again.",
        )
        return None
    result = data.get("mpr_result")
    if result is None or getattr(result, "n_slices", 0) < 1:
        QMessageBox.information(
            mw,
            _TITLE_SAVE_MPR_DICOM,
            "No MPR slice stack is available to export yet.",
        )
        return None

    template = data.get("mpr_source_dataset")
    if template is None:
        try:
            template = result.source_volume.source_datasets[0]
        except Exception:
            template = None
    if template is None:
        QMessageBox.warning(
            mw,
            _TITLE_SAVE_MPR_DICOM,
            "Could not resolve a source DICOM dataset for metadata export.",
        )
        return None
    return data, result, template

def _save_mpr_pick_output_root(controller: Any, mw) -> str | None:
    """Prompt for an export folder and remember it in config."""
    app = controller._app
    start = app.config_manager.get_last_export_path() or ""
    if not start or not os.path.exists(start):
        start = os.getcwd()
    folder_dialog = QFileDialog(mw)
    folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
    folder_dialog.setWindowTitle("Select folder for MPR DICOM export")
    folder_dialog.setDirectory(start)
    folder_dialog.setWindowFlags(
        folder_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
    )
    folder_dialog.activateWindow()
    folder_dialog.raise_()
    if not folder_dialog.exec():
        return None
    selected = folder_dialog.selectedFiles()
    if not selected:
        return None
    output_root = selected[0]
    app.config_manager.set_last_export_path(output_root)
    return output_root

def _save_mpr_write_series(
    mw,
    output_root: str,
    result: MprResult,
    template: Any,
    opts: MprDicomExportOptions,
) -> None:
    """Write MPR DICOM files with progress UI and success/error messaging."""
    progress = QProgressDialog(
        "Writing MPR DICOM files…",
        "Cancel",
        0,
        result.n_slices,
        mw,
    )
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    def _progress_cb(cur: int, total: int, msg: str) -> bool:
        progress.setMaximum(max(total, 1))
        progress.setValue(min(cur, total))
        progress.setLabelText(msg)
        QApplication.processEvents()
        return not progress.wasCanceled()

    template_copy = copy.deepcopy(template)
    try:
        paths = write_mpr_series(
            output_root,
            result,
            template_copy,
            opts,
            progress_callback=_progress_cb,
        )
    except MprDicomExportError as exc:
        progress.close()
        if "cancelled" in str(exc).lower():
            return
        QMessageBox.critical(
            mw,
            _TITLE_SAVE_MPR_DICOM,
            "Export failed. Details were withheld to protect private data.",
        )
        return

    progress.close()
    QMessageBox.information(
        mw,
        _TITLE_SAVE_MPR_DICOM,
        f"Successfully wrote {len(paths)} file(s).\n\n"
        f"First file:\n{paths[0]}",
    )
