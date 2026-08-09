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


def test_sync_mode_multiple_visible_subwindows_and_no_layout_widget() -> None:
    """Test sync_mode when multiple subwindows are visible and layout_widget is None."""
    sub0 = MagicMock()
    sub0.isVisible.return_value = True
    sub0.image_viewer.cursor.return_value = "cursor0"

    sub1 = MagicMock()
    sub1.isVisible.return_value = True
    sub1.image_viewer.cursor.return_value = "cursor1"

    layout = MagicMock()
    layout.layout_widget = None
    layout.get_all_subwindows.return_value = [sub0, sub1]

    h = _handler(layout=layout)
    h.handle_mouse_mode_changed("pan")

    sub0.image_viewer.set_mouse_mode.assert_called_once_with("pan")
    sub1.image_viewer.set_mouse_mode.assert_called_once_with("pan")
    # tool_cursor set from sub0 ("cursor0")
    layout.setCursor.assert_called_once_with("cursor0")


def test_sync_mode_no_visible_subwindows_tool_cursor_none() -> None:
    """Test sync_mode when no subwindows are visible (tool_cursor remains None)."""
    sub0 = MagicMock()
    sub0.isVisible.return_value = False

    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub0, None]

    h = _handler(layout=layout)
    h.handle_mouse_mode_changed("zoom")

    sub0.image_viewer.set_mouse_mode.assert_not_called()
    layout.setCursor.assert_not_called()


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


def test_flaw_select_mode_sets_explicit_cursor_instead_of_unsetCursor() -> None:
    """Document flaw: switching to 'select' mode calls setCursor on layout instead of unsetCursor."""
    sub = MagicMock()
    sub.isVisible.return_value = True
    sub.image_viewer.cursor.return_value = "arrow_cursor"

    layout = MagicMock()
    layout.get_all_subwindows.return_value = [sub]

    h = _handler(layout=layout)
    h.handle_mouse_mode_changed("select")

    # Documents flaw: setCursor is called on layout instead of unsetCursor
    layout.setCursor.assert_called_once_with("arrow_cursor")
    layout.unsetCursor.assert_not_called()


def test_flaw_visible_subwindow_with_null_image_viewer_skipped() -> None:
    """Document flaw: visible subwindow with image_viewer=None is skipped, leaving stale cursor."""
    empty_sub = MagicMock()
    empty_sub.isVisible.return_value = True
    empty_sub.image_viewer = None  # Empty grid slot

    layout = MagicMock()
    layout.get_all_subwindows.return_value = [empty_sub]

    h = _handler(layout=layout)
    h.handle_mouse_mode_changed("pan")

    # Documents flaw: empty_sub.setCursor is never called to update/reset container cursor
    empty_sub.setCursor.assert_not_called()
