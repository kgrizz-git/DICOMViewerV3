"""
Characterization tests for ``SubwindowManagementMixin`` methods with real bodies.

The one-line forwards live in the case tables; these cover the methods that do
more: per-pane manager creation from persisted config, slice-sync group
colours, the navigation-slider state machine, the fusion cache reset, the
window-slot thumbnail, focus propagation, and histogram throttling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from main_mixin_delegation_support import _stub_for

from utils.slice_sync_group_palette import slice_sync_group_rgb

# --- SubwindowManagementMixin: per-pane manager creation and state seeding ----------


def _viewer_stub(**overrides: Any) -> MagicMock:
    viewer = MagicMock(name="image_viewer")
    viewer.subwindow_index = 0
    for name, value in overrides.items():
        setattr(viewer, name, value)
    return viewer


def _config_stub(**overrides: Any) -> MagicMock:
    config = MagicMock(name="config_manager")
    config.get_slice_sync_enabled.return_value = False
    config.get_slice_sync_groups.return_value = []
    config.get_slice_sync_group_strip_height_px.return_value = 4
    for name, value in overrides.items():
        setattr(config, name, value)
    return config


def test_create_managers_for_subwindow_pushes_persisted_display_settings() -> None:
    """A new pane must start from the persisted display settings, not defaults."""
    viewer = _viewer_stub()
    subwindow = MagicMock(name="subwindow")
    subwindow.image_viewer = viewer
    config = _config_stub(
        get_slice_sync_enabled=MagicMock(return_value=True),
        get_smooth_image_when_zoomed=MagicMock(return_value=False),
        get_show_scale_markers=MagicMock(return_value=True),
        get_show_direction_labels=MagicMock(return_value=False),
        get_scale_markers_color=MagicMock(return_value=(1, 2, 3)),
        get_direction_labels_color=MagicMock(return_value=(4, 5, 6)),
        get_direction_label_size=MagicMock(return_value=18),
        get_scale_markers_major_tick_interval_mm=MagicMock(return_value=10.0),
        get_scale_markers_minor_tick_interval_mm=MagicMock(return_value=2.0),
    )
    managers = {"view_state_manager": MagicMock()}
    stub = _stub_for(
        "SubwindowManagementMixin",
        config_manager=config,
        subwindow_managers={},
        subwindow_data={},
    )
    stub._build_managers_for_subwindow = MagicMock(return_value=managers)
    stub._refresh_slice_sync_group_indicators = MagicMock()

    stub._create_managers_for_subwindow(2, subwindow)

    viewer.set_subwindow_index.assert_called_once_with(2)
    viewer.set_slice_sync_enabled_state.assert_called_once_with(True)
    viewer.set_smooth_when_zoomed_state.assert_called_once_with(False)
    viewer.set_scale_markers_state.assert_called_once_with(True)
    viewer.set_direction_labels_state.assert_called_once_with(False)
    viewer.set_scale_markers_color_state.assert_called_once_with((1, 2, 3))
    viewer.set_direction_labels_color_state.assert_called_once_with((4, 5, 6))
    viewer.set_direction_label_size_state.assert_called_once_with(18)
    viewer.set_scale_markers_tick_intervals_state.assert_called_once_with(10.0, 2.0)
    viewer.set_mouse_mode.assert_called_once_with("pan")
    assert stub.subwindow_managers == {2: managers}
    assert stub.subwindow_data[2] == {
        "current_dataset": None,
        "current_slice_index": 0,
        "current_series_uid": "",
        "current_study_uid": "",
        "current_datasets": [],
    }


def test_create_managers_for_subwindow_preserves_existing_pane_data() -> None:
    """Re-creating managers for a pane already holding a series must not wipe its data."""
    existing = {"current_slice_index": 12, "current_series_uid": "1.2.3"}
    stub = _stub_for(
        "SubwindowManagementMixin",
        config_manager=_config_stub(),
        subwindow_managers={},
        subwindow_data={1: existing},
    )
    stub._build_managers_for_subwindow = MagicMock(return_value={})
    stub._refresh_slice_sync_group_indicators = MagicMock()
    subwindow = MagicMock(name="subwindow")
    subwindow.image_viewer = _viewer_stub()

    stub._create_managers_for_subwindow(1, subwindow)

    assert stub.subwindow_data[1] is existing


def test_create_managers_for_subwindow_ignores_a_missing_pane() -> None:
    """A layout slot with no container yet must be a no-op, not an AttributeError."""
    stub = _stub_for("SubwindowManagementMixin")
    stub._build_managers_for_subwindow = MagicMock()

    stub._create_managers_for_subwindow(0, None)

    stub._build_managers_for_subwindow.assert_not_called()


def test_create_managers_for_subwindow_installs_the_file_path_callback() -> None:
    """The new pane's viewer must resolve its own file path through the coordinator seam."""
    stub = _stub_for(
        "SubwindowManagementMixin",
        config_manager=_config_stub(),
        subwindow_managers={},
        subwindow_data={},
    )
    stub._build_managers_for_subwindow = MagicMock(return_value={})
    stub._refresh_slice_sync_group_indicators = MagicMock()
    stub._get_current_slice_file_path = MagicMock(return_value="/data/a.dcm")
    viewer = _viewer_stub()
    subwindow = MagicMock(name="subwindow")
    subwindow.image_viewer = viewer

    stub._create_managers_for_subwindow(3, subwindow)

    assert viewer.get_file_path_callback() == "/data/a.dcm"


