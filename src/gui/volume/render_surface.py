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
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from utils.debug_flags import DEBUG_VOLUME_3D

# Minimum offscreen buffer size.  A zero-sized render window is invalid in VTK
# and a 1x1 buffer makes camera resets degenerate.
_MIN_DIM = 8


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
        """Resize the offscreen buffer.

        Does **not** render inline; the owning widget re-renders through its
        own debounce timer so a drag-resize cannot queue a render per pixel.
        """
        super().resizeEvent(event)
        if self._cleaned_up or self._render_window is None:
            return
        width, height = self._target_pixel_size()
        if (width, height) != self._buffer_size:
            self._render_window.SetSize(width, height)
            self._buffer_size = (width, height)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Render offscreen and cache the frame, then schedule a repaint.

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

        self._render_window.Render()
        self._image = self._grab(width, height)
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
        """Draw the cached frame.  Never renders — that is the whole point."""
        painter = QPainter(self)
        if self._image is None or self._image.isNull():
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            return
        painter.drawImage(0, 0, self._image)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release the offscreen window and the cached frame."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        self._image = None
        if self._render_window is not None:
            try:
                self._render_window.Finalize()
            except Exception:
                pass
            self._render_window = None
