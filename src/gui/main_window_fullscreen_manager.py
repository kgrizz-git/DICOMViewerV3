"""
Main-window fullscreen manager (refactor Extraction #5).

Owns the View → Fullscreen chrome snapshot/restore state: collapsing the
side panes, hiding the series-navigator bar and main toolbar on entry, and
restoring them on exit — whether exit is triggered by the app's own
``set_fullscreen(False)``, the OS taking the window out of fullscreen (e.g.
green-button / Escape on macOS, delivered as a ``QEvent.WindowStateChange``
to ``MainWindow.changeEvent``), or the window closing while fullscreen.

Extracted from ``gui/main_window.py`` so the window stays a layout + signal
surface, mirroring ``main_window_toast_controller`` and
``main_window_recent_files_manager``. The snapshot is in-memory only and is
never written to config defaults, so leaving fullscreen never persists the
forced-narrow splitter/hidden-chrome layout as the user's normal layout.

Ownership: constructed once in ``MainWindow.__init__`` and stored as
``main_window._fullscreen``. ``MainWindow`` keeps thin wrapper methods
(``set_fullscreen``, ``_take_fullscreen_snapshot``,
``_apply_fullscreen_chrome_hidden``, ``_restore_fullscreen_chrome``, and the
``_fullscreen_snapshot`` property) that delegate to this manager for
backward compatibility with ``main_window_menu_builder``, external callers
(e.g. ``main_app_key_event_filter``), and the
``tests/test_main_window_fullscreen.py`` characterization tests.

Inputs:
    - ``parent``: the ``MainWindow`` instance. Duck-typed (no import of
      ``MainWindow`` or the ``main`` package, avoiding a circular import
      since ``main_window.py`` imports this module) — accessed only via the
      attributes/methods it is documented to expose: ``splitter``,
      ``main_toolbar`` (may not exist yet), ``series_navigator_container``
      (may not exist yet), ``show_left_pane_action``,
      ``show_right_pane_action``, ``show_series_navigator_action``,
      ``fullscreen_action``, ``series_navigator_visible``,
      ``viewport_resizing``/``viewport_resized`` signals, and the
      ``QMainWindow`` fullscreen methods (``isFullScreen``, ``isMaximized``,
      ``showFullScreen``, ``showNormal``, ``showMaximized``).

Outputs:
    - Mutates the parent's splitter sizes, pane/toolbar/navigator visibility,
      and related View-menu checkbox state; toggles the parent's window
      state (fullscreen/normal/maximized).

Requirements:
    - PySide6 (QEvent, QTimer)
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QTimer


class MainWindowFullscreenManager:
    """Owns fullscreen enter/exit chrome snapshot + restore state for MainWindow."""

    def __init__(self, parent) -> None:
        """
        Args:
            parent: The ``MainWindow`` instance. See module docstring for the
                attributes/methods this manager relies on.
        """
        self._parent = parent
        self._snapshot: dict[str, Any] | None = None
        self._transitioning = False

    @property
    def snapshot(self) -> dict[str, Any] | None:
        """Current in-memory chrome snapshot, or ``None`` when not in fullscreen."""
        return self._snapshot

    @snapshot.setter
    def snapshot(self, value: dict[str, Any] | None) -> None:
        self._snapshot = value

    @property
    def is_fullscreen(self) -> bool:
        """Whether the parent window currently reports fullscreen state."""
        return bool(self._parent.isFullScreen())

    def take_snapshot(self) -> dict[str, Any]:
        """Capture splitter sizes, navigator bar, and toolbar visibility before entering fullscreen."""
        parent = self._parent
        container = getattr(parent, "series_navigator_container", None)
        bar_visible = bool(container.isVisible()) if container is not None else False
        toolbar = getattr(parent, "main_toolbar", None)
        toolbar_vis = toolbar.isVisible() if toolbar is not None else True
        return {
            "splitter_sizes": list(parent.splitter.sizes()),
            "series_navigator_bar_visible": bar_visible,
            "toolbar_visible": toolbar_vis,
            "was_maximized": parent.isMaximized(),
        }

    def apply_chrome_hidden(self) -> None:
        """Collapse side panes, hide bottom navigator bar and main toolbar (no config persist)."""
        parent = self._parent
        sizes = parent.splitter.sizes()
        parent.viewport_resizing.emit()
        if len(sizes) == 3:
            total = max(sizes[0] + sizes[1] + sizes[2], 1)
            parent.splitter.setSizes([0, total, 0])
            if parent.show_left_pane_action is not None:
                parent.show_left_pane_action.setChecked(False)
            if parent.show_right_pane_action is not None:
                parent.show_right_pane_action.setChecked(False)
        container = getattr(parent, "series_navigator_container", None)
        if container is not None:
            container.setVisible(False)
        toolbar = getattr(parent, "main_toolbar", None)
        if toolbar is not None:
            toolbar.hide()
        QTimer.singleShot(10, lambda: parent.viewport_resized.emit())

    def restore_chrome(self, snap: dict[str, Any]) -> None:
        """Restore splitter, navigator bar, toolbar, and View menu checks from *snap*."""
        parent = self._parent
        parent.viewport_resizing.emit()
        restored: list[int] = list(snap.get("splitter_sizes", []))
        if len(restored) == 3:
            parent.splitter.setSizes(restored)
            if parent.show_left_pane_action is not None:
                parent.show_left_pane_action.setChecked(restored[0] > 0)
            if parent.show_right_pane_action is not None:
                parent.show_right_pane_action.setChecked(restored[2] > 0)
        bar_vis = bool(snap.get("series_navigator_bar_visible", False))
        parent.series_navigator_visible = bar_vis
        container = getattr(parent, "series_navigator_container", None)
        if container is not None:
            container.setVisible(bar_vis)
        if parent.show_series_navigator_action is not None:
            parent.show_series_navigator_action.setChecked(bar_vis)
        tb_vis = bool(snap.get("toolbar_visible", True))
        toolbar = getattr(parent, "main_toolbar", None)
        if toolbar is not None:
            toolbar.setVisible(tb_vis)
        QTimer.singleShot(10, lambda: parent.viewport_resized.emit())

    def enter_fullscreen(self) -> None:
        """Snapshot chrome, hide it, and switch the parent window to fullscreen."""
        parent = self._parent
        if parent.isFullScreen():
            if parent.fullscreen_action is not None:
                parent.fullscreen_action.setChecked(True)
            return
        self._transitioning = True
        try:
            self._snapshot = self.take_snapshot()
            self.apply_chrome_hidden()
            parent.showFullScreen()
            if parent.fullscreen_action is not None:
                parent.fullscreen_action.setChecked(True)
        finally:
            self._transitioning = False

    def exit_fullscreen(self) -> None:
        """Leave fullscreen and restore chrome from the snapshot (if any)."""
        parent = self._parent
        self._transitioning = True
        try:
            snap = self._snapshot
            self._snapshot = None
            parent.showNormal()
            if snap is not None and snap.get("was_maximized"):
                parent.showMaximized()
            if snap is not None:
                self.restore_chrome(snap)
            if parent.fullscreen_action is not None:
                parent.fullscreen_action.setChecked(False)
        finally:
            self._transitioning = False

    def set_fullscreen(self, enable: bool) -> None:
        """
        Enter or leave application fullscreen.

        Entering hides left/right panes, the series navigator bar, and the main toolbar
        using a snapshot so leaving restores prior layout without persisting fullscreen
        as user defaults.
        """
        if enable:
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def handle_change_event(self, event: QEvent) -> bool:
        """
        Restore chrome if the OS took the window out of fullscreen.

        Called from ``MainWindow.changeEvent`` (after ``super().changeEvent(event)``
        has already run — this manager does not gate that call). Returns ``True``
        if this manager consumed the event (restored chrome), ``False`` for
        non-``WindowStateChange`` events, re-entrant calls during our own
        transition, or ``WindowStateChange`` events that are not an OS-driven
        fullscreen exit.
        """
        if event.type() != QEvent.Type.WindowStateChange:
            return False
        if self._transitioning:
            return False
        parent = self._parent
        if not parent.isFullScreen() and self._snapshot is not None:
            self._transitioning = True
            try:
                snap = self._snapshot
                self._snapshot = None
                if snap is not None:
                    self.restore_chrome(snap)
                if parent.fullscreen_action is not None:
                    parent.fullscreen_action.setChecked(False)
            finally:
                self._transitioning = False
            return True
        return False

    def restore_on_close(self) -> None:
        """
        Restore chrome before geometry is persisted in ``closeEvent``.

        Note the restore-vs-``showMaximized`` ordering here intentionally
        differs from :meth:`exit_fullscreen` (which restores chrome *after*
        ``showMaximized``) — this matches pre-extraction ``closeEvent``
        behavior exactly and is not a re-entrancy-guarded transition (the
        window is closing either way).
        """
        parent = self._parent
        if parent.isFullScreen():
            snap = self._snapshot
            self._snapshot = None
            parent.showNormal()
            if snap is not None:
                self.restore_chrome(snap)
                if snap.get("was_maximized"):
                    parent.showMaximized()
            if parent.fullscreen_action is not None:
                parent.fullscreen_action.setChecked(False)
        elif self._snapshot is not None:
            snap = self._snapshot
            self._snapshot = None
            self.restore_chrome(snap)
