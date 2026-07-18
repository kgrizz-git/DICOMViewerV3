"""Tests for gui.mouse_mode_handler.MouseModeHandler (orchestration only)."""

from __future__ import annotations

from unittest.mock import MagicMock

from gui.mouse_mode_handler import MouseModeHandler


def _handler(layout=None) -> MouseModeHandler:
    return MouseModeHandler(
        image_viewer=MagicMock(),
        main_window=MagicMock(),
        slice_navigator=MagicMock(),
        config_manager=MagicMock(),
        multi_window_layout=layout,
    )


def test_sync_mode_no_layout_uses_image_viewer() -> None:
    h = _handler(layout=None)
    h.handle_mouse_mode_changed("pan")
    h.image_viewer.set_mouse_mode.assert_called_once_with("pan")


def test_sync_mode_with_layout_sets_visible_subwindows() -> None:
    visible = MagicMock()
    visible.isVisible.return_value = True
    hidden = MagicMock()
    hidden.isVisible.return_value = False
    layout = MagicMock()
    layout.get_all_subwindows.return_value = [visible, hidden, None]
    h = _handler(layout=layout)

    h.handle_mouse_mode_changed("zoom")

    visible.image_viewer.set_mouse_mode.assert_called_once_with("zoom")
    hidden.image_viewer.set_mouse_mode.assert_not_called()
    layout.setCursor.assert_called_once()
    layout.layout_widget.setCursor.assert_called_once()


def test_set_mouse_mode_updates_toolbar() -> None:
    h = _handler()
    h.set_mouse_mode("select")
    h.image_viewer.set_mouse_mode.assert_called_once_with("select")
    h.main_window.set_mouse_mode_checked.assert_called_once_with("select")


def test_set_roi_mode() -> None:
    h = _handler()
    h.set_roi_mode("ellipse")
    h.image_viewer.set_roi_drawing_mode.assert_called_once_with("ellipse")


def test_context_menu_mouse_mode_delegates_to_main_window() -> None:
    h = _handler()
    h.handle_context_menu_mouse_mode_changed("measure")
    h.main_window._on_mouse_mode_changed.assert_called_once_with("measure")


def test_scroll_wheel_mode_changed_updates_all() -> None:
    h = _handler()
    h.handle_scroll_wheel_mode_changed("zoom")
    h.config_manager.set_scroll_wheel_mode.assert_called_once_with("zoom")
    h.image_viewer.set_scroll_wheel_mode.assert_called_once_with("zoom")
    h.slice_navigator.set_scroll_wheel_mode.assert_called_once_with("zoom")


def test_context_menu_scroll_wheel_slice_sets_combo_and_emits() -> None:
    h = _handler()
    combo = MagicMock()
    h.main_window.scroll_wheel_mode_combo = combo
    h.handle_context_menu_scroll_wheel_mode_changed("slice")
    combo.setCurrentText.assert_called_once_with("Slice")
    h.main_window.scroll_wheel_mode_changed.emit.assert_called_once_with("slice")


def test_context_menu_scroll_wheel_zoom_sets_combo() -> None:
    h = _handler()
    combo = MagicMock()
    h.main_window.scroll_wheel_mode_combo = combo
    h.handle_context_menu_scroll_wheel_mode_changed("zoom")
    combo.setCurrentText.assert_called_once_with("Zoom")


def test_context_menu_scroll_wheel_no_combo() -> None:
    h = _handler()
    h.main_window.scroll_wheel_mode_combo = None
    # Should not raise when the combo is absent.
    h.handle_context_menu_scroll_wheel_mode_changed("slice")
    h.main_window.scroll_wheel_mode_changed.emit.assert_called_once_with("slice")
