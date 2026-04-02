"""
Stage 1 dialog: optional scan-extent tolerance for ACR CT (pylinac).

Does not import pylinac. Default is strict (vanilla) behavior.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class AcrCtQaOptionsDialog(QDialog):
    """Collect optional scan-extent tolerance before ACR CT analysis."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACR CT (pylinac) — Options")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        intro = QLabel(
            "By default pylinac uses a strict check that the DICOM z-range covers "
            "all phantom modules. If analysis fails with a “physical scan extent” "
            "error but the scan truly covers the phantom, you may enable a small "
            "tolerance (recorded in JSON as non-vanilla)."
        )
        intro.setWordWrap(True)

        geom = QGroupBox("Scan extent (optional)")
        form = QFormLayout()
        self._extent_tol = QCheckBox(
            "Allow small scan-extent tolerance (DICOM z rounding)"
        )
        self._extent_tol.setChecked(False)
        self._tol_spin = QDoubleSpinBox()
        self._tol_spin.setRange(0.5, 2.0)
        self._tol_spin.setSingleStep(0.5)
        self._tol_spin.setDecimals(2)
        self._tol_spin.setValue(1.0)
        self._tol_spin.setEnabled(False)
        self._extent_tol.toggled.connect(self._tol_spin.setEnabled)
        form.addRow(self._extent_tol)
        form.addRow("Tolerance (mm):", self._tol_spin)
        geom.setLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(geom)
        layout.addWidget(buttons)

    def get_scan_extent_tolerance_mm(self) -> float:
        if not self._extent_tol.isChecked():
            return 0.0
        return float(self._tol_spin.value())


def prompt_acr_ct_options(parent: Optional[QWidget] = None) -> Optional[float]:
    """
    Show modal dialog; return scan_extent_tolerance_mm (0 = strict), or None if cancelled.
    """
    dlg = AcrCtQaOptionsDialog(parent)
    dlg.activateWindow()
    dlg.raise_()
    if dlg.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dlg.get_scan_extent_tolerance_mm()
