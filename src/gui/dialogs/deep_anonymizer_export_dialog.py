"""
Deep Anonymizer Export Dialog

Modal dialog for exporting DICOM with deep metadata stripping. All strip options
default on; includes a burned-in PHI warning (pixel text is not removed).

Inputs:
    studies dict, config_manager, parent widget

Outputs:
    DICOM files via ExportManager (deep_anonymize path)

Requirements:
    PySide6, gui.export_manager, utils.deep_anonymizer
"""

from __future__ import annotations

import os

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from gui.dialogs.anonymization_options_widget import AnonymizationOptionsWidget
from gui.export_manager import ExportManager
from utils.deep_anonymizer import DeepAnonymizerOptions
from utils.log_sanitizer import sanitize_message


class DeepAnonymizerExportDialog(QDialog):
    """Export selected slices as DICOM with configurable deep anonymization."""

    def __init__(
        self,
        studies: dict[str, dict[str, list[Dataset]]],
        config_manager=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("De-identify & Export DICOM (PS3.15)")
        self.setModal(True)
        self.resize(820, 700)

        self.studies = studies
        self.config_manager = config_manager
        self.output_path = config_manager.get_last_export_path() if config_manager else ""
        self.selected_items: dict[tuple[str, str, int], Dataset] = {}

        self._create_ui()
        self._populate_tree()

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.options_widget = AnonymizationOptionsWidget(
            DeepAnonymizerOptions.standard_share(), parent=self
        )
        layout.addWidget(self.options_widget)

        selection_group = QGroupBox("Select Studies, Series, and Slices (DICOM export)")
        selection_layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all(True))
        btn_row.addWidget(select_all_btn)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all(False))
        btn_row.addWidget(deselect_all_btn)
        btn_row.addStretch()
        selection_layout.addLayout(btn_row)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Item", "Count"])
        self.tree_widget.setColumnWidth(0, 420)
        self.tree_widget.itemChanged.connect(self._on_item_changed)
        selection_layout.addWidget(self.tree_widget)

        self.count_label = QLabel("Selected: 0 items")
        selection_layout.addWidget(self.count_label)

        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Output Directory:"))
        self.path_edit = QLabel(self.output_path or "(Not selected)")
        path_layout.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        export_btn = QPushButton("Export DICOM")
        export_btn.clicked.connect(self._on_export)
        button_layout.addWidget(export_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def get_options(self) -> DeepAnonymizerOptions:
        """Build DeepAnonymizerOptions from the shared options widget."""
        return self.options_widget.get_options()

    def _populate_tree(self) -> None:
        """Populate study/series/slice tree (same structure as ExportDialog)."""
        self.tree_widget.clear()
        self.tree_widget.blockSignals(True)

        for study_uid, series_dict in self.studies.items():
            first_series_uid = next(iter(series_dict))
            first_dataset = series_dict[first_series_uid][0]
            study_desc = getattr(first_dataset, "StudyDescription", "Unknown Study")
            study_date = getattr(first_dataset, "StudyDate", "")
            date_suffix = f" ({study_date})" if study_date else ""
            total_slices = sum(len(datasets) for datasets in series_dict.values())

            study_item = QTreeWidgetItem(self.tree_widget)
            study_item.setText(0, f"{study_desc}{date_suffix}")
            study_item.setText(1, str(total_slices))
            study_item.setData(0, Qt.ItemDataRole.UserRole, study_uid)
            study_item.setFlags(study_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            study_item.setCheckState(0, Qt.CheckState.Unchecked)
            study_item.setExpanded(True)

            series_list = []
            for series_uid, datasets in series_dict.items():
                first_ds = datasets[0]
                series_num = getattr(first_ds, "SeriesNumber", "")
                try:
                    series_num_int = int(series_num) if series_num else 0
                except (ValueError, TypeError):
                    series_num_int = 0
                series_list.append((series_uid, datasets, series_num_int))
            series_list.sort(key=lambda x: x[2])

            for series_uid, datasets, _ in series_list:
                first_ds = datasets[0]
                series_num = getattr(first_ds, "SeriesNumber", "")
                series_desc = getattr(first_ds, "SeriesDescription", "Unknown Series")
                modality = getattr(first_ds, "Modality", "")

                series_item = QTreeWidgetItem(study_item)
                series_item.setText(0, f"Series {series_num}: {series_desc} ({modality})")
                series_item.setText(1, str(len(datasets)))
                series_item.setData(0, Qt.ItemDataRole.UserRole, series_uid)
                series_item.setData(0, Qt.ItemDataRole.UserRole + 1, study_uid)
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                series_item.setCheckState(0, Qt.CheckState.Unchecked)

                for idx, dataset in enumerate(datasets):
                    instance_num = getattr(dataset, "InstanceNumber", idx + 1)
                    slice_item = QTreeWidgetItem(series_item)
                    slice_item.setText(0, f"Instance {instance_num}")
                    slice_item.setData(0, Qt.ItemDataRole.UserRole, idx)
                    slice_item.setData(0, Qt.ItemDataRole.UserRole + 1, series_uid)
                    slice_item.setData(0, Qt.ItemDataRole.UserRole + 2, study_uid)
                    slice_item.setFlags(slice_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    slice_item.setCheckState(0, Qt.CheckState.Unchecked)

        self.tree_widget.blockSignals(False)
        self._update_selection_count()

    def _toggle_all(self, checked: bool) -> None:
        self.tree_widget.blockSignals(True)
        root = self.tree_widget.invisibleRootItem()
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(root.childCount()):
            root.child(i).setCheckState(0, state)
        self.tree_widget.blockSignals(False)
        self._update_selection()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        self.tree_widget.blockSignals(True)
        check_state = item.checkState(0)
        if item.parent() is None:
            for i in range(item.childCount()):
                series_item = item.child(i)
                series_item.setCheckState(0, check_state)
                for j in range(series_item.childCount()):
                    series_item.child(j).setCheckState(0, check_state)
        elif item.parent().parent() is None:
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, check_state)
            self._update_parent_state(item.parent())
        else:
            self._update_parent_state(item.parent())
        self.tree_widget.blockSignals(False)
        self._update_selection()

    def _update_parent_state(self, item: QTreeWidgetItem | None) -> None:
        if item is None:
            return
        checked = unchecked = 0
        for i in range(item.childCount()):
            state = item.child(i).checkState(0)
            if state == Qt.CheckState.Checked:
                checked += 1
            elif state == Qt.CheckState.Unchecked:
                unchecked += 1
        total = item.childCount()
        if checked == total:
            item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked == total:
            item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        parent = item.parent()
        if parent is not None:
            self._update_parent_state(parent)

    def _update_selection(self) -> None:
        self.selected_items.clear()
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            study_item = root.child(i)
            study_uid = study_item.data(0, Qt.ItemDataRole.UserRole)
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                series_uid = series_item.data(0, Qt.ItemDataRole.UserRole)
                for k in range(series_item.childCount()):
                    slice_item = series_item.child(k)
                    if slice_item.checkState(0) == Qt.CheckState.Checked:
                        slice_index = slice_item.data(0, Qt.ItemDataRole.UserRole)
                        key = (study_uid, series_uid, slice_index)
                        self.selected_items[key] = self.studies[study_uid][series_uid][slice_index]
        self._update_selection_count()

    def _update_selection_count(self) -> None:
        self.count_label.setText(f"Selected: {len(self.selected_items)} items")

    def _browse_output(self) -> None:
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Output Directory")
        if self.output_path and os.path.exists(self.output_path):
            dialog.setDirectory(self.output_path)
        elif self.config_manager:
            last = self.config_manager.get_last_export_path()
            if last and os.path.exists(last):
                dialog.setDirectory(last)
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                self.output_path = selected[0]
                self.path_edit.setText(self.output_path)
                if self.config_manager:
                    self.config_manager.set_last_export_path(self.output_path)

    def _on_export(self) -> None:
        if not self.selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one item to export.")
            return
        if not self.output_path:
            QMessageBox.warning(self, "No Output Directory", "Please select an output directory.")
            return

        anonymizer_options = self.get_options()
        deep_anonymized_items = ExportManager.build_deep_anonymized_selection(
            self.selected_items,
            anonymizer_options,
        )
        paths = ExportManager.get_export_paths_for_selection(
            self.selected_items,
            self.output_path,
            "DICOM",
            deep_anonymize=True,
            deep_anonymizer_options=anonymizer_options,
            deep_anonymized_items=deep_anonymized_items,
        )
        existing = [p for p in paths if os.path.exists(p)]
        if existing:
            msg = (
                f"{len(existing)} file(s) already exist and will be overwritten.\n\nContinue?"
            )
            reply = QMessageBox.question(
                self,
                "Overwrite existing files?",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            manager = ExportManager()
            exported_count, _downgraded = manager.export_selected(
                self.selected_items,
                self.output_path,
                "DICOM",
                studies=self.studies,
                deep_anonymize=True,
                deep_anonymizer_options=anonymizer_options,
                deep_anonymized_items=deep_anonymized_items,
            )
            if self.config_manager and self.output_path:
                self.config_manager.set_last_export_path(self.output_path)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {exported_count} anonymized DICOM file(s) to:\n{self.output_path}",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export files:\n{sanitize_message(str(exc), redact_paths=True)}",
            )