# --- SubwindowManagementMixin: slice-sync group indicators ---------------------------


def test_refresh_slice_sync_group_indicators_paints_group_colors() -> None:
    """A grouped pane gets its group's palette color on the title strip."""
    sub_a, sub_b = MagicMock(name="a"), MagicMock(name="b")
    sub_a.image_viewer = _viewer_stub(subwindow_index=0)
    sub_b.image_viewer = _viewer_stub(subwindow_index=1)
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub_a, sub_b, None]
    config = _config_stub(
        get_slice_sync_enabled=MagicMock(return_value=True),
        get_slice_sync_groups=MagicMock(return_value=[[0, 1]]),
    )
    stub = _stub_for("SubwindowManagementMixin", config_manager=config, multi_window_layout=layout)

    stub._refresh_slice_sync_group_indicators()

    for sub in (sub_a, sub_b):
        sub.set_slice_sync_strip_height.assert_called_once_with(4)
        indicator = sub.set_slice_sync_group_indicator.call_args.args[0]
        assert indicator is not None
        assert (indicator.red(), indicator.green(), indicator.blue()) == slice_sync_group_rgb(0)


def test_refresh_slice_sync_group_indicators_clears_when_sync_is_off() -> None:
    """With slice sync disabled there are no groups, so every strip color is cleared."""
    sub = MagicMock(name="sub")
    sub.image_viewer = _viewer_stub(subwindow_index=0)
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub]
    stub = _stub_for("SubwindowManagementMixin", config_manager=_config_stub(), multi_window_layout=layout)

    stub._refresh_slice_sync_group_indicators()

    sub.set_slice_sync_group_indicator.assert_called_once_with(None)
    config_groups_read = stub.config_manager.get_slice_sync_groups
    config_groups_read.assert_not_called()


def test_refresh_slice_sync_group_indicators_clears_ungrouped_panes() -> None:
    """A pane outside every group shows no color, even while sync is on."""
    grouped, ungrouped = MagicMock(name="g"), MagicMock(name="u")
    grouped.image_viewer = _viewer_stub(subwindow_index=0)
    ungrouped.image_viewer = _viewer_stub(subwindow_index=2)
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [grouped, ungrouped]
    config = _config_stub(
        get_slice_sync_enabled=MagicMock(return_value=True),
        get_slice_sync_groups=MagicMock(return_value=[[0, 1]]),
    )
    stub = _stub_for("SubwindowManagementMixin", config_manager=config, multi_window_layout=layout)

    stub._refresh_slice_sync_group_indicators()

    assert grouped.set_slice_sync_group_indicator.call_args.args[0] is not None
    ungrouped.set_slice_sync_group_indicator.assert_called_once_with(None)


def test_refresh_slice_sync_group_indicators_clears_panes_without_a_viewer() -> None:
    """A pane whose viewer is not wired up yet must not raise on ``subwindow_index``."""
    sub = MagicMock(name="sub")
    sub.image_viewer = None
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub]
    stub = _stub_for("SubwindowManagementMixin", config_manager=_config_stub(), multi_window_layout=layout)

    stub._refresh_slice_sync_group_indicators()

    sub.set_slice_sync_group_indicator.assert_called_once_with(None)


# --- SubwindowManagementMixin: navigation slider state ------------------------------


