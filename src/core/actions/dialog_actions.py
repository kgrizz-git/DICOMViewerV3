"""
Dialog, menu, and file-open entrypoints moved from ``DICOMViewerApp``.

Each public function takes the application instance as ``app`` (replacing ``self``
in the original methods). Heavy cine export and study/SR flows live here so
``main.py`` stays a thinner composition root.

Inputs:
    ``app``: running ``DICOMViewerApp`` instance.

Outputs:
    Side effects (dialogs, QMessageBox, file I/O, threads).

Requirements:
    PySide6, pydicom datasets where applicable; must not ``import main`` at runtime
    (use ``TYPE_CHECKING`` only) to avoid circular imports.
"""

from __future__ import annotations

# pyright: reportImportCycles=false

import os
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QProgressDialog
from PySide6.QtCore import QEventLoop, Qt

from core.cine_video_export import (
    build_cine_export_frame_indices,
    cleanup_temp_frame_dir,
    describe_focused_cine_export_blocker,
    rasterize_cine_export_frame,
    safe_remove_partial_output,
)
from core.sr_sop_classes import is_structured_report_dataset
from gui.dialogs.cine_export_dialog import CineExportDialog
from gui.dialogs.cine_export_encode_thread import CineVideoEncodeThread
from gui.dialogs.quick_window_level_dialog import QuickWindowLevelDialog
from gui.dialogs.slice_sync_dialog import SliceSyncDialog
from gui.dialogs.study_index_search_dialog import StudyIndexSearchDialog

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def open_about_this_file(app: "DICOMViewerApp") -> None:
    """Handle About This File dialog request."""
    focused_idx = app.focused_subwindow_index
    current_dataset = None
    file_path = None

    if focused_idx in app.subwindow_data:
        current_dataset = app.subwindow_data[focused_idx].get('current_dataset')
        if current_dataset:
            file_path = app._get_file_path_for_dataset(
                current_dataset,
                app.subwindow_data[focused_idx].get('current_study_uid', ''),
                app.subwindow_data[focused_idx].get('current_series_uid', ''),
                app.subwindow_data[focused_idx].get('current_slice_index', 0),
            )

    app.dialog_coordinator.open_about_this_file(current_dataset, file_path)


def open_slice_sync_dialog(app: "DICOMViewerApp") -> None:
    """Open the Manage Sync Groups dialog."""
    current_groups = app.config_manager.get_slice_sync_groups()
    dlg = SliceSyncDialog(current_groups, parent=app.main_window)
    dlg.groups_changed.connect(app._on_slice_sync_groups_changed)
    dlg.exec()


def open_overlay_config(app: "DICOMViewerApp") -> None:
    """Handle overlay configuration dialog request."""
    current_modality = None
    if app.current_dataset is not None:
        modality = getattr(app.current_dataset, 'Modality', None)
        if modality:
            modality_str = str(modality).strip()
            # Valid modalities list (must match overlay_config_dialog.py, alphabetical order, default first)
            valid_modalities = [
                "default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA",
            ]
            if modality_str in valid_modalities:
                current_modality = modality_str
            # If modality is not in valid list, current_modality remains None (defaults to "default")

    app.dialog_coordinator.open_overlay_config(current_modality=current_modality)


def open_quick_window_level(app: "DICOMViewerApp") -> None:
    """Open Quick Window/Level dialog; apply entered center/width via view_state_manager."""
    if not app.view_state_manager:
        return
    initial_center = app.view_state_manager.current_window_center
    initial_width = app.view_state_manager.current_window_width
    center_range = app.window_level_controls.center_range
    width_range = app.window_level_controls.width_range
    unit = getattr(app.view_state_manager, "rescale_type", None) or None
    apply_callback = app.view_state_manager.handle_window_changed
    dlg = QuickWindowLevelDialog(
        parent=app.main_window,
        initial_center=initial_center,
        initial_width=initial_width,
        center_range=center_range,
        width_range=width_range,
        apply_callback=apply_callback,
        unit=unit,
    )
    dlg.raise_()
    dlg.activateWindow()
    dlg.exec()


