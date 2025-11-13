"""
Export Dialog

This module provides export functionality for DICOM images to JPEG, PNG,
and DICOM formats, with hierarchical selection of studies, series, and slices.

Inputs:
    - User export preferences
    - DICOM studies data
    - Window/level settings
    - Export format and scope
    - Output directory
    
Outputs:
    - Exported image files
    
Requirements:
    - PySide6 for dialogs
    - PIL/Pillow for image export
    - pydicom for DICOM export
    - DICOMProcessor for image conversion
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QComboBox, QPushButton, QFileDialog, QMessageBox,
                                QGroupBox, QRadioButton, QButtonGroup, QTreeWidget,
                                QTreeWidgetItem, QCheckBox, QProgressDialog)
from PySide6.QtCore import Qt, QRectF
from typing import Optional, List, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont
import pydicom
from pydicom.dataset import Dataset
import os
import numpy as np

from core.dicom_processor import DICOMProcessor
from core.dicom_parser import DICOMParser


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
        current_zoom: Optional[float] = None,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        parent=None
    ):
        """
        Initialize the export dialog.
        
        Args:
            studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}
            current_window_center: Optional current window center from viewer
            current_window_width: Optional current window width from viewer
            current_zoom: Optional current zoom level from viewer
            use_rescaled_values: Whether to use rescaled values (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Export Images")
        self.setModal(True)
        self.resize(800, 600)
        
        self.studies = studies
        self.current_window_center = current_window_center
        self.current_window_width = current_window_width
        self.current_zoom = current_zoom
        self.use_rescaled_values = use_rescaled_values
        self.roi_manager = roi_manager
        self.overlay_manager = overlay_manager
        self.measurement_tool = measurement_tool
        self.config_manager = config_manager
        
        self.export_format = "PNG"
        self.window_level_option = "current"  # "current" or "dataset"
        self.include_overlays = True
        self.export_at_display_resolution = True
        
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
        
        # Window/Level options (only for PNG/JPG)
        self.window_level_group = QGroupBox("Window/Level (for PNG/JPG)")
        window_level_layout = QVBoxLayout()
        
        self.window_level_button_group = QButtonGroup()
        self.current_wl_radio = QRadioButton("Use current viewer window/level")
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
        
        # Display resolution option (only for PNG/JPG)
        self.display_res_checkbox = QCheckBox("Export at displayed resolution (apply current zoom)")
        self.display_res_checkbox.setChecked(True)
        self.display_res_checkbox.stateChanged.connect(lambda: setattr(self, 'export_at_display_resolution', self.display_res_checkbox.isChecked()))
        layout.addWidget(self.display_res_checkbox)
        
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
        self.window_level_group.setEnabled(is_image_format)
        self.overlay_checkbox.setEnabled(is_image_format)
        self.display_res_checkbox.setEnabled(is_image_format)
        
        if not is_image_format:
            # DICOM format - disable overlay and display resolution options
            self.overlay_checkbox.setChecked(False)
            self.include_overlays = False
            self.display_res_checkbox.setChecked(False)
            self.export_at_display_resolution = False
    
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
        
        # Perform export
        try:
            manager = ExportManager()
            exported_count = manager.export_selected(
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
                self.studies,
                self.export_at_display_resolution,
                self.current_zoom
            )
            
            # Save export path to config for next time
            if self.config_manager and self.output_path:
                self.config_manager.set_last_export_path(self.output_path)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {exported_count} file(s) to:\n{self.output_path}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export files:\n{str(e)}"
            )


