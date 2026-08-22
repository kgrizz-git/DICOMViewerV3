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
    """Push a converted Qt pointer position and modifier state into VTK."""
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
