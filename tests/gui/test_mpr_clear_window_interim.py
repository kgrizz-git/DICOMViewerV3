"""Interim Clear-Window semantics for the parking slice.

Until the parking update arrives, MPR panes have no park action:
"Clear This Window" is disabled on them and pane-reset safety nets discard
the mapped view (the same outcome as "Clear MPR View"). These tests pin the
interim contract; the parking update replaces both behaviors and this file.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.study_navigation_handlers import clear_subwindow, clear_subwindow_content
from core.subwindow_signal_wiring import _connect_clear_and_cine_slots


def _wired_viewer(subwindow_data: dict, idx: int = 0) -> SimpleNamespace:
    app = SimpleNamespace(subwindow_data={idx: subwindow_data})
    ctrl = SimpleNamespace(
        _clear_window_slots={},
        _cine_toggle_slots={},
        _cine_stop_slots={},
    )
    viewer = SimpleNamespace(
        clear_window_content_requested=MagicMock(),
        cine_play_pause_toggle_requested=MagicMock(),
        cine_stop_requested=MagicMock(),
        get_cine_loop_state_callback=None,
        get_cine_is_playing_callback=None,
        get_clear_this_window_enabled_callback=None,
    )
    app.cine_app_facade = MagicMock()
    app.cine_player = MagicMock()
    _connect_clear_and_cine_slots(ctrl, app, viewer, idx, vid=1)
    return viewer


class TestClearThisWindowEnabledState:
    def test_enabled_for_an_ordinary_pane_with_a_dataset(self) -> None:
        viewer = _wired_viewer({"current_dataset": object(), "is_mpr": False})
        assert viewer.get_clear_this_window_enabled_callback() is True

    def test_disabled_for_an_empty_pane(self) -> None:
        viewer = _wired_viewer({})
        assert viewer.get_clear_this_window_enabled_callback() is False

    def test_disabled_on_an_mpr_pane_interim(self) -> None:
        viewer = _wired_viewer({"current_dataset": object(), "is_mpr": True})
        assert viewer.get_clear_this_window_enabled_callback() is False


def _app_with_mpr_pane(is_mpr: bool) -> MagicMock:
    app = MagicMock()
    app.subwindow_data = {0: {"is_mpr": is_mpr, "current_dataset": object() if is_mpr else None}}
    app._mpr_controller.is_mpr.return_value = is_mpr
    app._mpr_controller.clear_mpr = MagicMock()
    app.focused_subwindow_index = -1
    return app


class TestPaneResetInterimDiscard:
    def test_clear_subwindow_discards_the_view_on_an_mpr_pane(self) -> None:
        app = _app_with_mpr_pane(is_mpr=True)
        app._mpr_controller.attached_view_id.return_value = 7
        clear_subwindow(app, 0)
        app._mpr_controller.discard_view_on_pane_reset.assert_called_once_with(0)
        app._mpr_controller.clear_mpr.assert_not_called()

    def test_clear_subwindow_discards_even_when_the_pane_flag_was_already_cleared(self) -> None:
        # Review regression: the safety net is keyed off the registry mapping,
        # not the pane's display flag.
        app = _app_with_mpr_pane(is_mpr=False)
        app._mpr_controller.attached_view_id.return_value = 7
        clear_subwindow(app, 0)
        app._mpr_controller.discard_view_on_pane_reset.assert_called_once_with(0)

    def test_clear_subwindow_leaves_unmapped_panes_alone(self) -> None:
        app = _app_with_mpr_pane(is_mpr=False)
        app._mpr_controller.attached_view_id.return_value = None
        clear_subwindow(app, 0)
        app._mpr_controller.discard_view_on_pane_reset.assert_called_once_with(0)
        app._mpr_controller.clear_mpr.assert_not_called()

    def test_real_registry_discard_on_inconsistent_pane_state(self) -> None:
        from mpr_lifecycle_harness import _make_controller, _make_result, _seed_mpr_pane

        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        assert ctrl.attached_view_id(0) is not None
        app.subwindow_data[0]["is_mpr"] = False  # inconsistent: view mapped, flag cleared
        assert ctrl.discard_view_on_pane_reset(0) is True
        assert ctrl.attached_view_id(0) is None
        assert ctrl._registry.session_count == 0
        assert ctrl.discard_view_on_pane_reset(0) is False  # idempotent

    def test_clear_subwindow_content_removes_the_view_instead_of_parking(self) -> None:
        app = _app_with_mpr_pane(is_mpr=True)
        clear_subwindow_content(app, 0)
        app._mpr_controller.clear_mpr.assert_called_once_with(0)
        app._mpr_controller.detach_mpr_from_subwindow.assert_not_called()
