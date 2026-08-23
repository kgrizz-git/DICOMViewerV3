"""Tests for forwarding Qt input events into the VTK generic interactor."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from gui.volume.interactor_bridge import (
    button_event_names,
    modifier_flags,
    qt_to_vtk_position,
)

vtk_all = pytest.importorskip("vtkmodules.all")

from gui.volume.render_surface import VolumeRenderSurface

# ----------------------------------------------------------------------
# Pure coordinate / modifier mapping
# ----------------------------------------------------------------------


def test_qt_to_vtk_position_inverts_y_axis():
    """Qt's top-left origin must become VTK's bottom-left origin."""
    assert qt_to_vtk_position(10, 0, height_px=300, ratio=1.0) == (10, 300)
    assert qt_to_vtk_position(10, 300, height_px=300, ratio=1.0) == (10, 0)


def test_qt_to_vtk_position_applies_device_pixel_ratio():
    """Logical Qt units scale to device pixels on Retina."""
    assert qt_to_vtk_position(100, 50, height_px=600, ratio=2.0) == (200, 500)


def test_qt_to_vtk_position_tolerates_zero_ratio():
    """A zero/unset DPR must fall back to 1.0 rather than collapsing to 0."""
    assert qt_to_vtk_position(10, 10, height_px=100, ratio=0.0) == (10, 90)


@pytest.mark.parametrize(
    ("modifiers", "expected"),
    [
        (Qt.KeyboardModifier.NoModifier, (0, 0)),
        (Qt.KeyboardModifier.ControlModifier, (1, 0)),
        (Qt.KeyboardModifier.ShiftModifier, (0, 1)),
        (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            (1, 1),
        ),
    ],
)
def test_modifier_flags(modifiers, expected):
    assert modifier_flags(modifiers) == expected


def test_button_event_names_covers_three_buttons():
    assert button_event_names(Qt.MouseButton.LeftButton) == (
        "LeftButtonPressEvent",
        "LeftButtonReleaseEvent",
    )
    assert button_event_names(Qt.MouseButton.MiddleButton) is not None
    assert button_event_names(Qt.MouseButton.RightButton) is not None
    assert button_event_names(Qt.MouseButton.BackButton) is None


# ----------------------------------------------------------------------
# Surface-level forwarding
# ----------------------------------------------------------------------


@pytest.fixture
def surface(qapp):
    widget = VolumeRenderSurface()
    widget.resize(200, 150)
    renderer = vtk_all.vtkRenderer()
    cone = vtk_all.vtkConeSource()
    mapper = vtk_all.vtkPolyDataMapper()
    mapper.SetInputConnection(cone.GetOutputPort())
    actor = vtk_all.vtkActor()
    actor.SetMapper(mapper)
    renderer.AddActor(actor)
    widget.add_renderer(renderer)
    renderer.ResetCamera()
    widget.render()
    yield widget
    widget.cleanup()


def _mouse(kind, pos, button=Qt.MouseButton.LeftButton):
    return QMouseEvent(
        kind,
        QPointF(*pos),
        QPointF(*pos),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )


def test_surface_exposes_generic_interactor(surface):
    """The interactor must be bound to the surface's offscreen window."""
    assert surface.interactor is not None
    assert surface.render_window.GetInteractor() is surface.interactor


def test_drag_moves_the_camera(surface):
    """A synthetic left-drag rotates the camera via the trackball style."""
    renderer = surface.render_window.GetRenderers().GetFirstRenderer()
    before = renderer.GetActiveCamera().GetPosition()

    surface.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, (100, 75)))
    for offset in range(0, 40, 8):
        surface.mouseMoveEvent(
            _mouse(QMouseEvent.Type.MouseMove, (100 + offset, 75), Qt.MouseButton.NoButton)
        )
    surface.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, (140, 75)))

    after = renderer.GetActiveCamera().GetPosition()
    assert before != after


def test_render_end_event_refreshes_cached_image(surface):
    """Renders driven by the interactor must refresh the widget's frame."""
    surface._image = None
    surface.render_window.Render()
    assert surface._image is not None


def test_wheel_event_dollies_camera(surface):
    """Wheel input reaches the interactor and changes the camera distance."""
    renderer = surface.render_window.GetRenderers().GetFirstRenderer()
    before = renderer.GetActiveCamera().GetPosition()

    event = QWheelEvent(
        QPointF(100, 75),
        QPointF(100, 75),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    surface.wheelEvent(event)

    assert renderer.GetActiveCamera().GetPosition() != before


def test_events_after_cleanup_do_not_raise(surface):
    """Input arriving after teardown must be inert, not a crash."""
    surface.cleanup()
    surface.mousePressEvent(_mouse(QMouseEvent.Type.MouseButtonPress, (10, 10)))
    surface.mouseMoveEvent(
        _mouse(QMouseEvent.Type.MouseMove, (20, 20), Qt.MouseButton.NoButton)
    )
    surface.mouseReleaseEvent(_mouse(QMouseEvent.Type.MouseButtonRelease, (20, 20)))
    assert surface.interactor is None


def test_crop_box_widget_can_attach(surface):
    """vtkBoxWidget2 needs a real interactor; this is why we keep one."""
    box = vtk_all.vtkBoxWidget2()
    representation = vtk_all.vtkBoxRepresentation()
    representation.SetPlaceFactor(1.0)
    renderer = surface.render_window.GetRenderers().GetFirstRenderer()
    representation.PlaceWidget(list(renderer.ComputeVisiblePropBounds()))
    box.SetRepresentation(representation)
    box.SetInteractor(surface.interactor)
    box.On()
    surface.render()
    box.Off()


def test_crop_box_change_updates_planes_and_rerenders(qapp):
    """Crop-box drags must refresh the frame explicitly.

    Previously this relied on vtkBoxWidget2 internally calling
    Interactor->Render(); making it explicit removes the dependence on VTK
    internals staying wired to the EndEvent blit.
    """
    import numpy as np

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
    try:
        widget.initialize(modality="CT")
        widget.resize(400, 300)
        widget.show()
        qapp.processEvents()
        widget._crop_cb.setChecked(True)
        qapp.processEvents()
        assert widget._box_widget is not None

        planes: list[object] = []
        renders = {"n": 0}
        widget._renderer.set_cropping = lambda p: planes.append(p)
        widget._surface.render_window.AddObserver(
            "StartEvent", lambda *_a: renders.__setitem__("n", renders["n"] + 1)
        )

        widget._on_crop_box_changed()

        assert planes, "clipping planes were not pushed to the renderer"
        assert renders["n"] >= 1, "crop-box change did not trigger a render"
    finally:
        widget.cleanup()
