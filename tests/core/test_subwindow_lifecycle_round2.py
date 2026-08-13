"""Synthetic lifecycle coverage for :mod:`core.subwindow_lifecycle_controller`."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.subwindow_lifecycle_controller import SubwindowLifecycleController


class _Signal:
    """Small signal double that supports the connect/disconnect contract."""

    def __init__(self) -> None:
        self.slots: list[object] = []
        self.disconnect_calls = 0

    def connect(self, slot: object, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.slots.append(slot)

    def disconnect(self, slot: object | None = None) -> None:
        self.disconnect_calls += 1
        if slot is None:
            self.slots.clear()
            return
        if slot not in self.slots:
            raise TypeError("slot is not connected")
        self.slots.remove(slot)

    def emit(self, *args: object) -> list[object]:
        return [slot(*args) for slot in list(self.slots)]  # type: ignore[operator]


_VIEWER_SIGNALS = (
    "files_dropped",
    "layout_change_requested",
    "privacy_view_toggled",
    "smooth_when_zoomed_toggled",
    "scale_markers_toggled",
    "direction_labels_toggled",
    "slice_sync_toggled",
    "slice_sync_manage_requested",
    "slice_location_lines_toggled",
    "slice_location_lines_same_group_only_toggled",
    "slice_location_lines_focused_only_toggled",
    "slice_location_lines_mode_toggled",
    "left_pane_toggle_requested",
    "right_pane_toggle_requested",
    "about_this_file_requested",
    "assign_series_requested",
    "swap_view_requested",
    "window_slot_map_popup_requested",
    "overlay_font_size_adjust_requested",
    "histogram_requested",
    "structured_report_browser_requested",
    "clear_window_content_requested",
    "cine_play_pause_toggle_requested",
    "cine_stop_requested",
    "create_mpr_view_requested",
    "clear_mpr_view_requested",
    "create_3d_view_requested",
    "transform_changed",
    "zoom_changed",
)


def _viewer() -> SimpleNamespace:
    viewer = SimpleNamespace(**{name: _Signal() for name in _VIEWER_SIGNALS})
    viewer.scene = SimpleNamespace(selectionChanged=_Signal())
    viewer.image_item = None
    viewer.set_pixel_info_callbacks = MagicMock()
    viewer.set_subwindow_index = MagicMock()
    return viewer


def _wiring_app() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    viewer = _viewer()
    subwindow = SimpleNamespace(
        image_viewer=viewer,
        mpr_assign_requested=_Signal(),
        assign_series_requested=_Signal(),
        expand_to_1x1_requested=_Signal(),
    )
    vsm = SimpleNamespace(
        handle_transform_changed=MagicMock(),
        handle_zoom_changed=MagicMock(),
    )
    main_window = SimpleNamespace(
        _toggle_left_pane=MagicMock(),
        _toggle_right_pane=MagicMock(),
        adjust_overlay_font_size=MagicMock(),
    )
    callback_names = (
        "_open_files_from_paths",
        "_on_layout_change_requested",
        "_on_privacy_view_toggled",
        "_on_smooth_when_zoomed_toggled",
        "_on_scale_markers_toggled",
        "_on_direction_labels_toggled",
        "_on_slice_sync_toggled",
        "_open_slice_sync_dialog",
        "_on_slice_location_lines_toggled",
        "_on_slice_location_lines_same_group_only_toggled",
        "_on_slice_location_lines_focused_only_toggled",
        "_on_slice_location_lines_mode_toggled",
        "_open_about_this_file",
        "_on_assign_series_requested",
        "_on_assign_series_from_context_menu",
        "_on_expand_to_1x1_requested",
        "_on_swap_view_requested",
        "_on_window_slot_map_popup_requested",
        "_get_current_slice_file_path",
        "_on_mpr_assign_requested",
        "_open_structured_report_browser",
        "_on_clear_subwindow_content_requested",
    )
    app = SimpleNamespace(
        multi_window_layout=SimpleNamespace(
            get_all_subwindows=MagicMock(return_value=[subwindow]),
            get_slot_to_view=MagicMock(return_value=0),
        ),
        subwindow_managers={0: {"view_state_manager": vsm}},
        subwindow_data={0: {"current_dataset": object(), "is_mpr": False}},
        config_manager=SimpleNamespace(
            get_slice_location_lines_same_group_only=MagicMock(return_value=True),
            get_slice_location_lines_focused_only=MagicMock(return_value=False),
            get_slice_location_line_mode=MagicMock(return_value="all"),
            get_slice_location_lines_visible=MagicMock(return_value=True),
        ),
        main_window=main_window,
        dialog_coordinator=SimpleNamespace(open_histogram=MagicMock()),
        cine_app_facade=SimpleNamespace(
            get_cine_loop_state=MagicMock(return_value=True),
            on_cine_play_pause_toggle=MagicMock(),
            on_cine_stop=MagicMock(),
        ),
        cine_player=SimpleNamespace(is_playing=False),
        _get_subwindow_dataset=MagicMock(return_value=None),
        _get_subwindow_slice_index=MagicMock(return_value=0),
        _mpr_controller=SimpleNamespace(
            open_mpr_dialog=MagicMock(),
            clear_mpr=MagicMock(),
            is_mpr=MagicMock(return_value=False),
        ),
        _volume_render_facade=SimpleNamespace(launch_3d_view=MagicMock()),
    )
    for name in callback_names:
        setattr(app, name, MagicMock(return_value="path" if name.startswith("_get_") else None))
    app._mpr_controller._get_image_viewer = MagicMock(return_value=None)
    return app, subwindow, viewer


def test_public_signal_handlers_delegate_to_wiring_helpers() -> None:
    app = SimpleNamespace()
    controller = SubwindowLifecycleController(app)
    cases = (
        ("connect_subwindow_signals", "_wiring_connect_subwindow"),
        ("connect_all_subwindow_transform_signals", "_wiring_connect_transforms"),
        ("connect_all_subwindow_context_menu_signals", "_wiring_connect_context_menu"),
        ("disconnect_focused_subwindow_signals", "_wiring_disconnect_focused"),
        ("connect_focused_subwindow_signals", "_wiring_connect_focused"),
    )
    for method_name, helper_name in cases:
        with patch(f"core.subwindow_lifecycle_controller.{helper_name}") as helper:
            getattr(controller, method_name)()
            helper.assert_called_once_with(controller)


def test_connect_subwindow_signals_tracks_and_replaces_slots() -> None:
    app, subwindow, viewer = _wiring_app()
    controller = SubwindowLifecycleController(app)

    controller.connect_subwindow_signals()

    viewer.histogram_requested.emit()
    app.dialog_coordinator.open_histogram.assert_called_once_with(0)
    viewer.cine_play_pause_toggle_requested.emit()
    app.cine_app_facade.on_cine_play_pause_toggle.assert_called_once_with()
    viewer.create_mpr_view_requested.emit()
    app._mpr_controller.open_mpr_dialog.assert_called_once_with(0)
    viewer.create_3d_view_requested.emit()
    app._volume_render_facade.launch_3d_view.assert_called_once_with(0)
    assert len(controller._histogram_slots) == 1
    assert len(controller._cine_stop_slots) == 1
    assert viewer.set_subwindow_index.call_args.args == (0,)

    histogram_disconnects = viewer.histogram_requested.disconnect_calls
    controller.connect_subwindow_signals()
    assert len(controller._histogram_slots) == 1
    assert viewer.histogram_requested.disconnect_calls > histogram_disconnects
    assert len(viewer.histogram_requested.slots) == 1


def test_redisplay_native_slice_updates_dataset_and_histogram() -> None:
    dataset = object()
    slice_display_manager = SimpleNamespace(display_slice=MagicMock())
    app = SimpleNamespace(
        subwindow_managers={0: {"slice_display_manager": slice_display_manager}},
        subwindow_data={
            0: {
                "current_dataset": object(),
                "current_study_uid": "study",
                "current_series_uid": "series",
                "current_slice_index": 2,
            }
        },
        current_studies={"study": {"series": [dataset]}},
        dialog_coordinator=SimpleNamespace(update_histogram_for_subwindow=MagicMock()),
    )
    controller = SubwindowLifecycleController(app)

    with patch.object(controller, "get_subwindow_dataset", return_value=dataset):
        controller.redisplay_subwindow_slice(0, preserve_view=True)

    slice_display_manager.display_slice.assert_called_once_with(
        dataset,
        app.current_studies,
        "study",
        "series",
        2,
        preserve_view_override=True,
    )
    assert app.subwindow_data[0]["current_dataset"] is dataset
    app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)


def test_redisplay_handles_empty_and_mpr_states() -> None:
    app = SimpleNamespace(
        subwindow_managers={},
        subwindow_data={},
        current_studies={},
    )
    controller = SubwindowLifecycleController(app)
    controller.redisplay_subwindow_slice(7)

    mpr_controller = SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock())
    app._mpr_controller = mpr_controller
    app.subwindow_managers[0] = {"slice_display_manager": MagicMock()}
    app.subwindow_data[0] = {"current_slice_index": 4}
    controller.redisplay_subwindow_slice(0)
    mpr_controller.display_mpr_slice.assert_called_once_with(0, 4)


def test_layout_manager_and_series_handlers_call_collaborators() -> None:
    app = MagicMock()
    container = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = [container]
    app.subwindow_managers = {}
    controller = SubwindowLifecycleController(app)

    controller.ensure_all_subwindows_have_managers()
    app._create_managers_for_subwindow.assert_called_once_with(0, container)

    controller.on_layout_change_requested("1x2")
    app.multi_window_layout.set_layout.assert_called_once_with("1x2")

    controller.assign_series_to_subwindow(container, "series", 3, target_study_uid="study")
    app._file_series_coordinator.assign_series_to_subwindow.assert_called_once_with(
        container, "series", 3, target_study_uid="study"
    )


def test_update_panels_skip_empty_state_and_update_when_dataset_exists() -> None:
    app = SimpleNamespace(image_viewer=None, current_dataset=None)
    controller = SubwindowLifecycleController(app)
    controller.update_right_panel_for_focused_subwindow()
    controller.update_left_panel_for_focused_subwindow()

    app.image_viewer = SimpleNamespace(current_zoom=1.25, set_rescale_toggle_state=MagicMock())
    app.zoom_display_widget = SimpleNamespace(update_zoom=MagicMock())
    app.view_state_manager = None
    app.multi_window_layout = SimpleNamespace(
        get_focused_subwindow=MagicMock(return_value=None), get_all_subwindows=MagicMock(return_value=[])
    )
    app.slice_display_manager = None
    app.intensity_projection_controls_widget = MagicMock()
    controller.update_right_panel_for_focused_subwindow()
    app.zoom_display_widget.update_zoom.assert_called_once_with(1.25)

    app.current_dataset = object()
    app.metadata_panel = SimpleNamespace(set_dataset=MagicMock())
    app.cine_app_facade = SimpleNamespace(update_cine_player_context=MagicMock())
    controller.update_left_panel_for_focused_subwindow()
    app.metadata_panel.set_dataset.assert_called_once_with(app.current_dataset)
    app.cine_app_facade.update_cine_player_context.assert_called_once_with()


@pytest.mark.qt
def test_on_main_window_layout_changed_defers_layout_call(qapp) -> None:
    app = SimpleNamespace(multi_window_layout=SimpleNamespace(set_layout=MagicMock()))
    controller = SubwindowLifecycleController(app)

    controller.on_main_window_layout_changed("2x1")
    qapp.processEvents()
    app.multi_window_layout.set_layout.assert_called_once_with("2x1")
