"""
Export Dialog

This module provides export functionality for DICOM images to JPEG, PNG,
and DICOM formats, with options to export single slice, series, or study.

Inputs:
    - User export preferences
    - Image data
    - Export format and scope
    
Outputs:
    - Exported image files
    
Requirements:
    - PySide6 for dialogs
    - PIL/Pillow for image export
    - pydicom for DICOM export
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QComboBox, QPushButton, QFileDialog, QMessageBox,
                                QGroupBox, QRadioButton, QButtonGroup)
from PySide6.QtCore import Qt
from typing import Optional, List
from PIL import Image
import pydicom
from pydicom.dataset import Dataset
import os

from core.dicom_processor import DICOMProcessor


class ExportDialog(QDialog):
    """
    Dialog for exporting DICOM images.
    
    Features:
    - Select export format (JPEG, PNG, DICOM)
    - Select export scope (slice, series, study)
    - Choose output location
    """
    
    def __init__(self, parent=None):
        """
        Initialize the export dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Export Images")
        self.setModal(True)
        
        self.export_format = "PNG"
        self.export_scope = "slice"
        self.output_path = ""
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG", "DICOM"])
        self.format_combo.setCurrentText("PNG")
        format_layout.addWidget(self.format_combo)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # Scope selection
        scope_group = QGroupBox("Export Scope")
        scope_layout = QVBoxLayout()
        
        self.scope_group = QButtonGroup()
        self.slice_radio = QRadioButton("Current Slice")
        self.series_radio = QRadioButton("Current Series")
        self.study_radio = QRadioButton("Current Study")
        
        self.slice_radio.setChecked(True)
        
        self.scope_group.addButton(self.slice_radio, 0)
        self.scope_group.addButton(self.series_radio, 1)
        self.scope_group.addButton(self.study_radio, 2)
        
        scope_layout.addWidget(self.slice_radio)
        scope_layout.addWidget(self.series_radio)
        scope_layout.addWidget(self.study_radio)
        
        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)
        
        # Output path
        path_layout = QHBoxLayout()
        path_label = QLabel("Output:")
        path_layout.addWidget(path_label)
        
        self.path_edit = QLabel("(Not selected)")
        path_layout.addWidget(self.path_edit, 1)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output)
        path_layout.addWidget(browse_button)
        
        layout.addLayout(path_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        export_button = QPushButton("Export")
        export_button.clicked.connect(self.accept)
        button_layout.addWidget(export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def _browse_output(self) -> None:
        """Browse for output directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Output Directory")
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                self.output_path = selected[0]
                self.path_edit.setText(self.output_path)
    
    def get_export_settings(self) -> dict:
        """
        Get export settings from dialog.
        
        Returns:
            Dictionary with export settings
        """
        return {
            "format": self.format_combo.currentText(),
            "scope": "slice" if self.slice_radio.isChecked() else 
                    "series" if self.series_radio.isChecked() else "study",
            "output_path": self.output_path
        }


class ExportManager:
    """
    Manages export operations.
    """
    
    def __init__(self):
        """Initialize the export manager."""
        pass
    
    def export_slice(self, dataset: Dataset, output_path: str, format: str) -> bool:
        """
        Export a single slice.
        
        Args:
            dataset: DICOM dataset
            output_path: Output file path
            format: Export format ("PNG", "JPEG", or "DICOM")
            
        Returns:
            True if successful
        """
        try:
            if format == "DICOM":
                # Export as DICOM
                dataset.save_as(output_path)
            else:
                # Export as image
                image = DICOMProcessor.dataset_to_image(dataset)
                if image is None:
                    return False
                
                if format == "PNG":
                    image.save(output_path, "PNG")
                elif format == "JPEG":
                    image.save(output_path, "JPEG", quality=95)
            
            return True
        except Exception as e:
            print(f"Error exporting slice: {e}")
            return False
    
    def export_series(self, datasets: List[Dataset], output_dir: str, format: str) -> int:
        """
        Export a series of slices.
        
        Args:
            datasets: List of DICOM datasets
            output_dir: Output directory
            format: Export format
            
        Returns:
            Number of files exported
        """
        exported = 0
        
        for idx, dataset in enumerate(datasets):
            # Generate filename
            instance_num = getattr(dataset, 'InstanceNumber', idx + 1)
            
            if format == "DICOM":
                filename = f"slice_{instance_num:04d}.dcm"
            elif format == "PNG":
                filename = f"slice_{instance_num:04d}.png"
            else:  # JPEG
                filename = f"slice_{instance_num:04d}.jpg"
            
            output_path = os.path.join(output_dir, filename)
            
            if self.export_slice(dataset, output_path, format):
                exported += 1
        
        return exported
    
    def export_study(self, studies: dict, output_dir: str, format: str) -> int:
        """
        Export a study (all series).
        
        Args:
            studies: Dictionary of studies {StudyUID: {SeriesUID: [datasets]}}
            output_dir: Output directory
            format: Export format
            
        Returns:
            Number of files exported
        """
        exported = 0
        
        for study_uid, series_dict in studies.items():
            study_dir = os.path.join(output_dir, f"study_{study_uid[:8]}")
            os.makedirs(study_dir, exist_ok=True)
            
            for series_uid, datasets in series_dict.items():
                series_dir = os.path.join(study_dir, f"series_{series_uid[:8]}")
                os.makedirs(series_dir, exist_ok=True)
                
                exported += self.export_series(datasets, series_dir, format)
        
        return exported