def open_export(app: "DICOMViewerApp") -> None:
    """Handle Export dialog request. Resolution options are in the dialog."""
    window_center, window_width = app.window_level_controls.get_window_level()
    use_rescaled_values = app.view_state_manager.use_rescaled_values
    projection_enabled = app.slice_display_manager.projection_enabled
    projection_type = app.slice_display_manager.projection_type
    projection_slice_count = app.slice_display_manager.projection_slice_count
    focused_subwindow_index = app.get_focused_subwindow_index()
    # Aggregate annotations from all subwindows for export
    subwindow_annotation_managers = []
    for idx in sorted(app.subwindow_managers.keys()):
        m = app.subwindow_managers[idx]
        subwindow_annotation_managers.append({
            'roi_manager': m.get('roi_manager'),
            'measurement_tool': m.get('measurement_tool'),
            'text_annotation_tool': m.get('text_annotation_tool'),
            'arrow_annotation_tool': m.get('arrow_annotation_tool'),
        })
    app.dialog_coordinator.open_export(
        current_window_center=window_center,
        current_window_width=window_width,
        focused_subwindow_index=focused_subwindow_index,
        use_rescaled_values=use_rescaled_values,
        roi_manager=app.roi_manager,
        overlay_manager=app.overlay_manager,
        measurement_tool=app.measurement_tool,
        text_annotation_tool=getattr(app, 'text_annotation_tool', None),
        arrow_annotation_tool=getattr(app, 'arrow_annotation_tool', None),
        projection_enabled=projection_enabled,
        projection_type=projection_type,
        projection_slice_count=projection_slice_count,
        subwindow_annotation_managers=subwindow_annotation_managers,
    )


def open_settings(app: "DICOMViewerApp") -> None:
    """Handle settings dialog request."""
    app.dialog_coordinator.open_settings()


def open_overlay_settings(app: "DICOMViewerApp") -> None:
    """Handle Overlay Settings dialog request."""
    app.dialog_coordinator.open_overlay_settings()


def open_tag_viewer(app: "DICOMViewerApp") -> None:
    """Handle tag viewer dialog request."""
    app.dialog_coordinator.open_tag_viewer(
        app.current_dataset, privacy_mode=app.privacy_view_enabled
    )


def open_annotation_options(app: "DICOMViewerApp") -> None:
    """Handle annotation options dialog request."""
    app.dialog_coordinator.open_annotation_options()


def open_quick_start_guide(app: "DICOMViewerApp") -> None:
    """Handle Quick Start Guide dialog request."""
    app.dialog_coordinator.open_quick_start_guide()


def open_user_documentation_in_browser(app: "DICOMViewerApp") -> None:
    """Open the user guide hub (Markdown on GitHub) in the system browser."""
    app.dialog_coordinator.open_user_documentation_in_browser()


def open_fusion_technical_doc(app: "DICOMViewerApp") -> None:
    """Handle Fusion Technical Documentation dialog request."""
    app.dialog_coordinator.open_fusion_technical_doc()


def open_tag_export(app: "DICOMViewerApp") -> None:
    """Handle Tag Export dialog request."""
    app.dialog_coordinator.open_tag_export()


def open_files(app: "DICOMViewerApp") -> None:
    """Handle open files request."""
    app._file_series_coordinator.open_files()


def open_folder(app: "DICOMViewerApp") -> None:
    """Handle open folder request."""
    app._file_series_coordinator.open_folder()


def open_recent_file(app: "DICOMViewerApp", file_path: str) -> None:
    """Handle open recent file/folder request."""
    app._file_series_coordinator.open_recent_file(file_path)


def open_files_from_paths(app: "DICOMViewerApp", paths: list[str]) -> None:
    """Handle open files/folders from drag-and-drop."""
    app._file_series_coordinator.open_files_from_paths(paths)


def open_study_index_search(app: "DICOMViewerApp") -> None:
    """Open the local study index browser (File menu and Tools menu)."""
    dlg = StudyIndexSearchDialog(
        app.study_index_service,
        app.config_manager,
        open_paths_callback=lambda paths: app.main_window.open_files_from_paths_requested.emit(
            paths
        ),
        parent=app.main_window,
    )
    dlg.exec()


def open_structured_report_browser(
    app: "DICOMViewerApp", subwindow_idx: Optional[int] = None
) -> None:
    """
    Tools → Structured Report… — open the SR document browser for the focused pane's
    current dataset when it is a Structured Report (SR storage class or Modality SR).
    """
    idx = (
        subwindow_idx
        if subwindow_idx is not None
        else app.get_focused_subwindow_index()
    )
    if idx < 0:
        return
    data = app.subwindow_data.get(idx, {})
    if data.get("is_mpr"):
        QMessageBox.information(
            app.main_window,
            "Structured Report",
            "MPR views do not carry the SR document. Switch to a 2D SR instance.",
        )
        return
    ds = app._get_subwindow_dataset(idx)
    if ds is None:
        QMessageBox.information(
            app.main_window,
            "Structured Report",
            "No DICOM file is loaded in this window.",
        )
        return
    if not is_structured_report_dataset(ds):
        QMessageBox.information(
            app.main_window,
            "Structured Report",
            "The current file is not a Structured Report (SR storage class or Modality SR).",
        )
        return
    app.dialog_coordinator.open_structured_report_browser(
        ds,
        get_privacy_enabled=app.config_manager.get_privacy_view,
        open_tag_viewer_callback=lambda d: app.dialog_coordinator.open_tag_viewer(
            d, privacy_mode=app.config_manager.get_privacy_view()
        ),
    )


