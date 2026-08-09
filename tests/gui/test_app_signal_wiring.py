"""
Comprehensive unit tests for src/gui/app_signal_wiring.py.

Achieves 100% statement and branch coverage for wire_all_signals.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gui.app_signal_wiring import wire_all_signals


class DummySignal:
    """Mock Qt Signal for tracking connects and triggering connected slots."""

    def __init__(self) -> None:
        self.connected_slots = []

    def connect(self, slot) -> None:
        self.connected_slots.append(slot)

    def emit(self, *args, **kwargs) -> None:
        for slot in self.connected_slots:
            # Select the arity from the slot signature rather than catching a
            # TypeError, which could mask a real error inside the slot and call
            # it twice.
            try:
                inspect.signature(slot).bind(*args, **kwargs)
            except TypeError:
                slot()
            else:
                slot(*args, **kwargs)


@pytest.fixture
def mock_app() -> SimpleNamespace:
    """Fixture providing a mock DICOMViewerApp with all required signals and methods."""
    app = SimpleNamespace()

    # Multi-window layout signals
    app.multi_window_layout = SimpleNamespace(
        focused_subwindow_changed=DummySignal(),
        layout_changed=DummySignal(),
    )

    # Main window signals
    app.main_window = SimpleNamespace(
        layout_changed=DummySignal(),
        open_file_requested=DummySignal(),
        open_folder_requested=DummySignal(),
        open_recent_file_requested=DummySignal(),
        open_files_from_paths_requested=DummySignal(),
        close_requested=DummySignal(),
        settings_requested=DummySignal(),
        overlay_settings_requested=DummySignal(),
        tag_viewer_requested=DummySignal(),
        study_index_search_requested=DummySignal(),
        overlay_config_requested=DummySignal(),
        annotation_options_requested=DummySignal(),
        quick_start_guide_requested=DummySignal(),
        keyboard_shortcuts_requested=DummySignal(),
        _apply_wl_preset_requested=DummySignal(),
        user_documentation_requested=DummySignal(),
        fusion_technical_doc_requested=DummySignal(),
        tag_export_requested=DummySignal(),
        histogram_requested=DummySignal(),
        structured_report_browser_requested=DummySignal(),
        export_roi_statistics_requested=DummySignal(),
        acr_ct_phantom_requested=DummySignal(),
        acr_ct_batch_requested=DummySignal(),
        acr_mri_phantom_requested=DummySignal(),
        nuclear_qc_requested=DummySignal(),
        export_requested=DummySignal(),
        deep_anonymizer_export_requested=DummySignal(),
        export_screenshots_requested=DummySignal(),
        save_mpr_dicom_requested=DummySignal(),
        export_cine_video_requested=DummySignal(),
        about_this_file_requested=DummySignal(),
        create_mpr_view_requested=DummySignal(),
        create_3d_view_requested=DummySignal(),
        undo_tag_edit_requested=DummySignal(),
        redo_tag_edit_requested=DummySignal(),
        copy_annotation_requested=DummySignal(),
        cut_annotation_requested=DummySignal(),
        paste_annotation_requested=DummySignal(),
        cine_play_pause_requested=DummySignal(),
        privacy_view_toggled=DummySignal(),
        smooth_when_zoomed_toggled=DummySignal(),
        scale_markers_toggled=DummySignal(),
        direction_labels_toggled=DummySignal(),
        slice_slider_toggled=DummySignal(),
        slice_slider_placement_changed=DummySignal(),
        slice_slider_direction_changed=DummySignal(),
        scale_markers_color_changed=DummySignal(),
        direction_labels_color_changed=DummySignal(),
        show_instances_separately_toggled=DummySignal(),
        theme_changed=DummySignal(),
        slice_sync_toggled=DummySignal(),
        slice_sync_manage_requested=DummySignal(),
        slice_location_lines_toggled=DummySignal(),
        slice_location_lines_same_group_only_toggled=DummySignal(),
        slice_location_lines_focused_only_toggled=DummySignal(),
        slice_location_lines_mode_toggled=DummySignal(),
        orientation_flip_h_requested=DummySignal(),
        orientation_flip_v_requested=DummySignal(),
        orientation_rotate_cw_requested=DummySignal(),
        orientation_rotate_ccw_requested=DummySignal(),
        orientation_rotate_180_requested=DummySignal(),
        orientation_reset_requested=DummySignal(),
        toggle_overlay_requested=DummySignal(),
        export_customizations_requested=DummySignal(),
        import_customizations_requested=DummySignal(),
        export_tag_presets_requested=DummySignal(),
        import_tag_presets_requested=DummySignal(),
    )

    # App application instance
    app.app = SimpleNamespace(
        aboutToQuit=DummySignal(),
    )

    # Series navigator signals
    app.series_navigator = SimpleNamespace(
        close_series_requested=DummySignal(),
        close_study_requested=DummySignal(),
        mpr_thumbnail_clicked=DummySignal(),
        mpr_thumbnail_clear_requested=DummySignal(),
    )

    # Metadata panel signals
    app.metadata_panel = SimpleNamespace(
        tag_edited=DummySignal(),
    )

    # Cine controls widget signals
    app.cine_controls_widget = SimpleNamespace(
        play_requested=DummySignal(),
        pause_requested=DummySignal(),
        stop_requested=DummySignal(),
        speed_changed=DummySignal(),
        loop_toggled=DummySignal(),
        frame_position_changed=DummySignal(),
        loop_start_set=DummySignal(),
        loop_end_set=DummySignal(),
        loop_bounds_cleared=DummySignal(),
    )

    # Cine player signals
    app.cine_player = SimpleNamespace(
        frame_advance_requested=DummySignal(),
        playback_state_changed=DummySignal(),
    )

    # MPR Controller signals & methods
    app._mpr_controller = SimpleNamespace(
        mpr_activated=DummySignal(),
        mpr_cleared=DummySignal(),
        mpr_detached=DummySignal(),
        open_mpr_dialog=MagicMock(),
        clear_persistent_cache=MagicMock(),
    )

    # Subwindow lifecycle controller
    app._subwindow_lifecycle_controller = SimpleNamespace(
        connect_subwindow_signals=MagicMock(),
        connect_focused_subwindow_signals=MagicMock(),
    )

    # Helper objects & handlers
    app.dialog_coordinator = SimpleNamespace(
        open_histogram=MagicMock(),
    )
    app._volume_render_facade = SimpleNamespace(
        launch_3d_view=MagicMock(),
    )
    app._annotation_paste_handler = SimpleNamespace(
        copy_annotations=MagicMock(),
        cut_annotations=MagicMock(),
        paste_annotations=MagicMock(),
    )
    app.cine_app_facade = SimpleNamespace(
        on_cine_play=MagicMock(),
        on_cine_pause=MagicMock(),
        on_cine_stop=MagicMock(),
        on_cine_speed_changed=MagicMock(),
        on_cine_loop_toggled=MagicMock(),
        on_frame_slider_changed=MagicMock(),
        on_cine_loop_start_set=MagicMock(),
        on_cine_loop_end_set=MagicMock(),
        on_cine_loop_bounds_cleared=MagicMock(),
        on_cine_frame_advance=MagicMock(),
        on_cine_playback_state_changed=MagicMock(),
        on_cine_play_pause_toggle=MagicMock(),
        update_cine_player_context=MagicMock(),
    )
    app.fusion_controls_widget = SimpleNamespace(
        update_status_text_colors=MagicMock(),
    )
    app.overlay_coordinator = SimpleNamespace(
        handle_toggle_overlay=MagicMock(),
    )

    # Method stubs on app
    app._on_focused_subwindow_changed = MagicMock()
    app._on_layout_changed = MagicMock()
    app._on_main_window_layout_changed = MagicMock()
    app._open_files = MagicMock()
    app._open_folder = MagicMock()
    app._open_recent_file = MagicMock()
    app._open_files_from_paths = MagicMock()
    app._close_files = MagicMock()
    app._on_app_about_to_quit = MagicMock()
    app._open_settings = MagicMock()
    app._open_overlay_settings = MagicMock()
    app._open_tag_viewer = MagicMock()
    app._open_study_index_search = MagicMock()
    app._open_overlay_config = MagicMock()
    app._open_annotation_options = MagicMock()
    app._open_quick_start_guide = MagicMock()
    app._on_keyboard_shortcuts_requested = MagicMock()
    app._on_window_level_preset_selected = MagicMock()
    app._open_user_documentation_in_browser = MagicMock()
    app._open_fusion_technical_doc = MagicMock()
    app._open_tag_export = MagicMock()
    app._open_structured_report_browser = MagicMock()
    app._open_export_roi_statistics = MagicMock()
    app._open_acr_ct_phantom_analysis = MagicMock()
    app._open_acr_ct_batch_analysis = MagicMock()
    app._open_acr_mri_phantom_analysis = MagicMock()
    app._open_nuclear_qc_analysis = MagicMock()
    app._open_export = MagicMock()
    app._open_deep_anonymizer_export = MagicMock()
    app._open_export_screenshots = MagicMock()
    app._on_save_mpr_as_dicom = MagicMock()
    app._on_export_cine_video = MagicMock()
    app._open_about_this_file = MagicMock()
    app._close_series = MagicMock()
    app._close_study = MagicMock()
    app._on_mpr_thumbnail_clicked = MagicMock()
    app._on_mpr_clear_from_navigator_thumbnail = MagicMock()
    app._on_undo_requested = MagicMock()
    app._on_redo_requested = MagicMock()
    app._on_tag_edited = MagicMock()
    app._on_privacy_view_toggled = MagicMock()
    app._on_smooth_when_zoomed_toggled = MagicMock()
    app._on_scale_markers_toggled = MagicMock()
    app._on_direction_labels_toggled = MagicMock()
    app._on_slice_slider_toggled = MagicMock()
    app._on_slice_slider_placement_changed = MagicMock()
    app._on_slice_slider_direction_changed = MagicMock()
    app._on_scale_markers_color_changed = MagicMock()
    app._on_direction_labels_color_changed = MagicMock()
    app._on_show_instances_separately_toggled = MagicMock()
    app._on_slice_sync_toggled = MagicMock()
    app._open_slice_sync_dialog = MagicMock()
    app._on_slice_location_lines_toggled = MagicMock()
    app._on_slice_location_lines_same_group_only_toggled = MagicMock()
    app._on_slice_location_lines_focused_only_toggled = MagicMock()
    app._on_slice_location_lines_mode_toggled = MagicMock()
    app._on_orientation_flip_h = MagicMock()
    app._on_orientation_flip_v = MagicMock()
    app._on_orientation_rotate_cw = MagicMock()
    app._on_orientation_rotate_ccw = MagicMock()
    app._on_orientation_rotate_180 = MagicMock()
    app._on_orientation_reset = MagicMock()
    app._on_export_customizations = MagicMock()
    app._on_import_customizations = MagicMock()
    app._on_export_tag_presets = MagicMock()
    app._on_import_tag_presets = MagicMock()
    app._update_mpr_navigator_thumbnail = MagicMock()
    app._clear_mpr_navigator_thumbnail = MagicMock()
    app._on_mpr_detached = MagicMock()
    app.get_focused_subwindow_index = MagicMock(return_value=1)

    return app


def test_wire_all_signals_connects_all(mock_app: SimpleNamespace) -> None:
    """Test wire_all_signals connects all signals and delegates subwindow signal wiring."""
    with patch(
        "gui.app_signal_wiring.apply_theme_viewer_background_all"
    ) as mock_theme_bg:
        wire_all_signals(mock_app)

        # Verify subwindow signal wiring calls
        mock_app._subwindow_lifecycle_controller.connect_subwindow_signals.assert_called_once()
        mock_app._subwindow_lifecycle_controller.connect_focused_subwindow_signals.assert_called_once()

        # Test lambda in create_mpr_view_requested
        mock_app.main_window.create_mpr_view_requested.emit()
        mock_app._mpr_controller.open_mpr_dialog.assert_called_once_with(1)

        # Test lambda in theme_changed
        mock_app.main_window.theme_changed.emit("dark")
        mock_theme_bg.assert_called_once_with(mock_app)

        # Test lambdas in mpr_activated, mpr_cleared, mpr_detached
        mock_app._mpr_controller.mpr_activated.emit(0)
        mock_app._mpr_controller.mpr_cleared.emit(0)
        mock_app._mpr_controller.mpr_detached.emit(0)

        assert mock_app.cine_app_facade.update_cine_player_context.call_count == 3


def test_wire_signals_requires_complete_application_graph() -> None:
    """Signal wiring runs only after complete application construction."""
    incomplete_app = SimpleNamespace()

    with pytest.raises(AttributeError, match="has no attribute 'multi_window_layout'"):
        wire_all_signals(incomplete_app)


def test_wire_signals_requires_declared_main_window_signals(
    mock_app: SimpleNamespace,
) -> None:
    """A missing required signal rejects an incomplete main-window fixture."""
    # Delete a single signal from main_window
    delattr(mock_app.main_window, "open_file_requested")

    with pytest.raises(
        AttributeError,
        match=r"'types.SimpleNamespace' object has no attribute 'open_file_requested'",
    ):
        wire_all_signals(mock_app)

    mock_app._subwindow_lifecycle_controller.connect_subwindow_signals.assert_not_called()
