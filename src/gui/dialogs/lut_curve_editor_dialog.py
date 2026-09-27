"""
Edit a grayscale LUT by control points.

Endpoints stay at x = 0 and x = 1. Freehand strokes go through
``simplify_freehand`` (epsilon 0.02), which pins those endpoints. The painted
curve is sampled with ``lut_samples`` (``apply_lut_to_uint8``). The preview
strip under the graph is ``LutTransferFunctionWidget``, so the composed
result uses the same sampler as the histogram. Color colormaps are not
editable here.

Inputs:
    - Optional starting grayscale ``LookUpTable``
    - Optional display context (window center/width, photometric, user invert)

Outputs:
    - A custom or parameter ``LookUpTable``, or None on cancel

Requirements:
    - PySide6
    - core.lut_curve.simplify_freehand
    - core.lut_engine.LookUpTable
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.lut_curve import simplify_freehand
from core.lut_engine import (
    LookUpTable,
    evaluate_lut,
    exponential_transfer,
    gamma_transfer,
    sigmoid_transfer,
)
from gui.dialogs.lut_parameter_dialog import edit_lut_parameters
from gui.widgets.lut_transfer_function_widget import (
    LutTransferFunctionWidget,
    lut_samples,
)

_INTERPOLATION = ("linear", "monotone_cubic", "catmull_rom")


class _CurveCanvas(QWidget):
    """Unit-square curve. Endpoints cannot be deleted or moved in x."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.points: list[tuple[float, float]] = [(0.0, 0.0), (1.0, 1.0)]
        self.interpolation = "linear"
        self.freehand = False
        self.selected: int | None = None
        self.on_changed: Any = None
        self._drag: int | None = None
        self._stroke: list[tuple[float, float]] = []
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)

    def mousePressEvent(self, event: Any) -> None:
        """Start a drag, add a point, or begin a freehand stroke."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        unit = self._to_unit(event.position())
        if self.freehand:
            self._stroke = [unit]
            return
        index = self._hit(unit)
        if index is None:
            unit = _separate_x(unit, self.points)
            self.points.append(unit)
            self.points.sort(key=lambda item: item[0])
            self.selected = self.points.index(unit)
            self._drag = self.selected
            self._notify()
        else:
            self.selected = index
            self._drag = index
        self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        """Drag a breakpoint or extend the freehand stroke."""
        unit = self._to_unit(event.position())
        if self.freehand and self._stroke:
            self._stroke.append(unit)
            self.update()
            return
        if self._drag is None:
            return
        x, y = unit
        if self._drag == 0:
            x = 0.0
        elif self._drag == len(self.points) - 1:
            x = 1.0
        else:
            left = self.points[self._drag - 1][0] + 0.01
            right = self.points[self._drag + 1][0] - 0.01
            x = min(max(x, left), right)
        self.points[self._drag] = (x, y)
        self.update()

    def mouseReleaseEvent(self, event: Any) -> None:
        """Finish a drag or commit a simplified freehand stroke."""
        if self.freehand and self._stroke:
            simplified = simplify_freehand(np.asarray(self._stroke, dtype=np.float64))
            self.points = [(float(x), float(y)) for x, y in simplified]
            self._stroke = []
            self._notify()
        elif self._drag is not None:
            self._notify()
        self._drag = None
        self.update()
        _ = event

    def paintEvent(self, _event: Any) -> None:
        """Draw the uint8-sampled curve and the breakpoints."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 24, 24))
        try:
            lut = _curve_lut(self.points, self.interpolation)
            samples = lut_samples(lut)
        except ValueError:
            painter.end()
            return
        pen = QPen(QColor(220, 220, 220))
        pen.setWidth(2)
        painter.setPen(pen)
        previous: QPointF | None = None
        count = len(samples)
        for index, value in enumerate(samples):
            point = self._from_unit(index / max(1, count - 1), float(value) / 255.0)
            if previous is not None:
                painter.drawLine(previous, point)
            previous = point
        painter.setBrush(QColor(80, 160, 255))
        for x, y in self.points:
            painter.drawEllipse(self._from_unit(x, y), 4, 4)
        painter.end()

    def _notify(self) -> None:
        if callable(self.on_changed):
            self.on_changed()

    def _to_unit(self, position: QPointF) -> tuple[float, float]:
        width = max(1, self.width())
        height = max(1, self.height())
        x = min(max(position.x() / width, 0.0), 1.0)
        y = 1.0 - min(max(position.y() / height, 0.0), 1.0)
        return (x, y)

    def _from_unit(self, x: float, y: float) -> QPointF:
        return QPointF(x * self.width(), (1.0 - y) * self.height())

    def _hit(self, unit: tuple[float, float]) -> int | None:
        best: int | None = None
        best_distance = 0.04
        for index, point in enumerate(self.points):
            distance = abs(point[0] - unit[0]) + abs(point[1] - unit[1])
            if distance < best_distance:
                best = index
                best_distance = distance
        return best


