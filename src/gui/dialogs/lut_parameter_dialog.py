"""
Slider for gamma, sigmoid steepness, or exponential steepness.

The dialog returns a new ``LookUpTable`` via ``dataclasses.replace``.
It does not mutate the LUT that was passed in.

Inputs:
    - A parameter LUT (gamma, sigmoid, or exponential)

Outputs:
    - A replacement LUT, or None if the user cancels

Requirements:
    - PySide6
    - dataclasses.replace on LookUpTable
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.lut_engine import (
    LookUpTable,
    exponential_transfer,
    gamma_transfer,
    sigmoid_transfer,
)


class LutParameterDialog(QDialog):
    """One slider whose range matches the LUT kind."""

    def __init__(self, lut: LookUpTable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = lut
        self._result = lut
        self.setWindowTitle(f"Adjust {lut.name}")
        self._slider = QSlider()
        self._slider.setOrientation(Qt.Orientation.Horizontal)
        self._label = QLabel()
        self._configure_range()
        self._slider.valueChanged.connect(self._on_value)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._slider)
        layout.addWidget(buttons)
        self._on_value(self._slider.value())

    def result_lut(self) -> LookUpTable:
        """LUT matching the slider at close time."""
        return self._result

    def _configure_range(self) -> None:
        fn = self._source.transfer_fn
        if fn is gamma_transfer:
            self._kind = "gamma"
            self._slider.setRange(1, 50)
            self._slider.setValue(int(round(_required(self._source.gamma) * 10)))
        elif fn is sigmoid_transfer:
            self._kind = "sigmoid"
            self._slider.setRange(1, 200)
            self._slider.setValue(int(round(_required(self._source.sigmoid_k) * 10)))
        elif fn is exponential_transfer:
            self._kind = "exponential"
            self._slider.setRange(1, 50)
            self._slider.setValue(int(round(self._source.exp_k * 10)))
        else:
            raise ValueError("LUT has no adjustable parameter")

    def _on_value(self, raw: int) -> None:
        value = max(raw, 1) / 10.0
        if self._kind == "gamma":
            self._result = replace(self._source, gamma=value)
            self._label.setText(f"Gamma {value:.1f}")
        elif self._kind == "sigmoid":
            self._result = replace(self._source, sigmoid_k=value)
            self._label.setText(f"Sigmoid steepness {value:.1f}")
        else:
            self._result = replace(self._source, exp_k=value)
            self._label.setText(f"Exponential steepness {value:.1f}")


def _required(value: float | None) -> float:
    """Return a parameter that the LUT kind guarantees is set."""
    if value is None:
        raise ValueError("parameter LUT is missing its value")
    return value


def edit_lut_parameters(lut: LookUpTable, parent: QWidget | None) -> LookUpTable | None:
    """Show the slider. Returns the replacement LUT, or None on cancel."""
    dialog = LutParameterDialog(lut, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.result_lut()
