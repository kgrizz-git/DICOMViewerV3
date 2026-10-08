"""Phase 0 diagnostics for tool-window stacking (histogram, 3D window).

Gated by ``DEBUG_WINDOW_STACKING``. Traces, in order:

- mouse presses, with the clicked widget's class, its top-level window's
  class, and whether the click landed in a native child window;
- ``WindowActivate`` / ``WindowDeactivate`` on top-level windows;
- ``QGuiApplication.focusWindowChanged`` and ``applicationStateChanged``;
- histogram raise calls (logged from ``HistogramDialog.eventFilter``).

Privacy: only class names, object names, event types, and states are printed.
Window titles are never printed, because 3D titles carry the series
description.

See ``dev-docs/plans/3D_WINDOW_AND_HISTOGRAM_KEEP_IN_FRONT_PLAN.md`` Phase 0.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

_START = perf_counter()
_TRACED_EVENTS = {
    QEvent.Type.WindowActivate: "WindowActivate",
    QEvent.Type.WindowDeactivate: "WindowDeactivate",
}


def _stamp() -> str:
    return f"{(perf_counter() - _START) * 1000.0:9.1f}ms"


def describe(obj: Any) -> str:
    """Class name plus object name, never a window title."""
    if obj is None:
        return "None"
    name = obj.objectName() if hasattr(obj, "objectName") else ""
    return f"{type(obj).__name__}" + (f"#{name}" if name else "")


def trace(message: str) -> None:
    print(f"[DEBUG-WINDOW-STACKING] {_stamp()} {message}")


def _in_native_child(widget: QWidget) -> bool:
    current: QWidget | None = widget
    while current is not None and not current.isWindow():
        if current.testAttribute(Qt.WidgetAttribute.WA_NativeWindow):
            return True
        current = current.parentWidget()
    return False


class _StackingTracer(QObject):
    """Application-wide event filter; observes only, never consumes events."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        etype = event.type()
        if etype in _TRACED_EVENTS and isinstance(watched, QWidget) and watched.isWindow():
            trace(f"{_TRACED_EVENTS[etype]} on {describe(watched)}")
        elif etype == QEvent.Type.MouseButtonPress and isinstance(watched, QWidget):
            top = watched.window()
            trace(
                f"MouseButtonPress on {describe(watched)} in {describe(top)}"
                f" native_child={_in_native_child(watched)}"
                f" activeWindow={describe(QApplication.activeWindow())}"
            )
        return False


_installed: list[QObject] = []


def install_window_stacking_trace(app: QApplication) -> None:
    """Install the tracer once; safe to call when the flag is off (no-op caller)."""
    if _installed:
        return
    tracer = _StackingTracer()
    app.installEventFilter(tracer)
    _installed.append(tracer)

    def _focus_window_changed(window: Any) -> None:
        trace(
            f"focusWindowChanged -> {describe(window)}"
            f" activeWindow={describe(QApplication.activeWindow())}"
        )

    def _state_changed(state: Any) -> None:
        trace(f"applicationStateChanged -> {getattr(state, 'name', state)}")

    QGuiApplication.instance().focusWindowChanged.connect(_focus_window_changed)  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]
    app.applicationStateChanged.connect(_state_changed)
    trace("tracer installed")
