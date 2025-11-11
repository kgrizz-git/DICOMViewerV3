"""
Overlay Configuration Dialog

This module provides a dialog for configuring overlay tags per corner
and per modality.

Inputs:
    - User tag selections for each corner
    - Modality selection
    
Outputs:
    - Updated overlay tag configuration
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
    - DICOMParser for available tag list
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QListWidget, QListWidgetItem,
                                QComboBox, QGroupBox, QFormLayout, QDialogButtonBox,
                                QLineEdit, QMessageBox, QTabWidget, QWidget)
from PySide6.QtCore import Qt, Signal
from typing import Dict, List, Optional

from utils.config_manager import ConfigManager
from core.dicom_parser import DICOMParser


# Common DICOM tag keywords
# Includes tags for all modalities: MR, CT, US, XA, CR, DX, RF, and common tags
COMMON_TAGS = [
    # Patient information
    "PatientName", "PatientID", "PatientBirthDate", "PatientSex", "PatientAge",
    # Study information
    "StudyDate", "StudyTime", "StudyDescription", "StudyInstanceUID",
    # Series information
    "SeriesNumber", "SeriesDescription", "SeriesInstanceUID", "SeriesDate",
    # Equipment information
    "Modality", "Manufacturer", "ManufacturerModelName", "StationName", "DeviceSerialNumber", "ScanOptions", "PerformedStationName",
    # Image information
    "InstanceNumber", "SliceLocation", "SliceThickness", "SpacingBetweenSlices",
    # Window/Level
    "WindowCenter", "WindowWidth", "RescaleIntercept", "RescaleSlope", "RescaleType",
    # Image geometry
    "ImagePositionPatient", "ImageOrientationPatient",
    # Image matrix
    "Rows", "Columns", "PixelSpacing", "ImagerPixelSpacing", "BitsAllocated", "BitsStored",
    # MR-specific tags
    "RepetitionTime", "EchoTime", "EchoTrainLength", "FlipAngle", "MagneticFieldStrength",
    # CT-specific tags
    "RevolutionTime", "KVP", "ExposureTime", "Exposure", "XRayTubeCurrent", "ExposureInmAs",
    "TableHeight", "GantryDetectorTilt",
    # US-specific tags
    "TransducerFrequency", "MechanicalIndex", "ThermalIndex",
    # XA/CR/DX/RF-specific tags (some overlap with CT)
    "BodyPartThickness"
]


class OverlayConfigDialog(QDialog):
    """
    Dialog for configuring overlay tags per corner and modality.
    
    Features:
    - Modality selection (tabs or dropdown)
    - 4 corners with tag selection
    - Add/remove tags from each corner
    - Save/load presets
    """
    
    # Signal emitted when configuration is applied
    config_applied = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None):
        """
        Initialize the overlay configuration dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.setWindowTitle("Overlay Configuration")
        self.setModal(True)
        self.resize(700, 600)
        
        # Store current modality
        self.current_modality = "default"
        
        # Store tag configurations per modality
        self.modality_configs: Dict[str, Dict[str, List[str]]] = {}
        
        self._create_ui()
        self._load_configurations()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Modality selection
        modality_layout = QHBoxLayout()
        modality_label = QLabel("Modality:")
        self.modality_combo = QComboBox()
        # Sort modalities alphabetically, but keep "default" first
        modalities = ["default"] + sorted(["CT", "MR", "US", "CR", "DX", "NM", "PT", "RT", "MG"])
        self.modality_combo.addItems(modalities)
        self.modality_combo.currentTextChanged.connect(self._on_modality_changed)
        modality_layout.addWidget(modality_label)
        modality_layout.addWidget(self.modality_combo)
        modality_layout.addStretch()
        layout.addLayout(modality_layout)
        
        # Create tab widget for 4 corners
        corners_tab = QTabWidget()
        
        # Upper Left
        self.upper_left_widget = self._create_corner_widget("Upper Left")
        corners_tab.addTab(self.upper_left_widget, "Upper Left")
        
        # Upper Right
        self.upper_right_widget = self._create_corner_widget("Upper Right")
        corners_tab.addTab(self.upper_right_widget, "Upper Right")
        
        # Lower Left
        self.lower_left_widget = self._create_corner_widget("Lower Left")
        corners_tab.addTab(self.lower_left_widget, "Lower Left")
        
        # Lower Right
        self.lower_right_widget = self._create_corner_widget("Lower Right")
        corners_tab.addTab(self.lower_right_widget, "Lower Right")
        
        layout.addWidget(corners_tab)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._apply_configuration)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_corner_widget(self, corner_name: str) -> QWidget:
        """
        Create widget for configuring one corner.
        
        Args:
            corner_name: Name of the corner
            
        Returns:
            Widget with tag selection UI
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Available tags
        available_group = QGroupBox("Available Tags")
        available_layout = QVBoxLayout()
        
        # Search/filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter tags...")
        self.search_edit.textChanged.connect(lambda: self._filter_tags(corner_name))
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        available_layout.addLayout(search_layout)
        
        # Store reference to search edit by corner
        if not hasattr(self, 'search_edits'):
            self.search_edits = {}
        self.search_edits[corner_name] = self.search_edit
        
        # Available tags list
        available_list = QListWidget()
        available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for tag in COMMON_TAGS:
            available_list.addItem(tag)
        available_list.itemDoubleClicked.connect(
            lambda item: self._add_tag_to_corner(corner_name, item.text())
        )
        
        # Store reference to available list by corner
        if not hasattr(self, 'available_lists'):
            self.available_lists = {}
        self.available_lists[corner_name] = available_list
        
        available_layout.addWidget(available_list)
        available_group.setLayout(available_layout)
        layout.addWidget(available_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add →")
        add_button.clicked.connect(
            lambda: self._add_selected_tags(corner_name)
        )
        button_layout.addWidget(add_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Selected tags
        selected_group = QGroupBox(f"{corner_name} Tags")
        selected_layout = QVBoxLayout()
        
        selected_list = QListWidget()
        selected_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        
        # Store reference to selected list by corner
        if not hasattr(self, 'selected_lists'):
            self.selected_lists = {}
        self.selected_lists[corner_name] = selected_list
        
        selected_layout.addWidget(selected_list)
        
        # Remove button
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(
            lambda: self._remove_selected_tags(corner_name)
        )
        selected_layout.addWidget(remove_button)
        
        selected_group.setLayout(selected_layout)
        layout.addWidget(selected_group)
        
        return widget
    
    def _filter_tags(self, corner_name: str) -> None:
        """Filter available tags based on search text."""
        if corner_name not in self.available_lists:
            return
        
        search_text = self.search_edits[corner_name].text().lower()
        available_list = self.available_lists[corner_name]
        
        for i in range(available_list.count()):
            item = available_list.item(i)
            if search_text in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def _add_selected_tags(self, corner_name: str) -> None:
        """Add selected tags from available list to corner."""
        if corner_name not in self.available_lists or corner_name not in self.selected_lists:
            return
        
        available_list = self.available_lists[corner_name]
        selected_list = self.selected_lists[corner_name]
        
        for item in available_list.selectedItems():
            tag = item.text()
            # Check if already in selected list
            existing = [selected_list.item(i).text() for i in range(selected_list.count())]
            if tag not in existing:
                selected_list.addItem(tag)
    
    def _add_tag_to_corner(self, corner_name: str, tag: str) -> None:
        """Add a tag to corner (double-click handler)."""
        if corner_name not in self.selected_lists:
            return
        
        selected_list = self.selected_lists[corner_name]
        existing = [selected_list.item(i).text() for i in range(selected_list.count())]
        if tag not in existing:
            selected_list.addItem(tag)
    
    def _remove_selected_tags(self, corner_name: str) -> None:
        """Remove selected tags from corner."""
        if corner_name not in self.selected_lists:
            return
        
        selected_list = self.selected_lists[corner_name]
        for item in selected_list.selectedItems():
            selected_list.takeItem(selected_list.row(item))
    
    def _on_modality_changed(self, modality: str) -> None:
        """Handle modality change."""
        # Save current configuration
        self._save_current_modality_config()
        
        # Load new modality configuration
        self.current_modality = modality
        self._load_modality_config(modality)
    
    def _save_current_modality_config(self) -> None:
        """Save current modality configuration to memory."""
        config = {
            "upper_left": [self.selected_lists["Upper Left"].item(i).text() 
                          for i in range(self.selected_lists["Upper Left"].count())],
            "upper_right": [self.selected_lists["Upper Right"].item(i).text() 
                           for i in range(self.selected_lists["Upper Right"].count())],
            "lower_left": [self.selected_lists["Lower Left"].item(i).text() 
                          for i in range(self.selected_lists["Lower Left"].count())],
            "lower_right": [self.selected_lists["Lower Right"].item(i).text() 
                           for i in range(self.selected_lists["Lower Right"].count())]
        }
        self.modality_configs[self.current_modality] = config
    
    def _load_modality_config(self, modality: str) -> None:
        """Load modality configuration from memory (if available) or config manager."""
        # Check memory first for in-memory changes
        if modality in self.modality_configs:
            # Use in-memory configuration
            corner_tags = self.modality_configs[modality]
        else:
            # Fall back to config manager
            corner_tags = self.config_manager.get_overlay_tags(modality)
        
        # Update UI
        for corner_name, corner_key in [
            ("Upper Left", "upper_left"),
            ("Upper Right", "upper_right"),
            ("Lower Left", "lower_left"),
            ("Lower Right", "lower_right")
        ]:
            if corner_name in self.selected_lists:
                selected_list = self.selected_lists[corner_name]
                selected_list.clear()
                for tag in corner_tags.get(corner_key, []):
                    selected_list.addItem(tag)
    
    def _load_configurations(self) -> None:
        """Load all configurations from config manager into memory."""
        # Initialize modality_configs with all modalities from config_manager
        # This ensures we have a baseline for all modalities, and any changes
        # made by the user will be stored in memory and only applied on OK
        modalities = ["default", "CT", "MR", "US", "CR", "DX", "NM", "PT", "RT"]
        for modality in modalities:
            self.modality_configs[modality] = self.config_manager.get_overlay_tags(modality)
        
        # Load current modality configuration into UI
        self._load_modality_config(self.current_modality)
    
    def _apply_configuration(self) -> None:
        """Apply and save configuration."""
        # Save current modality
        self._save_current_modality_config()
        
        # Save all modalities to config manager
        for modality, config in self.modality_configs.items():
            self.config_manager.set_overlay_tags(modality, config)
        
        # Emit signal
        self.config_applied.emit()
        
        self.accept()

