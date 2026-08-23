"""Keyboard shortcut tests for the 3D volume viewport.

These cover the end-to-end forwarding path (Qt key event -> render surface ->
VTK keysym -> shortcut handler), which is where the shortcuts silently broke
when the offscreen surface replaced the native VTK interactor.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from gui.volume.interactor_bridge import qt_key_to_vtk_keysym
from gui.volume.preset_nav import preset_step_index
from gui.volume.shortcuts import handle_shortcut

pytest.importorskip("vtkmodules.all")


# ----------------------------------------------------------------------
# Keysym translation (pure)
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "text", "expected"),
    [
        (Qt.Key.Key_Space, " ", "space"),
        (Qt.Key.Key_Plus, "+", "plus"),
        (Qt.Key.Key_Equal, "=", "equal"),
        (Qt.Key.Key_Minus, "-", "minus"),
        (Qt.Key.Key_BracketLeft, "[", "bracketleft"),
        (Qt.Key.Key_BracketRight, "]", "bracketright"),
        (Qt.Key.Key_R, "r", "r"),
        (Qt.Key.Key_1, "1", "1"),
    ],
)
def test_named_keys_map_to_vtk_keysyms(key, text, expected):
    """Regression: forwarding event.text() alone yields '+', ']', ' ' etc.

    The viewer's handler matches VTK keysym names, so the literal characters
    silently disabled opacity stepping, preset stepping, and Space-reset.
    """
    assert qt_key_to_vtk_keysym(key.value, text) == expected


def test_unknown_key_without_text_yields_empty():
    assert qt_key_to_vtk_keysym(Qt.Key.Key_F5.value, "") == ""


# ----------------------------------------------------------------------
# Preset stepping skips heading rows
# ----------------------------------------------------------------------


def test_preset_step_skips_headings():
    """Rows 0/2 are headings; stepping from 1 must land on 3, not 2."""
    selectable = {1, 3, 4}
    assert preset_step_index(1, 1, 5, lambda r: r in selectable) == 3


def test_preset_step_backwards_skips_headings():
    selectable = {1, 3, 4}
    assert preset_step_index(3, -1, 5, lambda r: r in selectable) == 1


def test_preset_step_returns_none_at_the_end():
    selectable = {1, 3}
    assert preset_step_index(3, 1, 5, lambda r: r in selectable) is None


def test_preset_step_returns_none_for_zero_step():
    assert preset_step_index(1, 0, 5, lambda _r: True) is None


# ----------------------------------------------------------------------
# End-to-end through the real widget
# ----------------------------------------------------------------------


@pytest.fixture
def viewer(qapp):
    from core.volume_renderer import VolumeData, VolumeRenderer
    from gui.volume_viewer_widget import VolumeViewerWidget

    array = np.full((8, 32, 32), -1000.0, dtype=np.float32)
    array[:, 8:24, 8:24] = 300.0
    renderer = VolumeRenderer()
    renderer.attach_volume(
        VolumeData(
            array=np.ascontiguousarray(array),
            spacing=(1.0, 1.0, 1.0),
            origin=(0.0, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            rescale_applied=True,
            scalar_units="HU",
        )
    )
    widget = VolumeViewerWidget(renderer)
    widget.initialize(modality="CT")
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    yield widget
    widget.cleanup()


def _press(widget, key, text):
    """Route a real Qt key event through the render surface, as Qt would."""
    widget._surface.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)
    )


def test_plus_and_minus_step_opacity(viewer):
    viewer._opacity_spin.setValue(50.0)
    _press(viewer, Qt.Key.Key_Plus, "+")
    assert viewer._opacity_spin.value() == pytest.approx(55.0)
    _press(viewer, Qt.Key.Key_Minus, "-")
    assert viewer._opacity_spin.value() == pytest.approx(50.0)


def test_brackets_step_presets(viewer):
    viewer._preset_combo.setCurrentIndex(1)
    _press(viewer, Qt.Key.Key_BracketRight, "]")
    assert viewer._preset_combo.currentIndex() != 1
    assert viewer._builtin_index_for_combo(viewer._preset_combo.currentIndex()) >= 0


def test_bracket_stepping_never_lands_on_a_heading(viewer):
    """Walk the whole combo with ']' and assert every stop is a real preset."""
    combo = viewer._preset_combo
    combo.setCurrentIndex(1)
    seen = 0
    for _ in range(combo.count()):
        _press(viewer, Qt.Key.Key_BracketRight, "]")
        assert viewer._builtin_index_for_combo(combo.currentIndex()) >= 0
        seen += 1
    assert seen > 0


def test_space_resets_the_view(viewer, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(viewer._renderer, "set_view", lambda view: calls.append(view))
    _press(viewer, Qt.Key.Key_Space, " ")
    assert calls == ["Anterior"]


def test_key_dispatches_exactly_once(viewer):
    """Guard against double dispatch through both VTK and the Qt parent chain."""
    viewer._opacity_spin.setValue(50.0)
    _press(viewer, Qt.Key.Key_Plus, "+")
    assert viewer._opacity_spin.value() == pytest.approx(55.0)


def test_unhandled_shortcut_reports_false():
    class _Stub:
        pass

    assert handle_shortcut(_Stub(), "") is False
