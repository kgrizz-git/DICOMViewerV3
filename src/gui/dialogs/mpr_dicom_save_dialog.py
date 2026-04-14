"""
Small options dialog for **Save MPR as DICOM** (suffix, anonymize, rescale).

Used by ``MprController.prompt_save_mpr_as_dicom`` after the output folder is
chosen. Does not pick the folder (that uses ``QFileDialog`` like export flows).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from core.mpr_dicom_export import MprDicomExportOptions


class MprDicomSaveDialog(QDialog):
    """Collect series suffix and privacy / pixel options for MPR DICOM export."""

    def __init__(self, parent=None, *, orientation_label: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Save MPR as DICOM")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        info = (
            "Exports one DICOM file per MPR plane with new series and instance UIDs.\n"
            "Patient/study metadata follows the same rules as other DICOM exports."
        )
        if orientation_label:
            info += f"\n\nOrientation: {orientation_label}"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(info))

        form = QFormLayout()
        self._suffix = QLineEdit(self)
        self._suffix.setPlaceholderText("Optional text appended to Series Description")
        form.addRow("Series description suffix:", self._suffix)

        self._anonymize = QCheckBox("Anonymize patient identifiers (same as DICOM export)", self)
        self._anonymize.setChecked(False)
        form.addRow(self._anonymize)

        self._rescaled = QCheckBox(
            "Use rescaled pixel values (HU when slope/intercept present)", self
        )
        self._rescaled.setChecked(True)
        form.addRow(self._rescaled)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_options(self, orientation_label: str) -> MprDicomExportOptions:
        """Return ``MprDicomExportOptions`` from the current dialog fields."""
        return MprDicomExportOptions(
            orientation_label=orientation_label or "",
            series_description_suffix=self._suffix.text().strip(),
            anonymize=self._anonymize.isChecked(),
            use_rescaled_pixel_values=self._rescaled.isChecked(),
            window_center_override=None,
            window_width_override=None,
            series_number=None,
        )