class ExportManager:
    """
    Manages export operations.
    """
    
    def __init__(self):
        """Initialize the export manager."""
        pass
    
    @staticmethod
    def process_image_by_photometric_interpretation(image: Image.Image, dataset: Dataset) -> Image.Image:
        """
        Process image based on PhotometricInterpretation tag.
        
        Handles:
        - MONOCHROME1: Invert image (pixel values increase with decreasing brightness)
        - MONOCHROME2: No inversion needed (standard grayscale)
        - RGB: No special handling needed (already RGB)
        - YBR_FULL, YBR_FULL_422, YBR_ICT, YBR_RCT: Convert to RGB
        - PALETTE COLOR: Handle palette lookup (basic support)
        
        Args:
            image: PIL Image to process
            dataset: DICOM dataset containing PhotometricInterpretation tag
            
        Returns:
            Processed PIL Image ready for export
        """
        try:
            # Get PhotometricInterpretation tag (default to MONOCHROME2)
            photometric_interpretation = getattr(dataset, 'PhotometricInterpretation', 'MONOCHROME2')
            
            # Handle string or list/tuple values
            if isinstance(photometric_interpretation, (list, tuple)):
                photometric_interpretation = str(photometric_interpretation[0]).strip()
            else:
                photometric_interpretation = str(photometric_interpretation).strip()
            
            if not photometric_interpretation:
                photometric_interpretation = 'MONOCHROME2'  # Default
            
            pi_upper = photometric_interpretation.upper()
            
            # Handle MONOCHROME1: Invert image
            if pi_upper == 'MONOCHROME1':
                img_array = np.array(image)
                if len(img_array.shape) == 2:
                    # Grayscale
                    img_array = 255 - img_array
                    image = Image.fromarray(img_array, mode='L')
                elif len(img_array.shape) == 3:
                    # Color (shouldn't happen for MONOCHROME1, but handle gracefully)
                    img_array = 255 - img_array
                    image = Image.fromarray(img_array, mode=image.mode)
            
            # Handle MONOCHROME2: No inversion needed (standard grayscale)
            elif pi_upper == 'MONOCHROME2':
                # No processing needed - MONOCHROME2 is the standard format
                pass
            
            # Handle RGB: Check for JPEGLS-RGB channel order issues
            elif pi_upper == 'RGB':
                # Already RGB, but check for JPEGLS-RGB channel order issues
                img_array = np.array(image)
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    # Get transfer syntax for RGB/BGR detection
                    transfer_syntax = None
                    if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                        transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                    # Check and fix RGB/BGR channel order for JPEGLS-RGB
                    rgb_array = DICOMProcessor.detect_and_fix_rgb_channel_order(
                        img_array, 
                        photometric_interpretation=photometric_interpretation,
                        transfer_syntax=transfer_syntax,
                        dataset=dataset
                    )
                    image = Image.fromarray(rgb_array, mode='RGB')
            
            # Handle YBR formats: Convert to RGB
            elif any(ybr_type in pi_upper for ybr_type in ['YBR_FULL', 'YBR_FULL_422', 'YBR_ICT', 'YBR_RCT']):
                # Convert YBR to RGB (pass PhotometricInterpretation for correct coefficient selection)
                img_array = np.array(image)
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    # Get transfer syntax for YBR conversion
                    transfer_syntax = None
                    if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                        transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                    # Convert YBR to RGB
                    rgb_array = DICOMProcessor.convert_ybr_to_rgb(
                        img_array, 
                        photometric_interpretation=photometric_interpretation,
                        transfer_syntax=transfer_syntax
                    )
                    image = Image.fromarray(rgb_array, mode='RGB')
                else:
                    # Unexpected shape for YBR, log warning but continue
                    print(f"[EXPORT] Warning: Unexpected image shape for YBR format: {img_array.shape}")
            
            # Handle PALETTE COLOR: Basic support (may need palette lookup table in future)
            elif 'PALETTE' in pi_upper or 'COLOR' in pi_upper:
                # For now, just ensure it's RGB mode
                # Future enhancement: Apply palette lookup table if available
                if image.mode != 'RGB':
                    image = image.convert('RGB')
            
            # Unknown format: Try to ensure RGB mode for color images
            else:
                # For unknown formats, ensure RGB mode if it's a color image
                if image.mode not in ['L', 'RGB']:
                    image = image.convert('RGB')
            
            return image
            
        except Exception as e:
            print(f"[EXPORT] Error processing image by PhotometricInterpretation: {e}")
            import traceback
            traceback.print_exc()
            # Return original image on error
            return image
    
    def export_selected(
        self,
        selected_items: Dict[Tuple[str, str, int], Dataset],
        output_dir: str,
        format: str,
        window_level_option: str = "dataset",
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        include_overlays: bool = False,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        studies: Optional[Dict[str, Dict[str, List[Dataset]]]] = None,
        export_at_display_resolution: bool = False,
        current_zoom: Optional[float] = None
    ) -> int:
        """
        Export selected items based on hierarchical selection.
        
        Args:
            selected_items: Dictionary of {(study_uid, series_uid, slice_index): dataset}
            output_dir: Output directory
            format: Export format ("PNG", "JPG", or "DICOM")
            window_level_option: "current" or "dataset"
            current_window_center: Current window center from viewer
            current_window_width: Current window width from viewer
            include_overlays: Whether to include overlays/ROIs (PNG/JPG only)
            use_rescaled_values: Whether to apply rescale slope/intercept (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            studies: Optional studies dictionary for calculating total_slices {study_uid: {series_uid: [datasets]}}
            export_at_display_resolution: Whether to export at displayed resolution (apply zoom)
            current_zoom: Optional current zoom level from viewer
            
        Returns:
            Number of files exported
        """
        exported = 0
        
        # Create progress dialog
        progress = QProgressDialog("Exporting images...", "Cancel", 0, len(selected_items))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        # Group by study and series for directory structure
        items_by_study_series: Dict[Tuple[str, str], List[Tuple[int, Dataset]]] = {}
        for (study_uid, series_uid, slice_index), dataset in selected_items.items():
            key = (study_uid, series_uid)
            if key not in items_by_study_series:
                items_by_study_series[key] = []
            items_by_study_series[key].append((slice_index, dataset))
        
        # Sort by slice index within each series
        for key in items_by_study_series:
            items_by_study_series[key].sort(key=lambda x: x[0])
        
        try:
            for (study_uid, series_uid), items in items_by_study_series.items():
                # Get first dataset to extract folder structure info
                first_dataset = items[0][1] if items else None
                if first_dataset is None:
                    continue
                
                # Extract DICOM tags for folder structure: Patient ID / Study Date - Study Description / Series Number - Series Description
                patient_id = getattr(first_dataset, 'PatientID', 'UNKNOWN_PATIENT')
                study_date = getattr(first_dataset, 'StudyDate', 'UNKNOWN_DATE')
                study_description = getattr(first_dataset, 'StudyDescription', 'UNKNOWN_STUDY')
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                series_description = getattr(first_dataset, 'SeriesDescription', 'UNKNOWN_SERIES')
                
                # Handle missing or empty SeriesNumber
                if series_number is None or series_number == '':
                    series_number = 'UNKNOWN_SERIES_NUM'
                else:
                    series_number = str(int(series_number)) if isinstance(series_number, (int, float)) else str(series_number)
                
                # Sanitize folder names (remove invalid characters)
                def sanitize_folder_name(name: str) -> str:
                    # Replace invalid characters with underscore
                    invalid_chars = '<>:"/\\|?*'
                    for char in invalid_chars:
                        name = name.replace(char, '_')
                    # Replace spaces with underscore
                    name = name.replace(' ', '_')
                    # Remove leading/trailing dots and spaces
                    name = name.strip('. ')
                    return name if name else 'UNKNOWN'
                
                # Sanitize all components
                patient_id_sanitized = sanitize_folder_name(str(patient_id))
                study_date_sanitized = sanitize_folder_name(str(study_date))
                study_description_sanitized = sanitize_folder_name(str(study_description))
                series_number_sanitized = sanitize_folder_name(str(series_number))
                series_description_sanitized = sanitize_folder_name(str(series_description))
                
                # Construct the new folder hierarchy: Patient ID / Study Date - Study Description / Series Number - Series Description
                patient_dir = os.path.join(output_dir, patient_id_sanitized)
                
                # Combine Study Date and Study Description
                study_folder_name = f"{study_date_sanitized}-{study_description_sanitized}"
                study_dir = os.path.join(patient_dir, study_folder_name)
                
                # Combine Series Number and Series Description
                series_folder_name = f"{series_number_sanitized}-{series_description_sanitized}"
                series_dir = os.path.join(study_dir, series_folder_name)
                
                os.makedirs(series_dir, exist_ok=True)
                
                for slice_index, dataset in items:
                    if progress.wasCanceled():
                        break
                    
                    # Generate filename
                    instance_num = getattr(dataset, 'InstanceNumber', slice_index + 1)
                    
                    if format == "DICOM":
                        filename = f"Instance_{instance_num:04d}.dcm"
                    elif format == "PNG":
                        filename = f"Instance_{instance_num:04d}.png"
                    else:  # JPG
                        filename = f"Instance_{instance_num:04d}.jpg"
                    
                    output_path = os.path.join(series_dir, filename)
                    
                    # Calculate total slices for this series
                    total_slices = None
                    if studies and study_uid in studies and series_uid in studies[study_uid]:
                        total_slices = len(studies[study_uid][series_uid])
                    
                    if self.export_slice(
                        dataset,
                        output_path,
                        format,
                        window_level_option,
                        current_window_center,
                        current_window_width,
                        include_overlays,
                        use_rescaled_values,
                        roi_manager,
                        overlay_manager,
                        measurement_tool,
                        config_manager,
                        study_uid,
                        series_uid,
                        slice_index,
                        total_slices,
                        export_at_display_resolution,
                        current_zoom
                    ):
                        exported += 1
                    
                    progress.setValue(exported)
            
            progress.close()
        except Exception as e:
            progress.close()
            raise e
        
        return exported
    
    def export_slice(
        self,
        dataset: Dataset,
        output_path: str,
        format: str,
        window_level_option: str = "dataset",
        current_window_center: Optional[float] = None,
        current_window_width: Optional[float] = None,
        include_overlays: bool = False,
        use_rescaled_values: bool = False,
        roi_manager=None,
        overlay_manager=None,
        measurement_tool=None,
        config_manager=None,
        study_uid: Optional[str] = None,
        series_uid: Optional[str] = None,
        slice_index: Optional[int] = None,
        total_slices: Optional[int] = None,
        export_at_display_resolution: bool = False,
        current_zoom: Optional[float] = None
    ) -> bool:
        """
        Export a single slice.
        
        Args:
            dataset: DICOM dataset
            output_path: Output file path
            format: Export format ("PNG", "JPG", or "DICOM")
            window_level_option: "current" or "dataset"
            current_window_center: Current window center from viewer
            current_window_width: Current window width from viewer
            include_overlays: Whether to include overlays/ROIs (PNG/JPG only)
            use_rescaled_values: Whether to apply rescale slope/intercept (matches viewer setting)
            roi_manager: Optional ROI manager for rendering ROIs
            overlay_manager: Optional overlay manager for rendering overlays
            measurement_tool: Optional measurement tool for rendering measurements
            config_manager: Optional config manager for overlay configuration
            study_uid: Optional study UID for ROI lookup
            series_uid: Optional series UID for ROI lookup
            slice_index: Optional slice index for ROI lookup
            total_slices: Optional total number of slices in series (for "Slice X/Y" formatting)
            export_at_display_resolution: Whether to export at displayed resolution (apply zoom)
            current_zoom: Optional current zoom level from viewer
            
        Returns:
            True if successful
        """
        try:
            if format == "DICOM":
                # Export as DICOM - always preserve original data
                dataset.save_as(output_path)
            else:
                # Export as image (PNG or JPG)
                window_center = None
                window_width = None
                
                if window_level_option == "current" and current_window_center is not None and current_window_width is not None:
                    window_center = current_window_center
                    window_width = current_window_width
                
                # Convert to image - use apply_rescale to match viewer behavior
                image = DICOMProcessor.dataset_to_image(
                    dataset,
                    window_center=window_center,
                    window_width=window_width,
                    apply_rescale=use_rescaled_values
                )
                
                if image is None:
                    return False
                
                # Handle PhotometricInterpretation (MONOCHROME1 inversion, YBR conversion, etc.)
                image = ExportManager.process_image_by_photometric_interpretation(image, dataset)
                
                # Apply display resolution scaling BEFORE rendering overlays
                # This ensures font size is calculated based on magnified dimensions
                zoom_factor = 1.0
                if export_at_display_resolution and current_zoom and current_zoom > 1.0:
                    zoom_factor = current_zoom
                    new_width = int(image.width * zoom_factor)
                    new_height = int(image.height * zoom_factor)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Render overlays and ROIs if requested (now on magnified image)
                # Font size will be calculated based on magnified dimensions
                if include_overlays:
                    image = self._render_overlays_and_rois(
                        image,
                        dataset,
                        roi_manager,
                        overlay_manager,
                        measurement_tool,
                        config_manager,
                        study_uid,
                        series_uid,
                        slice_index,
                        total_slices,
                        zoom_factor  # Pass zoom factor to scale ROI/measurement coordinates
                    )
                
                if format == "PNG":
                    image.save(output_path, "PNG")
                elif format == "JPG":
                    image.save(output_path, "JPEG", quality=95)
            
            return True
        except Exception as e:
            print(f"Error exporting slice: {e}")
            return False
    
    def _render_overlays_and_rois(
        self,
        image: Image.Image,
        dataset: Dataset,
        roi_manager,
        overlay_manager,
        measurement_tool,
        config_manager,
        study_uid: Optional[str],
        series_uid: Optional[str],
        slice_index: Optional[int],
        total_slices: Optional[int] = None,
        zoom_factor: float = 1.0
    ) -> Image.Image:
        """
        Render overlays, ROIs, and measurements onto a PIL Image.
        
        Args:
            image: PIL Image to draw on
            dataset: DICOM dataset
            roi_manager: ROI manager instance
            overlay_manager: Overlay manager instance
            measurement_tool: Measurement tool instance
            config_manager: Config manager instance
            study_uid: Study UID for ROI lookup
            series_uid: Series UID for ROI lookup
            slice_index: Slice index for ROI lookup
            total_slices: Optional total number of slices in series (for "Slice X/Y" formatting)
            zoom_factor: Factor to scale ROI/measurement coordinates by (default 1.0)
            
        Returns:
            PIL Image with overlays, ROIs, and measurements rendered
        """
        # Convert to RGB if grayscale (needed for drawing colored ROIs)
        if image.mode == 'L':
            image = image.convert('RGB')
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Draw ROIs (scale coordinates by zoom_factor)
        if roi_manager and study_uid and series_uid and slice_index is not None:
            rois = roi_manager.get_rois_for_slice(study_uid, series_uid, slice_index)
            for roi in rois:
                bounds = roi.get_bounds()
                # Convert QRectF coordinates to integers and scale by zoom
                x1 = int(max(0, min(bounds.left() * zoom_factor, width)))
                y1 = int(max(0, min(bounds.top() * zoom_factor, height)))
                x2 = int(max(0, min(bounds.right() * zoom_factor, width)))
                y2 = int(max(0, min(bounds.bottom() * zoom_factor, height)))
                
                if roi.shape_type == "rectangle":
                    draw.rectangle([x1, y1, x2, y2], outline=(255, 0, 0), width=max(1, int(zoom_factor)))
                elif roi.shape_type == "ellipse":
                    draw.ellipse([x1, y1, x2, y2], outline=(255, 0, 0), width=max(1, int(zoom_factor)))
        
        # Draw measurements (scale coordinates by zoom_factor)
        if measurement_tool and study_uid and series_uid and slice_index is not None:
            measurements = measurement_tool.measurements.get((study_uid, series_uid, slice_index), [])
            for measurement in measurements:
                # Scale measurement coordinates
                start_x = int(measurement.start_point.x() * zoom_factor)
                start_y = int(measurement.start_point.y() * zoom_factor)
                end_x = int((measurement.start_point.x() + measurement.end_relative.x()) * zoom_factor)
                end_y = int((measurement.start_point.y() + measurement.end_relative.y()) * zoom_factor)
                
                # Draw measurement line in green
                draw.line([(start_x, start_y), (end_x, end_y)], fill=(0, 255, 0), width=max(2, int(2 * zoom_factor)))
                
                # Draw text label at midpoint
                mid_x = int((start_x + end_x) / 2)
                mid_y = int((start_y + end_y) / 2)
                
                # Try to get a font for measurement text
                measurement_font = None
                font_paths = [
                    "arial.ttf",
                    "Arial.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "C:/Windows/Fonts/arial.ttf"
                ]
                for font_path in font_paths:
                    try:
                        measurement_font = ImageFont.truetype(font_path, 12)
                        break
                    except:
                        continue
                
                if measurement_font is None:
                    try:
                        measurement_font = ImageFont.load_default()
                    except:
                        pass
                
                # Draw measurement text in green
                if measurement_font:
                    draw.text((mid_x, mid_y), measurement.distance_formatted, fill=(0, 255, 0), font=measurement_font)
        
        # Draw overlay text
        if overlay_manager and config_manager:
            parser = DICOMParser(dataset)
            modality = overlay_manager._get_modality(parser)
            corner_tags = config_manager.get_overlay_tags(modality)
            
            # Get base font size from overlay manager
            base_font_size = overlay_manager.font_size
            font_color = overlay_manager.font_color
            
            # Scale font size based on image dimensions
            # Use reference size of 512 pixels (typical DICOM matrix size)
            reference_size = 512.0
            image_min_dimension = min(width, height)
            scale_factor = image_min_dimension / reference_size
            
            # Apply scale factor to base font size
            font_size = int(base_font_size * scale_factor)
            
            # Clamp font size to reasonable bounds for readability
            font_size = max(9, min(48, font_size))
            
            # Ensure text color is bright enough for visibility
            # If font_color is too dark, use bright yellow (255, 255, 0) or white
            if isinstance(font_color, (list, tuple)) and len(font_color) >= 3:
                r, g, b = font_color[0], font_color[1], font_color[2]
                # Calculate brightness
                brightness = (r + g + b) / 3.0
                # Use bright yellow if original color is too dark, otherwise use original
                if brightness < 200:
                    text_color = (255, 255, 0)  # Bright yellow for better visibility
                else:
                    text_color = (r, g, b)
            else:
                text_color = (255, 255, 0)  # Default to bright yellow
            
            # Try to load a font, fallback to default
            font = None
            # Try common font paths
            font_paths = [
                "arial.ttf",
                "Arial.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:/Windows/Fonts/arial.ttf"
            ]
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except:
                    continue
            
            # If no font loaded, try default
            if font is None:
                try:
                    font = ImageFont.load_default()
                except:
                    pass
            
            margin = 10
            
            # Draw text for each corner
            corners = [
                ("upper_left", margin, margin, "left", False),
                ("upper_right", width - margin, margin, "right", False),
                ("lower_left", margin, height - margin, "left", True),
                ("lower_right", width - margin, height - margin, "right", True)
            ]
            
            for corner_name, x, y, align, is_bottom in corners:
                tags = corner_tags.get(corner_name, [])
                if not tags:
                    continue
                
                # Use overlay_manager's _get_corner_text() method for consistent formatting
                # This handles "Slice X/Y" formatting and other edge cases
                text = overlay_manager._get_corner_text(parser, tags, total_slices)
                
                if not text:
                    continue
                
                if not font:
                    continue
                
                # Calculate text bounding box to get dimensions
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # Adjust y-position for bottom corners to prevent clipping
                if is_bottom:
                    y = y - text_height
                
                # Draw text - handle right alignment by drawing each line separately
                if align == "right":
                    lines = text.split('\n')
                    current_y = y
                    for line in lines:
                        if line.strip():  # Only draw non-empty lines
                            line_bbox = draw.textbbox((0, 0), line, font=font)
                            line_width = line_bbox[2] - line_bbox[0]
                            line_height = line_bbox[3] - line_bbox[1]
                            # Position each line so it ends at x (the right edge position)
                            line_x = x - line_width
                            draw.text((line_x, current_y), line, fill=text_color, font=font)
                            current_y += line_height
                        else:
                            # For empty lines, just advance by a line height
                            empty_bbox = draw.textbbox((0, 0), "A", font=font)
                            empty_height = empty_bbox[3] - empty_bbox[1]
                            current_y += empty_height
                else:
                    # Left alignment - draw normally
                    draw.text((x, y), text, fill=text_color, font=font)
        
        return image
