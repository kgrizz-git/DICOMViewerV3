"""
Export Dialog

This module provides the Export dialog UI for exporting DICOM images to JPEG,
PNG, and DICOM formats, with hierarchical selection of studies, series, and slices.
Export execution is delegated to core.export_manager.ExportManager.

Inputs:
    - User export preferences
    - DICOM studies data
    - Window/level settings
    - Export format and scope
    - Output directory

Outputs:
    - Exported image files (via ExportManager)

Requirements:
    - PySide6 for dialogs
    - core.export_manager for export execution
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QComboBox, QPushButton, QFileDialog, QMessageBox,
                                QGroupBox, QRadioButton, QButtonGroup, QTreeWidget,
                                QTreeWidgetItem, QCheckBox)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QStandardItemModel, QStandardItem
from typing import Optional, List, Dict, Tuple, Any
import os

from pydicom.dataset import Dataset

from core.export_manager import ExportManager


class ExportDialog(QDialog):
    """
    Dialog for exporting DICOM images with hierarchical selection.
    
    Features:
    - Hierarchical selection of studies, series, and slices
    - Select export format (JPEG, PNG, DICOM)
    - Window/level options
    - Overlay/ROI inclusion option
    - Choose output location
    """
    
    def __init__(
        self,
        studies: Dict[str, Dict[str, List[Dataset]]],
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        focused_subwindow_index: Optional[int] = None,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        text_annotation_tool=None,
        arrow_annotation_tool=None,
        projection_enabled: bool = False,
        projection_type: str = "aip",
        projection_slice_count: int = 4,
        subwindow_annotation_managers: Optional[List[Dict[str, Any]]] = None,
        parent=None
    ):
        """
        Initialize the export dialog.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_window_center: Optional current window center from viewer (focused sub-window)
            current_window_width: Optional current window width from viewer (focused sub-window)
            focused_subwindow_index: Optional 0-based index of the focused sub-window (for label, e.g. "sub-window 1")
            use_rescaled_values: Whether to use rescaled values (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            projection_enabled: Whether intensity projection (combine slices) is enabled
            projection_type: Type of projection ("aip", "mip", or "minip")
            projection_slice_count: Number of slices to combine (2, 3, 4, 6, or 8)
            subwindow_annotation_managers: Optional list of per-subwindow dicts (roi_manager, measurement_tool,
                text_annotation_tool, arrow_annotation_tool). When provided, annotations are aggregated from all
                subwindows for export (Option B).
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Export Images")
        self.setModal(True)
        self.resize(800, 600)
        
        self.studies = studies
        self.current_window_center = current_window_center
        self.current_window_width = current_window_width
        self.focused_subwindow_index = focused_subwindow_index  # 0-based; None if unknown
        self.use_rescaled_values = use_rescaled_values
        self.roi_manager = roi_manager
        self.overlay_manager = overlay_manager
        self.measurement_tool = measurement_tool
        self.config_manager = config_manager
        self.text_annotation_tool = text_annotation_tool
        self.arrow_annotation_tool = arrow_annotation_tool
        self.projection_enabled = projection_enabled
        self.projection_type = projection_type
        self.projection_slice_count = projection_slice_count
        self.subwindow_annotation_managers = subwindow_annotation_managers or []
        
        self.export_format = "PNG"
        self.window_level_option = "current"  # "current" or "dataset"
        self.include_overlays = True
        self.export_scale = 1.0  # 1.0, 1.5, 2.0, or 4.0
        self.anonymize_enabled = False
        
        # Get last export path from config if available
        if config_manager:
            self.output_path = config_manager.get_last_export_path()
        else:
            self.output_path = ""
        
        # Store selected items: {(study_uid, series_uid, slice_index): dataset}
        self.selected_items: Dict[Tuple[str, str, int], Dataset] = {}
        
        self._create_ui()
        self._populate_tree()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()
        
        self.format_group = QButtonGroup()
        self.png_radio = QRadioButton("PNG")
        self.jpg_radio = QRadioButton("JPG")
        self.dicom_radio = QRadioButton("DICOM")
        
        self.png_radio.setChecked(True)
        
        self.format_group.addButton(self.png_radio, 0)
        self.format_group.addButton(self.jpg_radio, 1)
        self.format_group.addButton(self.dicom_radio, 2)
        
        format_layout.addWidget(self.png_radio)
        format_layout.addWidget(self.jpg_radio)
        format_layout.addWidget(self.dicom_radio)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # Projection information label (if enabled)
        if self.projection_enabled:
            # Map projection type to display name
            projection_name_map = {
                "aip": "Average Intensity Projection (AIP)",
                "mip": "Maximum Intensity Projection (MIP)",
                "minip": "Minimum Intensity Projection (MinIP)"
            }
            projection_display_name = projection_name_map.get(self.projection_type, "Unknown")
            
            projection_info_label = QLabel(
                f"<b>Note:</b> Combine Slices is enabled. Exports will use <b>{projection_display_name}</b> with <b>{self.projection_slice_count}</b> slices combined."
            )
            projection_info_label.setWordWrap(True)
            projection_info_label.setStyleSheet("QLabel { color: #0066cc; padding: 5px; }")
            layout.addWidget(projection_info_label)
        
        # Anonymize option (only for DICOM)
        self.anonymize_checkbox = QCheckBox("Anonymize patient information (DICOM only)")
        self.anonymize_checkbox.setEnabled(False)  # Initially disabled (only enabled for DICOM)
        self.anonymize_checkbox.setChecked(False)
        self.anonymize_checkbox.toggled.connect(lambda checked: setattr(self, 'anonymize_enabled', checked))
        layout.addWidget(self.anonymize_checkbox)
        
        # Window/Level options (only for PNG/JPG)
        self.window_level_group = QGroupBox("Window/Level (for PNG/JPG)")
        window_level_layout = QVBoxLayout()
        
        self.window_level_button_group = QButtonGroup()
        # Label clarifies focused sub-window and shows center/width when available (e.g. "sub-window 1 - 44/486")
        if (self.current_window_center is not None and self.current_window_width is not None
                and self.focused_subwindow_index is not None):
            sub_num = self.focused_subwindow_index + 1
            c = int(round(self.current_window_center))
            w = int(round(self.current_window_width))
            current_wl_label = f"Use currently focused sub-window window/level (sub-window {sub_num} - {c}/{w})"
        else:
            current_wl_label = "Use currently focused sub-window window/level"
        self.current_wl_radio = QRadioButton(current_wl_label)
        self.dataset_wl_radio = QRadioButton("Use dataset default window/level")
        
        # Default to current if available, otherwise dataset
        if self.current_window_center is not None and self.current_window_width is not None:
            self.current_wl_radio.setChecked(True)
            self.window_level_option = "current"
        else:
            self.dataset_wl_radio.setChecked(True)
            self.window_level_option = "dataset"
            self.current_wl_radio.setEnabled(False)
        
        self.window_level_button_group.addButton(self.current_wl_radio, 0)
        self.window_level_button_group.addButton(self.dataset_wl_radio, 1)
        
        self.current_wl_radio.toggled.connect(lambda checked: setattr(self, 'window_level_option', 'current') if checked else None)
        self.dataset_wl_radio.toggled.connect(lambda checked: setattr(self, 'window_level_option', 'dataset') if checked else None)
        
        window_level_layout.addWidget(self.current_wl_radio)
        window_level_layout.addWidget(self.dataset_wl_radio)
        
        self.window_level_group.setLayout(window_level_layout)
        layout.addWidget(self.window_level_group)
        
        # Overlay/ROI option (only for PNG/JPG)
        self.overlay_checkbox = QCheckBox("Include overlays and ROIs (PNG/JPG only)")
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.toggled.connect(lambda checked: setattr(self, 'include_overlays', checked))
        layout.addWidget(self.overlay_checkbox)
        
        # Resolution: Native, 1.5×, 2×, 4× (only for PNG/JPG); scale limits applied on selection
        self.resolution_group = QGroupBox("Resolution (PNG/JPG)")
        resolution_layout = QVBoxLayout()
        self.resolution_combo = QComboBox()
        resolution_model = QStandardItemModel()
        for label, scale in [("Native resolution", 1.0), ("1.5×", 1.5), ("2×", 2.0), ("4×", 4.0)]:
            item = QStandardItem(label)
            item.setData(scale, Qt.ItemDataRole.UserRole)
            resolution_model.appendRow(item)
        self.resolution_combo.setModel(resolution_model)
        self.resolution_combo.setCurrentIndex(0)
        self.resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        resolution_layout.addWidget(self.resolution_combo)
        self.resolution_group.setLayout(resolution_layout)
        layout.addWidget(self.resolution_group)
        
        # Update window/level and overlay options when format changes
        self.png_radio.toggled.connect(self._on_format_changed)
        self.jpg_radio.toggled.connect(self._on_format_changed)
        self.dicom_radio.toggled.connect(self._on_format_changed)
        
        # Selection tree
        selection_group = QGroupBox("Select Studies, Series, and Slices")
        selection_layout = QVBoxLayout()
        
        # Select/Deselect buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._toggle_all(True))
        button_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self._toggle_all(False))
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        
        selection_layout.addLayout(button_layout)
        
        # Tree widget
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Item", "Count"])
        self.tree_widget.setColumnWidth(0, 400)
        self.tree_widget.setColumnWidth(1, 100)
        self.tree_widget.itemChanged.connect(self._on_item_changed)
        selection_layout.addWidget(self.tree_widget)
        
        # Selection count label
        self.count_label = QLabel("Selected: 0 items")
        selection_layout.addWidget(self.count_label)
        
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)
        
        # Output path
        path_layout = QHBoxLayout()
        path_label = QLabel("Output Directory:")
        path_layout.addWidget(path_label)
        
        self.path_edit = QLabel("(Not selected)")
        # Show last export path if available
        if self.output_path:
            self.path_edit.setText(self.output_path)
        path_layout.addWidget(self.path_edit, 1)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output)
        path_layout.addWidget(browse_button)
        
        layout.addLayout(path_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_button = QPushButton("Export")
        export_button.clicked.connect(self._on_export)
        button_layout.addWidget(export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _on_format_changed(self) -> None:
        """Handle format selection change."""
        is_image_format = self.png_radio.isChecked() or self.jpg_radio.isChecked()
        is_dicom_format = self.dicom_radio.isChecked()
        
        self.window_level_group.setEnabled(is_image_format)
        self.overlay_checkbox.setEnabled(is_image_format)
        self.resolution_group.setEnabled(is_image_format)
        self.anonymize_checkbox.setEnabled(is_dicom_format)
        
        if not is_image_format:
            self.overlay_checkbox.setChecked(False)
            self.include_overlays = False
        else:
            self.anonymize_checkbox.setChecked(False)
            self.anonymize_enabled = False
            self._update_resolution_availability()
    
    def _on_resolution_changed(self, index: int) -> None:
        """Sync export_scale from resolution combo."""
        scale = self.resolution_combo.currentData()
        if scale is not None:
            self.export_scale = float(scale)
    
    def _update_resolution_availability(self) -> None:
        """Keep all resolution options enabled; per-slice fallback and post-export message handle 8192 px limit."""
        # Scale options are always selectable. Export manager steps down (4→2→1.5→Native) per image
        # and reports which files were exported at lower magnification, so we do not disable or reset here.
        model = self.resolution_combo.model()
        if not isinstance(model, QStandardItemModel):
            return
        tooltip = "Images whose size would exceed 8192 px will be exported at a lower magnification; you will be notified after export."
        for i in range(self.resolution_combo.count()):
            scale = self.resolution_combo.itemData(i)
            item = model.item(i)
            if item is None:
                continue
            item.setEnabled(True)
            if scale is not None and float(scale) > 1.0:
                item.setToolTip(tooltip)
            else:
                item.setToolTip("")
    
    def _populate_tree(self) -> None:
        """Populate the tree with studies, series, and slices."""
        self.tree_widget.clear()
        self.tree_widget.blockSignals(True)
        
        for study_uid, series_dict in self.studies.items():
            # Get first dataset to extract study info
            first_series_uid = list(series_dict.keys())[0]
            first_dataset = series_dict[first_series_uid][0]
            
            study_desc = getattr(first_dataset, 'StudyDescription', 'Unknown Study')
            study_date = getattr(first_dataset, 'StudyDate', '')
            if study_date:
                study_date = f" ({study_date})"
            
            # Count total slices in study
            total_slices = sum(len(datasets) for datasets in series_dict.values())
            
            # Create study item
            study_item = QTreeWidgetItem(self.tree_widget)
            study_item.setText(0, f"{study_desc}{study_date}")
            study_item.setText(1, str(total_slices))
            study_item.setData(0, Qt.ItemDataRole.UserRole, study_uid)
            study_item.setFlags(study_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            study_item.setCheckState(0, Qt.CheckState.Unchecked)
            study_item.setExpanded(True)
            
            # Add series items - sort by SeriesNumber
            # Create list of (series_uid, datasets, series_num) tuples for sorting
            series_list = []
            for series_uid, datasets in series_dict.items():
                first_ds = datasets[0]
                series_num = getattr(first_ds, 'SeriesNumber', '')
                # Convert to int for proper numeric sorting, use 0 if missing/invalid
                try:
                    series_num_int = int(series_num) if series_num else 0
                except (ValueError, TypeError):
                    series_num_int = 0
                series_list.append((series_uid, datasets, series_num_int))
            
            # Sort by SeriesNumber (ascending)
            series_list.sort(key=lambda x: x[2])
            
            # Add series items in sorted order
            for series_uid, datasets, _ in series_list:
                first_ds = datasets[0]
                series_num = getattr(first_ds, 'SeriesNumber', '')
                series_desc = getattr(first_ds, 'SeriesDescription', 'Unknown Series')
                modality = getattr(first_ds, 'Modality', '')
                
                series_item = QTreeWidgetItem(study_item)
                series_text = f"Series {series_num}: {series_desc} ({modality})"
                series_item.setText(0, series_text)
                series_item.setText(1, str(len(datasets)))
                series_item.setData(0, Qt.ItemDataRole.UserRole, series_uid)
                series_item.setData(0, Qt.ItemDataRole.UserRole + 1, study_uid)
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                series_item.setCheckState(0, Qt.CheckState.Unchecked)
                series_item.setExpanded(False)
                
                # Add slice items
                for idx, dataset in enumerate(datasets):
                    instance_num = getattr(dataset, 'InstanceNumber', idx + 1)
                    slice_item = QTreeWidgetItem(series_item)
                    slice_text = f"Instance {instance_num}"
                    slice_item.setText(0, slice_text)
                    slice_item.setText(1, "")
                    slice_item.setData(0, Qt.ItemDataRole.UserRole, idx)  # Slice index
                    slice_item.setData(0, Qt.ItemDataRole.UserRole + 1, series_uid)
                    slice_item.setData(0, Qt.ItemDataRole.UserRole + 2, study_uid)
                    slice_item.setFlags(slice_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    slice_item.setCheckState(0, Qt.CheckState.Unchecked)
        
        self.tree_widget.blockSignals(False)
        self._update_selection_count()
    
    def _toggle_all(self, checked: bool) -> None:
        """Toggle all items selection."""
        self.tree_widget.blockSignals(True)
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            study_item = root.child(i)
            study_item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tree_widget.blockSignals(False)
        self._update_selection()
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item checkbox state change."""
        if column != 0:
            return
        
        self.tree_widget.blockSignals(True)
        check_state = item.checkState(0)
        
        # If this is a study item, update all series
        if item.parent() is None:
            for i in range(item.childCount()):
                series_item = item.child(i)
                series_item.setCheckState(0, check_state)
                # Update all slices under this series
                for j in range(series_item.childCount()):
                    slice_item = series_item.child(j)
                    slice_item.setCheckState(0, check_state)
        # If this is a series item, update all slices
        elif item.parent().parent() is None:
            for i in range(item.childCount()):
                slice_item = item.child(i)
                slice_item.setCheckState(0, check_state)
            # Update parent study state
            self._update_parent_state(item.parent())
        # If this is a slice item, update parent series and study states
        else:
            self._update_parent_state(item.parent())
        
        self.tree_widget.blockSignals(False)
        self._update_selection()
    
    def _update_parent_state(self, item: QTreeWidgetItem) -> None:
        """Update parent item state based on children."""
        if item is None:
            return
        
        checked_count = 0
        unchecked_count = 0
        
        for i in range(item.childCount()):
            child = item.child(i)
            state = child.checkState(0)
            if state == Qt.CheckState.Checked:
                checked_count += 1
            elif state == Qt.CheckState.Unchecked:
                unchecked_count += 1
        
        total = item.childCount()
        if checked_count == total:
            item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked_count == total:
            item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        
        # Update grandparent if exists
        parent = item.parent()
        if parent is not None:
            self._update_parent_state(parent)
    
    def _update_selection(self) -> None:
        """Update selected items dictionary."""
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
                        dataset = self.studies[study_uid][series_uid][slice_index]
                        self.selected_items[key] = dataset
        
        self._update_selection_count()
        if self.png_radio.isChecked() or self.jpg_radio.isChecked():
            self._update_resolution_availability()
    
    def _update_selection_count(self) -> None:
        """Update selection count label."""
        count = len(self.selected_items)
        self.count_label.setText(f"Selected: {count} items")
    
    def _browse_output(self) -> None:
        """Browse for output directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Output Directory")
        
        # Set initial directory to last export path or current path
        if self.output_path and os.path.exists(self.output_path):
            dialog.setDirectory(self.output_path)
        elif self.config_manager:
            last_export_path = self.config_manager.get_last_export_path()
            if last_export_path and os.path.exists(last_export_path):
                dialog.setDirectory(last_export_path)
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                self.output_path = selected[0]
                self.path_edit.setText(self.output_path)
                # Save to config for next time
                if self.config_manager:
                    self.config_manager.set_last_export_path(self.output_path)
    
    def _on_export(self) -> None:
        """Handle export button click."""
        if not self.selected_items:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one item to export."
            )
            return
        
        if not self.output_path:
            QMessageBox.warning(
                self,
                "No Output Directory",
                "Please select an output directory."
            )
            return
        
        # Get export format
        if self.png_radio.isChecked():
            self.export_format = "PNG"
        elif self.jpg_radio.isChecked():
            self.export_format = "JPG"
        else:
            self.export_format = "DICOM"
        
        # Check for overwrites before exporting
        paths = ExportManager.get_export_paths_for_selection(
            self.selected_items,
            self.output_path,
            self.export_format,
            projection_enabled=self.projection_enabled,
            projection_type=self.projection_type,
            projection_slice_count=self.projection_slice_count
        )
        existing = [p for p in paths if os.path.exists(p)]
        if existing:
            msg = f"{len(existing)} file(s) already exist and will be overwritten.\n\nExamples:\n" + "\n".join(os.path.basename(p) for p in existing[:5])
            if len(existing) > 5:
                msg += f"\n... and {len(existing) - 5} more."
            msg += "\n\nContinue?"
            reply = QMessageBox.question(
                self,
                "Overwrite existing files?",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Get anonymize state (only for DICOM format)
        anonymize = self.anonymize_enabled and self.export_format == "DICOM"
        # Sync export scale from combo (in case index changed)
        scale_data = self.resolution_combo.currentData()
        export_scale = float(scale_data) if scale_data is not None else 1.0
        # Annotation sizes are formula-based only; do not scale with export magnification
        scale_annotations = False
        
        # Perform export
        try:
            manager = ExportManager()
            exported_count, downgraded_list = manager.export_selected(
                self.selected_items,
                self.output_path,
                self.export_format,
                self.window_level_option,
                self.current_window_center,
                self.current_window_width,
                self.include_overlays,
                self.use_rescaled_values,
                self.roi_manager,
                self.overlay_manager,
                self.measurement_tool,
                self.config_manager,
                self.text_annotation_tool,
                self.arrow_annotation_tool,
                self.studies,
                export_scale,
                scale_annotations,
                anonymize=anonymize,
                projection_enabled=self.projection_enabled,
                projection_type=self.projection_type,
                projection_slice_count=self.projection_slice_count,
                subwindow_annotation_managers=self.subwindow_annotation_managers
            )
            
            # Save export path to config for next time
            if self.config_manager and self.output_path:
                self.config_manager.set_last_export_path(self.output_path)
            
            msg = f"Successfully exported {exported_count} file(s) to:\n{self.output_path}"
            if downgraded_list:
                def scale_label(s: float) -> str:
                    if s == 1.0:
                        return "Native"
                    return f"{s}×"
                lines = []
                for filename, req, actual in downgraded_list[:20]:
                    lines.append(f"  • {filename}: requested {scale_label(req)}, exported at {scale_label(actual)} (would exceed 8192 px)")
                if len(downgraded_list) > 20:
                    lines.append(f"  ... and {len(downgraded_list) - 20} more.")
                msg += "\n\nThe following were exported at a lower magnification than requested (max dimension 8192 px):\n" + "\n".join(lines)
            QMessageBox.information(
                self,
                "Export Complete",
                msg
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export files:\n{str(e)}"
            )


