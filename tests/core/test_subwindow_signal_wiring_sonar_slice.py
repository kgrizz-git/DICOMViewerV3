"""
Characterization tests for connect_subwindow_signals helpers (Sonar S3776 slice).

Covers safe disconnect helpers and layout wiring orchestration extracted from
``connect_subwindow_signals``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, Signal

from core.subwindow_signal_wiring import (
    _disconnect_ignore_missing,
    _layout_fixed_signal_pairs,
    _pop_tracked_disconnect,
    connect_subwindow_signals,
)


class _Emitter(QObject):
    fired = Signal()
    other = Signal()


def test_disconnect_ignore_missing_with_and_without_slot(qapp) -> None:
    emitter = _Emitter()
    calls: list[str] = []

    def slot() -> None:
        calls.append("x")

    emitter.fired.connect(slot)
    _disconnect_ignore_missing(emitter.fired, slot)
    emitter.fired.emit()
    assert calls == []

    # Missing connection must not raise.
    _disconnect_ignore_missing(emitter.fired, slot)
    _disconnect_ignore_missing(emitter.other)


def test_pop_tracked_disconnect_removes_slot(qapp) -> None:
    emitter = _Emitter()
    calls: list[str] = []

    def slot() -> None:
        calls.append("x")

    emitter.fired.connect(slot)
    slot_map = {42: slot}
    _pop_tracked_disconnect(emitter.fired, slot_map, 42)
    assert 42 not in slot_map
    emitter.fired.emit()
    assert calls == []

    _pop_tracked_disconnect(emitter.fired, slot_map, 99)  # missing key: no-op


def test_layout_fixed_signal_pairs_includes_core_app_slots() -> None:
    app = MagicMock()
    image_viewer = MagicMock()
    subwindow = MagicMock()
    pairs = _layout_fixed_signal_pairs(app, image_viewer, subwindow)
    slots = {slot for _, slot in pairs}
    assert app._open_files_from_paths in slots
    assert app._on_layout_change_requested in slots
    assert app._on_assign_series_requested in slots
    assert app.main_window._toggle_left_pane in slots
    assert len(pairs) >= 20


def _make_image_viewer() -> MagicMock:
    image_viewer = MagicMock()
    for name in (
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
    ):
        setattr(image_viewer, name, MagicMock())
    return image_viewer


def test_connect_subwindow_signals_wires_and_tracks_slots() -> None:
    image_viewer = _make_image_viewer()
    subwindow = MagicMock()
    subwindow.image_viewer = image_viewer
    subwindow.assign_series_requested = MagicMock()
    subwindow.expand_to_1x1_requested = MagicMock()
    subwindow.mpr_assign_requested = MagicMock()

    config = MagicMock()
    config.get_slice_location_lines_same_group_only.return_value = False
    config.get_slice_location_lines_focused_only.return_value = False
    config.get_slice_location_line_mode.return_value = "solid"
    config.get_slice_location_lines_visible.return_value = True

    layout = MagicMock()
    layout.get_all_subwindows.return_value = [subwindow]
    layout.get_slot_to_view.return_value = {}

    app = SimpleNamespace(
        multi_window_layout=layout,
        main_window=MagicMock(),
        config_manager=config,
        dialog_coordinator=MagicMock(),
        cine_app_facade=MagicMock(),
        cine_player=MagicMock(is_playing=False),
        subwindow_managers={},
        subwindow_data={},
        _open_files_from_paths=MagicMock(),
        _on_layout_change_requested=MagicMock(),
        _on_privacy_view_toggled=MagicMock(),
        _on_smooth_when_zoomed_toggled=MagicMock(),
        _on_scale_markers_toggled=MagicMock(),
        _on_direction_labels_toggled=MagicMock(),
        _on_slice_sync_toggled=MagicMock(),
        _open_slice_sync_dialog=MagicMock(),
        _on_slice_location_lines_toggled=MagicMock(),
        _on_slice_location_lines_same_group_only_toggled=MagicMock(),
        _on_slice_location_lines_focused_only_toggled=MagicMock(),
        _on_slice_location_lines_mode_toggled=MagicMock(),
        _open_about_this_file=MagicMock(),
        _on_assign_series_requested=MagicMock(),
        _on_assign_series_from_context_menu=MagicMock(),
        _on_expand_to_1x1_requested=MagicMock(),
        _on_swap_view_requested=MagicMock(),
        _on_window_slot_map_popup_requested=MagicMock(),
        _on_mpr_assign_requested=MagicMock(),
        _open_structured_report_browser=MagicMock(),
        _get_current_slice_file_path=MagicMock(return_value=None),
        _on_clear_subwindow_content_requested=MagicMock(),
        _get_subwindow_dataset=MagicMock(return_value=None),
        _get_subwindow_slice_index=MagicMock(return_value=0),
    )

    ctrl = SimpleNamespace(
        app=app,
        _rdsr_report_slots={},
        _histogram_slots={},
        _mpr_open_slots={},
        _mpr_clear_slots={},
        _3d_view_slots={},
        _clear_window_slots={},
        _cine_toggle_slots={},
        _cine_stop_slots={},
    )

    with patch(
        "core.subwindow_signal_wiring.wire_pixel_info_callbacks_for_subwindow"
    ) as wire_px:
        connect_subwindow_signals(ctrl)

    vid = id(image_viewer)
    assert vid in ctrl._histogram_slots
    assert vid in ctrl._rdsr_report_slots
    assert vid in ctrl._clear_window_slots
    assert vid in ctrl._cine_toggle_slots
    assert vid in ctrl._cine_stop_slots
    assert vid not in ctrl._mpr_open_slots
    assert vid not in ctrl._3d_view_slots
    image_viewer.files_dropped.connect.assert_called_once_with(app._open_files_from_paths)
    image_viewer.set_subwindow_index.assert_called_once_with(0)
    wire_px.assert_called_once()
    subwindow.mpr_assign_requested.connect.assert_called_once_with(
        app._on_mpr_assign_requested
    )

    # Second pass should disconnect tracked slots before reconnecting.
    old_hist = ctrl._histogram_slots[vid]
    connect_subwindow_signals(ctrl)
    image_viewer.histogram_requested.disconnect.assert_any_call(old_hist)
    assert ctrl._histogram_slots[vid] is not old_hist
