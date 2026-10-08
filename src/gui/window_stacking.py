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
import weakref
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
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


class _ModalWatcher(QObject):
    """One application-wide filter that tells every helper when a modal comes or goes.

    ``focusWindowChanged`` alone misses a modal that never takes focus and the
    moment a modal closes, so watch Show/Hide/Close of modal top-level widgets
    and re-evaluate after Qt has updated its modal stack.
    """

    _WATCHED = (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Close)

    def __init__(self) -> None:
        super().__init__()
        self._helpers: weakref.WeakSet[AppScopedStayOnTop] = weakref.WeakSet()

    def register(self, helper: AppScopedStayOnTop) -> None:
        if not self._helpers:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
        self._helpers.add(helper)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in self._WATCHED and isinstance(watched, QWidget):
            if watched.isWindow() and watched.windowModality() != Qt.WindowModality.NonModal:
                if event.type() == QEvent.Type.Show and not watched.property("_stackWatch"):
                    watched.setProperty("_stackWatch", True)
                    watched.destroyed.connect(self._schedule)
                self._schedule()
        return False

    def _schedule(self, *_args: object) -> None:
        QTimer.singleShot(0, self._notify)

    def _notify(self) -> None:
        for helper in list(self._helpers):
            try:
                helper._reapply()
            except RuntimeError:  # its window was deleted
                self._helpers.discard(helper)


_modal_watcher: _ModalWatcher | None = None


def _watcher() -> _ModalWatcher:
    global _modal_watcher
    if _modal_watcher is None:
        _modal_watcher = _ModalWatcher()
    return _modal_watcher


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
        # Entries are dropped when they reach zero.
        self._block_depth: dict[QObject, int] = {}
        window.installEventFilter(self)
        depths = self._block_depth
        window.destroyed.connect(depths.clear)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.applicationStateChanged.connect(self._on_state_changed)
            # A window-modal dialog on another window sends no WindowBlocked
            # to a parentless tool window, so also watch the modal stack.
            app.focusWindowChanged.connect(self._on_focus_window_changed)
            _watcher().register(self)
        self._watched_handles: list[object] = []
        self._reapply()

    def is_blocked(self) -> bool:
        """Return True while Qt reports an application-modal window blocking the tool window."""
        return bool(self._block_depth)

    def _modal_other_active(self) -> bool:
        """True while a modal widget other than this window (or its children) is up."""
        modal = QApplication.activeModalWidget()
        # isAncestorOf() stops at window boundaries, so walk the parent chain.
        node: QWidget | None = modal
        while node is not None:
            if node is self._window:
                return False
            node = node.parentWidget()
        return modal is not None

    def suppressed(self) -> bool:
        """True while the tool window must not cover or raise over a modal prompt."""
        return self.is_blocked() or self._modal_other_active()

    def _on_focus_window_changed(self, _window: object) -> None:
        self._reapply()

    def _on_state_changed(self, state: Qt.ApplicationState) -> None:
        self._app_active = state == Qt.ApplicationState.ApplicationActive
        self._reapply()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        kind = event.type()
        if kind == QEvent.Type.WindowBlocked:
            self._block_depth[watched] = self._block_depth.get(watched, 0) + 1
            _trace(f"{type(self._window).__name__} blocked by modal")
            self._reapply()
        elif kind == QEvent.Type.WindowUnblocked:
            depth = self._block_depth.get(watched, 0) - 1
            if depth > 0:
                self._block_depth[watched] = depth
            else:
                self._block_depth.pop(watched, None)
            _trace(f"{type(self._window).__name__} unblocked")
            self._reapply()
        elif kind == QEvent.Type.Hide and watched is self._window:
            # An unblock may never be delivered to a hidden window.
            self._block_depth.clear()
        return False

    def _reapply(self) -> None:
        on = bool(self._app_active and not self.suppressed() and self._enabled())
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

    def _forget_handle(self, handle: object) -> None:
        """Forget a destroyed native window so its wrapper is not kept alive."""
        self._block_depth.pop(handle, None)
        self._watched_handles = [h for h in self._watched_handles if h is not handle]

    def on_shown(self) -> None:
        """Call from the window's ``showEvent``: the native handle now exists."""
        handle = self._window.windowHandle()
        if handle is not None:
            handle.installEventFilter(self)
            if not any(h is handle for h in self._watched_handles):
                self._watched_handles.append(handle)
                # Drop a destroyed QWindow's block entry; no unblock will follow.
                handle.destroyed.connect(lambda *_a, h=handle: self._forget_handle(h))
        self._reapply()  # uses the app state tracked via applicationStateChanged
