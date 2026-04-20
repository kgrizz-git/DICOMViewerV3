"""
Dialog Action Handlers

Logic-bearing ``_open_*`` handlers extracted from ``DICOMViewerApp``.
Each module-level function receives the app instance as its first argument (``app``),
replacing ``self`` throughout.
"""

from __future__ import annotations

# Pyright follows TYPE_CHECKING imports and can report a false-positive cycle here:
# dialog_action_handlers -> main -> dialog_action_handlers (analysis-only).
# Runtime keeps the import inside TYPE_CHECKING, so no circular import occurs at execution.
# pyright: reportImportCycles=false

from typing import TYPE_CHECKING

from gui.dialogs.quick_window_level_dialog import QuickWindowLevelDialog

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
    from gui.dialogs.slice_sync_dialog import SliceSyncDialog

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
