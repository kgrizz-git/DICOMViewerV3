"""Tests for the offscreen 3D volume render surface.

The central guarantee is that ``paintEvent`` never triggers a VTK render.
That invariant is what fixes the native-macOS hard freeze: the old
``QVTKRenderWindowInteractor`` rendered from inside ``paintEvent``, which
deadlocks in ``glFinish`` under a CoreAnimation transaction commit.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPaintEvent, QResizeEvent

pytest.importorskip("vtkmodules.all")

from gui.volume.render_surface import VolumeRenderSurface


@pytest.fixture
def surface(qapp):
    """Return a render surface, cleaned up after the test."""
    widget = VolumeRenderSurface()
    widget.resize(120, 90)
    yield widget
    widget.cleanup()


def test_paint_event_never_renders(surface, monkeypatch):
    """paintEvent must draw the cached image only — the freeze invariant."""
    calls = {"render": 0}

    def _tracked_render() -> None:
        calls["render"] += 1

    monkeypatch.setattr(surface.render_window, "Render", _tracked_render)
    surface._image = QImage(10, 10, QImage.Format.Format_RGB888)
    surface._image.fill(0)

    surface.paintEvent(QPaintEvent(QRect(0, 0, 120, 90)))

    assert calls["render"] == 0


def test_paint_event_without_image_does_not_crash(surface):
    """A paint before the first render fills black instead of raising."""
    assert surface._image is None
    surface.paintEvent(QPaintEvent(QRect(0, 0, 120, 90)))


def test_render_populates_cached_image(surface):
    """render() performs the VTK render and caches a frame."""
    import vtkmodules.all as vtk_mod

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.2, 0.4, 0.6)
    surface.add_renderer(renderer)

    surface.render()

    assert surface._image is not None
    assert not surface._image.isNull()


def test_rendered_image_is_opaque_not_transparent(surface):
    """Alpha must be discarded; an RGBA blit would be ~99% transparent.

    Regression guard for the Phase 0 finding: the offscreen buffer's
    background alpha is 0, so Format_RGBA8888 yields a near-invisible image.
    """
    import vtkmodules.all as vtk_mod

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.2, 0.4, 0.6)
    surface.add_renderer(renderer)

    surface.render()
    image = surface._image

    assert image.format() == QImage.Format.Format_RGB888
    # A known non-black background must survive the round trip.
    colour = image.pixelColor(image.width() // 2, image.height() // 2)
    assert colour.red() + colour.green() + colour.blue() > 0
    assert colour.alpha() == 255


def test_render_survives_dropped_numpy_buffer(surface):
    """The QImage must be detached from the numpy buffer that backed it."""
    import vtkmodules.all as vtk_mod

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.9, 0.1, 0.1)
    surface.add_renderer(renderer)

    surface.render()
    # Force garbage collection of any transient readback buffers.
    import gc

    gc.collect()

    image = surface._image
    colour = image.pixelColor(image.width() // 2, image.height() // 2)
    assert colour.red() > colour.blue()


def test_resize_updates_offscreen_buffer_without_rendering(surface, monkeypatch):
    """resizeEvent resizes the buffer but must not render inline.

    The handler is invoked directly: Qt does not deliver resizeEvent
    synchronously to a hidden widget under the offscreen platform plugin.
    """
    calls = {"render": 0}
    monkeypatch.setattr(
        surface.render_window, "Render", lambda: calls.__setitem__("render", 1)
    )

    old_size = surface.size()
    surface.setGeometry(0, 0, 300, 200)
    surface.resizeEvent(QResizeEvent(surface.size(), old_size))

    assert calls["render"] == 0
    ratio = surface.devicePixelRatioF() or 1.0
    assert surface._buffer_size == (int(300 * ratio), int(200 * ratio))


def test_device_pixel_ratio_applied_to_image(surface):
    """The cached image carries the widget's DPR so Retina is not blurry."""
    import vtkmodules.all as vtk_mod

    surface.add_renderer(vtk_mod.vtkRenderer())
    surface.render()

    expected = surface.devicePixelRatioF() or 1.0
    assert surface._image.devicePixelRatio() == pytest.approx(expected)


def test_vertical_flip_orientation(surface):
    """VTK's bottom-left origin must be flipped to QImage's top-left."""
    import vtkmodules.all as vtk_mod

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.0, 0.0, 0.0)
    # A cone placed high in the viewport should appear near the image top.
    cone = vtk_mod.vtkConeSource()
    mapper = vtk_mod.vtkPolyDataMapper()
    mapper.SetInputConnection(cone.GetOutputPort())
    actor = vtk_mod.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(1.0, 1.0, 1.0)
    actor.SetPosition(0.0, 3.0, 0.0)
    renderer.AddActor(actor)
    surface.add_renderer(renderer)
    renderer.ResetCamera()

    surface.render()
    image = surface._image

    width, height = image.width(), image.height()
    rows = []
    for y in range(height):
        for x in range(0, width, 4):
            colour = image.pixelColor(x, y)
            if colour.red() + colour.green() + colour.blue() > 150:
                rows.append(y)
                break
    if not rows:
        pytest.skip("offscreen GL produced no geometry in this environment")
    assert float(np.mean(rows)) < height / 2


def test_cleanup_is_idempotent(surface):
    surface.cleanup()
    surface.cleanup()
    assert surface.render_window is None


def test_render_after_cleanup_is_a_noop(surface):
    surface.cleanup()
    surface.render()  # must not raise
    assert surface._image is None


def test_cleanup_does_not_finalize_render_window(surface, monkeypatch):
    """cleanup() must not call Finalize() on the offscreen render window.

    Regression guard: Finalize() destroys the offscreen GL context, and VTK's
    destructor frees it again when the last reference drops. That double free
    segfaults at application teardown on macOS.
    """
    calls = {"finalize": 0}
    monkeypatch.setattr(
        surface.render_window,
        "Finalize",
        lambda: calls.__setitem__("finalize", calls["finalize"] + 1),
    )

    surface.cleanup()

    assert calls["finalize"] == 0
