"""
About This File Dialog

This module provides a dialog that displays detailed information about the current DICOM file.

Inputs:
    - DICOM dataset
    - File path
    
Outputs:
    - Displayed file information with explanations
    
Requirements:
    - PySide6 for dialog components
    - pydicom for DICOM data access
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QScrollArea, QWidget, QGroupBox)
from PySide6.QtCore import Qt
from typing import Optional
from pathlib import Path
from pydicom.dataset import Dataset


class AboutThisFileDialog(QDialog):
    """
    Dialog that displays detailed information about the current DICOM file.
    
    Features:
    - Non-modal (can stay open)
    - Updates automatically when slice or subwindow changes
    - Shows file, study, series, and image information
    - Includes explanations for technical terms
    """
    
    def __init__(self, parent=None):
        """
        Initialize the About This File dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("About this File")
        self.setModal(False)  # Non-modal so it can stay open
        self.resize(600, 700)
        
        self.dataset: Optional[Dataset] = None
        self.file_path: Optional[str] = None
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Create content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Store labels for updating
        self.labels = {}
        
        # File Information Group
        file_group = QGroupBox("File Information")
        file_layout = QVBoxLayout()
        file_layout.setSpacing(8)
        
        self._add_info_field(file_layout, "Folder Path", "folder_path",
                            "The directory containing this DICOM file")
        self._add_info_field(file_layout, "Filename", "filename",
                            "The name of the DICOM file")
        
        file_group.setLayout(file_layout)
        content_layout.addWidget(file_group)
        
        # Study Information Group
        study_group = QGroupBox("Study Information")
        study_layout = QVBoxLayout()
        study_layout.setSpacing(8)
        
        self._add_info_field(study_layout, "Study Description", "study_description",
                            "A description of the imaging study")
        self._add_info_field(study_layout, "Study Instance UID", "study_instance_uid",
                            "Unique identifier for this study")
        
        study_group.setLayout(study_layout)
        content_layout.addWidget(study_group)
        
        # Series Information Group
        series_group = QGroupBox("Series Information")
        series_layout = QVBoxLayout()
        series_layout.setSpacing(8)
        
        self._add_info_field(series_layout, "Series Description", "series_description",
                            "A description of this image series")
        self._add_info_field(series_layout, "Series Number", "series_number",
                            "The number assigned to this series")
        self._add_info_field(series_layout, "Series Instance UID", "series_instance_uid",
                            "Unique identifier for this series")
        
        series_group.setLayout(series_layout)
        content_layout.addWidget(series_group)
        
        # Image Information Group
        image_group = QGroupBox("Image Information")
        image_layout = QVBoxLayout()
        image_layout.setSpacing(8)
        
        self._add_info_field(image_layout, "Modality", "modality",
                            "The type of imaging modality (e.g., CT, MR, US)")
        self._add_info_field(image_layout, "Transfer Syntax", "transfer_syntax",
                            "The encoding format used for the DICOM data")
        self._add_info_field(image_layout, "Photometric Interpretation", "photometric_interpretation",
                            "How pixel values represent color/grayscale (e.g., MONOCHROME2, RGB)")
        self._add_info_field(image_layout, "Samples per Pixel", "samples_per_pixel",
                            "Number of color components per pixel (1 = grayscale, 3 = color)")
        self._add_info_field(image_layout, "Number of Rows", "rows",
                            "Height of the image in pixels")
        self._add_info_field(image_layout, "Number of Columns", "columns",
                            "Width of the image in pixels")
        self._add_info_field(image_layout, "Number of Frames", "number_of_frames",
                            "Number of frames in a multi-frame image (1 if single frame)")
        
        image_group.setLayout(image_layout)
        content_layout.addWidget(image_group)
        
        # Add stretch at end
        content_layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
    
    def _add_info_field(self, layout: QVBoxLayout, label_text: str, key: str, explanation: str) -> None:
        """
        Add an information field with label, value, and explanation.
        
        Args:
            layout: Layout to add to
            label_text: Label text
            key: Key for storing the value label
            explanation: Explanation text
        """
        # Label
        label = QLabel(f"<b>{label_text}:</b>")
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Value
        value_label = QLabel("—")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(value_label)
        self.labels[key] = value_label
        
        # Explanation
        explanation_label = QLabel(f"<i>{explanation}</i>")
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(explanation_label)
    
    def update_file_info(self, dataset: Optional[Dataset], file_path: Optional[str] = None) -> None:
        """
        Update the displayed file information.
        
        Args:
            dataset: DICOM dataset (can be None)
            file_path: Path to the DICOM file (can be None)
        """
        self.dataset = dataset
        self.file_path = file_path
        
        # Update file information
        if file_path:
            path_obj = Path(file_path)
            self.labels["folder_path"].setText(str(path_obj.parent))
            self.labels["filename"].setText(path_obj.name)
        else:
            self.labels["folder_path"].setText("—")
            self.labels["filename"].setText("—")
        
        # Update DICOM information
        if dataset is None:
            # Clear all fields
            for key in ["study_description", "study_instance_uid", "series_description",
                       "series_number", "series_instance_uid", "modality", "transfer_syntax",
                       "photometric_interpretation", "samples_per_pixel", "rows", "columns",
                       "number_of_frames"]:
                self.labels[key].setText("—")
            return
        
        # Extract DICOM tags
        # Study information
        study_desc = getattr(dataset, 'StudyDescription', None)
        self.labels["study_description"].setText(str(study_desc) if study_desc else "—")
        
        study_uid = getattr(dataset, 'StudyInstanceUID', None)
        self.labels["study_instance_uid"].setText(str(study_uid) if study_uid else "—")
        
        # Series information
        series_desc = getattr(dataset, 'SeriesDescription', None)
        self.labels["series_description"].setText(str(series_desc) if series_desc else "—")
        
        series_number = getattr(dataset, 'SeriesNumber', None)
        self.labels["series_number"].setText(str(series_number) if series_number is not None else "—")
        
        series_uid = getattr(dataset, 'SeriesInstanceUID', None)
        self.labels["series_instance_uid"].setText(str(series_uid) if series_uid else "—")
        
        # Image information
        modality = getattr(dataset, 'Modality', None)
        self.labels["modality"].setText(str(modality) if modality else "—")
        
        # Transfer Syntax
        transfer_syntax = None
        if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
            transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
            # Add human-readable name if known
            transfer_syntax_names = {
                '1.2.840.10008.1.2': 'Implicit VR Little Endian',
                '1.2.840.10008.1.2.1': 'Explicit VR Little Endian',
                '1.2.840.10008.1.2.2': 'Explicit VR Big Endian',
                '1.2.840.10008.1.2.4.50': 'JPEG Baseline (Process 1)',
                '1.2.840.10008.1.2.4.51': 'JPEG Extended (Process 2 & 4)',
                '1.2.840.10008.1.2.4.57': 'JPEG Lossless, Non-Hierarchical (Process 14)',
                '1.2.840.10008.1.2.4.70': 'JPEG Lossless, Non-Hierarchical (Process 14 [Selection Value 1])',
                '1.2.840.10008.1.2.4.80': 'JPEG-LS Lossless',
                '1.2.840.10008.1.2.4.81': 'JPEG-LS Lossy (Near-Lossless)',
                '1.2.840.10008.1.2.4.90': 'JPEG 2000 Image Compression (Lossless Only)',
                '1.2.840.10008.1.2.4.91': 'JPEG 2000 Image Compression',
            }
            if transfer_syntax in transfer_syntax_names:
                transfer_syntax = f"{transfer_syntax_names[transfer_syntax]} ({transfer_syntax})"
        self.labels["transfer_syntax"].setText(transfer_syntax if transfer_syntax else "—")
        
        # Photometric Interpretation
        photometric = getattr(dataset, 'PhotometricInterpretation', None)
        self.labels["photometric_interpretation"].setText(str(photometric) if photometric else "—")
        
        # Samples per Pixel
        samples = getattr(dataset, 'SamplesPerPixel', None)
        self.labels["samples_per_pixel"].setText(str(samples) if samples is not None else "—")
        
        # Rows and Columns
        rows = getattr(dataset, 'Rows', None)
        self.labels["rows"].setText(str(rows) if rows is not None else "—")
        
        columns = getattr(dataset, 'Columns', None)
        self.labels["columns"].setText(str(columns) if columns is not None else "—")
        
        # Number of Frames
        num_frames = getattr(dataset, 'NumberOfFrames', None)
        if num_frames is None:
            # If NumberOfFrames is not present, assume single frame
            num_frames = 1
        self.labels["number_of_frames"].setText(str(num_frames))

