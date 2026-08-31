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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from core.mpr_dicom_export import MprDicomExportOptions
from gui.dialogs.anonymization_options_widget import (
    BURNED_IN_PHI_WARNING,
    AnonymizationOptionsDialog,
)
from utils.deep_anonymizer import DeepAnonymizerOptions


class MprDicomSaveDialog(QDialog):
    """Collect series suffix and privacy / pixel options for MPR DICOM export."""

    def __init__(self, parent=None, *, orientation_label: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Save MPR as DICOM")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        info = "Exports one DICOM file per MPR plane with new series and instance UIDs."
        if orientation_label:
            info += f"\n\nOrientation: {orientation_label}"

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(info))

        form = QFormLayout()
        self._suffix = QLineEdit(self)
        self._suffix.setPlaceholderText("Optional text appended to Series Description")
        form.addRow("Series description suffix:", self._suffix)

        self._anonymizer_options = DeepAnonymizerOptions.standard_share()
        self._anonymize = QCheckBox("De-identify DICOM metadata", self)
        self._anonymize.setChecked(False)
        self._anonymize_options_button = QPushButton("Options…", self)
        self._anonymize_options_button.setEnabled(False)
        self._anonymize.toggled.connect(self._on_anonymize_toggled)
        self._anonymize_options_button.clicked.connect(self._open_anonymizer_options)
        anonymize_row = QHBoxLayout()
        anonymize_row.addWidget(self._anonymize)
        anonymize_row.addWidget(self._anonymize_options_button)
        form.addRow(anonymize_row)

        self._anonymize_scope_notice = QLabel(BURNED_IN_PHI_WARNING, self)
        self._anonymize_scope_notice.setObjectName("deidentificationScopeNotice")
        self._anonymize_scope_notice.setWordWrap(True)
        self._anonymize_scope_notice.setStyleSheet(
            "QLabel { color: #b45309; padding: 6px; background: #fffbeb; }"
        )
        self._anonymize_scope_notice.setVisible(False)
        form.addRow(self._anonymize_scope_notice)

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

    def _on_anonymize_toggled(self, checked: bool) -> None:
        """Show metadata-deidentification controls only when enabled."""
        self._anonymize_options_button.setEnabled(checked)
        self._anonymize_scope_notice.setVisible(checked)

    def _open_anonymizer_options(self) -> None:
        """Edit the same deep de-identification settings used by DICOM export."""
        dialog = AnonymizationOptionsDialog(self._anonymizer_options, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._anonymizer_options = dialog.get_options()

    def build_options(self, orientation_label: str) -> MprDicomExportOptions:
        """Return ``MprDicomExportOptions`` from the current dialog fields."""
        return MprDicomExportOptions(
            orientation_label=orientation_label or "",
            series_description_suffix=self._suffix.text().strip(),
            anonymize=self._anonymize.isChecked(),
            deep_anonymizer_options=(
                self._anonymizer_options if self._anonymize.isChecked() else None
            ),
            use_rescaled_pixel_values=self._rescaled.isChecked(),
            window_center_override=None,
            window_width_override=None,
            series_number=None,
        )
