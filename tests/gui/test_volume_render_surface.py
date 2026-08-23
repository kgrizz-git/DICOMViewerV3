"""Tests for the offscreen 3D volume render surface.

The central guarantee is that ``paintEvent`` never triggers a VTK render.
That invariant is what fixes the native-macOS hard freeze: the old
``QVTKRenderWindowInteractor`` rendered from inside ``paintEvent``, which
deadlocks in ``glFinish`` under a CoreAnimation transaction commit.
"""

from __future__ import annotations

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

    surface.render_frame()

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

    surface.render_frame()
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

    surface.render_frame()
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
    surface.render_frame()

    expected = surface.devicePixelRatioF() or 1.0
    assert surface._image.devicePixelRatio() == pytest.approx(expected)


def test_vertical_flip_orientation(surface):
    """VTK's bottom-left origin must be flipped to QImage's top-left.

    The camera is placed explicitly rather than via ResetCamera(): resetting
    re-centres on the actor, which makes a vertically flipped frame produce the
    same result and renders the assertion vacuous.
    """
    import vtkmodules.all as vtk_mod

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.0, 0.0, 0.0)
    # Bright marker high in world space (+Y), dim marker low (-Y).
    for y_position, grey in ((3.0, 1.0), (-3.0, 0.25)):
        source = vtk_mod.vtkSphereSource()
        source.SetRadius(1.0)
        mapper = vtk_mod.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        actor = vtk_mod.vtkActor()
        actor.SetMapper(mapper)
        actor.SetPosition(0.0, y_position, 0.0)
        actor.GetProperty().SetColor(grey, grey, grey)
        actor.GetProperty().SetLighting(False)
        renderer.AddActor(actor)
    surface.add_renderer(renderer)

    # Fixed camera: +Y is up, so the bright marker belongs in the TOP half.
    camera = renderer.GetActiveCamera()
    camera.SetPosition(0.0, 0.0, 20.0)
    camera.SetFocalPoint(0.0, 0.0, 0.0)
    camera.SetViewUp(0.0, 1.0, 0.0)
    renderer.ResetCameraClippingRange()

    surface.render_frame()
    image = surface._image
    if image is None or image.isNull():
        pytest.skip("offscreen GL produced no frame in this environment")

    width, height = image.width(), image.height()

    def brightness(y_range):
        total = 0
        for y in y_range:
            for x in range(0, width, 3):
                colour = image.pixelColor(x, y)
                total += colour.red() + colour.green() + colour.blue()
        return total

    top = brightness(range(0, height // 2))
    bottom = brightness(range(height // 2, height))
    if top == 0 and bottom == 0:
        pytest.skip("offscreen GL produced no geometry in this environment")
    assert top > bottom, "bright +Y marker should render in the top half"


def test_cleanup_is_idempotent(surface):
    surface.cleanup()
    surface.cleanup()
    assert surface.render_window is None


def test_render_after_cleanup_is_a_noop(surface):
    surface.cleanup()
    surface.render_frame()  # must not raise
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


def test_hover_without_button_is_not_forwarded(surface, monkeypatch):
    """Plain hover must not reach the interactor.

    VTK's trackball ignores hover and the crop-box widget was measured to react
    to neither, so forwarding it is pure overhead exposed to VTK-version drift.
    """
    from PySide6.QtCore import QPointF
    from PySide6.QtCore import Qt as QtNs
    from PySide6.QtGui import QMouseEvent

    moves = {"n": 0}
    monkeypatch.setattr(
        surface.interactor,
        "MouseMoveEvent",
        lambda: moves.__setitem__("n", moves["n"] + 1),
    )

    hover = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(20, 20),
        QPointF(20, 20),
        QtNs.MouseButton.NoButton,
        QtNs.MouseButton.NoButton,
        QtNs.KeyboardModifier.NoModifier,
    )
    surface.mouseMoveEvent(hover)

    assert moves["n"] == 0


def test_drag_move_is_forwarded(surface, monkeypatch):
    """A move with a button held must still reach the interactor."""
    from PySide6.QtCore import QPointF
    from PySide6.QtCore import Qt as QtNs
    from PySide6.QtGui import QMouseEvent

    moves = {"n": 0}
    monkeypatch.setattr(
        surface.interactor,
        "MouseMoveEvent",
        lambda: moves.__setitem__("n", moves["n"] + 1),
    )

    def event(kind, button):
        return QMouseEvent(
            kind,
            QPointF(20, 20),
            QPointF(20, 20),
            button,
            button,
            QtNs.KeyboardModifier.NoModifier,
        )

    surface.mousePressEvent(
        event(QMouseEvent.Type.MouseButtonPress, QtNs.MouseButton.LeftButton)
    )
    surface.mouseMoveEvent(
        event(QMouseEvent.Type.MouseMove, QtNs.MouseButton.NoButton)
    )
    surface.mouseReleaseEvent(
        event(QMouseEvent.Type.MouseButtonRelease, QtNs.MouseButton.LeftButton)
    )
    surface.mouseMoveEvent(
        event(QMouseEvent.Type.MouseMove, QtNs.MouseButton.NoButton)
    )

    assert moves["n"] == 1


def test_paint_fills_whole_rect_before_drawing(surface):
    """Prevents a stale smear in the area beyond a smaller cached image.

    WA_OpaquePaintEvent means Qt does not clear the background, so after a
    resize the newly exposed region keeps whatever pixels were already there
    until the debounced re-render lands.  Painting into a pre-stained target
    reproduces that; ``grab()`` cannot, because it allocates a fresh pixmap.
    """
    from PySide6.QtGui import QColor, QImage, QPixmap
    from PySide6.QtWidgets import QWidget

    cached = QImage(4, 4, QImage.Format.Format_RGB888)
    cached.fill(0xFFFFFF)
    surface._image = cached
    surface.resize(60, 40)

    stained = QPixmap(60, 40)
    stained.fill(QColor(255, 0, 0))
    QWidget.render(surface, stained)

    grabbed = stained.toImage()
    corner = grabbed.pixelColor(grabbed.width() - 1, grabbed.height() - 1)
    assert (corner.red(), corner.green(), corner.blue()) == (0, 0, 0)


def test_escape_is_not_swallowed(surface, monkeypatch):
    """Escape must reach the hosting dialog so the 3D window can close.

    Regression: adding Escape to the keysym map and accepting handled keys made
    the dialog impossible to dismiss with Escape.
    """
    from PySide6.QtCore import Qt as QtNs
    from PySide6.QtGui import QKeyEvent

    forwarded = {"n": 0}
    monkeypatch.setattr(
        surface.interactor,
        "KeyPressEvent",
        lambda: forwarded.__setitem__("n", forwarded["n"] + 1),
    )

    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        QtNs.Key.Key_Escape,
        QtNs.KeyboardModifier.NoModifier,
        "\x1b",
    )
    surface.keyPressEvent(event)

    assert forwarded["n"] == 0
    assert not event.isAccepted()


def test_failed_grab_keeps_previous_frame(surface, monkeypatch):
    """A failed readback must not blank the viewport to black."""
    import vtkmodules.all as vtk_mod
    from PySide6.QtGui import QImage

    renderer = vtk_mod.vtkRenderer()
    renderer.SetBackground(0.2, 0.4, 0.6)
    surface.add_renderer(renderer)
    surface.render_frame()
    good = surface._image
    assert good is not None

    monkeypatch.setattr(surface, "_grab", lambda _w, _h: None)
    surface.render_frame()

    assert surface._image is good
    assert isinstance(surface._image, QImage)


def test_grab_uses_render_window_reported_size(surface, monkeypatch):
    """Readback dimensions come from the window, not the requested size."""
    import vtkmodules.all as vtk_mod

    surface.add_renderer(vtk_mod.vtkRenderer())
    seen: list[tuple[int, int]] = []
    real_grab = surface._grab
    monkeypatch.setattr(
        surface, "_grab", lambda w, h: (seen.append((w, h)), real_grab(w, h))[1]
    )

    surface.render_frame()

    assert seen
    assert seen[-1] == tuple(int(v) for v in surface.render_window.GetSize())
