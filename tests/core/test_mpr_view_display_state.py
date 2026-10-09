"""Unit tests for core.mpr_view_display_state (chunk 2, pure core).

Covers per-pane capture/restore of combine and display state, focus
independence (capture never consults shared controls or the focused pane),
fallback behavior for missing/invalid values, and per-pane LUT-override
independence.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from core.lut_catalog import linear_lut
from core.lut_engine import LookUpTable
from core.lut_series_state import get_series_lut, mpr_display_kwargs
from core.mpr_session_types import MprCombineState, MprDisplayState
from core.mpr_view_display_state import (
    MPR_LUT_OVERRIDE_KEY,
    capture_mpr_combine_state,
    capture_mpr_display_state,
    clear_mpr_lut_override,
    get_mpr_effective_lut,
    get_mpr_lut_override,
    restore_mpr_combine_state,
    restore_mpr_display_state,
    set_mpr_lut_override,
)


def _LUT() -> LookUpTable:
    return linear_lut()


def _manager(**overrides) -> SimpleNamespace:
    base = {
        "current_window_center": 40.0,
        "current_window_width": 400.0,
        "window_level_user_modified": True,
        "use_rescaled_values": True,
        "rescale_slope": 1.0,
        "rescale_intercept": -1024.0,
        "rescale_type": "HU",
        "series_defaults": {},
        "current_series_identifier": "series-A",
        "set_rescale_parameters": None,  # replaced below when needed
    }
    base.update(overrides)
    manager = SimpleNamespace(**base)
    calls: list[tuple[Any, ...]] = []

    def _set_rescale(slope, intercept, rescale_type):
        calls.append((slope, intercept, rescale_type))
        manager.rescale_slope = slope
        manager.rescale_intercept = intercept
        manager.rescale_type = rescale_type

    manager.set_rescale_parameters = _set_rescale
    manager.rescale_calls = calls
    return manager


def _viewer(*, inverted: bool = False) -> SimpleNamespace:
    viewer = SimpleNamespace(image_inverted=inverted)
    calls: list[bool] = []
    viewer.set_rescale_toggle_state = lambda value: calls.append(bool(value))
    viewer.rescale_toggle_calls = calls
    return viewer


class TestCombineRoundTrip:
    def test_capture_and_restore(self) -> None:
        data = {"mpr_combine_enabled": True, "mpr_combine_mode": "mip", "mpr_combine_slice_count": 6}
        state = capture_mpr_combine_state(data)
        assert state == MprCombineState(enabled=True, mode="mip", slice_count=6)
        target: dict[str, Any] = {}
        restore_mpr_combine_state(target, state)
        assert target == data

    def test_capture_falls_back_on_invalid(self) -> None:
        state = capture_mpr_combine_state(
            {"mpr_combine_enabled": 1, "mpr_combine_mode": "", "mpr_combine_slice_count": "bad"}
        )
        assert state == MprCombineState(enabled=True, mode="aip", slice_count=4)
        assert capture_mpr_combine_state({}) == MprCombineState()

    def test_restore_none_is_noop_and_invalid_falls_back(self) -> None:
        data = {"mpr_combine_enabled": True}
        restore_mpr_combine_state(data, None)
        assert data == {"mpr_combine_enabled": True}
        restore_mpr_combine_state(data, MprCombineState(enabled=False, mode="", slice_count=cast(Any, "bad")))
        assert data == {"mpr_combine_enabled": False, "mpr_combine_mode": "aip", "mpr_combine_slice_count": 4}


class TestDisplayCapture:
    def test_pane_values_captured_distinctly(self) -> None:
        first = _manager(current_window_center=10.0, current_window_width=100.0)
        second = _manager(current_window_center=70.0, current_window_width=700.0, window_level_user_modified=False)
        a = capture_mpr_display_state(first, _viewer(inverted=True))
        b = capture_mpr_display_state(second, _viewer(inverted=False))
        assert (a.window_center, a.window_width, a.wl_user_modified, a.inverted) == (10.0, 100.0, True, True)
        assert (b.window_center, b.window_width, b.wl_user_modified, b.inverted) == (70.0, 700.0, False, False)
        assert (a.rescale_slope, a.rescale_intercept, a.rescale_type) == (1.0, -1024.0, "HU")

    def test_capture_ignores_focus_and_shared_controls(self) -> None:
        # Capture takes only the pane's own manager/viewer: there is no
        # parameter for toolbar controls or a focused index at all.
        import inspect

        params = inspect.signature(capture_mpr_display_state).parameters
        assert set(params) == {"view_state_manager", "image_viewer"}
        manager = _manager(current_window_center=33.0)
        state = capture_mpr_display_state(manager, _viewer())
        assert state.window_center == 33.0

    def test_missing_and_non_numeric_degrade_gracefully(self) -> None:
        state = capture_mpr_display_state(SimpleNamespace(series_defaults={}), None)
        assert state.window_center is None and state.window_width is None
        assert state.wl_user_modified is False and state.use_rescaled is True
        assert state.rescale_slope is None and state.rescale_type == ""
        assert state.inverted is False
        broken = _manager(current_window_center="bad", current_window_width=None, rescale_slope="x")
        state = capture_mpr_display_state(broken, _viewer())
        assert state.window_center is None and state.rescale_slope is None

    def test_capture_reads_effective_lut_by_reference(self) -> None:
        lut = _LUT()
        manager = _manager()
        manager.series_defaults["series-A"] = {"current_lut": lut}
        state = capture_mpr_display_state(manager, _viewer())
        assert state.lut is lut


class TestDisplayRestore:
    def test_restore_writes_pane_only(self) -> None:
        source = _manager(current_window_center=11.0, current_window_width=111.0)
        dest = _manager(current_window_center=22.0, current_window_width=222.0)
        dest_viewer = _viewer(inverted=False)
        state = capture_mpr_display_state(source, _viewer(inverted=True))
        restore_mpr_display_state(dest, dest_viewer, state)
        assert (dest.current_window_center, dest.current_window_width) == (11.0, 111.0)
        assert dest.window_level_user_modified is True
        assert dest.rescale_calls == [(1.0, -1024.0, "HU")]
        assert dest.use_rescaled_values is True
        assert dest_viewer.image_inverted is True
        assert dest_viewer.rescale_toggle_calls == [True]
        # Source pane untouched by the restore.
        assert (source.current_window_center, source.current_window_width) == (11.0, 111.0)

    def test_restore_syncs_viewer_toggle_off(self) -> None:
        dest = _manager()
        viewer = _viewer()
        restore_mpr_display_state(dest, viewer, MprDisplayState(use_rescaled=False))
        assert viewer.rescale_toggle_calls == [False]
        assert dest.use_rescaled_values is False

    def test_restore_skips_bad_window_level_but_restores_rest(self) -> None:
        dest = _manager(current_window_center=22.0, current_window_width=222.0)
        restore_mpr_display_state(
            dest, _viewer(), MprDisplayState(window_center=5.0, window_width=0.0, inverted=True)
        )
        assert (dest.current_window_center, dest.current_window_width) == (22.0, 222.0)
        restore_mpr_display_state(dest, None, None)  # type: ignore[arg-type]
        assert (dest.current_window_center, dest.current_window_width) == (22.0, 222.0)

    def test_restore_none_is_noop(self) -> None:
        dest = _manager()
        restore_mpr_display_state(dest, _viewer(), None)
        assert (dest.current_window_center, dest.current_window_width) == (40.0, 400.0)
        assert dest.rescale_calls == []

    def test_restore_without_setter_assigns_attributes(self) -> None:
        dest = _manager()
        dest.set_rescale_parameters = None
        restore_mpr_display_state(
            dest, None, MprDisplayState(rescale_slope=2.0, rescale_intercept=3.0, rescale_type="X")
        )
        assert (dest.rescale_slope, dest.rescale_intercept, dest.rescale_type) == (2.0, 3.0, "X")

    def test_restore_handles_missing_manager_and_viewer(self) -> None:
        restore_mpr_display_state(None, None, MprDisplayState(window_center=1.0, window_width=2.0))
        restore_mpr_display_state(SimpleNamespace(series_defaults={}), None, MprDisplayState())


class TestLutOverride:
    def test_override_lifecycle(self) -> None:
        manager = _manager()
        assert get_mpr_lut_override(manager) is None
        lut = _LUT()
        set_mpr_lut_override(manager, lut)
        assert get_mpr_lut_override(manager) is lut
        assert MPR_LUT_OVERRIDE_KEY in manager.series_defaults
        # Series slot untouched: per-view override never rewrites shared state.
        assert "current_lut" not in manager.series_defaults.get("series-A", {})
        clear_mpr_lut_override(manager)
        assert get_mpr_lut_override(manager) is None
        assert MPR_LUT_OVERRIDE_KEY not in manager.series_defaults

    def test_non_lut_values_clear_and_missing_manager_safe(self) -> None:
        manager = _manager()
        set_mpr_lut_override(manager, _LUT())
        set_mpr_lut_override(manager, cast(Any, "not-a-lut"))
        assert get_mpr_lut_override(manager) is None
        set_mpr_lut_override(None, _LUT())
        clear_mpr_lut_override(None)
        assert get_mpr_lut_override(None) is None
        assert get_mpr_lut_override(SimpleNamespace()) is None

    def test_effective_lut_prefers_override_then_series_then_linear(self) -> None:
        series_lut = _LUT()
        override = _LUT()
        manager = _manager()
        assert get_mpr_effective_lut(manager).name == get_series_lut(manager, "series-A").name
        manager.series_defaults["series-A"] = {"current_lut": series_lut}
        assert get_mpr_effective_lut(manager) is series_lut
        set_mpr_lut_override(manager, override)
        assert get_mpr_effective_lut(manager) is override
        assert get_mpr_effective_lut(None).name == linear_lut().name

    def test_core_kwargs_prefer_override(self) -> None:
        override = _LUT()
        managers = {"view_state_manager": _manager()}
        before = mpr_display_kwargs(managers, "")
        assert before["lut"].name == linear_lut().name
        set_mpr_lut_override(managers["view_state_manager"], override)
        assert mpr_display_kwargs(managers, "")["lut"] is override
        assert mpr_display_kwargs(None, "")["lut"].name == linear_lut().name
