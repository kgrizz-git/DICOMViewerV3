"""
Main application ``QObject.eventFilter`` key routing.

Handles:
    - Letting Ctrl/Cmd+Z reach the menu shortcut system.
    - Escape exits application fullscreen when no modal is active and focus is not
      in a text field or spin box (see ``_escape_may_exit_fullscreen``).
    - Restricting layout hotkeys (1–4) to when focus lives under allowed panes
      (series navigator, left/right panels, image viewers).
    - Delegating other keys to ``KeyboardEventHandler``.

Extracted from ``main.py`` so shortcut policy stays in one module. Manual regression:
    - With focus in the image view, keys 1–4 change layout; with focus in a modal
      line edit, they should not steal digits.
    - Undo/redo shortcuts still work from the menu.

Inputs:
    - ``app``: ``DICOMViewerApp`` (``series_navigator``, ``main_window``,
      ``keyboard_event_handler``)
    - ``event``: Qt event from ``eventFilter``

Outputs:
    - ``None`` if this helper does not handle the event type (caller should use
      ``super().eventFilter``).
    - Otherwise a ``bool`` suitable as the ``eventFilter`` return value.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit, QPlainTextEdit, QTextEdit

from gui.image_viewer import ImageViewer


def _escape_may_exit_fullscreen(app: Any) -> bool:
    """
    Return True if Escape should leave application fullscreen.

    Skips when a modal dialog is active or when keyboard focus is in a text or
    spin entry so inline editors keep Escape for cancel/clear semantics.
    """
    mw = app.main_window
    if not mw.isFullScreen():
        return False
    if QApplication.activeModalWidget() is not None:
        return False
    fw = QApplication.focusWidget()
    if fw is None:
        return True
    if isinstance(fw, (QLineEdit, QTextEdit, QPlainTextEdit)):
        return False
    if isinstance(fw, QAbstractSpinBox):
        return False
    return True


def is_widget_allowed_for_layout_shortcuts(app: Any, widget: Optional[Any]) -> bool:
    """
    Return True if ``widget`` (or an ancestor within depth limit) is part of an
    allowed subtree for layout digit shortcuts.
    """
    if widget is None:
        return False

    current = widget
    max_depth = 10
    depth = 0

    while current is not None and depth < max_depth:
        if current == app.series_navigator:
            return True

        if hasattr(app.main_window, "left_panel") and current == app.main_window.left_panel:
            return True

        if hasattr(app.main_window, "right_panel") and current == app.main_window.right_panel:
            return True

        if isinstance(current, ImageViewer):
            return True

        if hasattr(current, "objectName"):
            obj_name = current.objectName()
            if obj_name == "left_panel" or obj_name == "right_panel":
                return True

        current = current.parentWidget()
        depth += 1

    return False


def dispatch_app_key_event(app: Any, event: Any) -> Optional[bool]:
    """
    Process a key event for the main app filter.

    Returns ``None`` if ``event`` is not a ``QKeyEvent`` (caller should fall through
    to ``super().eventFilter``).
    """
    if not isinstance(event, QKeyEvent):
        return None

    if (
        event.type() == QKeyEvent.Type.KeyPress
        and event.key() == Qt.Key.Key_Escape
        and _escape_may_exit_fullscreen(app)
    ):
        app.main_window.set_fullscreen(False)
        return True

    if event.key() == Qt.Key.Key_Z:
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        ):
            return False

    if event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4):
        focused_widget = QApplication.focusWidget()
        if focused_widget is not None:
            if not is_widget_allowed_for_layout_shortcuts(app, focused_widget):
                return False

    return app.keyboard_event_handler.handle_key_event(event)
