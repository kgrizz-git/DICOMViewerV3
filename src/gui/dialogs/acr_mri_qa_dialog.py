"""
Stage 1 dialog: ACR MRI Large (pylinac) advanced options.

Surfaces echo selection and optional check_uid for reproducibility in exports.
Does not import pylinac.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AcrMrIQaOptionsDialog(QDialog):
    """
    Collect MRI-specific pylinac options before running analysis.

    Returns:
        On accept: use_lowest_echo, echo_number (used when use_lowest_echo False),
        check_uid_strict, origin_slice (None if spin <= -1 sentinel).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACR MRI (pylinac) — Options")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        intro = QLabel(
            "Echo: pylinac uses the lowest echo by default if you leave "
            '"Use lowest echo number" checked.\n'
            "Match SeriesInstanceUID: enable for strict series matching when "
            "your pylinac version supports analyze(check_uid=...); otherwise "
            "the choice is recorded in JSON only."
        )
        intro.setWordWrap(True)

        advanced = QGroupBox("Advanced")
        form = QFormLayout()

        self._use_lowest_echo = QCheckBox("Use lowest echo number (recommended default)")
        self._use_lowest_echo.setChecked(True)
        self._use_lowest_echo.toggled.connect(self._on_use_lowest_toggled)

        self._echo_spin = QSpinBox()
        self._echo_spin.setRange(1, 32)
        self._echo_spin.setValue(1)
        self._echo_spin.setEnabled(False)

        self._check_uid = QCheckBox("Strict Series Instance UID matching (check_uid) when supported")
        self._check_uid.setChecked(True)

        self._origin_spin = QSpinBox()
        self._origin_spin.setRange(-1, 10_000)
        self._origin_spin.setSpecialValueText("(auto)")
        self._origin_spin.setValue(-1)

        form.addRow(self._use_lowest_echo)
        form.addRow("Echo number:", self._echo_spin)
        form.addRow(self._check_uid)
        form.addRow("Origin slice index (optional, -1 = auto):", self._origin_spin)
        advanced.setLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(advanced)
        layout.addWidget(buttons)

        self._on_use_lowest_toggled(self._use_lowest_echo.isChecked())

    def _on_use_lowest_toggled(self, checked: bool) -> None:
        self._echo_spin.setEnabled(not checked)

    def get_options(self) -> Tuple[Optional[int], bool, Optional[int]]:
        if self._use_lowest_echo.isChecked():
            echo: Optional[int] = None
        else:
            echo = int(self._echo_spin.value())
        check_uid = bool(self._check_uid.isChecked())
        origin = int(self._origin_spin.value())
        origin_out: Optional[int] = None if origin < 0 else origin
        return echo, check_uid, origin_out


def prompt_acr_mri_options(parent: Optional[QWidget] = None) -> Optional[Tuple[Optional[int], bool, Optional[int]]]:
    """
    Show modal options dialog; return (echo_number, check_uid, origin_slice) or None if cancelled.
    """
    dlg = AcrMrIQaOptionsDialog(parent)
    dlg.activateWindow()
    dlg.raise_()
    if dlg.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dlg.get_options()