def _slider_stub(
    *,
    mpr: bool = False,
    data: dict[str, Any] | None = None,
    studies: dict[str, dict[str, list[Any]]] | None = None,
    subwindow: Any = "auto",
) -> Any:
    viewer = _viewer_stub()
    container = MagicMock(name="subwindow")
    container.image_viewer = viewer
    if subwindow == "auto":
        subwindow = container
    controller = MagicMock(name="mpr_controller")
    controller.is_mpr.return_value = mpr
    layout = MagicMock()
    layout.get_subwindow.return_value = subwindow
    stub = _stub_for(
        "SubwindowManagementMixin",
        multi_window_layout=layout,
        subwindow_data={0: data if data is not None else {}},
        current_studies=studies if studies is not None else {},
        _mpr_controller=controller,
    )
    return stub, viewer


def test_sync_navigation_slider_uses_mpr_result_length() -> None:
    """An MPR pane's slider spans the MPR stack and shows the 1-based slice position."""
    result = MagicMock(n_slices=30)
    stub, viewer = _slider_stub(mpr=True, data={"mpr_result": result, "mpr_slice_index": 4})

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_called_once_with(
        enabled=True, minimum=1, maximum=30, value=5, mode_label="Slice"
    )


def test_sync_navigation_slider_hides_for_a_single_slice_mpr() -> None:
    """A one-slice MPR has nothing to navigate, so the strip is disabled at 1/1."""
    result = MagicMock(n_slices=1)
    stub, viewer = _slider_stub(mpr=True, data={"mpr_result": result})

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_called_once_with(
        enabled=False, minimum=1, maximum=1, value=1
    )


def test_sync_navigation_slider_uses_native_series_length() -> None:
    """A native 2-D pane's slider spans the loaded datasets and shows ``Slice``."""
    studies = {"1.2": {"1.2.3": [object(), object(), object()]}}
    stub, viewer = _slider_stub(
        data={
            "current_study_uid": "1.2",
            "current_series_uid": "1.2.3",
            "current_slice_index": 1,
        },
        studies=studies,
    )

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_called_once_with(
        enabled=True, minimum=1, maximum=3, value=2, mode_label="Slice"
    )


def test_sync_navigation_slider_labels_a_split_multiframe_instance_as_frame() -> None:
    """A per-instance wrapper makes the slider a *frame* navigator, not a slice one."""

    class _FrameWrapper:
        _frame_index = 0
        _original_dataset = object()

    studies = {"1.2": {"1.2.3": [object(), _FrameWrapper()]}}
    stub, viewer = _slider_stub(
        data={
            "current_study_uid": "1.2",
            "current_series_uid": "1.2.3",
            "current_slice_index": 1,
        },
        studies=studies,
    )

    stub._sync_navigation_slider_for_subwindow(0)

    assert viewer.set_navigation_slider_state.call_args.kwargs["mode_label"] == "Frame"


def test_sync_navigation_slider_hides_without_series_uids() -> None:
    """An empty pane has no navigable stack: the strip is disabled at 1/1."""
    stub, viewer = _slider_stub(data={"current_study_uid": "", "current_series_uid": ""})

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_called_once_with(
        enabled=False, minimum=1, maximum=1, value=1
    )


def test_sync_navigation_slider_hides_for_a_single_slice_series() -> None:
    """A one-slice native series is not navigable either."""
    stub, viewer = _slider_stub(
        data={
            "current_study_uid": "1.2",
            "current_series_uid": "1.2.3",
            "current_slice_index": 0,
        },
        studies={"1.2": {"1.2.3": [object()]}},
    )

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_called_once_with(
        enabled=False, minimum=1, maximum=1, value=1
    )


def test_sync_navigation_slider_ignores_a_negative_index() -> None:
    """A defensive early return keeps a bad caller from touching the layout."""
    stub, viewer = _slider_stub(data={})

    stub._sync_navigation_slider_for_subwindow(-1)

    viewer.set_navigation_slider_state.assert_not_called()


def test_sync_navigation_slider_ignores_an_empty_pane() -> None:
    """A layout slot with no container leaves the slider untouched."""
    stub, viewer = _slider_stub(data={}, subwindow=None)

    stub._sync_navigation_slider_for_subwindow(0)

    viewer.set_navigation_slider_state.assert_not_called()


# --- SubwindowManagementMixin: fusion reset + rescale params -------------------------


def test_reset_fusion_handler_for_subwindow_clears_every_cache() -> None:
    """Disabling fusion for a pane must drop the alignment/resampling caches too."""
    handler = MagicMock(name="fusion_handler")
    handler._slice_location_cache = {"a": 1}
    handler._resampling_decision_cache = object()
    handler._resampling_decision_cache_key = ("k", 1)
    stub = _stub_for("SubwindowManagementMixin", subwindow_managers={1: {"fusion_handler": handler}})

    stub._reset_fusion_handler_for_subwindow(1)

    assert handler.fusion_enabled is False
    assert handler._slice_location_cache == {}
    assert handler._resampling_decision_cache is None
    assert handler._resampling_decision_cache_key is None
    handler.clear_alignment_cache.assert_called_once_with()
    handler.image_resampler.clear_cache.assert_called_once_with()


