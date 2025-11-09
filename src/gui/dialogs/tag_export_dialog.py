"""
DICOM Tag Export Dialog

This module provides a dialog for selecting and exporting DICOM tags to Excel or CSV.
Features multi-series selection and hierarchical tag selection with search.

Inputs:
    - Studies and series data (dict)
    - pydicom.Dataset objects
    
Outputs:
    - Excel or CSV files with exported tags
    
Requirements:
    - PySide6 for dialog components
    - openpyxl for Excel export
    - csv module (standard library) for CSV export
    - DICOMParser for tag extraction
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QTreeWidget, QTreeWidgetItem, QLineEdit,
                                QPushButton, QCheckBox, QGroupBox, QSplitter,
                                QFileDialog, QMessageBox, QComboBox)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict, Any, List
import pydicom
from pydicom.dataset import Dataset
from pathlib import Path
import csv

from core.dicom_parser import DICOMParser


class TagExportDialog(QDialog):
    """
    Dialog for exporting DICOM tags to Excel or CSV with series and tag selection.
    
    Features:
    - Multi-series selection grouped by study
    - Hierarchical tag selection (by group)
    - Search/filter tags
    - Export to Excel (one tab per study, one row per tag) or CSV (one file per study)
    - Tag selection presets (save/load/delete)
    """
    
    def __init__(self, studies: Dict[str, Dict[str, List[Dataset]]], config_manager=None, parent=None):
        """
        Initialize the tag export dialog.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            config_manager: Optional ConfigManager instance for preset storage
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Export DICOM Tags")
        self.setModal(True)
        self.resize(1000, 700)
        
        self.studies = studies
        self.config_manager = config_manager
        self.selected_series: Dict[str, List[str]] = {}  # {study_uid: [series_uids]}
        self.selected_tags: List[str] = []  # List of selected tag strings
        
        self._create_ui()
        self._populate_series()
        self._populate_tags()
        self._load_presets_list()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Main splitter for two panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Series selection
        series_panel = self._create_series_panel()
        splitter.addWidget(series_panel)
        
        # Right panel: Tag selection
        tag_panel = self._create_tag_panel()
        splitter.addWidget(tag_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_button = QPushButton("Export Tags...")
        export_button.clicked.connect(self._export_to_excel)
        button_layout.addWidget(export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _create_series_panel(self) -> QGroupBox:
        """Create the series selection panel."""
        group = QGroupBox("Select Series")
        layout = QVBoxLayout()
        
        # Select/Deselect buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_series(True))
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_series(False))
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Series tree
        self.series_tree = QTreeWidget()
        self.series_tree.setHeaderLabels(["Series"])
        self.series_tree.setColumnWidth(0, 350)
        self.series_tree.itemChanged.connect(self._on_series_selection_changed)
        layout.addWidget(self.series_tree)
        
        group.setLayout(layout)
        return group
    
    def _create_tag_panel(self) -> QGroupBox:
        """Create the tag selection panel."""
        group = QGroupBox("Select Tags to Export")
        layout = QVBoxLayout()
        
        # Preset management section
        if self.config_manager:
            preset_layout = QHBoxLayout()
            preset_label = QLabel("Preset:")
            self.preset_combo = QComboBox()
            self.preset_combo.setEditable(False)
            self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
            preset_layout.addWidget(preset_label)
            preset_layout.addWidget(self.preset_combo)
            
            save_preset_btn = QPushButton("Save As...")
            save_preset_btn.clicked.connect(self._save_preset)
            preset_layout.addWidget(save_preset_btn)
            
            load_preset_btn = QPushButton("Load")
            load_preset_btn.clicked.connect(self._load_preset)
            preset_layout.addWidget(load_preset_btn)
            
            delete_preset_btn = QPushButton("Delete")
            delete_preset_btn.clicked.connect(self._delete_preset)
            preset_layout.addWidget(delete_preset_btn)
            
            preset_layout.addStretch()
            layout.addLayout(preset_layout)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Filter:")
        self.tag_search = QLineEdit()
        self.tag_search.setPlaceholderText("Search tags...")
        self.tag_search.textChanged.connect(self._filter_tags)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.tag_search)
        layout.addLayout(search_layout)
        
        # Select/Deselect buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all_tags(True))
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_tags(False))
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        
        # Show private tags checkbox
        self.private_tags_checkbox = QCheckBox("Include Private Tags")
        self.private_tags_checkbox.setChecked(False)
        self.private_tags_checkbox.toggled.connect(self._populate_tags)
        button_layout.addWidget(self.private_tags_checkbox)
        
        layout.addLayout(button_layout)
        
        # Tags tree
        self.tags_tree = QTreeWidget()
        self.tags_tree.setHeaderLabels(["Tag", "Name"])
        self.tags_tree.setColumnWidth(0, 120)
        self.tags_tree.setColumnWidth(1, 300)
        self.tags_tree.itemChanged.connect(self._on_tag_selection_changed)
        layout.addWidget(self.tags_tree)
        
        group.setLayout(layout)
        return group
    
    def _populate_series(self) -> None:
        """Populate the series tree with available series."""
        self.series_tree.clear()
        self.series_tree.blockSignals(True)
        
        for study_uid, series_dict in self.studies.items():
            # Get first dataset to extract study info
            first_series_uid = list(series_dict.keys())[0]
            first_dataset = series_dict[first_series_uid][0]
            
            study_desc = getattr(first_dataset, 'StudyDescription', 'Unknown Study')
            study_date = getattr(first_dataset, 'StudyDate', '')
            if study_date:
                study_date = f" ({study_date})"
            
            # Create study item
            study_item = QTreeWidgetItem(self.series_tree)
            study_item.setText(0, f"{study_desc}{study_date}")
            study_item.setData(0, Qt.ItemDataRole.UserRole, study_uid)
            study_item.setFlags(study_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            study_item.setCheckState(0, Qt.CheckState.Unchecked)
            study_item.setExpanded(True)
            
            # Add series items
            for series_uid, datasets in series_dict.items():
                first_ds = datasets[0]
                series_num = getattr(first_ds, 'SeriesNumber', '')
                series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown Series')
                modality = getattr(first_ds, 'Modality', '')
                
                series_item = QTreeWidgetItem(study_item)
                series_text = f"Series {series_num}: {series_desc} ({modality}) - {len(datasets)} images"
                series_item.setText(0, series_text)
                series_item.setData(0, Qt.ItemDataRole.UserRole, series_uid)
                series_item.setData(0, Qt.ItemDataRole.UserRole + 1, study_uid)
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                series_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.series_tree.blockSignals(False)
    
    def _populate_tags(self) -> None:
        """Populate the tags tree with DICOM tags from a representative dataset."""
        self.tags_tree.clear()
        self.tags_tree.blockSignals(True)
        
        # Get a representative dataset (first series, first image)
        if not self.studies:
            self.tags_tree.blockSignals(False)
            return
        
        first_study_uid = list(self.studies.keys())[0]
        first_series_uid = list(self.studies[first_study_uid].keys())[0]
        first_dataset = self.studies[first_study_uid][first_series_uid][0]
        
        parser = DICOMParser(first_dataset)
        tags = parser.get_all_tags(include_private=self.private_tags_checkbox.isChecked())
        
        # Sort tags by tag number
        sorted_tags = sorted(tags.items(), key=lambda x: x[0])
        
        # Group by tag group (first 4 hex digits)
        groups: Dict[str, list] = {}
        for tag_str, tag_data in sorted_tags:
            group = tag_str[:6]  # e.g., "(0008," for group 0008
            if group not in groups:
                groups[group] = []
            groups[group].append((tag_str, tag_data))
        
        # Create tree items
        for group, tag_list in sorted(groups.items()):
            group_item = QTreeWidgetItem(self.tags_tree)
            group_item.setText(0, f"Group {group[1:5]}")  # Remove parentheses
            group_item.setText(1, f"{len(tag_list)} tags")
            group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
            group_item.setExpanded(False)
            
            for tag_str, tag_data in tag_list:
                tag_item = QTreeWidgetItem(group_item)
                tag_item.setText(0, tag_data.get("tag", tag_str))
                tag_item.setText(1, tag_data.get("name", ""))
                tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
                tag_item.setFlags(tag_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                tag_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.tags_tree.blockSignals(False)
    
    def _toggle_all_series(self, checked: bool) -> None:
        """Toggle all series selection."""
        self.series_tree.blockSignals(True)
        root = self.series_tree.invisibleRootItem()
        for i in range(root.childCount()):
            study_item = root.child(i)
            study_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                series_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.series_tree.blockSignals(False)
        self._update_selected_series()
    
    def _toggle_all_tags(self, checked: bool) -> None:
        """Toggle all tag selection."""
        self.tags_tree.blockSignals(True)
        root = self.tags_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            if not group_item.isHidden():
                group_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                for j in range(group_item.childCount()):
                    tag_item = group_item.child(j)
                    if not tag_item.isHidden():
                        tag_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tags_tree.blockSignals(False)
        self._update_selected_tags()
    
    def _filter_tags(self, search_text: str) -> None:
        """Filter tags based on search text."""
        search_lower = search_text.lower()
        root = self.tags_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            group_item = root.child(i)
            group_has_visible_child = False
            
            for j in range(group_item.childCount()):
                tag_item = group_item.child(j)
                tag_text = tag_item.text(0).lower() + " " + tag_item.text(1).lower()
                
                if not search_text or search_lower in tag_text:
                    tag_item.setHidden(False)
                    group_has_visible_child = True
                else:
                    tag_item.setHidden(True)
            
            group_item.setHidden(not group_has_visible_child)
    
    def _on_series_selection_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle series selection changes."""
        # Block signals to prevent recursive calls
        self.series_tree.blockSignals(True)
        
        # If this is a study item, update all series under it
        if item.parent() is None:
            check_state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, check_state)
        else:
            # If this is a series item, update parent study's check state
            parent = item.parent()
            all_checked = True
            any_checked = False
            for i in range(parent.childCount()):
                child_state = parent.child(i).checkState(0)
                if child_state == Qt.CheckState.Unchecked:
                    all_checked = False
                else:
                    any_checked = True
            
            if all_checked:
                parent.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                parent.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.series_tree.blockSignals(False)
        self._update_selected_series()
    
    def _on_tag_selection_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle tag selection changes."""
        # Block signals to prevent recursive calls
        self.tags_tree.blockSignals(True)
        
        # If this is a group item, update all tags under it
        if item.parent() is None:
            check_state = item.checkState(0)
            for i in range(item.childCount()):
                if not item.child(i).isHidden():
                    item.child(i).setCheckState(0, check_state)
        else:
            # If this is a tag item, update parent group's check state
            parent = item.parent()
            all_checked = True
            any_checked = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                if not child.isHidden():
                    child_state = child.checkState(0)
                    if child_state == Qt.CheckState.Unchecked:
                        all_checked = False
                    else:
                        any_checked = True
            
            if all_checked:
                parent.setCheckState(0, Qt.CheckState.Checked)
            elif any_checked:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                parent.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.tags_tree.blockSignals(False)
        self._update_selected_tags()
    
    def _update_selected_series(self) -> None:
        """Update the list of selected series."""
        self.selected_series = {}
        root = self.series_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            study_item = root.child(i)
            study_uid = study_item.data(0, Qt.ItemDataRole.UserRole)
            
            series_list = []
            for j in range(study_item.childCount()):
                series_item = study_item.child(j)
                if series_item.checkState(0) == Qt.CheckState.Checked:
                    series_uid = series_item.data(0, Qt.ItemDataRole.UserRole)
                    series_list.append(series_uid)
            
            if series_list:
                self.selected_series[study_uid] = series_list
    
    def _update_selected_tags(self) -> None:
        """Update the list of selected tags."""
        self.selected_tags = []
        root = self.tags_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                tag_item = group_item.child(j)
                # Include all checked tags regardless of visibility (filter state)
                if tag_item.checkState(0) == Qt.CheckState.Checked:
                    tag_str = tag_item.data(0, Qt.ItemDataRole.UserRole)
                    self.selected_tags.append(tag_str)
    
    def _export_to_excel(self) -> None:
        """Export selected tags to Excel or CSV file."""
        # Update selected tags and series to ensure they're current
        self._update_selected_tags()
        self._update_selected_series()
        
        # Validate selections
        if not self.selected_series:
            QMessageBox.warning(self, "No Series Selected", 
                              "Please select at least one series to export.")
            return
        
        if not self.selected_tags:
            QMessageBox.warning(self, "No Tags Selected",
                              "Please select at least one tag to export.")
            return
        
        # Generate default filename
        default_filename = self._generate_default_filename()
        
        # Show file save dialog
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save DICOM Tag Export",
            default_filename,
            "Excel Files (*.xlsx);;CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # Determine format and ensure correct extension
        is_csv = selected_filter.startswith("CSV") or file_path.endswith('.csv')
        if is_csv:
            if not file_path.endswith('.csv'):
                file_path += '.csv'
        else:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
        
        # Perform export
        try:
            if is_csv:
                exported_files = self._write_csv_files(file_path)
                if len(exported_files) > 1:
                    file_list = "\n".join(str(f) for f in exported_files)
                    QMessageBox.information(self, "Export Complete",
                                          f"Tags exported successfully to {len(exported_files)} files:\n{file_list}")
                else:
                    QMessageBox.information(self, "Export Complete",
                                          f"Tags exported successfully to:\n{exported_files[0]}")
            else:
                self._write_excel_file(file_path)
                QMessageBox.information(self, "Export Complete",
                                  f"Tags exported successfully to:\n{file_path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export tags:\n{str(e)}")
    
    def _generate_default_filename(self) -> str:
        """Generate default filename for export."""
        # Get first selected series to extract info
        first_study_uid = list(self.selected_series.keys())[0]
        first_series_uid = self.selected_series[first_study_uid][0]
        first_dataset = self.studies[first_study_uid][first_series_uid][0]
        
        modality = getattr(first_dataset, 'Modality', 'Unknown')
        accession = getattr(first_dataset, 'AccessionNumber', 'Unknown')
        
        # Default to Excel format (user can change in file dialog)
        return f"{modality} DICOM Tag Export {accession}.xlsx"
    
    def _write_excel_file(self, file_path: str) -> None:
        """Write selected tags to Excel file."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment
        except ImportError:
            raise ImportError("openpyxl library is required for Excel export. "
                            "Install it with: pip install openpyxl")
        
        wb = Workbook()
        wb.remove(wb.active)  # Remove default sheet
        
        # Create one sheet per study
        for study_uid, series_uids in self.selected_series.items():
            # Get study info for sheet name
            first_series_uid = series_uids[0]
            first_dataset = self.studies[study_uid][first_series_uid][0]
            study_desc = getattr(first_dataset, 'StudyDescription', 'Study')
            # Sanitize sheet name (max 31 chars, no special chars)
            sheet_name = study_desc[:31].replace('/', '-').replace('\\', '-').replace(':', '-')
            
            ws = wb.create_sheet(title=sheet_name)
            
            # Write header
            ws['A1'] = 'Tag Number'
            ws['B1'] = 'Name'
            ws['C1'] = 'Value'
            ws['A1'].font = Font(bold=True)
            ws['B1'].font = Font(bold=True)
            ws['C1'].font = Font(bold=True)
            
            row = 2
            
            # Export each selected series
            for series_uid in series_uids:
                datasets = self.studies[study_uid][series_uid]
                first_ds = datasets[0]
                
                # Write series header
                series_num = getattr(first_ds, 'SeriesNumber', '')
                series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown')
                ws[f'A{row}'] = f"Series {series_num}: {series_desc}"
                ws[f'A{row}'].font = Font(bold=True, italic=True)
                ws.merge_cells(f'A{row}:C{row}')
                row += 1
                
                # Parse tags from first dataset of series
                parser = DICOMParser(first_ds)
                all_tags = parser.get_all_tags(include_private=self.private_tags_checkbox.isChecked())
                
                # Export selected tags
                for tag_str in self.selected_tags:
                    if tag_str in all_tags:
                        tag_data = all_tags[tag_str]
                        ws[f'A{row}'] = tag_data.get('tag', tag_str)
                        ws[f'B{row}'] = tag_data.get('name', '')
                        
                        # Format value
                        value = tag_data.get('value', '')
                        if isinstance(value, list):
                            value_str = ', '.join(str(v) for v in value)
                        else:
                            value_str = str(value)
                        ws[f'C{row}'] = value_str
                        
                        row += 1
                
                # Add blank row between series
                row += 1
        
        # Adjust column widths
        for sheet in wb.worksheets:
            sheet.column_dimensions['A'].width = 15
            sheet.column_dimensions['B'].width = 40
            sheet.column_dimensions['C'].width = 60
        
        # Save file
        wb.save(file_path)
    
    def _write_csv_files(self, base_file_path: str) -> List[Path]:
        """
        Write selected tags to CSV files (one file per study).
        
        Returns:
            List of created file paths
        """
        base_path = Path(base_file_path)
        base_name = base_path.stem
        base_dir = base_path.parent
        exported_files = []
        
        # Create one CSV file per study
        for study_uid, series_uids in self.selected_series.items():
            # Get study info for filename
            first_series_uid = series_uids[0]
            first_dataset = self.studies[study_uid][first_series_uid][0]
            study_desc = getattr(first_dataset, 'StudyDescription', 'Study')
            # Sanitize filename
            safe_study_desc = study_desc.replace('/', '-').replace('\\', '-').replace(':', '-')[:50]
            
            # Create filename: base_name_StudyDescription.csv
            if len(self.selected_series) > 1:
                csv_filename = f"{base_name}_{safe_study_desc}.csv"
            else:
                csv_filename = f"{base_name}.csv"
            
            csv_path = base_dir / csv_filename
            
            # Write CSV file
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Tag Number', 'Name', 'Value'])
                
                # Export each selected series
                for series_uid in series_uids:
                    datasets = self.studies[study_uid][series_uid]
                    first_ds = datasets[0]
                    
                    # Write series header
                    series_num = getattr(first_ds, 'SeriesNumber', '')
                    series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown')
                    writer.writerow([f"Series {series_num}: {series_desc}", '', ''])
                    
                    # Parse tags from first dataset of series
                    parser = DICOMParser(first_ds)
                    all_tags = parser.get_all_tags(include_private=self.private_tags_checkbox.isChecked())
                    
                    # Export selected tags
                    for tag_str in self.selected_tags:
                        if tag_str in all_tags:
                            tag_data = all_tags[tag_str]
                            tag_num = tag_data.get('tag', tag_str)
                            tag_name = tag_data.get('name', '')
                            
                            # Format value
                            value = tag_data.get('value', '')
                            if isinstance(value, list):
                                value_str = ', '.join(str(v) for v in value)
                            else:
                                value_str = str(value)
                            
                            writer.writerow([tag_num, tag_name, value_str])
                    
                    # Add blank row between series
                    writer.writerow([])
            
            exported_files.append(csv_path)
        
        return exported_files
    
    def _load_presets_list(self) -> None:
        """Load list of presets into combo box."""
        if not self.config_manager:
            return
        
        self.preset_combo.clear()
        presets = self.config_manager.get_tag_export_presets()
        if presets:
            self.preset_combo.addItems(sorted(presets.keys()))
        self.preset_combo.addItem("(No preset)")
        self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)
    
    def _on_preset_selected(self, preset_name: str) -> None:
        """Handle preset selection (for future use, e.g., auto-load on selection)."""
        pass
    
    def _save_preset(self) -> None:
        """Save current tag selections as a preset."""
        if not self.config_manager:
            QMessageBox.warning(self, "No Config Manager",
                              "Preset saving is not available.")
            return
        
        # Update selected tags first
        self._update_selected_tags()
        
        if not self.selected_tags:
            QMessageBox.warning(self, "No Tags Selected",
                              "Please select at least one tag to save as a preset.")
            return
        
        # Get preset name from user
        from PySide6.QtWidgets import QInputDialog
        preset_name, ok = QInputDialog.getText(
            self,
            "Save Preset",
            "Enter preset name:",
            text=""
        )
        
        if not ok or not preset_name.strip():
            return
        
        preset_name = preset_name.strip()
        
        # Save preset
        self.config_manager.save_tag_export_preset(preset_name, self.selected_tags)
        self._load_presets_list()
        
        # Select the newly saved preset
        index = self.preset_combo.findText(preset_name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        
        QMessageBox.information(self, "Preset Saved",
                               f"Preset '{preset_name}' saved successfully.")
    
    def _load_preset(self) -> None:
        """Load a preset and apply tag selections."""
        if not self.config_manager:
            QMessageBox.warning(self, "No Config Manager",
                              "Preset loading is not available.")
            return
        
        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == "(No preset)":
            QMessageBox.warning(self, "No Preset Selected",
                              "Please select a preset to load.")
            return
        
        # Get preset tags
        presets = self.config_manager.get_tag_export_presets()
        if preset_name not in presets:
            QMessageBox.warning(self, "Preset Not Found",
                              f"Preset '{preset_name}' not found.")
            return
        
        preset_tags = presets[preset_name]
        
        # Apply preset to tag tree
        self.tags_tree.blockSignals(True)
        root = self.tags_tree.invisibleRootItem()
        
        # First, uncheck all tags
        for i in range(root.childCount()):
            group_item = root.child(i)
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
            for j in range(group_item.childCount()):
                tag_item = group_item.child(j)
                tag_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        # Then check tags that are in the preset
        for i in range(root.childCount()):
            group_item = root.child(i)
            group_has_checked = False
            for j in range(group_item.childCount()):
                tag_item = group_item.child(j)
                tag_str = tag_item.data(0, Qt.ItemDataRole.UserRole)
                if tag_str in preset_tags:
                    tag_item.setCheckState(0, Qt.CheckState.Checked)
                    group_has_checked = True
            
            # Update group check state
            if group_has_checked:
                # Check if all tags in group are checked
                all_checked = True
                for j in range(group_item.childCount()):
                    if group_item.child(j).checkState(0) != Qt.CheckState.Checked:
                        all_checked = False
                        break
                if all_checked:
                    group_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        
        self.tags_tree.blockSignals(False)
        self._update_selected_tags()
        
        QMessageBox.information(self, "Preset Loaded",
                               f"Preset '{preset_name}' loaded successfully.")
    
    def _delete_preset(self) -> None:
        """Delete the selected preset."""
        if not self.config_manager:
            QMessageBox.warning(self, "No Config Manager",
                              "Preset deletion is not available.")
            return
        
        preset_name = self.preset_combo.currentText()
        if not preset_name or preset_name == "(No preset)":
            QMessageBox.warning(self, "No Preset Selected",
                              "Please select a preset to delete.")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Preset",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_tag_export_preset(preset_name)
            self._load_presets_list()
            QMessageBox.information(self, "Preset Deleted",
                                   f"Preset '{preset_name}' deleted successfully.")