class LutCurveEditorDialog(QDialog):
    """Grayscale control-point editor with undo and interpolation choice."""

    def __init__(
        self,
        lut: LookUpTable | None,
        parent: QWidget | None = None,
        display: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit LUT Curve")
        self._display = display or {}
        self._canvas = _CurveCanvas(self)
        self._preview = LutTransferFunctionWidget(self)
        self._undo: list[list[tuple[float, float]]] = []
        self._redo: list[list[tuple[float, float]]] = []
        self._parameter: LookUpTable | None = lut if _is_parameter(lut) else None
        self._points_dirty = False
        self._load(lut)
        self._canvas.on_changed = self._on_points_changed
        self._remember()
        interpolation = QComboBox()
        interpolation.addItems(list(_INTERPOLATION))
        interpolation.setCurrentText(self._canvas.interpolation)
        interpolation.currentTextChanged.connect(self._set_interpolation)
        freehand = QPushButton("Freehand")
        freehand.setCheckable(True)
        freehand.toggled.connect(self._set_freehand)
        delete = QPushButton("Delete Point")
        delete.clicked.connect(self._delete_selected)
        parameters = QPushButton("Parameters...")
        parameters.clicked.connect(self._edit_parameters)
        undo = QPushButton("Undo")
        undo.clicked.connect(self._undo_points)
        redo = QPushButton("Redo")
        redo.clicked.connect(self._redo_points)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        for widget in (interpolation, freehand, delete, parameters, undo, redo):
            row.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas)
        layout.addWidget(self._preview)
        layout.addLayout(row)
        layout.addWidget(buttons)
        self._refresh_preview()

    def result_lut(self) -> LookUpTable:
        """Parameter LUT when the points were not edited, otherwise a custom curve."""
        if self._parameter is not None and not self._points_dirty:
            return self._parameter
        return _curve_lut(self._canvas.points, self._canvas.interpolation)

    def _load(self, lut: LookUpTable | None) -> None:
        if lut is not None and lut.control_points:
            self._canvas.points = [(float(x), float(y)) for x, y in lut.control_points]
            self._canvas.interpolation = lut.interpolation
        elif lut is not None and lut.lut_type == "grayscale_ramp":
            xs = np.linspace(0.0, 1.0, 5)
            ys = evaluate_lut(lut, xs)
            self._canvas.points = [(float(x), float(y)) for x, y in zip(xs, ys, strict=True)]

    def _remember(self) -> None:
        self._undo.append(list(self._canvas.points))
        if len(self._undo) > 50:
            del self._undo[0]
        self._redo.clear()

    def _on_points_changed(self) -> None:
        self._points_dirty = True
        self._parameter = None
        self._remember()
        self._refresh_preview()

    def _set_interpolation(self, name: str) -> None:
        self._canvas.interpolation = name
        self._points_dirty = True
        self._parameter = None
        self._canvas.update()
        self._refresh_preview()

    def _set_freehand(self, enabled: bool) -> None:
        self._canvas.freehand = enabled

    def _delete_selected(self) -> None:
        index = self._canvas.selected
        if index is None or index == 0 or index == len(self._canvas.points) - 1:
            return
        if len(self._canvas.points) <= 2:
            return
        del self._canvas.points[index]
        self._canvas.selected = None
        self._on_points_changed()
        self._canvas.update()

    def _edit_parameters(self) -> None:
        start = self._parameter
        if start is None or not _is_parameter(start):
            from core.lut_catalog import gamma_lut

            start = gamma_lut(1.0)
        updated = edit_lut_parameters(start, self)
        if updated is None:
            return
        self._parameter = updated
        self._points_dirty = False
        self._load(updated)
        self._remember()
        self._canvas.update()
        self._refresh_preview()

    def _undo_points(self) -> None:
        if len(self._undo) < 2:
            return
        self._redo.append(self._undo.pop())
        self._canvas.points = list(self._undo[-1])
        self._points_dirty = True
        self._parameter = None
        self._canvas.update()
        self._refresh_preview()

    def _redo_points(self) -> None:
        if not self._redo:
            return
        points = self._redo.pop()
        self._undo.append(list(points))
        self._canvas.points = list(points)
        self._canvas.update()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        lut = self.result_lut()
        self._preview.set_lut(
            lut,
            window_center=_optional_float(self._display.get("window_center")),
            window_width=_optional_float(self._display.get("window_width")),
            photometric_interpretation=self._display.get("photometric"),
            image_inverted=bool(self._display.get("image_inverted", False)),
        )


def edit_lut_curve(
    lut: LookUpTable | None,
    parent: QWidget | None,
    display: dict[str, Any] | None = None,
) -> LookUpTable | None:
    """Open the editor. Returns the LUT, or None on cancel."""
    dialog = LutCurveEditorDialog(lut, parent, display)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.result_lut()


def _curve_lut(points: list[tuple[float, float]], interpolation: str) -> LookUpTable:
    """Custom grayscale LUT. Endpoints are forced to x = 0 and x = 1."""
    pinned = list(points) if points else [(0.0, 0.0), (1.0, 1.0)]
    pinned[0] = (0.0, pinned[0][1])
    pinned[-1] = (1.0, pinned[-1][1])
    mode = interpolation if interpolation in _INTERPOLATION else "linear"
    return LookUpTable(
        name="Custom",
        source="custom",
        control_points=tuple(pinned),
        interpolation=mode,  # type: ignore[arg-type]
    )


def _is_parameter(lut: LookUpTable | None) -> bool:
    if lut is None or lut.transfer_fn is None:
        return False
    return lut.transfer_fn in (gamma_transfer, sigmoid_transfer, exponential_transfer)


def _separate_x(unit: tuple[float, float], points: list[tuple[float, float]]) -> tuple[float, float]:
    """Nudge a new point off an existing x so the LUT stays strictly increasing."""
    x, y = unit
    used = {round(point[0], 5) for point in points}
    if round(x, 5) not in used:
        return (x, y)
    for step in range(1, 50):
        candidate = min(0.99, max(0.01, x + step * 0.01))
        if round(candidate, 5) not in used:
            return (candidate, y)
    return (x, y)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number
