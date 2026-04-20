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
                                QPushButton, QListWidget,
                                QComboBox, QGroupBox, QDialogButtonBox,
                                QLineEdit, QMessageBox, QTabWidget, QWidget,
                                QSizePolicy)
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
    - Modality selection (dropdown)
    - Four corners (tabs): per corner, **Simple** and **Detailed-only** tag lists are
      visible together with buttons to move tags between them, plus a shared
      available-tag picker
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
        # Wide, short default so the window fits laptop screens; inner lists scroll.
        self.resize(1240, 480)
        self.setMinimumSize(880, 380)

        # Valid modalities list (alphabetical order, default first)
        valid_modalities = ["default", "CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"]

        # Store current modality - use initial_modality if provided and valid, otherwise "default"
        if initial_modality and initial_modality.strip() in valid_modalities:
            self.current_modality = initial_modality.strip()
        else:
            self.current_modality = "default"

        # Store tag configurations per modality (working copy, updated on every change)
        self.modality_configs: Dict[str, Dict[str, List[str]]] = {}
        self.modality_configs_detailed: Dict[str, Dict[str, List[str]]] = {}

        # Per-corner UI (populated in _create_corner_widget): one shared catalog + dual lists
        self.search_edits: Dict[str, QLineEdit] = {}
        self.available_lists: Dict[str, QListWidget] = {}
        self.selected_lists: Dict[str, QListWidget] = {}
        self.move_up_buttons: Dict[str, QPushButton] = {}
        self.move_down_buttons: Dict[str, QPushButton] = {}
        self.detailed_selected_lists: Dict[str, QListWidget] = {}
        self.detailed_move_up_buttons: Dict[str, QPushButton] = {}
        self.detailed_move_down_buttons: Dict[str, QPushButton] = {}

        self._create_ui()
        self._load_configurations()

        # Deep-copy snapshot used to revert on Cancel
        self._original_configs: Dict[str, Dict[str, List[str]]] = copy.deepcopy(self.modality_configs)
        self._original_configs_detailed: Dict[str, Dict[str, List[str]]] = copy.deepcopy(
            self.modality_configs_detailed
        )
        self._original_overlay_mode: str = self.config_manager.get_overlay_mode()

        # Set the combo box to the initial modality after loading configurations
        if self.modality_combo.findText(self.current_modality) >= 0:
            self.modality_combo.setCurrentText(self.current_modality)

        self._sync_detail_mode_combo_from_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _sync_detail_mode_combo_from_config(self) -> None:
        """Set the detail-level combo from ConfigManager without emitting live updates."""
        mode = self.config_manager.get_overlay_mode()
        if mode not in ("minimal", "detailed", "hidden"):
            mode = "minimal"
        self.detail_mode_combo.blockSignals(True)
        for i in range(self.detail_mode_combo.count()):
            if self.detail_mode_combo.itemData(i) == mode:
                self.detail_mode_combo.setCurrentIndex(i)
                break
        self.detail_mode_combo.blockSignals(False)

    def _on_detail_mode_combo_changed(self, _index: int) -> None:
        """Persist overlay mode and refresh live preview."""
        mode = self.detail_mode_combo.currentData()
        if mode not in ("minimal", "detailed", "hidden"):
            return
        self.config_manager.set_overlay_mode(mode)
        self.config_changed.emit()

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)

        # Single compact row: default overlay mode (Space) + modality picker.
        header_group = QGroupBox("Overlay mode & modality")
        header_group.setToolTip(
            "Space cycles Simple → Detailed → Hidden on all views. "
            "Shift+Space uses the older per-view visibility cycle (focused view only)."
        )
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Default (Space):"))
        self.detail_mode_combo = QComboBox()
        self.detail_mode_combo.addItem("Simple (fewer tags)", "minimal")
        self.detail_mode_combo.addItem("Detailed (more tags)", "detailed")
        self.detail_mode_combo.addItem("Hidden (no corner text)", "hidden")
        self.detail_mode_combo.currentIndexChanged.connect(self._on_detail_mode_combo_changed)
        header_row.addWidget(self.detail_mode_combo, 1)
        header_row.addSpacing(24)
        header_row.addWidget(QLabel("Modality:"))
        self.modality_combo = QComboBox()
        modalities = ["default"] + sorted(["CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"])
        self.modality_combo.addItems(modalities)
        self.modality_combo.currentTextChanged.connect(self._on_modality_changed)
        header_row.addWidget(self.modality_combo, 1)
        header_group.setLayout(header_row)
        layout.addWidget(header_group)

        tags_help = QLabel(
            "Corner tabs: catalog at left; Simple and Detailed-only lists share one row. "
            "→ Detailed / ← Simple move selection. Double-click catalog → Simple."
        )
        tags_help.setWordWrap(True)
        tags_help.setMaximumHeight(42)
        layout.addWidget(tags_help)

        corners_tab = QTabWidget()
        self.upper_left_widget = self._create_corner_widget("Upper Left")
        corners_tab.addTab(self.upper_left_widget, "Upper Left")
        self.upper_right_widget = self._create_corner_widget("Upper Right")
        corners_tab.addTab(self.upper_right_widget, "Upper Right")
        self.lower_left_widget = self._create_corner_widget("Lower Left")
        corners_tab.addTab(self.lower_left_widget, "Lower Left")
        self.lower_right_widget = self._create_corner_widget("Lower Right")
        corners_tab.addTab(self.lower_right_widget, "Lower Right")
        corners_tab.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(corners_tab, 1)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._apply_configuration)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _corner_ui_maps(
        self, layer: str
    ) -> tuple[
        Dict[str, QLineEdit],
        Dict[str, QListWidget],
        Dict[str, QListWidget],
        Dict[str, QPushButton],
        Dict[str, QPushButton],
    ]:
        """Return per-corner UI dicts for the simple list or the detailed-only list."""
        if layer == "detailed":
            return (
                self.search_edits,
                self.available_lists,
                self.detailed_selected_lists,
                self.detailed_move_up_buttons,
                self.detailed_move_down_buttons,
            )
        return (
            self.search_edits,
            self.available_lists,
            self.selected_lists,
            self.move_up_buttons,
            self.move_down_buttons,
        )

    def _create_corner_widget(self, corner_name: str) -> QWidget:
        """
        One corner: catalog in a left column; Simple | arrows | Detailed in one row
        so the tab stays short (lists scroll, fixed max height).
        """
        widget = QWidget()
        root = QHBoxLayout(widget)
        root.setSpacing(8)

        # Fixed-ish catalog column: keeps overall dialog shorter than stacking catalog above lists.
        list_max_h = 200
        list_min_h = 120

        available_group = QGroupBox("Catalog")
        available_group.setMaximumWidth(280)
        available_layout = QVBoxLayout()

        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Filter…")
        search_edit.textChanged.connect(lambda _t, cn=corner_name: self._filter_tags(cn))
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit)
        available_layout.addLayout(search_layout)

        self.search_edits[corner_name] = search_edit

        available_list = QListWidget()
        available_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_list.setMinimumHeight(list_min_h)
        available_list.setMaximumHeight(list_max_h)
        available_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for tag in COMMON_TAGS:
            available_list.addItem(tag)
        available_list.itemDoubleClicked.connect(
            lambda item, cn=corner_name: self._add_tag_to_corner(cn, item.text(), "simple")
        )

        self.available_lists[corner_name] = available_list

        available_layout.addWidget(available_list)
        add_row = QHBoxLayout()
        add_simple = QPushButton("Add to Simple")
        add_simple.clicked.connect(lambda _=False, cn=corner_name: self._add_selected_tags(cn, "simple"))
        add_detailed = QPushButton("Add to Detailed")
        add_detailed.clicked.connect(
            lambda _=False, cn=corner_name: self._add_selected_tags(cn, "detailed")
        )
        add_row.addWidget(add_simple)
        add_row.addWidget(add_detailed)
        available_layout.addLayout(add_row)
        available_group.setLayout(available_layout)
        root.addWidget(available_group, 0)

        dual = QHBoxLayout()
        dual_wrap = QWidget()
        dual_wrap.setLayout(dual)

        simple_group = QGroupBox("Simple (minimal mode)")
        simple_col = QVBoxLayout()
        simple_list = QListWidget()
        simple_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        simple_list.setMinimumHeight(list_min_h)
        simple_list.setMaximumHeight(list_max_h)
        simple_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.selected_lists[corner_name] = simple_list
        simple_col.addWidget(simple_list)
        simple_btns = QHBoxLayout()
        rm_s = QPushButton("Remove")
        rm_s.clicked.connect(lambda _=False, cn=corner_name: self._remove_selected_tags(cn, "simple"))
        mu_s = QPushButton("Move Up")
        mu_s.clicked.connect(lambda _=False, cn=corner_name: self._move_tag_up(cn, "simple"))
        md_s = QPushButton("Move Down")
        md_s.clicked.connect(lambda _=False, cn=corner_name: self._move_tag_down(cn, "simple"))
        simple_btns.addWidget(rm_s)
        simple_btns.addWidget(mu_s)
        simple_btns.addWidget(md_s)
        simple_col.addLayout(simple_btns)
        self.move_up_buttons[corner_name] = mu_s
        self.move_down_buttons[corner_name] = md_s
        simple_group.setLayout(simple_col)
        dual.addWidget(simple_group, 1)

        mid = QVBoxLayout()
        mid.addStretch(1)
        to_det = QPushButton("→\nDetailed")
        to_det.setToolTip("Move selected tags from Simple to Detailed-only (removes from Simple).")
        to_det.clicked.connect(lambda _=False, cn=corner_name: self._move_selected_simple_to_detailed(cn))
        mid.addWidget(to_det)
        to_sim = QPushButton("←\nSimple")
        to_sim.setToolTip("Move selected tags from Detailed-only to Simple (removes from Detailed).")
        to_sim.clicked.connect(lambda _=False, cn=corner_name: self._move_selected_detailed_to_simple(cn))
        mid.addWidget(to_sim)
        mid.addStretch(2)
        dual.addLayout(mid)

        det_group = QGroupBox("Detailed only (additional)")
        det_col = QVBoxLayout()
        det_list = QListWidget()
        det_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        det_list.setMinimumHeight(list_min_h)
        det_list.setMaximumHeight(list_max_h)
        det_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detailed_selected_lists[corner_name] = det_list
        det_col.addWidget(det_list)
        det_btns = QHBoxLayout()
        rm_d = QPushButton("Remove")
        rm_d.clicked.connect(lambda _=False, cn=corner_name: self._remove_selected_tags(cn, "detailed"))
        mu_d = QPushButton("Move Up")
        mu_d.clicked.connect(lambda _=False, cn=corner_name: self._move_tag_up(cn, "detailed"))
        md_d = QPushButton("Move Down")
        md_d.clicked.connect(lambda _=False, cn=corner_name: self._move_tag_down(cn, "detailed"))
        det_btns.addWidget(rm_d)
        det_btns.addWidget(mu_d)
        det_btns.addWidget(md_d)
        det_col.addLayout(det_btns)
        self.detailed_move_up_buttons[corner_name] = mu_d
        self.detailed_move_down_buttons[corner_name] = md_d
        det_group.setLayout(det_col)
        dual.addWidget(det_group, 1)

        root.addWidget(dual_wrap, 1)

        sel_changed = lambda cn=corner_name: self._on_corner_selection_changed(cn)
        simple_list.itemSelectionChanged.connect(sel_changed)
        det_list.itemSelectionChanged.connect(sel_changed)
        self._on_corner_selection_changed(corner_name)

        return widget

    def _on_corner_selection_changed(self, corner_name: str) -> None:
        """Refresh move up/down for both lists when selection changes in either."""
        self._update_move_buttons_state(corner_name, "simple")
        self._update_move_buttons_state(corner_name, "detailed")

    def _move_selected_simple_to_detailed(self, corner_name: str) -> None:
        """Remove selected from Simple and append to Detailed if not already there."""
        if corner_name not in self.selected_lists or corner_name not in self.detailed_selected_lists:
            return
        src = self.selected_lists[corner_name]
        dst = self.detailed_selected_lists[corner_name]
        existing_dst = {dst.item(i).text() for i in range(dst.count())}
        tags = [item.text() for item in src.selectedItems()]
        if not tags:
            return
        for item in list(src.selectedItems()):
            src.takeItem(src.row(item))
        for tag in tags:
            if tag not in existing_dst:
                dst.addItem(tag)
                existing_dst.add(tag)
        self._on_corner_selection_changed(corner_name)
        self._on_live_update()

    def _move_selected_detailed_to_simple(self, corner_name: str) -> None:
        """Remove selected from Detailed and append to Simple if not already there."""
        if corner_name not in self.selected_lists or corner_name not in self.detailed_selected_lists:
            return
        dst = self.selected_lists[corner_name]
        src = self.detailed_selected_lists[corner_name]
        existing_dst = {dst.item(i).text() for i in range(dst.count())}
        tags = [item.text() for item in src.selectedItems()]
        if not tags:
            return
        for item in list(src.selectedItems()):
            src.takeItem(src.row(item))
        for tag in tags:
            if tag not in existing_dst:
                dst.addItem(tag)
                existing_dst.add(tag)
        self._on_corner_selection_changed(corner_name)
        self._on_live_update()

    # ------------------------------------------------------------------
    # Tag list helpers
    # ------------------------------------------------------------------

    def _filter_tags(self, corner_name: str) -> None:
        """Filter the shared available-tag catalog for this corner."""
        if corner_name not in self.available_lists or corner_name not in self.search_edits:
            return

        search_text = self.search_edits[corner_name].text().lower()
        available_list = self.available_lists[corner_name]

        for i in range(available_list.count()):
            item = available_list.item(i)
            if search_text in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _add_selected_tags(self, corner_name: str, layer: str = "simple") -> None:
        """Add selected tags from available list to corner."""
        _se, al, sl, _mu, _md = self._corner_ui_maps(layer)
        if corner_name not in al or corner_name not in sl:
            return

        available_list = al[corner_name]
        selected_list = sl[corner_name]

        added = False
        for item in available_list.selectedItems():
            tag = item.text()
            existing = [selected_list.item(i).text() for i in range(selected_list.count())]
            if tag not in existing:
                selected_list.addItem(tag)
                added = True

        if added:
            self._on_live_update()

    def _add_tag_to_corner(self, corner_name: str, tag: str, layer: str = "simple") -> None:
        """Add a tag to corner (double-click handler)."""
        _se, _al, sl, _mu, _md = self._corner_ui_maps(layer)
        if corner_name not in sl:
            return

        selected_list = sl[corner_name]
        existing = [selected_list.item(i).text() for i in range(selected_list.count())]
        if tag not in existing:
            selected_list.addItem(tag)
            self._on_live_update()

    def _remove_selected_tags(self, corner_name: str, layer: str = "simple") -> None:
        """Remove selected tags from corner."""
        _se, _al, sl, _mu, _md = self._corner_ui_maps(layer)
        if corner_name not in sl:
            return

        selected_list = sl[corner_name]
        items_to_remove = selected_list.selectedItems()
        if not items_to_remove:
            return

        for item in items_to_remove:
            selected_list.takeItem(selected_list.row(item))

        self._on_live_update()

    def _move_tag_up(self, corner_name: str, layer: str = "simple") -> None:
        """Move selected tags up by one position in the corner's list."""
        _se, _al, sl, _mu, _md = self._corner_ui_maps(layer)
        if corner_name not in sl:
            return

        selected_list = sl[corner_name]
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

        self._update_move_buttons_state(corner_name, layer)
        self._on_live_update()

    def _move_tag_down(self, corner_name: str, layer: str = "simple") -> None:
        """Move selected tags down by one position in the corner's list."""
        _se, _al, sl, _mu, _md = self._corner_ui_maps(layer)
        if corner_name not in sl:
            return

        selected_list = sl[corner_name]
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

        self._update_move_buttons_state(corner_name, layer)
        self._on_live_update()

    def _update_move_buttons_state(self, corner_name: str, layer: str = "simple") -> None:
        """Update enabled state of Move Up/Down buttons based on selection."""
        _se, _al, sl, mu, md = self._corner_ui_maps(layer)
        if corner_name not in sl:
            return

        selected_list = sl[corner_name]
        selected_items = selected_list.selectedItems()

        move_up_button = mu.get(corner_name)
        move_down_button = md.get(corner_name)

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
        self._save_current_modality_config("simple")
        self._save_current_modality_config("detailed")
        self.current_modality = modality
        self._load_modality_config(modality, "simple")
        self._load_modality_config(modality, "detailed")
        self._commit_current_modality_to_config()
        self._commit_current_modality_detailed_to_config()
        self.config_changed.emit()

    def _save_current_modality_config(self, layer: str = "simple") -> None:
        """Save current modality configuration to the in-memory dict for *layer*."""
        _se, _al, sl, _mu, _md = self._corner_ui_maps(layer)
        config = {
            "upper_left": [sl["Upper Left"].item(i).text() for i in range(sl["Upper Left"].count())],
            "upper_right": [sl["Upper Right"].item(i).text() for i in range(sl["Upper Right"].count())],
            "lower_left": [sl["Lower Left"].item(i).text() for i in range(sl["Lower Left"].count())],
            "lower_right": [sl["Lower Right"].item(i).text() for i in range(sl["Lower Right"].count())],
        }
        if layer == "detailed":
            self.modality_configs_detailed[self.current_modality] = config
        else:
            self.modality_configs[self.current_modality] = config

    def _commit_current_modality_to_config(self) -> None:
        """Write the current modality's in-memory simple tags to ConfigManager."""
        if self.current_modality in self.modality_configs:
            self.config_manager.set_overlay_tags(
                self.current_modality, self.modality_configs[self.current_modality]
            )

    def _commit_current_modality_detailed_to_config(self) -> None:
        """Write the current modality's detailed-extra tags to ConfigManager."""
        if self.current_modality in self.modality_configs_detailed:
            self.config_manager.set_overlay_tags_detailed_extra(
                self.current_modality, self.modality_configs_detailed[self.current_modality]
            )

    def _load_modality_config(self, modality: str, layer: str = "simple") -> None:
        """Load modality configuration from memory (if available) or config manager."""
        if layer == "detailed":
            if modality in self.modality_configs_detailed:
                corner_tags = self.modality_configs_detailed[modality]
            else:
                corner_tags = self.config_manager.get_overlay_tags_detailed_extra(modality)
            lists = self.detailed_selected_lists
        else:
            if modality in self.modality_configs:
                corner_tags = self.modality_configs[modality]
            else:
                corner_tags = self.config_manager.get_overlay_tags(modality)
            lists = self.selected_lists

        for corner_name, corner_key in [
            ("Upper Left", "upper_left"),
            ("Upper Right", "upper_right"),
            ("Lower Left", "lower_left"),
            ("Lower Right", "lower_right"),
        ]:
            if corner_name in lists:
                selected_list = lists[corner_name]
                selected_list.clear()
                for tag in corner_tags.get(corner_key, []):
                    selected_list.addItem(tag)
                self._update_move_buttons_state(corner_name, layer)

    def _load_configurations(self) -> None:
        """Load all configurations from config manager into memory."""
        modalities = ["default"] + sorted(["CR", "CT", "DX", "MG", "MR", "NM", "PT", "RF", "RT", "US", "XA"])
        for modality in modalities:
            self.modality_configs[modality] = self.config_manager.get_overlay_tags(modality)
            self.modality_configs_detailed[modality] = (
                self.config_manager.get_overlay_tags_detailed_extra(modality)
            )

        self._load_modality_config(self.current_modality, "simple")
        self._load_modality_config(self.current_modality, "detailed")

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _on_live_update(self) -> None:
        """
        Persist both Simple and Detailed-only lists for the current modality and
        emit config_changed for live preview.
        """
        self._save_current_modality_config("simple")
        self._save_current_modality_config("detailed")
        self._commit_current_modality_to_config()
        self._commit_current_modality_detailed_to_config()
        self.config_changed.emit()

    # ------------------------------------------------------------------
    # OK / Cancel
    # ------------------------------------------------------------------

    def _apply_configuration(self) -> None:
        """Save all modality configs to ConfigManager, emit config_applied, and close."""
        self._save_current_modality_config("simple")
        self._save_current_modality_config("detailed")

        for modality, config in self.modality_configs.items():
            self.config_manager.set_overlay_tags(modality, config)
        for modality, config in self.modality_configs_detailed.items():
            self.config_manager.set_overlay_tags_detailed_extra(modality, config)

        self.config_applied.emit()
        self.accept()

    def reject(self) -> None:
        """Restore all modalities to their original values on Cancel."""
        for modality, config in self._original_configs.items():
            self.config_manager.set_overlay_tags(modality, config)
        for modality, config in self._original_configs_detailed.items():
            self.config_manager.set_overlay_tags_detailed_extra(modality, config)
        self.config_manager.set_overlay_mode(self._original_overlay_mode)
        self.config_changed.emit()
        super().reject()
