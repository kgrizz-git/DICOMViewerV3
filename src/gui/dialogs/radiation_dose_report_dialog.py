"""
Radiation dose SR (RDSR) summary dialog — read-only table, JSON/CSV export.

Shows :class:`core.rdsr_dose_sr.CtRadiationDoseSummary` for the current DICOM radiation dose SR (RDSR),
when the bounded dose parser recognizes the instance (often CT-related dose concepts).
Privacy Mode masks UIDs and device strings in the table; export offers an **Anonymize**
checkbox that applies the same masking before writing files.

Requirements: PySide6; ``pydicom`` dataset is not retained after parse (summary only).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.rdsr_dose_sr import (
    CtRadiationDoseSummary,
    apply_privacy_to_ct_radiation_dose_summary,
    write_dose_summary_csv,
    write_dose_summary_json,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


class RadiationDoseReportDialog(QDialog):
    """Modeless-capable dialog listing parsed radiation dose metrics from a dose SR (RDSR)."""

    def __init__(
        self,
        parent: Optional["QWidget"],
        summary: CtRadiationDoseSummary,
        *,
        get_privacy_enabled: Any,
        main_window: Optional["QWidget"] = None,
        series_description: str = "",
    ) -> None:
        super().__init__(parent)
        self._summary = summary
        self._get_privacy_enabled = get_privacy_enabled
        self._series_description = series_description or "Radiation dose SR"
        self.setWindowTitle(f"Radiation dose summary — {self._series_description}")
        self.setModal(False)
        self.resize(560, 420)
        self.setMinimumSize(400, 280)

        layout = QVBoxLayout(self)
        self._hint = QLabel(
            "Fixed dose-summary rows extracted from this SR when the parser finds standard "
            "identifiers and CT-style dose NUM items; many fluoroscopy RDSRs use different template "
            "nodes, so several cells may be empty. This is not a full SR tree—use "
            "Tools → View/Edit DICOM Tags for every element. Export may contain identifiers unless "
            "Anonymize export is checked."
        )
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._table = QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(["Field", "Value"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        export_row = QHBoxLayout()
        self._anonymize_cb = QCheckBox("Anonymize export (mask UIDs / device strings)")
        self._anonymize_cb.setChecked(True)
        export_row.addWidget(self._anonymize_cb)
        export_row.addStretch()
        self._json_btn = QPushButton("Export JSON…")
        self._csv_btn = QPushButton("Export CSV…")
        self._json_btn.clicked.connect(self._export_json)
        self._csv_btn.clicked.connect(self._export_csv)
        export_row.addWidget(self._json_btn)
        export_row.addWidget(self._csv_btn)
        layout.addLayout(export_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        if main_window is not None and hasattr(main_window, "privacy_view_toggled"):
            main_window.privacy_view_toggled.connect(self._on_privacy_toggled)  # type: ignore[attr-defined]

        self._populate_table()

    def _effective_privacy(self) -> bool:
        try:
            return bool(self._get_privacy_enabled())
        except Exception:
            return False

    def _on_privacy_toggled(self, _enabled: bool) -> None:
        self._populate_table()

    def _display_summary(self) -> CtRadiationDoseSummary:
        s = self._summary
        if self._effective_privacy():
            return apply_privacy_to_ct_radiation_dose_summary(s)
        return s

    def _populate_table(self) -> None:
        """Populate the fixed schema from ``CtRadiationDoseSummary`` (MVP subset), not a generic SR walk."""
        s = self._display_summary()
        rows: list[tuple[str, str]] = [
            ("Study Instance UID", _fmt(s.study_instance_uid)),
            ("Series Instance UID", _fmt(s.series_instance_uid)),
            ("SOP Instance UID", _fmt(s.sop_instance_uid)),
            ("Manufacturer", _fmt(s.manufacturer)),
            ("Manufacturer Model Name", _fmt(s.manufacturer_model_name)),
            ("Device Serial Number", _fmt(s.device_serial_number)),
            ("CTDIvol (mGy)", _fmt(s.ctdi_vol_mgy)),
            ("DLP (mGy·cm)", _fmt(s.dlp_mgy_cm)),
            ("SSDE (mGy)", _fmt(s.ssde_mgy)),
            ("Irradiation events (113819)", _fmt(s.irradiation_event_count)),
            ("Parse hit node cap", _fmt(s.parse_node_cap_hit)),
        ]
        self._table.setRowCount(len(rows))
        for r, (label, val) in enumerate(rows):
            self._table.setItem(r, 0, QTableWidgetItem(label))
            it = QTableWidgetItem(val)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(r, 1, it)

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export dose summary as JSON",
            str(Path.home() / "dose_summary.json"),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            write_dose_summary_json(
                path, self._summary, anonymize=self._anonymize_cb.isChecked()
            )
        except OSError as e:
            QMessageBox.warning(self, "Export", f"Could not write file:\n{e}")
            return
        QMessageBox.information(self, "Export", f"Wrote JSON:\n{path}")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export dose summary as CSV",
            str(Path.home() / "dose_summary.csv"),
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            write_dose_summary_csv(
                path, self._summary, anonymize=self._anonymize_cb.isChecked()
            )
        except OSError as e:
            QMessageBox.warning(self, "Export", f"Could not write file:\n{e}")
            return
        QMessageBox.information(self, "Export", f"Wrote CSV:\n{path}")
