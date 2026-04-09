"""
Stage 1 dialog: optional scan-extent tolerance, vanilla stock pylinac toggle, and
HU-module origin slice for ACR CT (pylinac).

Does not import pylinac. Viewer integration (default) allows any in-range origin
index; vanilla mode uses stock ``ACRCT`` (stricter interior-only origin rule).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AcrCtQaOptionsDialog(QDialog):
    """Collect ACR CT pylinac options before analysis."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        vanilla_pylinac_default: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("ACR CT (pylinac) — Options")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        intro = QLabel(
            "By default the viewer uses integration classes that allow origin slices "
            "on the first, second, or last image. Enable Vanilla pylinac to use "
            "stock ACRCT (stricter slice-index rules, matches CLI pylinac). "
            "Physical scan-extent tolerance applies only to viewer integration, not "
            "vanilla."
        )
        intro.setWordWrap(True)

        self._vanilla = QCheckBox("Vanilla pylinac (stock ACRCT)")
        self._vanilla.setChecked(bool(vanilla_pylinac_default))
        self._vanilla.toggled.connect(self._on_vanilla_toggled)

        localisation = QGroupBox("HU linearity module (origin slice)")
        loc_form = QFormLayout()
        origin_hint = QLabel(
            "0-based slice index for the HU linearity (module 1) slice, or (auto). "
            "Viewer integration allows 0 … last; vanilla mode matches stock pylinac "
            "(typically indices 2 … N−2 only for auto-origin). Recorded in JSON."
        )
        origin_hint.setWordWrap(True)
        loc_form.addRow(origin_hint)
        self._origin_spin = QSpinBox()
        self._origin_spin.setRange(-1, 10_000)
        self._origin_spin.setSpecialValueText("(auto)")
        self._origin_spin.setValue(-1)
        loc_form.addRow("Origin slice index:", self._origin_spin)
        localisation.setLayout(loc_form)

        self._geom = QGroupBox("Scan extent (optional, viewer integration only)")
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
        self._geom.setLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._vanilla)
        layout.addWidget(localisation)
        layout.addWidget(self._geom)
        layout.addWidget(buttons)

        self._on_vanilla_toggled(self._vanilla.isChecked())

    def _on_vanilla_toggled(self, checked: bool) -> None:
        self._geom.setEnabled(not checked)
        if checked:
            self._extent_tol.setChecked(False)

    def get_options(self) -> Tuple[float, Optional[int], bool]:
        """
        Return ``(scan_extent_tolerance_mm, origin_slice_or_none, vanilla_pylinac)``.
        """
        vanilla = bool(self._vanilla.isChecked())
        tol = 0.0
        if not vanilla and self._extent_tol.isChecked():
            tol = float(self._tol_spin.value())
        origin = int(self._origin_spin.value())
        origin_out: Optional[int] = None if origin < 0 else origin
        return tol, origin_out, vanilla


def prompt_acr_ct_options(
    parent: Optional[QWidget] = None,
    *,
    vanilla_pylinac_default: bool = False,
) -> Optional[Tuple[float, Optional[int], bool]]:
    """
    Show modal dialog.

    Returns:
        ``(scan_extent_tolerance_mm, origin_slice, vanilla_pylinac)``, or
        ``None`` if cancelled.
    """
    dlg = AcrCtQaOptionsDialog(
        parent, vanilla_pylinac_default=vanilla_pylinac_default
    )
    dlg.activateWindow()
    dlg.raise_()
    if dlg.exec() != int(QDialog.DialogCode.Accepted):
        return None
    return dlg.get_options()
