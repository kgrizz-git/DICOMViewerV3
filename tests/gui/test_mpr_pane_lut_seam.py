"""Tests for the MPR-aware pane LUT seam in the subwindow manager factory.

The real LUT menu calls ``image_viewer.apply_series_lut`` /
``image_viewer.current_series_lut`` (wired by ``_wire_series_lut``). These
tests drive those actual closures with fakes: selecting a LUT on an MPR pane
must write the isolated per-pane override (never the shared series slot),
read back the effective LUT for menus, survive detach capture, and leave
non-MPR panes on the legacy series-slot path.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from core.lut_catalog import linear_lut, sigmoid_lut
from core.lut_series_state import clear_mpr_lut_override
from core.mpr_view_display_state import (
    capture_mpr_display_state,
    get_mpr_lut_override,
)
from gui.lut_actions import _current as _menu_current_lut
from gui.subwindow_manager_factory import _wire_series_lut


def _manager() -> SimpleNamespace:
    return SimpleNamespace(
        current_window_center=40.0,
        current_window_width=400.0,
        window_level_user_modified=False,
        use_rescaled_values=True,
        rescale_slope=1.0,
        rescale_intercept=0.0,
        rescale_type="HU",
        series_defaults={},
        current_series_identifier="series-id",
    )


def _wire(*, mpr: bool) -> tuple[Any, SimpleNamespace, MagicMock]:
    manager = _manager()
    viewer = MagicMock()
    viewer.image_inverted = False
    app = SimpleNamespace(
        _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=mpr)),
        _redisplay_subwindow_slice=MagicMock(),
        _update_mpr_navigator_thumbnail=MagicMock(),
        main_window=MagicMock(),
    )
    _wire_series_lut(app, 0, {"view_state_manager": manager}, viewer)
    return app, manager, viewer


class TestMprPaneLutSeam:
    def test_select_writes_override_not_series_slot(self) -> None:
        app, manager, viewer = _wire(mpr=True)
        custom = sigmoid_lut()
        viewer.apply_series_lut(custom)
        assert get_mpr_lut_override(manager) is custom
        assert "current_lut" not in manager.series_defaults.get("series-id", {})
        app._redisplay_subwindow_slice.assert_called_once_with(0, preserve_view=True)
        app._update_mpr_navigator_thumbnail.assert_called_once_with(0)

    def test_menu_reads_effective_lut(self) -> None:
        _app, _pane, viewer = _wire(mpr=True)
        current = _menu_current_lut(viewer)
        assert current is not None and current.name == "Linear"
        custom = sigmoid_lut()
        viewer.apply_series_lut(custom)
        assert _menu_current_lut(viewer) is custom
        assert viewer.current_series_lut() is custom

    def test_change_after_attach_takes_effect_and_survives_capture(self) -> None:
        _app, manager, viewer = _wire(mpr=True)
        first = sigmoid_lut()
        viewer.apply_series_lut(first)
        second = linear_lut()
        viewer.apply_series_lut(second)
        assert get_mpr_lut_override(manager) is second
        # Detach capture picks up the latest selection for the payload.
        state = capture_mpr_display_state(manager, viewer)
        assert state.lut is second

    def test_sibling_series_slot_untouched(self) -> None:
        _app, manager, viewer = _wire(mpr=True)
        sibling = _manager()
        sibling.series_defaults["series-id"] = {"current_lut": linear_lut()}
        viewer.apply_series_lut(sigmoid_lut())
        assert sibling.series_defaults["series-id"]["current_lut"].name == "Linear"
        assert get_mpr_lut_override(sibling) is None

    def test_non_mpr_pane_keeps_series_slot_path(self) -> None:
        app, manager, viewer = _wire(mpr=False)
        custom = sigmoid_lut()
        viewer.apply_series_lut(custom)
        assert manager.series_defaults["series-id"]["current_lut"] is custom
        assert get_mpr_lut_override(manager) is None
        assert viewer.current_series_lut() is custom
        assert _menu_current_lut(viewer) is custom
        app._redisplay_subwindow_slice.assert_called_once_with(0, preserve_view=True)

    def test_clear_override_falls_back_to_series_lut(self) -> None:
        _app, manager, viewer = _wire(mpr=True)
        series_lut = linear_lut()
        manager.series_defaults["series-id"] = {"current_lut": series_lut}
        viewer.apply_series_lut(sigmoid_lut())
        assert viewer.current_series_lut().name == "Sigmoid"
        clear_mpr_lut_override(manager)
        assert viewer.current_series_lut() is series_lut