def test_reset_fusion_handler_for_subwindow_skips_an_unknown_pane() -> None:
    """A pane with no manager registry entry must be a no-op."""
    stub = _stub_for("SubwindowManagementMixin", subwindow_managers={})

    stub._reset_fusion_handler_for_subwindow(1)


def test_reset_fusion_handler_for_subwindow_skips_a_pane_without_fusion() -> None:
    """Non-fusion panes have no handler to reset."""
    stub = _stub_for("SubwindowManagementMixin", subwindow_managers={1: {}})

    stub._reset_fusion_handler_for_subwindow(1)


def test_reset_fusion_for_all_subwindows_also_resets_the_shared_widget() -> None:
    """A full close must clear the shared fusion controls, not just per-pane handlers."""
    widget = MagicMock(name="fusion_controls_widget")
    handler = MagicMock(name="fusion_handler")
    stub = _stub_for(
        "SubwindowManagementMixin",
        subwindow_managers={0: {"fusion_handler": handler}, 1: {}},
        fusion_controls_widget=widget,
    )

    stub._reset_fusion_for_all_subwindows()

    assert handler.fusion_enabled is False
    widget.set_fusion_enabled.assert_called_once_with(False)
    widget.clear_status.assert_called_once_with()


def test_get_rescale_params_reads_the_legacy_focused_view_state() -> None:
    """The legacy alias still reports the focused pane's rescale tuple."""
    vsm = MagicMock(rescale_slope=2.0, rescale_intercept=-1024.0, rescale_type="HU", use_rescaled_values=True)
    stub = _stub_for("SubwindowManagementMixin", view_state_manager=vsm)

    assert stub._get_rescale_params() == (2.0, -1024.0, "HU", True)


def test_get_subwindow_rescale_params_reads_that_panes_manager() -> None:
    """ROI statistics must match the pane's own ViewStateManager, not the alias."""
    vsm = MagicMock(rescale_slope=1.0, rescale_intercept=0.0, rescale_type="US", use_rescaled_values=False)
    stub = _stub_for("SubwindowManagementMixin", subwindow_managers={2: {"view_state_manager": vsm}})

    assert stub._get_subwindow_rescale_params(2) == (1.0, 0.0, "US", False)


def test_get_subwindow_rescale_params_defaults_when_no_manager_exists() -> None:
    """A pane without managers falls back to "no rescale, use rescaled values"."""
    stub = _stub_for("SubwindowManagementMixin", subwindow_managers={})

    assert stub._get_subwindow_rescale_params(1) == (None, None, None, True)


# --- SubwindowManagementMixin: window-slot thumbnail ---------------------------------


def test_get_thumbnail_for_view_scales_the_live_viewport() -> None:
    """A loaded pane yields a 40-px thumbnail for the window-slot map."""
    pixmap = MagicMock(name="grabbed_pixmap")
    pixmap.isNull.return_value = False
    scaled = MagicMock(name="scaled_pixmap")
    pixmap.scaled.return_value = scaled
    viewport = MagicMock(name="viewport")
    viewport.width.return_value = 512
    viewport.height.return_value = 512
    viewport.grab.return_value = pixmap
    viewer = MagicMock(name="viewer")
    viewer.viewport.return_value = viewport
    subwindow = MagicMock(name="subwindow")
    subwindow.image_viewer = viewer
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [subwindow]
    stub = _stub_for("SubwindowManagementMixin", multi_window_layout=layout)

    assert stub._get_thumbnail_for_view(0) is scaled
    assert pixmap.scaled.call_args.args[:2] == (40, 40)


def test_get_thumbnail_for_view_returns_none_for_an_out_of_range_slot() -> None:
    """Slot indices beyond the layout have no thumbnail rather than raising."""
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [MagicMock()]
    stub = _stub_for("SubwindowManagementMixin", multi_window_layout=layout)

    assert stub._get_thumbnail_for_view(3) is None
    assert stub._get_thumbnail_for_view(-1) is None


