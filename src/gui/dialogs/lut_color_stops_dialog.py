"""
Edit a colormap as color stops.

Each row is one stop: its position in ``[0, 1]`` and its RGB color. Stops
sample to a ``(256, 3)`` table through ``LookUpTable(color_stops=...)``, so the
preview strip and the viewport use the same table. This surface is separate
from the grayscale curve editor: a stop is a color at a position, not an
``(x, y)`` breakpoint.

Opening a built-in colormap seeds five stops sampled from its table, so the
edit starts from the map the pane already shows.

Inputs:
    - Optional starting ``LookUpTable`` (a colormap, with or without stops)

Outputs:
    - A custom colormap ``LookUpTable``, or None on cancel

Requirements:
    - PySide6
    - core.lut_color_stops
    - core.lut_engine.LookUpTable
"""

from __future__ import annotations

from itertools import pairwise

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.lut_color_stops import COLOR_INTERPOLATIONS, ColorStop
from core.lut_engine import LookUpTable
from gui.widgets.lut_transfer_function_widget import LutTransferFunctionWidget

_SEED_POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
_DEFAULT_STOPS: tuple[ColorStop, ...] = ((0.0, (0, 0, 0)), (1.0, (255, 255, 255)))


def seed_stops(lut: LookUpTable | None) -> tuple[ColorStop, ...]:
    """Starting stops: the LUT's own, or five samples of a colormap table."""
    if lut is not None and lut.color_stops is not None:
        return lut.color_stops
    if lut is not None and lut.lut_type == "colormap" and lut.colormap is not None:
        table = lut.colormap
        stops = []
        for x in _SEED_POSITIONS:
            r, g, b = (int(v) for v in table[int(round(x * 255))])
            stops.append((x, (r, g, b)))
        return tuple(stops)
    return _DEFAULT_STOPS


class LutColorStopsDialog(QDialog):
    """Table of color stops with a live gradient preview."""

    def __init__(self, lut: LookUpTable | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Colormap")
        self._colors: list[tuple[int, int, int]] = []
        self._table = QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(["Position", "Color"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._interpolation = QComboBox(self)
        self._interpolation.addItems(list(COLOR_INTERPOLATIONS))
        if lut is not None and lut.color_stops is not None:
            self._interpolation.setCurrentText(lut.color_interpolation)
        self._interpolation.currentTextChanged.connect(lambda _text: self._refresh())
        self._preview = LutTransferFunctionWidget(self)
        self._error = QLabel("", self)
        add = QPushButton("Add Stop")
        add.clicked.connect(self._add_stop)
        remove = QPushButton("Remove Stop")
        remove.clicked.connect(self._remove_stop)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        for widget in (QLabel("Between stops:"), self._interpolation, add, remove):
            row.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(row)
        layout.addWidget(self._preview)
        layout.addWidget(self._error)
        layout.addWidget(self._buttons)
        for x, rgb in seed_stops(lut):
            self._append_row(x, rgb)
        self._refresh()

    def stops(self) -> list[tuple[float, tuple[int, int, int]]]:
        """Current rows as ``(x, (r, g, b))``, in table order."""
        found = []
        for row, rgb in enumerate(self._colors):
            spin = self._table.cellWidget(row, 0)
            x = float(spin.value()) if isinstance(spin, QDoubleSpinBox) else 0.0
            found.append((x, rgb))
        return found

    def result_lut(self) -> LookUpTable | None:
        """The edited colormap, or None while the stops are invalid."""
        try:
            return LookUpTable(
                name="Custom Colors",
                lut_type="colormap",
                source="custom",
                color_stops=tuple(self.stops()),
                color_interpolation="step" if self._interpolation.currentText() == "step" else "linear",
            )
        except ValueError:
            return None

    def set_stop_color(self, row: int, rgb: tuple[int, int, int]) -> None:
        """Replace one stop's color and repaint its swatch."""
        self._colors[row] = rgb
        button = self._table.cellWidget(row, 1)
        if isinstance(button, QPushButton):
            button.setStyleSheet(_swatch_style(rgb))
        self._refresh()

    def _append_row(self, x: float, rgb: tuple[int, int, int]) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._colors.append(rgb)
        spin = QDoubleSpinBox(self._table)
        spin.setRange(0.0, 1.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.05)
        spin.setValue(x)
        spin.valueChanged.connect(lambda _value: self._refresh())
        self._table.setCellWidget(row, 0, spin)
        button = QPushButton("", self._table)
        button.setStyleSheet(_swatch_style(rgb))
        button.clicked.connect(lambda _checked=False, owner=button: self._pick_color(owner))
        self._table.setCellWidget(row, 1, button)

    def _row_of(self, button: QPushButton) -> int | None:
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 1) is button:
                return row
        return None

    def _pick_color(self, button: QPushButton) -> None:
        row = self._row_of(button)
        if row is None:
            return
        chosen = QColorDialog.getColor(QColor(*self._colors[row]), self, "Stop Color")
        if chosen.isValid():
            self.set_stop_color(row, (chosen.red(), chosen.green(), chosen.blue()))

    def _add_stop(self) -> None:
        """Insert a stop midway along the widest gap, colored as the map is there."""
        stops = sorted(self.stops(), key=lambda item: item[0])
        gaps = [(b[0] - a[0], a, b) for a, b in pairwise(stops)]
        if not gaps:
            self._append_row(0.5, (128, 128, 128))
            self._refresh()
            return
        _width, left, right = max(gaps, key=lambda item: item[0])
        x = (left[0] + right[0]) / 2.0
        rgb = tuple(int(round((a + b) / 2.0)) for a, b in zip(left[1], right[1], strict=True))
        self._append_row(x, (rgb[0], rgb[1], rgb[2]))
        self._refresh()

    def _remove_stop(self) -> None:
        """Remove the selected stop. Two stops always remain."""
        row = self._table.currentRow()
        if row < 0 or self._table.rowCount() <= 2:
            return
        self._table.removeRow(row)
        del self._colors[row]
        self._refresh()

    def _refresh(self) -> None:
        lut = self.result_lut()
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(lut is not None)
        self._error.setText("" if lut is not None else "Each stop needs its own position.")
        self._preview.set_lut(lut)


def edit_color_stops(lut: LookUpTable | None, parent: QWidget | None) -> LookUpTable | None:
    """Open the editor. Returns the colormap, or None on cancel."""
    dialog = LutColorStopsDialog(lut, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.result_lut()


def _swatch_style(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"background-color: rgb({r}, {g}, {b}); border: 1px solid #555;"