def open_export_cine_video(app: "DICOMViewerApp") -> None:
    """
    File → Export Cine As… — GIF / AVI / MP4 / MPG for the focused 2D multi-frame pane.

    Renders each frame with the same PIL path as PNG export (not a viewport grab),
    writes temporary PNGs, then encodes in a ``QThread`` (imageio / FFmpeg, no
    ``shell=True``). Cancel removes partial output when possible.
    """
    blocker = describe_focused_cine_export_blocker(app)
    if blocker:
        QMessageBox.information(app.main_window, "Export Cine", blocker)
        return

    idx = app.get_focused_subwindow_index()
    data = app.subwindow_data.get(idx, {})
    study_uid = str(data.get("current_study_uid") or "")
    series_uid = str(data.get("current_series_uid") or "")
    studies = app.current_studies
    if not studies or study_uid not in studies or series_uid not in studies[study_uid]:
        QMessageBox.warning(app.main_window, "Export Cine", "Series data is not available.")
        return
    series_list = studies[study_uid][series_uid]
    total = len(series_list)
    if total < 2:
        QMessageBox.information(app.main_window, "Export Cine", "Not enough frames to export.")
        return

    fps_default = float(app.cine_player.get_effective_frame_rate())
    dlg = CineExportDialog(
        app.main_window,
        default_fps=fps_default,
        total_frames=total,
        loop_start=app.cine_player.loop_start_frame,
        loop_end=app.cine_player.loop_end_frame,
    )
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    opts = dlg.build_options()
    indices = build_cine_export_frame_indices(
        total,
        opts.loop_start_frame,
        opts.loop_end_frame,
        opts.use_cine_loop_bounds,
    )
    if not indices:
        QMessageBox.warning(app.main_window, "Export Cine", "No frames in the selected range.")
        return

    ext = "." + opts.video_format.lower()
    filters = (
        "GIF Image (*.gif);;AVI Video (*.avi);;MP4 Video (*.mp4);;MPEG Program Stream (*.mpg)"
    )
    ds0 = series_list[0]
    raw_desc = getattr(ds0, "SeriesDescription", None) or "cine_export"
    stem = str(raw_desc).strip() or "cine_export"
    for ch in '<>:"/\\|?*':
        stem = stem.replace(ch, "_")
    stem = stem[:80]
    start_dir = app.config_manager.get_last_export_path() or os.getcwd()
    if os.path.isfile(start_dir):
        start_dir = os.path.dirname(start_dir)
    if not start_dir or not os.path.isdir(start_dir):
        start_dir = os.getcwd()
    default_path = os.path.join(start_dir, stem + ext)
    outp = app._export_app_facade.prompt_save_path(
        "Save Cine Export As",
        default_path,
        filters,
    )
    if not outp:
        return
    base, old_ext = os.path.splitext(outp)
    if old_ext.lower() != ext:
        outp = base + ext
    app.config_manager.set_last_export_path(os.path.dirname(os.path.abspath(outp)))

    managers = app.subwindow_managers.get(idx, {})
    vsm = managers.get("view_state_manager")
    sdm = managers.get("slice_display_manager")
    if (
        vsm is not None
        and vsm.current_window_center is not None
        and vsm.current_window_width is not None
    ):
        wl_opt = "current"
        wc = vsm.current_window_center
        ww = vsm.current_window_width
    else:
        wl_opt = "dataset"
        wc = None
        ww = None
    use_rescaled = bool(getattr(vsm, "use_rescaled_values", False)) if vsm else False
    proj_en = bool(getattr(sdm, "projection_enabled", False)) if sdm else False
    proj_ty = str(getattr(sdm, "projection_type", "aip") or "aip") if sdm else "aip"
    proj_cnt = int(getattr(sdm, "projection_slice_count", 4) or 4) if sdm else 4

    # Match **Export Images**: aggregate annotations from all subwindows when drawing overlays.
    subwindow_annotation_managers: List[Dict[str, Any]] = []
    for si in sorted(app.subwindow_managers.keys()):
        m = app.subwindow_managers[si]
        subwindow_annotation_managers.append(
            {
                "roi_manager": m.get("roi_manager"),
                "measurement_tool": m.get("measurement_tool"),
                "text_annotation_tool": m.get("text_annotation_tool"),
                "arrow_annotation_tool": m.get("arrow_annotation_tool"),
            }
        )

    cancel_event = threading.Event()
    temp_dir = tempfile.mkdtemp(prefix="dv3_cine_")
    png_paths: List[Path] = []
    try:
        progress = QProgressDialog(
            "Rendering cine frames…",
            "Cancel",
            0,
            len(indices),
            app.main_window,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        for step, frame_idx in enumerate(indices):
            if progress.wasCanceled():
                cancel_event.set()
                break
            progress.setValue(step)
            dataset = series_list[frame_idx]
            img = rasterize_cine_export_frame(
                dataset,
                studies,
                study_uid,
                series_uid,
                frame_idx,
                total,
                wl_opt,
                wc,
                ww,
                opts.include_overlays,
                use_rescaled,
                managers.get("roi_manager"),
                managers.get("overlay_manager"),
                managers.get("measurement_tool"),
                app.config_manager,
                managers.get("text_annotation_tool"),
                managers.get("arrow_annotation_tool"),
                proj_en,
                proj_ty,
                proj_cnt,
                export_scale=opts.export_scale,
                scale_annotations_with_image=False,
                subwindow_annotation_managers=subwindow_annotation_managers,
            )
            if img is None:
                QMessageBox.critical(
                    app.main_window,
                    "Export Cine",
                    f"Failed to rasterize frame {frame_idx + 1} of {total}.",
                )
                safe_remove_partial_output(outp)
                return
            out_png = Path(temp_dir) / f"f{step:05d}.png"
            img.save(str(out_png), "PNG")
            png_paths.append(out_png)
            QApplication.processEvents()

        progress.setValue(len(indices))
        progress.close()

        if cancel_event.is_set() or not png_paths:
            safe_remove_partial_output(outp)
            return

        progress_enc = QProgressDialog(
            "Encoding video…",
            "Cancel",
            0,
            0,
            app.main_window,
        )
        progress_enc.setWindowModality(Qt.WindowModality.WindowModal)
        progress_enc.setMinimumDuration(0)
        progress_enc.canceled.connect(cancel_event.set)
        progress_enc.show()
        QApplication.processEvents()

        enc_thread = CineVideoEncodeThread(
            png_paths,
            outp,
            opts.video_format,
            opts.fps,
            cancel_event,
        )
        enc_err: List[Optional[str]] = [None]

        def _on_enc_fail(msg: str) -> None:
            enc_err[0] = msg

        def _on_enc_ok() -> None:
            if enc_err[0] is None:
                enc_err[0] = ""

        enc_loop = QEventLoop()
        enc_thread.failed.connect(_on_enc_fail)
        enc_thread.succeeded.connect(_on_enc_ok)
        enc_thread.finished.connect(enc_loop.quit)
        enc_thread.start()
        enc_loop.exec()
        progress_enc.close()
        enc_thread.wait(60_000)

        if enc_err[0] is None:
            QMessageBox.critical(
                app.main_window,
                "Export Cine",
                "Encoding did not complete.",
            )
            safe_remove_partial_output(outp)
        elif enc_err[0] == "":
            QMessageBox.information(
                app.main_window,
                "Export Cine",
                f"Successfully wrote:\n{outp}",
            )
        else:
            low = enc_err[0].lower()
            if "cancel" not in low:
                QMessageBox.critical(
                    app.main_window,
                    "Export Cine",
                    enc_err[0],
                )
            safe_remove_partial_output(outp)
    finally:
        cleanup_temp_frame_dir(temp_dir)


def open_acr_ct_phantom_analysis(app: "DICOMViewerApp") -> None:
    """Open the Stage 1 ACR CT (pylinac) analysis flow (menu / signal slot)."""
    app._qa_app_facade.open_acr_ct_phantom_analysis()


def open_acr_mri_phantom_analysis(app: "DICOMViewerApp") -> None:
    """Open the Stage 1 ACR MRI Large (pylinac) analysis flow (menu / signal slot)."""
    app._qa_app_facade.open_acr_mri_phantom_analysis()


def open_path_in_system_viewer(app: "DICOMViewerApp", path: str) -> None:
    """Open a file path with the OS default application (PDF viewer, etc.)."""
    app._qa_app_facade.open_path_in_system_viewer(path)
