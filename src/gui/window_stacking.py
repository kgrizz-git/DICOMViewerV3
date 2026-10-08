"""Keep a tool window in front of the main window while the app is active.

Option B of ``dev-docs/plans/completed/3D_WINDOW_AND_HISTOGRAM_KEEP_IN_FRONT_PLAN.md``:
the window gets ``WindowStaysOnTopHint`` while the application is active and
loses it when the application goes inactive, so it never floats above other
applications. Phase 0 showed that timed re-raises lose a race with macOS after
Mission Control or an app switch; a window level is enforced by the window
manager instead.

The flag is changed on the native ``QWindow`` (``windowHandle()``), not with
``QWidget.setWindowFlags``. The widget call hides and re-creates the window,
which would drop the minimized state and can steal focus.

A stay-on-top window would cover the application's own modal dialogs, so the
flag is also cleared while Qt reports the window as blocked by a modal
(``QEvent.WindowBlocked`` / ``WindowUnblocked``) and restored afterwards.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget

from utils.debug_flags import DEBUG_WINDOW_STACKING


def _trace(message: str) -> None:
    if DEBUG_WINDOW_STACKING:
        from gui.window_stacking_debug import trace

        trace(message)


def _current_platform() -> str:
    """Return ``sys.platform`` (a seam so tests can simulate other platforms)."""
    return sys.platform


def platform_supports_stay_on_top() -> bool:
    """Return whether app-scoped stay-on-top may be used on this platform.

    Option B is not shipped on Windows until its native check passes (see the
    keep-in-front plan); Windows keeps the ``WindowActivate`` raise instead.
    """
    return _current_platform() != "win32"


def _app_is_active() -> bool:
    app = QApplication.instance()
    return isinstance(app, QApplication) and (
        app.applicationState() == Qt.ApplicationState.ApplicationActive
    )


class AppScopedStayOnTop(QObject):
    """Toggle stay-on-top on *window* with the application's active state."""

    def __init__(
        self, window: QWidget, *, enabled: Callable[[], bool] = lambda: True
    ) -> None:
        super().__init__(window)
        self._window = window
        self._enabled = enabled
        self._app_active = _app_is_active()
        # Block depth per event source (widget and native window may both
        # report the same transition, so sources are tracked separately).
        self._block_depth: dict[int, int] = {}
        window.installEventFilter(self)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.applicationStateChanged.connect(self._on_state_changed)
        self._reapply()

    def is_blocked(self) -> bool:
        """Return True while an application-modal window blocks the tool window."""
        return any(depth > 0 for depth in self._block_depth.values())

    def _on_state_changed(self, state: Qt.ApplicationState) -> None:
        self._app_active = state == Qt.ApplicationState.ApplicationActive
        self._reapply()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.WindowBlocked:
            key = id(watched)
            self._block_depth[key] = self._block_depth.get(key, 0) + 1
            _trace(f"{type(self._window).__name__} blocked by modal")
            self._reapply()
        elif kind == QEvent.Type.WindowUnblocked:
            key = id(watched)
            self._block_depth[key] = max(0, self._block_depth.get(key, 0) - 1)
            _trace(f"{type(self._window).__name__} unblocked")
            self._reapply()
        return False

    def _reapply(self) -> None:
        on = bool(self._app_active and not self.is_blocked() and self._enabled())
        handle = self._window.windowHandle()
        if handle is None:
            return  # not shown yet; on_shown() runs again from showEvent
        if bool(handle.flags() & Qt.WindowType.WindowStaysOnTopHint) == on:
            return
        handle.setFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        _trace(f"stay-on-top {'on' if on else 'off'} for {type(self._window).__name__}")

    def apply(self, app_active: bool) -> None:
        """Set the app-active state and update the native flag."""
        self._app_active = app_active
        self._reapply()

    def refresh(self) -> None:
        """Re-read the enabled callback and app state, then update the flag."""
        self._app_active = _app_is_active()
        self._reapply()

    def on_shown(self) -> None:
        """Call from the window's ``showEvent``: the native handle now exists."""
        handle = self._window.windowHandle()
        if handle is not None:
            handle.installEventFilter(self)
        self._reapply()  # uses the app state tracked via applicationStateChanged
