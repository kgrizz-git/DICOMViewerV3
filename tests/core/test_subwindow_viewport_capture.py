"""
Tests for viewport center capture before coalesced layout/focus resize.

Ensures every visible subwindow's ViewStateManager receives handle_viewport_resizing
when scheduling the viewport-resized timer, so pan can be restored after refit.
"""

from unittest.mock import MagicMock, patch


def _subwindow(visible: bool = True):
    sw = MagicMock()
    sw.isVisible.return_value = visible
    return sw


def _make_controller_with_two_panes():
    """Minimal app + controller with two visible panes and VSM mocks."""
    sw0, sw1 = _subwindow(True), _subwindow(True)
    app = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = [sw0, sw1]

    vsm0 = MagicMock()
    vsm1 = MagicMock()
    app.subwindow_managers = {
        0: {"view_state_manager": vsm0},
        1: {"view_state_manager": vsm1},
    }

    with patch("core.subwindow_lifecycle_controller.QTimer"):
        from core.subwindow_lifecycle_controller import SubwindowLifecycleController

        ctrl = SubwindowLifecycleController.__new__(SubwindowLifecycleController)
        ctrl.app = app
        ctrl._histogram_slots = {}
        ctrl._mpr_open_slots = {}
        ctrl._mpr_clear_slots = {}
        ctrl._clear_window_slots = {}
        ctrl._cine_toggle_slots = {}
        ctrl._cine_stop_slots = {}
        ctrl._viewport_resized_timer = None

    return ctrl, vsm0, vsm1


class TestViewportCenterCapture:
    def test_capture_calls_all_visible_managers(self):
        ctrl, vsm0, vsm1 = _make_controller_with_two_panes()
        ctrl._capture_viewport_centers_for_visible_subwindows()
        vsm0.handle_viewport_resizing.assert_called_once()
        vsm1.handle_viewport_resizing.assert_called_once()

    def test_capture_skips_invisible_and_missing_managers(self):
        sw0, sw1, sw2 = _subwindow(True), _subwindow(False), _subwindow(True)
        app = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [sw0, sw1, sw2]
        vsm0 = MagicMock()
        vsm2 = MagicMock()
        app.subwindow_managers = {
            0: {"view_state_manager": vsm0},
            # idx 1 invisible — skipped
            2: {"view_state_manager": vsm2},
        }
        with patch("core.subwindow_lifecycle_controller.QTimer"):
            from core.subwindow_lifecycle_controller import SubwindowLifecycleController

            ctrl = SubwindowLifecycleController.__new__(SubwindowLifecycleController)
            ctrl.app = app
            ctrl._histogram_slots = {}
            ctrl._mpr_open_slots = {}
            ctrl._mpr_clear_slots = {}
            ctrl._clear_window_slots = {}
            ctrl._cine_toggle_slots = {}
            ctrl._cine_stop_slots = {}
            ctrl._viewport_resized_timer = None

        ctrl._capture_viewport_centers_for_visible_subwindows()
        vsm0.handle_viewport_resizing.assert_called_once()
        vsm2.handle_viewport_resizing.assert_called_once()

    def test_schedule_viewport_timer_calls_capture_first(self):
        ctrl, vsm0, vsm1 = _make_controller_with_two_panes()
        call_order = []

        def track0():
            call_order.append("vsm0")

        def track1():
            call_order.append("vsm1")

        vsm0.handle_viewport_resizing.side_effect = track0
        vsm1.handle_viewport_resizing.side_effect = track1

        mock_timer = MagicMock()
        mock_timer.isActive.return_value = False

        with patch("core.subwindow_lifecycle_controller.QTimer", return_value=mock_timer):
            ctrl._schedule_viewport_resized_timer()

        assert "vsm0" in call_order and "vsm1" in call_order
        assert call_order.index("vsm0") < call_order.index("vsm1")
        mock_timer.start.assert_called_once()
