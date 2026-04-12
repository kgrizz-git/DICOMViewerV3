"""
Tests for focused-subwindow keyboard callback rewiring.

Keyboard shortcuts like Space (toggle overlay) and C (clear measurements)
must follow the currently focused pane rather than staying bound to whatever
subwindow was focused during app startup.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.subwindow_lifecycle_controller import SubwindowLifecycleController


class _MeasurementCoordinatorStub:
    def _noop(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, name):
        return self._noop

    def handle_clear_measurements(self) -> None:
        pass

    def handle_measurement_delete_requested(self, item) -> None:
        pass


class _OverlayCoordinatorStub:
    def _noop(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, name):
        return self._noop

    def handle_toggle_overlay(self) -> None:
        pass


class _RoiCoordinatorStub:
    def _noop(self, *args, **kwargs) -> None:
        pass

    def __getattr__(self, name):
        return self._noop

    def delete_all_rois_current_slice(self) -> None:
        pass


class TestFocusedKeyboardCallbacks(unittest.TestCase):
    def test_connect_focused_subwindow_signals_rebinds_keyboard_callbacks(self) -> None:
        new_image_viewer = MagicMock()
        focused_subwindow = SimpleNamespace(image_viewer=new_image_viewer)

        measurement_coordinator = _MeasurementCoordinatorStub()
        overlay_coordinator = _OverlayCoordinatorStub()
        roi_coordinator = _RoiCoordinatorStub()

        keyboard_event_handler = SimpleNamespace(
            roi_manager=None,
            measurement_tool=None,
            overlay_manager=None,
            image_viewer=None,
            clear_measurements_callback=lambda: "old-clear",
            toggle_overlay_callback=lambda: "old-overlay",
            delete_measurement_callback=lambda item: "old-delete",
            delete_all_rois_callback=lambda: "old-roi-clear",
            invert_image_callback=None,
            delete_text_annotation_callback=None,
            delete_arrow_annotation_callback=None,
        )

        old_image_viewer = MagicMock()

        app = MagicMock()
        app.subwindow_managers = {
            0: {
                "view_state_manager": MagicMock(),
                "slice_display_manager": MagicMock(),
                "roi_coordinator": roi_coordinator,
                "measurement_coordinator": measurement_coordinator,
                "overlay_coordinator": overlay_coordinator,
                "roi_manager": MagicMock(),
                "measurement_tool": MagicMock(),
                "overlay_manager": MagicMock(),
            }
        }
        app.subwindow_data = {
            0: {
                "current_dataset": None,
                "current_slice_index": 0,
                "current_series_uid": "",
                "current_study_uid": "",
                "current_datasets": [],
            }
        }
        app.multi_window_layout = SimpleNamespace(
            get_focused_subwindow=lambda: focused_subwindow,
            get_all_subwindows=lambda: [focused_subwindow],
        )
        app.main_window = MagicMock()
        app.image_viewer = old_image_viewer
        app.keyboard_event_handler = keyboard_event_handler
        app.mouse_mode_handler = MagicMock()
        app.current_dataset = None
        app.current_slice_index = 0
        app.current_series_uid = ""
        app.current_study_uid = ""
        app.current_datasets = []
        app.current_studies = {}
        app.slice_navigator = MagicMock()
        app.roi_coordinator = roi_coordinator
        app.window_level_controls = MagicMock()
        app.roi_list_panel = MagicMock()
        app.text_annotation_coordinator = None
        app.arrow_annotation_coordinator = None
        app._on_pixel_info_changed = MagicMock()
        app.intensity_projection_controls_widget = MagicMock()
        app.cine_app_facade = MagicMock()
        app.zoom_display_widget = MagicMock()
        app.series_navigator = MagicMock()
        app._previous_fusion_coordinator = None
        app.main_window.get_current_mouse_mode.return_value = "pan"

        controller = SubwindowLifecycleController.__new__(SubwindowLifecycleController)
        controller.app = app
        controller.update_right_panel_for_focused_subwindow = MagicMock()
        controller.update_left_panel_for_focused_subwindow = MagicMock()
        controller.wire_pixel_info_callbacks_for_subwindow = MagicMock()
        controller.disconnect_focused_subwindow_signals = MagicMock()
        controller.redisplay_subwindow_slice = MagicMock()

        controller.update_focused_subwindow_references()
        controller.connect_focused_subwindow_signals()

        self.assertIs(keyboard_event_handler.image_viewer, new_image_viewer)
        self.assertIs(
            keyboard_event_handler.clear_measurements_callback.__self__,
            measurement_coordinator,
        )
        self.assertIs(
            keyboard_event_handler.delete_measurement_callback.__self__,
            measurement_coordinator,
        )
        self.assertIs(
            keyboard_event_handler.toggle_overlay_callback.__self__,
            overlay_coordinator,
        )
        self.assertIs(
            keyboard_event_handler.delete_all_rois_callback.__self__,
            roi_coordinator,
        )


if __name__ == "__main__":
    unittest.main()
