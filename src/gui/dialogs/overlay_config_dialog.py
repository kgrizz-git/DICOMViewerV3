"""
Overlay Tags Configuration Dialog

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

import copy

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
    "StudyDate", "StudyTime", "StudyDescription", "StudyInstanceUID", "AccessionNumber",
    # Series information
    "SeriesNumber", "SeriesDescription", "SeriesInstanceUID", "SeriesDate",
    # Acquisition timing
    "AcquisitionDate", "AcquisitionTime", "AcquisitionNumber", "ContentDate", "ContentTime",
    "AcquisitionDuration", "TriggerTime", "NominalCardiacTriggerTime",
    # Equipment information
    "Modality", "Manufacturer", "ManufacturerModelName", "StationName", "DeviceSerialNumber",
    "ScanOptions", "PerformedStationName", "SoftwareVersions", "ProtocolName",
    # Institution information
    "InstitutionName", "InstitutionAddress", "InstitutionalDepartmentName",
    # Patient/image context
    "BodyPartExamined", "PatientPosition", "Laterality", "ImageLaterality", "ViewPosition",
    # Image information
    "InstanceNumber", "SliceLocation", "SliceThickness", "SpacingBetweenSlices",
    "NumberOfFrames",
    # Window/Level and rescale
    "WindowCenter", "WindowWidth", "RescaleIntercept", "RescaleSlope", "RescaleType",
    # Image geometry
    "ImagePositionPatient", "ImageOrientationPatient",
    # Image matrix
    "Rows", "Columns", "PixelSpacing", "ImagerPixelSpacing", "BitsAllocated", "BitsStored",
    # Field of view and reconstruction geometry (CT, XA, MR, CR/DX)
    "FieldOfViewShape", "FieldOfViewDimensions", "FieldOfViewOrigin", "FieldOfViewRotation",
    "ReconstructionDiameter", "DataCollectionDiameter",
    "ReconstructionFieldOfView", "PercentPhaseFieldOfView", "SpatialResolution",
    # MR-specific tags
    "ScanningSequence", "SequenceVariant", "SequenceName", "MRAcquisitionType",
    "RepetitionTime", "EchoTime", "InversionTime", "EchoTrainLength", "FlipAngle",
    "MagneticFieldStrength", "NumberOfAverages", "PixelBandwidth",
    "NumberOfPhaseEncodingSteps", "InPlanePhaseEncodingDirection",
    "ReceiveCoilName", "TransmitCoilName",
    "DiffusionBValue",
    # CT-specific tags
    "ConvolutionKernel", "CTDIvol",
    "RevolutionTime", "KVP", "ExposureTime", "Exposure", "XRayTubeCurrent", "ExposureInmAs",
    "ExposureIndex", "DeviationIndex", "HelicalPitch", "SpiralPitchFactor",
    "SingleCollimationWidth", "TotalCollimationWidth", "TableSpeed",
    "TableHeight", "GantryDetectorTilt",
    "DistanceSourceToDetector", "DistanceSourceToPatient",
    "FocalSpots", "FilterType",
    # CT/XA tube and filter details
    "AnodeTargetMaterial", "FilterMaterial",
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
    - Live overlay preview: every tag addition, removal, reorder, or modality
      switch is immediately written to ConfigManager and reflected on the
      overlay while the dialog remains open.

    Signals:
        config_applied: Emitted when the user confirms with OK (all modalities
            written to config).
        config_changed: Emitted after every interactive change (live preview).

    Cancel behaviour: on reject() all modalities are restored to the snapshot
    captured at dialog construction and config_changed is emitted once so the
    overlay reverts.
    """

    # Emitted on OK (final confirmation — all modalities saved)
    config_applied = Signal()
    # Emitted on every live change for immediate overlay preview
    config_changed = Signal()

    def __init__(self, config_manager: ConfigManager, parent: Optional[QWidget] = None, initial_modality: Optional[str] = None):
        """
        Initialize the overlay configuration dialog.

        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
            initial_modality: Optional initial modality to select (e.g., "CT", "MR").
                             If None or invalid, defaults to "default"
        """
        super().__init__(parent)

        self.config_manager = config_manager
        self.setWindowTitle("Overlay Tags Configuration")
        self.setModal(True)
        self.resize(700, 600)

        # Valid modalities list (alphabetical order, default first)
        valid_modalities = ["default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"]

        # Store current modality - use initial_modality if provided and valid, otherwise "default"
        if initial_modality and initial_modality.strip() in valid_modalities:
            self.current_modality = initial_modality.strip()
        else:
            self.current_modality = "default"

        # Store tag configurations per modality (working copy, updated on every change)
        self.modality_configs: Dict[str, Dict[str, List[str]]] = {}

        # Per-corner UI references (populated in _create_corner_widget)
        self.search_edits: Dict[str, QLineEdit] = {}
        self.available_lists: Dict[str, QListWidget] = {}
        self.selected_lists: Dict[str, QListWidget] = {}
        self.move_up_buttons: Dict[str, QPushButton] = {}
        self.move_down_buttons: Dict[str, QPushButton] = {}

        self._create_ui()
        self._load_configurations()

        # Deep-copy snapshot used to revert on Cancel
        self._original_configs: Dict[str, Dict[str, List[str]]] = copy.deepcopy(self.modality_configs)

        # Set the combo box to the initial modality after loading configurations
        if self.modality_combo.findText(self.current_modality) >= 0:
            self.modality_combo.setCurrentText(self.current_modality)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)

        # Modality selection
        modality_layout = QHBoxLayout()
        modality_label = QLabel("Modality:")
        self.modality_combo = QComboBox()
        # Sort modalities alphabetically, but keep "default" first
        modalities = ["default"] + sorted(["CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"])
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
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Filter tags...")
        search_edit.textChanged.connect(lambda: self._filter_tags(corner_name))
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit)
        available_layout.addLayout(search_layout)

        self.search_edits[corner_name] = search_edit

        # Available tags list
        available_list = QListWidget()
        available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for tag in COMMON_TAGS:
            available_list.addItem(tag)
        available_list.itemDoubleClicked.connect(
            lambda item: self._add_tag_to_corner(corner_name, item.text())
        )

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

        self.selected_lists[corner_name] = selected_list

        selected_layout.addWidget(selected_list)

        # Button layout for Remove, Move Up, Move Down
        button_layout = QHBoxLayout()

        # Remove button
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(
            lambda: self._remove_selected_tags(corner_name)
        )
        button_layout.addWidget(remove_button)

        # Move Up button
        move_up_button = QPushButton("Move Up")
        move_up_button.clicked.connect(
            lambda: self._move_tag_up(corner_name)
        )
        button_layout.addWidget(move_up_button)

        # Move Down button
        move_down_button = QPushButton("Move Down")
        move_down_button.clicked.connect(
            lambda: self._move_tag_down(corner_name)
        )
        button_layout.addWidget(move_down_button)

        self.move_up_buttons[corner_name] = move_up_button
        self.move_down_buttons[corner_name] = move_down_button

        selected_layout.addLayout(button_layout)

        # Connect selection changed signal to update button states
        selected_list.itemSelectionChanged.connect(
            lambda: self._update_move_buttons_state(corner_name)
        )

        # Initialize button states
        self._update_move_buttons_state(corner_name)

        selected_group.setLayout(selected_layout)
        layout.addWidget(selected_group)

        return widget

    # ------------------------------------------------------------------
    # Tag list helpers
    # ------------------------------------------------------------------

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

        added = False
        for item in available_list.selectedItems():
            tag = item.text()
            existing = [selected_list.item(i).text() for i in range(selected_list.count())]
            if tag not in existing:
                selected_list.addItem(tag)
                added = True

        if added:
            self._on_live_update()

    def _add_tag_to_corner(self, corner_name: str, tag: str) -> None:
        """Add a tag to corner (double-click handler)."""
        if corner_name not in self.selected_lists:
            return

        selected_list = self.selected_lists[corner_name]
        existing = [selected_list.item(i).text() for i in range(selected_list.count())]
        if tag not in existing:
            selected_list.addItem(tag)
            self._on_live_update()

    def _remove_selected_tags(self, corner_name: str) -> None:
        """Remove selected tags from corner."""
        if corner_name not in self.selected_lists:
            return

        selected_list = self.selected_lists[corner_name]
        items_to_remove = selected_list.selectedItems()
        if not items_to_remove:
            return

        for item in items_to_remove:
            selected_list.takeItem(selected_list.row(item))

        self._on_live_update()

    def _move_tag_up(self, corner_name: str) -> None:
        """Move selected tags up by one position in the corner's list."""
        if corner_name not in self.selected_lists:
            return

        selected_list = self.selected_lists[corner_name]
        selected_items = selected_list.selectedItems()

        if not selected_items:
            return

        # Get row indices of selected items, sorted from top to bottom
        selected_rows = sorted([selected_list.row(item) for item in selected_items])

        # Check if any selected item is at the top (row 0)
        if selected_rows[0] == 0:
            return  # Can't move up if first item is selected

        # Store selected items to restore selection after move
        selected_texts = [item.text() for item in selected_items]

        # Process from bottom to top to avoid index shifting issues
        for row in reversed(selected_rows):
            if row > 0:
                item = selected_list.takeItem(row)
                selected_list.insertItem(row - 1, item)

        # Restore selection
        for i in range(selected_list.count()):
            item = selected_list.item(i)
            if item.text() in selected_texts:
                item.setSelected(True)

        self._update_move_buttons_state(corner_name)
        self._on_live_update()

    def _move_tag_down(self, corner_name: str) -> None:
        """Move selected tags down by one position in the corner's list."""
        if corner_name not in self.selected_lists:
            return

        selected_list = self.selected_lists[corner_name]
        selected_items = selected_list.selectedItems()

        if not selected_items:
            return

        # Get row indices of selected items, sorted from top to bottom
        selected_rows = sorted([selected_list.row(item) for item in selected_items])
        last_row = selected_list.count() - 1

        # Check if any selected item is at the bottom
        if selected_rows[-1] == last_row:
            return  # Can't move down if last item is selected

        # Store selected items to restore selection after move
        selected_texts = [item.text() for item in selected_items]

        # Process from bottom to top to avoid index shifting issues
        for row in reversed(selected_rows):
            if row < last_row:
                item = selected_list.takeItem(row)
                selected_list.insertItem(row + 1, item)

        # Restore selection
        for i in range(selected_list.count()):
            item = selected_list.item(i)
            if item.text() in selected_texts:
                item.setSelected(True)

        self._update_move_buttons_state(corner_name)
        self._on_live_update()

    def _update_move_buttons_state(self, corner_name: str) -> None:
        """Update enabled state of Move Up/Down buttons based on selection."""
        if corner_name not in self.selected_lists:
            return

        selected_list = self.selected_lists[corner_name]
        selected_items = selected_list.selectedItems()

        move_up_button = self.move_up_buttons.get(corner_name)
        move_down_button = self.move_down_buttons.get(corner_name)

        if not move_up_button or not move_down_button:
            return

        if not selected_items:
            move_up_button.setEnabled(False)
            move_down_button.setEnabled(False)
            return

        selected_rows = [selected_list.row(item) for item in selected_items]
        first_selected_row = min(selected_rows)
        last_selected_row = max(selected_rows)
        last_row = selected_list.count() - 1

        move_up_button.setEnabled(first_selected_row > 0)
        move_down_button.setEnabled(last_selected_row < last_row)

    # ------------------------------------------------------------------
    # Modality switching
    # ------------------------------------------------------------------

    def _on_modality_changed(self, modality: str) -> None:
        """Save current modality config to memory + config, then load the new one."""
        self._save_current_modality_config()
        self.current_modality = modality
        self._load_modality_config(modality)
        # Emit live update so the overlay shows the correct modality's tags
        self._commit_current_modality_to_config()
        self.config_changed.emit()

    def _save_current_modality_config(self) -> None:
        """Save current modality configuration to in-memory dict."""
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

    def _commit_current_modality_to_config(self) -> None:
        """Write the current modality's in-memory config to ConfigManager."""
        if self.current_modality in self.modality_configs:
            self.config_manager.set_overlay_tags(
                self.current_modality, self.modality_configs[self.current_modality]
            )

    def _load_modality_config(self, modality: str) -> None:
        """Load modality configuration from memory (if available) or config manager."""
        if modality in self.modality_configs:
            corner_tags = self.modality_configs[modality]
        else:
            corner_tags = self.config_manager.get_overlay_tags(modality)

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
                self._update_move_buttons_state(corner_name)

    def _load_configurations(self) -> None:
        """Load all configurations from config manager into memory."""
        modalities = ["default"] + sorted(["CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"])
        for modality in modalities:
            self.modality_configs[modality] = self.config_manager.get_overlay_tags(modality)

        self._load_modality_config(self.current_modality)

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _on_live_update(self) -> None:
        """
        Persist the current modality config and emit config_changed for live preview.

        Called after every tag addition, removal, or reorder.
        """
        self._save_current_modality_config()
        self._commit_current_modality_to_config()
        self.config_changed.emit()

    # ------------------------------------------------------------------
    # OK / Cancel
    # ------------------------------------------------------------------

    def _apply_configuration(self) -> None:
        """Save all modality configs to ConfigManager, emit config_applied, and close."""
        # Flush the currently visible modality before saving everything
        self._save_current_modality_config()

        for modality, config in self.modality_configs.items():
            self.config_manager.set_overlay_tags(modality, config)

        self.config_applied.emit()
        self.accept()

    def reject(self) -> None:
        """Restore all modalities to their original values on Cancel."""
        for modality, config in self._original_configs.items():
            self.config_manager.set_overlay_tags(modality, config)
        self.config_changed.emit()
        super().reject()
