"""Keep a tool window in front of the main window while the app is active.

Option B of ``dev-docs/plans/3D_WINDOW_AND_HISTOGRAM_KEEP_IN_FRONT_PLAN.md``:
the window gets ``WindowStaysOnTopHint`` while the application is active and
loses it when the application goes inactive, so it never floats above other
applications. Phase 0 showed that timed re-raises lose a race with macOS after
Mission Control or an app switch; a window level is enforced by the window
manager instead.

The flag is changed on the native ``QWindow`` (``windowHandle()``), not with
``QWidget.setWindowFlags``. The widget call hides and re-creates the window,
which would drop the minimized state and can steal focus.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget

from utils.debug_flags import DEBUG_WINDOW_STACKING


def _trace(message: str) -> None:
    if DEBUG_WINDOW_STACKING:
        from gui.window_stacking_debug import trace

        trace(message)


class AppScopedStayOnTop(QObject):
    """Toggle stay-on-top on *window* with the application's active state."""

    def __init__(
        self, window: QWidget, *, enabled: Callable[[], bool] = lambda: True
    ) -> None:
        super().__init__(window)
        self._window = window
        self._enabled = enabled
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.applicationStateChanged.connect(self._on_state_changed)
            self.apply(app.applicationState() == Qt.ApplicationState.ApplicationActive)

    def _on_state_changed(self, state: Qt.ApplicationState) -> None:
        self.apply(state == Qt.ApplicationState.ApplicationActive)

    def apply(self, app_active: bool) -> None:
        """Set the native stay-on-top flag for the current app state."""
        on = bool(app_active and self._enabled())
        handle = self._window.windowHandle()
        if handle is None:
            return  # not shown yet; refresh() runs again from showEvent
        if bool(handle.flags() & Qt.WindowType.WindowStaysOnTopHint) == on:
            return
        handle.setFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        _trace(f"stay-on-top {'on' if on else 'off'} for {type(self._window).__name__}")

    def refresh(self) -> None:
        """Re-apply for the current app state (call after the window is shown)."""
        app = QApplication.instance()
        active = isinstance(app, QApplication) and (
            app.applicationState() == Qt.ApplicationState.ApplicationActive
        )
        self.apply(active)
