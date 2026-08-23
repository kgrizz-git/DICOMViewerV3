"""Keyboard shortcut dispatch for the 3D volume viewport.

Kept out of the widget so the mapping can be unit-tested without a live VTK
interactor.  Keys arrive as VTK keysym names (``"plus"``, ``"bracketright"``,
``"space"``); see :func:`gui.volume.interactor_bridge.qt_key_to_vtk_keysym`.
"""

from __future__ import annotations

from typing import Any

from gui.volume.preset_nav import preset_step_index

KEY_VIEW_MAP: dict[str, str] = {
    "1": "Anterior",
    "2": "Posterior",
    "3": "Left",
    "4": "Right",
    "5": "Superior",
    "6": "Inferior",
}

OPACITY_STEP = 5.0


def _step_preset(widget: Any, step: int) -> None:
    """Move to the next selectable preset, skipping modality heading rows."""
    combo = widget._preset_combo
    index = preset_step_index(
        combo.currentIndex(),
        step,
        combo.count(),
        lambda row: widget._builtin_index_for_combo(row) >= 0,
    )
    if index is not None:
        combo.setCurrentIndex(index)


def handle_shortcut(widget: Any, keysym: str) -> bool:
    """Apply the shortcut bound to *keysym*.  Returns ``True`` if handled."""
    if not keysym:
        return False
    key = keysym.lower()
    if key in ("r", "space"):
        widget._renderer.set_view("Anterior")
        widget._render()
    elif key == "f":
        widget._renderer.get_renderer().ResetCamera()
        widget._render()
    elif key == "a":
        widget._auto_rotate_btn.toggle()
    elif key in KEY_VIEW_MAP:
        widget._renderer.set_view(KEY_VIEW_MAP[key])
        widget._render()
    elif key in ("plus", "equal"):
        widget._opacity_spin.setValue(
            min(widget._opacity_spin.value() + OPACITY_STEP, 100.0)
        )
    elif key == "minus":
        widget._opacity_spin.setValue(
            max(widget._opacity_spin.value() - OPACITY_STEP, 0.0)
        )
    elif key == "bracketright":
        _step_preset(widget, 1)
    elif key == "bracketleft":
        _step_preset(widget, -1)
    else:
        return False
    return True