def test_get_thumbnail_for_view_returns_none_for_an_empty_pane() -> None:
    """A pane with no viewer or a null grab has no thumbnail."""
    empty = MagicMock(name="subwindow")
    empty.image_viewer = None
    null_pixmap = MagicMock(name="grabbed")
    null_pixmap.isNull.return_value = True
    viewer = MagicMock(name="viewer")
    viewport = MagicMock(name="viewport")
    viewport.width.return_value = 10
    viewport.height.return_value = 10
    viewport.grab.return_value = null_pixmap
    viewer.viewport.return_value = viewport
    loaded = MagicMock(name="subwindow")
    loaded.image_viewer = viewer
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [empty, loaded]
    stub = _stub_for("SubwindowManagementMixin", multi_window_layout=layout)

    assert stub._get_thumbnail_for_view(0) is None
    assert stub._get_thumbnail_for_view(1) is None


def test_get_thumbnail_for_view_returns_none_for_a_collapsed_viewport() -> None:
    """A splitter collapse to zero size must not hand back a degenerate pixmap."""
    viewer = MagicMock(name="viewer")
    viewport = MagicMock(name="viewport")
    viewport.width.return_value = 0
    viewport.height.return_value = 0
    viewer.viewport.return_value = viewport
    subwindow = MagicMock(name="subwindow")
    subwindow.image_viewer = viewer
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [subwindow]
    stub = _stub_for("SubwindowManagementMixin", multi_window_layout=layout)

    assert stub._get_thumbnail_for_view(0) is None
    viewport.grab.assert_not_called()


# --- SubwindowManagementMixin: focus + histogram throttling -------------------------


def test_on_focused_subwindow_changed_refreshes_lines_only_when_focused_only_is_on() -> None:
    """The slice-location-line refresh is conditional on the focused-only setting."""
    controller = MagicMock()
    line_coordinator = MagicMock()
    config = MagicMock()
    config.get_slice_location_lines_focused_only.return_value = True
    stub = _stub_for(
        "SubwindowManagementMixin",
        _subwindow_lifecycle_controller=controller,
        _slice_location_line_coordinator=line_coordinator,
        config_manager=config,
    )
    stub._update_3d_view_action_state = MagicMock()
    stub._refresh_window_slot_map_widgets = MagicMock()
    subwindow = MagicMock(name="subwindow")

    stub._on_focused_subwindow_changed(subwindow)

    controller.on_focused_subwindow_changed.assert_called_once_with(subwindow)
    stub._update_3d_view_action_state.assert_called_once_with()
    line_coordinator.refresh_all.assert_called_once_with()
    stub._refresh_window_slot_map_widgets.assert_called_once_with()


def test_on_focused_subwindow_changed_skips_line_refresh_when_not_focused_only() -> None:
    """With "show only for focused window" off, focusing a pane must not re-render lines."""
    controller = MagicMock()
    line_coordinator = MagicMock()
    config = MagicMock()
    config.get_slice_location_lines_focused_only.return_value = False
    stub = _stub_for(
        "SubwindowManagementMixin",
        _subwindow_lifecycle_controller=controller,
        _slice_location_line_coordinator=line_coordinator,
        config_manager=config,
    )
    stub._update_3d_view_action_state = MagicMock()
    stub._refresh_window_slot_map_widgets = MagicMock()

    stub._on_focused_subwindow_changed(MagicMock(name="subwindow"))

    line_coordinator.refresh_all.assert_not_called()
    stub._refresh_window_slot_map_widgets.assert_called_once_with()


def test_update_histogram_for_focused_subwindow_throttles_a_full_refresh() -> None:
    """Slice/series changes coalesce into one histogram refetch after 300 ms."""
    callback = MagicMock(name="do_update")
    stub = _stub_for("SubwindowManagementMixin", dialog_coordinator=MagicMock())
    stub._do_update_histogram_for_focused_subwindow = callback
    stub._restart_single_shot_timer = MagicMock()

    stub._update_histogram_for_focused_subwindow()

    stub._restart_single_shot_timer.assert_called_once_with(
        "_histogram_update_timer", 300, callback
    )


def test_update_histogram_for_focused_subwindow_without_dialog_coordinator_is_a_no_op() -> None:
    """No dialog coordinator means no timer to arm."""
    stub = _stub_for("SubwindowManagementMixin")
    stub._restart_single_shot_timer = MagicMock()

    stub._update_histogram_for_focused_subwindow()

    stub._restart_single_shot_timer.assert_not_called()


def test_do_update_histogram_for_focused_subwindow_targets_the_focused_pane() -> None:
    """The throttled refetch follows pane focus, not always pane 0."""
    coordinator = MagicMock()
    stub = _stub_for(
        "SubwindowManagementMixin", dialog_coordinator=coordinator, focused_subwindow_index=3
    )

    stub._do_update_histogram_for_focused_subwindow()

    coordinator.update_histogram_for_subwindow.assert_called_once_with(3)
