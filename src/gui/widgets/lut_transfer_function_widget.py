"""
Paint the LUT swatch and, when window/level is supplied, the composed trace.

Sampling lives in ``core.lut_transfer``. This widget only draws those arrays.
Toolbar icons use ``lut_actions.swatch_icon``; the histogram asks the core
sampler directly so it can use its own axes.

Inputs:
    - A ``LookUpTable`` and optional window, photometric interpretation, invert flag

Outputs:
    - A painted gradient and optional composed polyline

Requirements:
    - PySide6
    - core.lut_transfer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from core.lut_transfer import (
    curves_are_one_line,
    lut_samples,
    net_user_polarity_invert,
    sample_window_and_composed,
)

__all__ = [
    "LutTransferFunctionWidget",
    "TransferPaths",
    "lut_samples",
    "overlay_paths",
]


@dataclass(frozen=True)
class TransferPaths:
    """Arrays the histogram paints. Sampling happens only in this module."""

    xs: np.ndarray
    window: np.ndarray
    lut_trace: np.ndarray | None
    lut_colors: np.ndarray | None
    composed: np.ndarray
    collapse: bool
    net_inverted: bool
    name: str
    source: str


def overlay_paths(
    lut: Any,
    window_center: float | None,
    window_width: float | None,
    photometric_interpretation: object,
    image_inverted: bool,
    x_min: float,
    x_max: float,
) -> TransferPaths | None:
    """Sample the ramp, the LUT, and ``LUT(P_inv(u))`` across ``[x_min, x_max]``."""
    if lut is None or window_center is None or window_width is None or window_width <= 0:
        return None
    if not np.isfinite(x_min) or not np.isfinite(x_max) or x_max <= x_min:
        x_min = window_center - window_width / 2.0
        x_max = window_center + window_width / 2.0
    xs = np.linspace(x_min, x_max, 256)
    windowed, composed = sample_window_and_composed(
        xs,
        window_center,
        window_width,
        lut,
        photometric_interpretation,
        image_inverted,
    )
    samples = lut_samples(lut)
    if samples.ndim == 2:
        lut_trace = None
        lut_colors = samples
        composed_trace = composed.mean(axis=1)
    else:
        lut_trace = samples
        lut_colors = None
        composed_trace = composed
    return TransferPaths(
        xs=xs,
        window=windowed,
        lut_trace=lut_trace,
        lut_colors=lut_colors,
        composed=np.asarray(composed_trace, dtype=np.float64),
        collapse=curves_are_one_line(lut, photometric_interpretation, image_inverted),
        net_inverted=net_user_polarity_invert(photometric_interpretation, image_inverted),
        name=str(getattr(lut, "name", "LUT")),
        source=str(getattr(lut, "source", "")),
    )


class LutTransferFunctionWidget(QWidget):
    """Gradient of the active LUT, with the composed display curve when W/L is set."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lut: Any = None
        self._window_center: float | None = None
        self._window_width: float | None = None
        self._photometric: object = None
        self._image_inverted = False
        self.setMinimumHeight(72)

    def set_lut(
        self,
        lut: Any,
        *,
        window_center: float | None = None,
        window_width: float | None = None,
        photometric_interpretation: object = None,
        image_inverted: bool = False,
    ) -> None:
        """Replace the curves and repaint."""
        self._lut = lut
        self._window_center = window_center
        self._window_width = window_width
        self._photometric = photometric_interpretation
        self._image_inverted = image_inverted
        self.update()

    def paintEvent(self, _event: Any) -> None:
        """Draw the LUT strip and the composed trace in widget coordinates."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(32, 32, 32))
        if self._lut is None:
            painter.end()
            return
        samples = lut_samples(self._lut)
        strip = _rgb_strip(samples)
        image = QImage(
            strip.tobytes(),
            strip.shape[1],
            strip.shape[0],
            3 * strip.shape[1],
            QImage.Format.Format_RGB888,
        )
        target_height = max(16, self.height() // 3)
        painter.drawPixmap(0, self.height() - target_height, self.width(), target_height, QPixmap.fromImage(image.copy()))
        if self._window_center is None or self._window_width is None or self._window_width <= 0:
            painter.end()
            return
        stored = np.linspace(self._window_center - self._window_width / 2.0, self._window_center + self._window_width / 2.0, 256)
        _windowed, composed = sample_window_and_composed(
            stored,
            self._window_center,
            self._window_width,
            self._lut,
            self._photometric,
            self._image_inverted,
        )
        trace = composed.mean(axis=1) if composed.ndim == 2 else composed
        pen = QPen(QColor(240, 240, 240))
        pen.setWidth(2)
        painter.setPen(pen)
        width = max(1, self.width() - 1)
        height = max(1, self.height() - target_height - 1)
        previous: QPointF | None = None
        for index, value in enumerate(trace):
            x = width * index / max(1, len(trace) - 1)
            y = height * (1.0 - float(value) / 255.0)
            point = QPointF(x, y)
            if previous is not None:
                painter.drawLine(previous, point)
            previous = point
        painter.end()


def _rgb_strip(samples: np.ndarray) -> np.ndarray:
    """One-row RGB image of a grayscale or color LUT."""
    if samples.ndim == 1:
        column = np.asarray(samples, dtype=np.uint8)
        rgb = np.stack((column, column, column), axis=-1)
    else:
        rgb = np.asarray(samples, dtype=np.uint8)
    return np.ascontiguousarray(rgb.reshape(1, -1, 3))
