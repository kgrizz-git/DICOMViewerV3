"""
Export ROI Statistics Dialog

Dialog for exporting ROI statistics and crosshair coordinates to TXT, CSV, or XLSX.
Series selection (with annotation counts), format choice, rescale option, and file path.

Inputs:
    - current_studies: {study_uid: {series_uid: [Dataset]}}
    - subwindow_managers: {idx: {'roi_manager', 'crosshair_manager', ...}}
    - config_manager: for last export path

Outputs:
    - User-selected file path and format; calls roi_export_service.run_export

Requirements:
    - PySide6 for dialog
    - core.roi_export_service for run_export, collect_roi_data
    - core.dicom_processor.DICOMProcessor for rescale check
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt
from pydicom.dataset import Dataset

from core.roi_export_service import run_export, _sanitize_filename
from core.dicom_processor import DICOMProcessor


def _count_annotations_for_series(
    study_uid: str,
    series_uid: str,
    num_slices: int,
    subwindow_managers: Dict[int, Dict[str, Any]],
) -> Tuple[int, int]:
    """Return (roi_count, crosshair_count) for the given series across all subwindows."""
    roi_count = 0
    crosshair_count = 0
    for z in range(num_slices):
        key = (study_uid, series_uid, z)
        for idx in subwindow_managers:
            managers = subwindow_managers[idx]
            if managers.get("roi_manager") and hasattr(managers["roi_manager"], "rois"):
                roi_count += len(managers["roi_manager"].rois.get(key, []))
            if managers.get("crosshair_manager") and hasattr(managers["crosshair_manager"], "crosshairs"):
                crosshair_count += len(managers["crosshair_manager"].crosshairs.get(key, []))
    return roi_count, crosshair_count


def _any_series_has_rescale(current_studies: Dict[str, Dict[str, List[Dataset]]]) -> bool:
    """Return True if any loaded dataset has rescale parameters."""
    for series_dict in current_studies.values():
        for datasets in series_dict.values():
            for ds in datasets:
                slope, intercept, _ = DICOMProcessor.get_rescale_parameters(ds)
                if slope is not None and intercept is not None:
                    return True
    return False


class ExportROIStatisticsDialog(QDialog):
    """
    Dialog for exporting ROI statistics and crosshair data.

    Features:
    - Series tree with study → series and annotation counts (ROIs, crosshairs)
    - Format: TXT, CSV, XLSX
    - Rescale checkbox (use HU etc. when available)
    - File path with Browse; default filename from AccessionNumber or PatientID
    - Export validates selection and path, runs service, closes on success
    """

    def __init__(
        self,
        current_studies: Dict[str, Dict[str, List[Dataset]]],
        subwindow_managers: Dict[int, Dict[str, Any]],
        config_manager: Optional[Any] = None,
        parent: Optional[Any] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Export ROI Statistics")
        self.setModal(True)
        self.resize(700, 500)

        self.current_studies = current_studies
        self.subwindow_managers = subwindow_managers
        self.config_manager = config_manager

        self._create_ui()
        self._populate_series()
        self._update_default_file_path()
        self._format_group.buttonClicked.connect(self._on_format_changed)

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: series selection
        series_group = QGroupBox("Select Series")
        series_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_series(True))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_series(False))
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch()
        series_layout.addLayout(btn_layout)
        self.series_tree = QTreeWidget()
        self.series_tree.setHeaderLabels(["Series"])
        self.series_tree.setColumnWidth(0, 320)
        self.series_tree.itemChanged.connect(self._on_series_selection_changed)
        series_layout.addWidget(self.series_tree)
        series_group.setLayout(series_layout)
        splitter.addWidget(series_group)

        # Right: options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        # Format
        options_layout.addWidget(QLabel("Format:"))
        self._format_group = QButtonGroup(self)
        self.radio_txt = QRadioButton("TXT")
        self.radio_csv = QRadioButton("CSV")
        self.radio_xlsx = QRadioButton("XLSX")
        self.radio_xlsx.setChecked(True)
        self._format_group.addButton(self.radio_txt)
        self._format_group.addButton(self.radio_csv)
        self._format_group.addButton(self.radio_xlsx)
        options_layout.addWidget(self.radio_txt)
        options_layout.addWidget(self.radio_csv)
        options_layout.addWidget(self.radio_xlsx)

        # Rescale
        any_rescale = _any_series_has_rescale(self.current_studies)
        self.rescale_checkbox = QCheckBox("Use rescaled values (e.g. HU) if available")
        self.rescale_checkbox.setChecked(any_rescale)
        options_layout.addWidget(self.rescale_checkbox)

        # File path
        options_layout.addWidget(QLabel("File path:"))
        path_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Choose path with Browse...")
        path_layout.addWidget(self.file_path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file)
        path_layout.addWidget(browse_btn)
        options_layout.addLayout(path_layout)

        options_group.setLayout(options_layout)
        splitter.addWidget(options_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._do_export)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(export_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def _populate_series(self) -> None:
        self.series_tree.clear()
        self.series_tree.blockSignals(True)
        for study_uid, series_dict in self.current_studies.items():
            first_series_uid = next(iter(series_dict.keys()), None)
            if not first_series_uid:
                continue
            first_ds = series_dict[first_series_uid][0]
            study_desc = getattr(first_ds, "StudyDescription", "Unknown Study")
            study_item = QTreeWidgetItem(self.series_tree)
            study_item.setText(0, study_desc)
            study_item.setData(0, Qt.ItemDataRole.UserRole, study_uid)
            study_item.setFlags(study_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            study_item.setCheckState(0, Qt.CheckState.Unchecked)
            study_item.setExpanded(True)
            for series_uid, datasets in series_dict.items():
                if not datasets:
                    continue
                first_ds = datasets[0]
                series_num = getattr(first_ds, "SeriesNumber", "")
                series_desc = getattr(first_ds, "SeriesDescription", "Unknown Series")
                num_slices = len(datasets)
                roi_count, cross_count = _count_annotations_for_series(
                    study_uid, series_uid, num_slices, self.subwindow_managers
                )
                suffix = ""
                if roi_count or cross_count:
                    parts = []
                    if roi_count:
                        parts.append(f"{roi_count} ROI{'s' if roi_count != 1 else ''}")
                    if cross_count:
                        parts.append(f"{cross_count} crosshair{'s' if cross_count != 1 else ''}")
                    suffix = "  (" + ", ".join(parts) + ")"
                series_text = f"Series {series_num}: {series_desc}{suffix}"
                series_item = QTreeWidgetItem(study_item)
                series_item.setText(0, series_text)
                series_item.setData(0, Qt.ItemDataRole.UserRole, series_uid)
                series_item.setData(0, Qt.ItemDataRole.UserRole + 1, study_uid)
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                series_item.setCheckState(0, Qt.CheckState.Unchecked)
        self.series_tree.blockSignals(False)

    def _toggle_all_series(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.series_tree.blockSignals(True)
        for i in range(self.series_tree.topLevelItemCount()):
            study_item = self.series_tree.topLevelItem(i)
            for j in range(study_item.childCount()):
                study_item.child(j).setCheckState(0, state)
        self.series_tree.blockSignals(False)
        self._update_default_file_path()

    def _on_series_selection_changed(self) -> None:
        self._update_default_file_path()

    def _get_selected_series(self) -> List[Tuple[str, str]]:
        selected: List[Tuple[str, str]] = []
        for i in range(self.series_tree.topLevelItemCount()):
            study_item = self.series_tree.topLevelItem(i)
            study_uid = study_item.data(0, Qt.ItemDataRole.UserRole)
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                if series_item.checkState(0) == Qt.CheckState.Checked:
                    series_uid = series_item.data(0, Qt.ItemDataRole.UserRole)
                    if study_uid and series_uid:
                        selected.append((study_uid, series_uid))
        return selected

    def _get_format_extension(self) -> str:
        if self.radio_txt.isChecked():
            return ".txt"
        if self.radio_csv.isChecked():
            return ".csv"
        return ".xlsx"

    def _update_default_file_path(self) -> None:
        selected = self._get_selected_series()
        base = "ROI_stats"
        suffix = ""
        if selected:
            study_uid, series_uid = selected[0]
            series_dict = self.current_studies.get(study_uid, {}).get(series_uid, [])
            if series_dict:
                first_ds = series_dict[0]
                accession = (getattr(first_ds, "AccessionNumber", "") or "").strip()
                patient_id = (getattr(first_ds, "PatientID", "") or "").strip()
                if accession:
                    base = _sanitize_filename(accession)
                elif patient_id:
                    base = _sanitize_filename(patient_id)
                suffix = " ROI stats"
        name = f"{base}{suffix}"
        ext = self._get_format_extension()
        current = self.file_path_edit.text().strip()
        if not current:
            if self.config_manager and hasattr(self.config_manager, "get_last_export_path"):
                last = self.config_manager.get_last_export_path()
                if last and os.path.isdir(last):
                    full = str(Path(last) / (name + ext))
                else:
                    full = name + ext
            else:
                full = name + ext
            self.file_path_edit.setText(full)
        else:
            p = Path(current)
            parent = str(p.parent) if p.parent != p else ""
            new_path = (Path(parent) / (name + ext)) if parent else (name + ext)
            self.file_path_edit.setText(str(new_path))

    def _on_format_changed(self) -> None:
        current = self.file_path_edit.text().strip()
        if not current:
            self._update_default_file_path()
            return
        p = Path(current)
        ext = self._get_format_extension()
        if p.suffix and p.suffix.lower() in (".txt", ".csv", ".xlsx"):
            new_path = str(p.with_suffix(ext))
        else:
            new_path = str(p) + ext if not current.endswith(ext) else current
        self.file_path_edit.setText(new_path)

    def _browse_file(self) -> None:
        ext = self._get_format_extension()
        if ext == ".txt":
            filter_str = "Text files (*.txt);;All files (*.*)"
        elif ext == ".csv":
            filter_str = "CSV files (*.csv);;All files (*.*)"
        else:
            filter_str = "Excel files (*.xlsx);;All files (*.*)"
        start_path = self.file_path_edit.text().strip() or ""
        if start_path:
            start_dir = str(Path(start_path).parent) if Path(start_path).parent else ""
            if not os.path.isdir(start_dir):
                start_path = ""
        if not start_path and self.config_manager and hasattr(self.config_manager, "get_last_export_path"):
            start_path = self.config_manager.get_last_export_path() or ""
        if not start_path or not os.path.isdir(start_path):
            start_path = os.getcwd()
        if os.path.isfile(start_path):
            start_path = os.path.dirname(start_path)
        default_name = Path(self.file_path_edit.text().strip()).name if self.file_path_edit.text().strip() else "ROI stats" + ext
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ROI Statistics",
            str(Path(start_path) / default_name),
            filter_str,
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            self.raise_()
            self.activateWindow()

    def _do_export(self) -> None:
        selected = self._get_selected_series()
        if not selected:
            QMessageBox.warning(
                self,
                "No Series Selected",
                "Please select at least one series to export.",
            )
            return
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            QMessageBox.warning(
                self,
                "No File Path",
                "Please specify a file path (use Browse to choose location).",
            )
            return
        format_key = "TXT" if self.radio_txt.isChecked() else "CSV" if self.radio_csv.isChecked() else "XLSX"
        use_rescale = self.rescale_checkbox.isChecked()
        try:
            run_export(
                file_path=file_path,
                format_key=format_key,
                selected_series=selected,
                current_studies=self.current_studies,
                subwindow_managers=self.subwindow_managers,
                use_rescale=use_rescale,
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not write file:\n{str(e)}\n\nYou can change the path and try again.",
            )
            return
        if self.config_manager and hasattr(self.config_manager, "set_last_export_path"):
            export_dir = str(Path(file_path).parent)
            self.config_manager.set_last_export_path(export_dir)
        QMessageBox.information(
            self,
            "Export Complete",
            f"ROI statistics exported to:\n{file_path}",
        )
        self.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
