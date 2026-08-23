"""Bridge Qt input events into a ``vtkGenericRenderWindowInteractor``.

The offscreen render surface has no native VTK window, so VTK never receives
input on its own.  Binding a *generic* interactor to the offscreen render
window and forwarding Qt events into it keeps the stock
``vtkInteractorStyleTrackballCamera`` — and, importantly, VTK 3D widgets such
as ``vtkBoxWidget2`` (the crop box), which require a real interactor.

Coordinate systems differ and must be converted:
    Qt    — origin top-left, logical (device-independent) units.
    VTK   — origin bottom-left, device pixels.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt


def qt_to_vtk_position(
    x: float, y: float, *, height_px: int, ratio: float
) -> tuple[int, int]:
    """Convert a Qt widget position to VTK interactor coordinates.

    Args:
        x: Qt x in logical units (origin top-left).
        y: Qt y in logical units (origin top-left).
        height_px: Render-window height in device pixels.
        ratio: Device pixel ratio of the hosting widget.

    Returns:
        ``(x_px, y_px)`` in device pixels with the origin at the bottom-left.
    """
    scale = ratio or 1.0
    x_px = int(x * scale)
    # VTK's origin is the bottom-left, so the y axis is inverted.
    y_px = int(height_px - (y * scale))
    return x_px, y_px


def modifier_flags(modifiers: Qt.KeyboardModifier) -> tuple[int, int]:
    """Return ``(ctrl, shift)`` as the 0/1 ints VTK's interactor expects."""
    ctrl = int(bool(modifiers & Qt.KeyboardModifier.ControlModifier))
    shift = int(bool(modifiers & Qt.KeyboardModifier.ShiftModifier))
    return ctrl, shift


def create_interactor(render_window: Any) -> Any:
    """Create and initialise a generic interactor bound to *render_window*."""
    import vtkmodules.all as vtk_mod

    interactor = vtk_mod.vtkGenericRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    interactor.SetInteractorStyle(vtk_mod.vtkInteractorStyleTrackballCamera())
    interactor.Initialize()
    return interactor


def set_event_information(
    interactor: Any,
    *,
    x: float,
    y: float,
    height_px: int,
    ratio: float,
    modifiers: Qt.KeyboardModifier,
    key: str = chr(0),
) -> None:
    """Push a converted Qt pointer position and modifier state into VTK.

    Sets the *current* position only.  ``vtkInteractorStyleTrackballCamera``
    derives rotation from the delta between ``EventPosition`` and
    ``LastPosition``, and the interactor rolls the former into the latter inside
    its own ``MouseMoveEvent()``.  Do **not** "fix" this by also calling
    ``SetLastEventPosition`` — that collapses the delta to zero and rotation
    stops working.
    """
    x_px, y_px = qt_to_vtk_position(x, y, height_px=height_px, ratio=ratio)
    ctrl, shift = modifier_flags(modifiers)
    interactor.SetEventInformation(x_px, y_px, ctrl, shift, key, 0, None)


# Qt button -> (press_method, release_method) on the VTK interactor.
_BUTTON_EVENTS: dict[Qt.MouseButton, tuple[str, str]] = {
    Qt.MouseButton.LeftButton: ("LeftButtonPressEvent", "LeftButtonReleaseEvent"),
    Qt.MouseButton.MiddleButton: ("MiddleButtonPressEvent", "MiddleButtonReleaseEvent"),
    Qt.MouseButton.RightButton: ("RightButtonPressEvent", "RightButtonReleaseEvent"),
}


def button_event_names(button: Qt.MouseButton) -> tuple[str, str] | None:
    """Return the VTK press/release event names for a Qt mouse button."""
    return _BUTTON_EVENTS.get(button)


# Qt key -> VTK keysym name.  The native ``QVTKRenderWindowInteractor`` produced
# X11-style keysyms, and the viewer's key handler matches against those names.
# Forwarding ``event.text()`` alone yields the literal character ("+", "]", " "),
# which silently breaks every shortcut bound to a named key.
_QT_KEY_TO_KEYSYM: dict[int, str] = {
    # Escape is intentionally absent: the hosting dialog needs it to close.
    Qt.Key.Key_Space.value: "space",
    Qt.Key.Key_Plus.value: "plus",
    Qt.Key.Key_Equal.value: "equal",
    Qt.Key.Key_Minus.value: "minus",
    Qt.Key.Key_Underscore.value: "underscore",
    Qt.Key.Key_BracketLeft.value: "bracketleft",
    Qt.Key.Key_BracketRight.value: "bracketright",
    Qt.Key.Key_Return.value: "Return",
    Qt.Key.Key_Enter.value: "Return",
    Qt.Key.Key_Tab.value: "Tab",
    Qt.Key.Key_Backspace.value: "BackSpace",
    Qt.Key.Key_Delete.value: "Delete",
    Qt.Key.Key_Left.value: "Left",
    Qt.Key.Key_Right.value: "Right",
    Qt.Key.Key_Up.value: "Up",
    Qt.Key.Key_Down.value: "Down",
}


def qt_key_to_vtk_keysym(key: int, text: str) -> str:
    """Return the VTK keysym name for a Qt key/text pair.

    Named keys (space, plus, brackets, ...) map to their X11 keysym names, which
    is what the viewer's shortcut handler compares against.  Everything else
    falls back to the typed character, matching VTK's behaviour for letters and
    digits.
    """
    keysym = _QT_KEY_TO_KEYSYM.get(key)
    if keysym is not None:
        return keysym
    return text[:1] if text else ""
