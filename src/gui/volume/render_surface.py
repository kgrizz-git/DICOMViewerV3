"""Offscreen VTK render surface blitted into a plain Qt widget.

Replaces ``QVTKRenderWindowInteractor`` for 3D volume rendering.  The
interactor renders from inside ``paintEvent``, which on native macOS blocks
forever in ``glFinish`` inside a CoreAnimation transaction commit (see
``dev-docs/plans/3D_VIEWER_MACOS_NATIVE_RENDERING_PLAN.md``).  Rendering to an
offscreen ``vtkRenderWindow`` and painting the resulting image sidesteps the
Cocoa/CALayer path entirely.

The core invariant is that ``paintEvent`` only ever draws a cached image and
**never** calls ``Render()``.  Rendering happens explicitly via
:meth:`VolumeRenderSurface.render`.

Requirements:
    - PySide6
    - VTK >= 9.3.0
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.volume.interactor_bridge import (
    button_event_names,
    create_interactor,
    modifier_flags,
    qt_key_to_vtk_keysym,
    set_event_information,
)
from utils.debug_flags import DEBUG_VOLUME_3D

# Minimum offscreen buffer size.  A zero-sized render window is invalid in VTK
# and a 1x1 buffer makes camera resets degenerate.
_MIN_DIM = 8

# Debounce window for re-rendering after a resize.
_RESIZE_DEBOUNCE_MS = 80


def _vtk() -> Any:
    """Import VTK lazily so this module stays importable without it."""
    import vtkmodules.all as vtk_mod

    return vtk_mod


class VolumeRenderSurface(QWidget):
    """Widget that displays an offscreen VTK render as a cached ``QImage``.

    The widget owns the ``vtkRenderWindow``.  Callers attach their renderer
    via :meth:`add_renderer` and trigger frames with :meth:`render`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        vtk_mod = _vtk()
        self._render_window: Any = vtk_mod.vtkRenderWindow()
        self._render_window.SetOffScreenRendering(1)
        self._render_window.SetSize(_MIN_DIM, _MIN_DIM)

        self._image: QImage | None = None
        self._cleaned_up = False
        # ``_image`` is always a detached copy, so no numpy buffer needs to be
        # retained.  Track the last buffer size to avoid redundant SetSize churn.
        self._buffer_size: tuple[int, int] = (_MIN_DIM, _MIN_DIM)

        # A generic interactor keeps the stock trackball style and lets VTK 3D
        # widgets (crop box) work without a native VTK window.
        self._interactor: Any = create_interactor(self._render_window)
        # Blit whenever the render window finishes a frame, so renders driven by
        # the interactor refresh the widget too, not only explicit render()
        # calls.
        self._grabbing = False
        self._buttons_down = 0
        self._render_window.AddObserver("EndEvent", self._on_render_end)

        # Debounce re-render after a resize so a drag-resize does not queue one
        # full volume render per pixel of mouse travel.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self.render_frame)

    # ------------------------------------------------------------------
    # Interactor
    # ------------------------------------------------------------------

    @property
    def interactor(self) -> Any:
        """Return the generic interactor driving this surface."""
        return self._interactor

    # ------------------------------------------------------------------
    # Renderer wiring
    # ------------------------------------------------------------------

    def add_renderer(self, renderer: Any) -> None:
        """Attach a ``vtkRenderer`` to the offscreen window."""
        self._render_window.AddRenderer(renderer)

    @property
    def render_window(self) -> Any:
        """Return the offscreen ``vtkRenderWindow`` (may be ``None`` after cleanup)."""
        return self._render_window

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _target_pixel_size(self) -> tuple[int, int]:
        """Return the offscreen buffer size in device pixels."""
        ratio = self.devicePixelRatioF() or 1.0
        width = max(_MIN_DIM, int(self.width() * ratio))
        height = max(_MIN_DIM, int(self.height() * ratio))
        return width, height

    def sizeHint(self) -> QSize:
        return QSize(640, 480)

    def resizeEvent(self, event: Any) -> None:
        """Resize the offscreen buffer and schedule a debounced re-render.

        Rendering never happens inline here: a drag-resize would otherwise
        queue one full volume render per pixel of mouse travel.  The cached
        frame must still be refreshed afterwards, or the widget keeps painting
        an image of the old size and the newly exposed area shows stale
        content.
        """
        super().resizeEvent(event)
        if self._cleaned_up or self._render_window is None:
            return
        width, height = self._target_pixel_size()
        if (width, height) != self._buffer_size:
            self._render_window.SetSize(width, height)
            self._buffer_size = (width, height)
            self._resize_timer.start()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_frame(self) -> None:
        """Render offscreen and cache the frame, then schedule a repaint.

        Deliberately **not** named ``render``: ``QWidget.render(QPaintDevice, ...)``
        is an existing Qt API, and shadowing it with a different signature both
        breaks that API for callers and trips static override checks.

        This is the only place ``Render()`` is called.  It blocks for the
        duration of the VTK render, exactly as the old interactor did, but it
        is never invoked from inside ``paintEvent`` / a CALayer display pass.
        """
        if self._cleaned_up or self._render_window is None:
            return
        width, height = self._target_pixel_size()
        if (width, height) != self._buffer_size:
            self._render_window.SetSize(width, height)
            self._buffer_size = (width, height)

        # The EndEvent observer performs the readback and repaint.
        self._render_window.Render()

    def _on_render_end(self, _caller: Any = None, _event: str = "") -> None:
        """Cache the just-rendered frame and schedule a repaint."""
        if self._cleaned_up or self._render_window is None or self._grabbing:
            return
        self._grabbing = True
        try:
            width, height = self._buffer_size
            self._image = self._grab(width, height)
        finally:
            self._grabbing = False
        self.update()

    def _grab(self, width: int, height: int) -> QImage | None:
        """Read the offscreen buffer back into a detached ``QImage``."""
        vtk_mod = _vtk()
        try:
            from vtkmodules.util import numpy_support

            scalars = vtk_mod.vtkUnsignedCharArray()
            self._render_window.GetRGBACharPixelData(
                0, 0, width - 1, height - 1, 1, scalars
            )
            flat = numpy_support.vtk_to_numpy(scalars)
            if flat.size != width * height * 4:
                return None
            buffer = flat.reshape(height, width, 4)
            # VTK's origin is bottom-left, QImage's is top-left.
            # Drop alpha: the offscreen background alpha is 0, so an RGBA
            # QImage would render almost entirely transparent.
            rgb = np.ascontiguousarray(buffer[::-1, :, :3])
            image = QImage(
                rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888
            )
            # copy() detaches from the numpy buffer, which is about to be freed.
            detached = image.copy()
            detached.setDevicePixelRatio(self.devicePixelRatioF() or 1.0)
            return detached
        except Exception:
            if DEBUG_VOLUME_3D:
                print("[DEBUG-VOLUME-3D] render surface readback failed")
            return None

    def paintEvent(self, event: Any) -> None:
        """Draw the cached frame.  Never renders — that is the whole point.

        The whole rect is filled first: with ``WA_OpaquePaintEvent`` set Qt does
        not clear the background, so after a resize the area beyond the (still
        old, smaller) cached image would show stale pixels until the debounced
        re-render lands.
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._image is None or self._image.isNull():
            return
        painter.drawImage(0, 0, self._image)

    # ------------------------------------------------------------------
    # Input forwarding
    # ------------------------------------------------------------------

    def _push_event_info(self, event: Any, key: str = chr(0)) -> bool:
        """Feed a Qt pointer event's position and modifiers into VTK."""
        if self._cleaned_up or self._interactor is None:
            return False
        position = event.position()
        set_event_information(
            self._interactor,
            x=position.x(),
            y=position.y(),
            height_px=self._buffer_size[1],
            ratio=self.devicePixelRatioF() or 1.0,
            modifiers=event.modifiers(),
            key=key,
        )
        return True

    def mousePressEvent(self, event: Any) -> None:
        names = button_event_names(event.button())
        if names is None or not self._push_event_info(event):
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._buttons_down += 1
        getattr(self._interactor, names[0])()

    def mouseReleaseEvent(self, event: Any) -> None:
        names = button_event_names(event.button())
        if names is None or not self._push_event_info(event):
            super().mouseReleaseEvent(event)
            return
        self._buttons_down = max(0, self._buttons_down - 1)
        getattr(self._interactor, names[1])()

    def mouseMoveEvent(self, event: Any) -> None:
        """Forward drags only.

        Plain hover is not forwarded: VTK's trackball style ignores it and the
        crop-box widget was measured to react to neither (no renders, no state
        change), so forwarding it is pure overhead and leaves the cost exposed
        to VTK-version changes.
        """
        if self._buttons_down and self._push_event_info(event):
            self._interactor.MouseMoveEvent()
        else:
            super().mouseMoveEvent(event)

    def wheelEvent(self, event: Any) -> None:
        if self._cleaned_up or self._interactor is None:
            super().wheelEvent(event)
            return
        position = event.position()
        set_event_information(
            self._interactor,
            x=position.x(),
            y=position.y(),
            height_px=self._buffer_size[1],
            ratio=self.devicePixelRatioF() or 1.0,
            modifiers=event.modifiers(),
        )
        delta = event.angleDelta().y()
        if delta > 0:
            self._interactor.MouseWheelForwardEvent()
        elif delta < 0:
            self._interactor.MouseWheelBackwardEvent()

    def keyPressEvent(self, event: Any) -> None:
        if self._cleaned_up or self._interactor is None:
            super().keyPressEvent(event)
            return
        keysym = qt_key_to_vtk_keysym(event.key(), event.text())
        if not keysym:
            super().keyPressEvent(event)
            return
        ctrl, shift = modifier_flags(event.modifiers())
        # SetKeyEventInformation carries the keysym that GetKeySym() reports;
        # SetEventInformation's char argument alone does not.
        self._interactor.SetKeyEventInformation(
            ctrl, shift, event.text()[:1] or chr(0), 0, keysym
        )
        self._interactor.KeyPressEvent()
        # Accept rather than chaining to super(): the key has been dispatched to
        # VTK, and propagating it again risks double handling if an ancestor
        # later grows a keyPressEvent.
        event.accept()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release the interactor, offscreen window, and cached frame.

        Deliberately does **not** call ``vtkRenderWindow.Finalize()``.  On
        macOS that destroys the offscreen GL context here, and VTK's own
        destructor then frees it again when the last reference is dropped —
        a double free that segfaults at application teardown.  Dropping the
        references is sufficient; VTK releases the context in the destructor.
        """
        if self._cleaned_up:
            return
        self._cleaned_up = True
        self._resize_timer.stop()
        self._image = None
        if self._render_window is not None:
            try:
                self._render_window.RemoveAllObservers()
            except Exception:
                pass
        self._interactor = None
        self._render_window = None
