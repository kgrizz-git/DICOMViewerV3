"""
Application signal wiring for DICOM Viewer V3.

This module connects all Qt signals for DICOMViewerApp. It receives the app instance
and wires layout, file, dialog, undo/redo, cine, view, customization, subwindow,
and focused-subwindow signals. Handlers remain methods on DICOMViewerApp; only
the connection code lives here.

Call order matters: layout and file signals are wired before dialogs so that
subwindow and focus state is ready when dialogs are first triggered. Per-subwindow
and focused-subwindow signals are wired last.

Inputs:
    - app: DICOMViewerApp instance (or any object with the expected widgets and methods).

Outputs:
    - None; side effect is that signals are connected.

Requirements:
    - Called after all app managers, widgets, and controllers are created.
"""

def wire_all_signals(app) -> None:
    """
    Connect all application-level Qt signals for the given app.
    Preserves the order required for correct subwindow and dialog behavior.
    """
    _wire_layout_signals(app)
    _wire_file_signals(app)
    _wire_dialog_signals(app)
    _wire_undo_redo_and_annotation_signals(app)
    _wire_cine_signals(app)
    _wire_view_signals(app)
    _wire_customization_signals(app)
    _wire_subwindow_signals(app)
    _wire_focused_subwindow_signals(app)


def _wire_layout_signals(app: "DICOMViewerApp") -> None:
    """Wire multi-window layout and main-window layout-change signals."""
    app.multi_window_layout.focused_subwindow_changed.connect(app._on_focused_subwindow_changed)
    app.multi_window_layout.layout_changed.connect(app._on_layout_changed)
    app.main_window.layout_changed.connect(app._on_main_window_layout_changed)


def _wire_file_signals(app) -> None:
    """Wire file open/close and application-quit signals."""
    app.main_window.open_file_requested.connect(app._open_files)
    app.main_window.open_folder_requested.connect(app._open_folder)
    app.main_window.open_recent_file_requested.connect(app._open_recent_file)
    app.main_window.open_files_from_paths_requested.connect(app._open_files_from_paths)
    app.main_window.close_requested.connect(app._close_files)
    app.app.aboutToQuit.connect(app._on_app_about_to_quit)


def _wire_dialog_signals(app: "DICOMViewerApp") -> None:
    """Wire signals that open shared dialogs and panels (settings, overlays, export, etc.)."""
    app.main_window.settings_requested.connect(app._open_settings)
    app.main_window.overlay_settings_requested.connect(app._open_overlay_settings)
    app.main_window.tag_viewer_requested.connect(app._open_tag_viewer)
    app.main_window.overlay_config_requested.connect(app._open_overlay_config)
    app.main_window.annotation_options_requested.connect(app._open_annotation_options)
    app.main_window.quick_start_guide_requested.connect(app._open_quick_start_guide)
    app.main_window.fusion_technical_doc_requested.connect(app._open_fusion_technical_doc)
    app.main_window.tag_export_requested.connect(app._open_tag_export)
    app.main_window.histogram_requested.connect(app.dialog_coordinator.open_histogram)
    app.main_window.export_roi_statistics_requested.connect(app._open_export_roi_statistics)
    app.main_window.export_requested.connect(app._open_export)
    app.main_window.export_screenshots_requested.connect(app._open_export_screenshots)
    app.main_window.about_this_file_requested.connect(app._open_about_this_file)
    # Series navigator close actions
    app.series_navigator.close_series_requested.connect(app._close_series)
    app.series_navigator.close_study_requested.connect(app._close_study)


def _wire_undo_redo_and_annotation_signals(app) -> None:
    """Wire undo/redo (tag edits and annotations) and annotation copy/paste signals."""
    app.main_window.undo_tag_edit_requested.connect(app._on_undo_requested)
    app.main_window.redo_tag_edit_requested.connect(app._on_redo_requested)
    app.main_window.copy_annotation_requested.connect(app._copy_annotations)
    app.main_window.paste_annotation_requested.connect(app._paste_annotations)
    app.metadata_panel.tag_edited.connect(app._on_tag_edited)


def _wire_cine_signals(app) -> None:
    """Wire cine controls widget and cine player signals."""
    app.cine_controls_widget.play_requested.connect(app._on_cine_play)
    app.cine_controls_widget.pause_requested.connect(app._on_cine_pause)
    app.cine_controls_widget.stop_requested.connect(app._on_cine_stop)
    app.cine_controls_widget.speed_changed.connect(app._on_cine_speed_changed)
    app.cine_controls_widget.loop_toggled.connect(app._on_cine_loop_toggled)
    app.cine_controls_widget.frame_position_changed.connect(app._on_frame_slider_changed)
    app.cine_controls_widget.loop_start_set.connect(app._on_cine_loop_start_set)
    app.cine_controls_widget.loop_end_set.connect(app._on_cine_loop_end_set)
    app.cine_controls_widget.loop_bounds_cleared.connect(app._on_cine_loop_bounds_cleared)
    app.cine_player.frame_advance_requested.connect(app._on_cine_frame_advance)
    app.cine_player.playback_state_changed.connect(app._on_cine_playback_state_changed)


def _wire_view_signals(app: "DICOMViewerApp") -> None:
    """Wire privacy, image-smoothing, and theme-change view signals."""
    app.main_window.privacy_view_toggled.connect(app._on_privacy_view_toggled)
    app.main_window.smooth_when_zoomed_toggled.connect(app._on_smooth_when_zoomed_toggled)
    app.main_window.theme_changed.connect(app.fusion_controls_widget.update_status_text_colors)


def _wire_customization_signals(app) -> None:
    """Wire import/export signals for app customizations and tag-export presets."""
    app.main_window.export_customizations_requested.connect(app._on_export_customizations)
    app.main_window.import_customizations_requested.connect(app._on_import_customizations)
    app.main_window.export_tag_presets_requested.connect(app._on_export_tag_presets)
    app.main_window.import_tag_presets_requested.connect(app._on_import_tag_presets)


def _wire_subwindow_signals(app: "DICOMViewerApp") -> None:
    """Connect signals that apply to all subwindows. Delegates to subwindow lifecycle controller."""
    app._subwindow_lifecycle_controller.connect_subwindow_signals()


def _wire_focused_subwindow_signals(app) -> None:
    """Connect signals for the currently focused subwindow. Delegates to subwindow lifecycle controller."""
    app._subwindow_lifecycle_controller.connect_focused_subwindow_signals()
