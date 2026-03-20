"""
Annotation Options Dialog

This module provides a dialog for customizing annotation appearance settings
including ROI and measurement font sizes, colors, and line thicknesses.

Inputs:
    - User preference changes
    
Outputs:
    - Updated annotation configuration settings
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSpinBox, QColorDialog, QGroupBox,
                                QFormLayout, QDialogButtonBox, QCheckBox, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import Optional

from utils.config_manager import ConfigManager
from utils.bundled_fonts import get_font_families, get_font_variants


class AnnotationOptionsDialog(QDialog):
    """
    Dialog for customizing annotation appearance settings.
    
    Provides:
    - ROI font size, line thickness, and color customization (unified color for font and line)
    - Measurement font size, line thickness, and color customization (unified color for font and line)
    - Text annotation font size and color customization
    - Arrow annotation color customization
    """
    
    # Signal emitted when settings are applied
    settings_applied = Signal()
    # Emitted on live font adjustments so annotations refresh before OK.
    settings_changed = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the annotation options dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)

        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        
        self.config_manager = config_manager
        self.setWindowTitle("Annotation Options")
        self.setModal(True)
        self.resize(780, 480)
        
        # Store original values for cancel
        self._store_original_values()

        if DEBUG_FONT_VARIANT:
            debug_log(
                "annotation_options_dialog.py:__init__",
                "Annotation options dialog constructed",
                {
                    "original_text_annotation_font_family": self.original_text_annotation_font_family,
                    "original_text_annotation_font_variant": self.original_text_annotation_font_variant,
                    "original_roi_font_family": self.original_roi_font_family,
                    "original_roi_font_variant": self.original_roi_font_variant,
                    "original_measurement_font_family": self.original_measurement_font_family,
                    "original_measurement_font_variant": self.original_measurement_font_variant,
                },
                hypothesis_id="FONTVAR",
            )
        
        self._create_ui()
        self._load_settings()
        self._connect_live_preview_signals()
    
    def _store_original_values(self) -> None:
        """Store original values for cancel functionality."""
        self.original_roi_font_size = self.config_manager.get_roi_font_size()
        self.original_roi_font_color = self.config_manager.get_roi_font_color()
        self.original_roi_line_thickness = self.config_manager.get_roi_line_thickness()
        self.original_roi_line_color = self.config_manager.get_roi_line_color()
        self.original_measurement_font_size = self.config_manager.get_measurement_font_size()
        self.original_measurement_font_color = self.config_manager.get_measurement_font_color()
        self.original_measurement_line_thickness = self.config_manager.get_measurement_line_thickness()
        self.original_measurement_line_color = self.config_manager.get_measurement_line_color()
        self.original_text_annotation_color = self.config_manager.get_text_annotation_color()
        self.original_text_annotation_font_size = self.config_manager.get_text_annotation_font_size()
        self.original_text_annotation_font_family = self.config_manager.get_text_annotation_font_family()
        self.original_text_annotation_font_variant = self.config_manager.get_text_annotation_font_variant()
        self.original_roi_font_family = self.config_manager.get_roi_font_family()
        self.original_roi_font_variant = self.config_manager.get_roi_font_variant()
        self.original_measurement_font_family = self.config_manager.get_measurement_font_family()
        self.original_measurement_font_variant = self.config_manager.get_measurement_font_variant()
        self.original_arrow_annotation_color = self.config_manager.get_arrow_annotation_color()
        self.original_arrow_annotation_size = self.config_manager.get_arrow_annotation_size()

    def _connect_live_preview_signals(self) -> None:
        """Connect font controls that should live-update before OK is pressed."""
        self.roi_font_size_spinbox.valueChanged.connect(self._on_live_update)
        self.measurement_font_size_spinbox.valueChanged.connect(self._on_live_update)
        self.text_font_size_spinbox.valueChanged.connect(self._on_live_update)

        self.roi_font_family_combo.currentIndexChanged.connect(
            lambda: self._on_family_changed(self.roi_font_family_combo, self.roi_font_variant_combo)
        )
        self.measurement_font_family_combo.currentIndexChanged.connect(
            lambda: self._on_family_changed(
                self.measurement_font_family_combo,
                self.measurement_font_variant_combo,
            )
        )
        self.text_font_family_combo.currentIndexChanged.connect(
            lambda: self._on_family_changed(self.text_font_family_combo, self.text_font_variant_combo)
        )

        self.roi_font_variant_combo.currentIndexChanged.connect(self._on_live_update)
        self.measurement_font_variant_combo.currentIndexChanged.connect(self._on_live_update)
        self.text_font_variant_combo.currentIndexChanged.connect(self._on_live_update)
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        columns_layout = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()
        
        # ROI Settings Group
        roi_group = QGroupBox("ROI Settings")
        roi_layout = QFormLayout()
        
        # ROI Font Size with +/- buttons
        roi_font_size_layout = QHBoxLayout()
        roi_font_size_decrease_button = QPushButton("−")
        roi_font_size_decrease_button.setMaximumWidth(30)
        roi_font_size_decrease_button.clicked.connect(lambda: self.roi_font_size_spinbox.setValue(max(4, self.roi_font_size_spinbox.value() - 1)))
        
        self.roi_font_size_spinbox = QSpinBox()
        self.roi_font_size_spinbox.setRange(4, 24)
        self.roi_font_size_spinbox.setValue(6)
        self.roi_font_size_spinbox.setSuffix(" pt")
        
        roi_font_size_increase_button = QPushButton("+")
        roi_font_size_increase_button.setMaximumWidth(30)
        roi_font_size_increase_button.clicked.connect(lambda: self.roi_font_size_spinbox.setValue(min(24, self.roi_font_size_spinbox.value() + 1)))
        
        roi_font_size_layout.addWidget(roi_font_size_decrease_button)
        roi_font_size_layout.addWidget(self.roi_font_size_spinbox)
        roi_font_size_layout.addWidget(roi_font_size_increase_button)
        roi_font_size_layout.addStretch()
        
        roi_layout.addRow("Font Size:", roi_font_size_layout)
        
        # ROI Line Thickness with +/- buttons
        roi_line_thickness_layout = QHBoxLayout()
        roi_line_thickness_decrease_button = QPushButton("−")
        roi_line_thickness_decrease_button.setMaximumWidth(30)
        roi_line_thickness_decrease_button.clicked.connect(lambda: self.roi_line_thickness_spinbox.setValue(max(1, self.roi_line_thickness_spinbox.value() - 1)))
        
        self.roi_line_thickness_spinbox = QSpinBox()
        self.roi_line_thickness_spinbox.setRange(1, 10)
        self.roi_line_thickness_spinbox.setValue(2)
        self.roi_line_thickness_spinbox.setSuffix(" px")
        
        roi_line_thickness_increase_button = QPushButton("+")
        roi_line_thickness_increase_button.setMaximumWidth(30)
        roi_line_thickness_increase_button.clicked.connect(lambda: self.roi_line_thickness_spinbox.setValue(min(10, self.roi_line_thickness_spinbox.value() + 1)))
        
        roi_line_thickness_layout.addWidget(roi_line_thickness_decrease_button)
        roi_line_thickness_layout.addWidget(self.roi_line_thickness_spinbox)
        roi_line_thickness_layout.addWidget(roi_line_thickness_increase_button)
        roi_line_thickness_layout.addStretch()
        
        roi_layout.addRow("Line Thickness:", roi_line_thickness_layout)
        
        # ROI Color (unified for both font and line)
        roi_color_layout = QHBoxLayout()
        self.roi_color_label = QLabel()
        self.roi_color_label.setMinimumSize(50, 30)
        self.roi_color_label.setStyleSheet("background-color: rgb(255, 0, 0); border: 1px solid black;")
        self.roi_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        roi_color_button = QPushButton("Choose Color...")
        roi_color_button.clicked.connect(lambda: self._choose_color("roi"))
        
        roi_color_layout.addWidget(self.roi_color_label)
        roi_color_layout.addWidget(roi_color_button)
        roi_color_layout.addStretch()
        
        roi_layout.addRow("Color:", roi_color_layout)
        
        # ROI Font Family
        self.roi_font_family_combo = QComboBox()
        self.roi_font_family_combo.addItems(get_font_families())
        roi_layout.addRow("Font:", self.roi_font_family_combo)

        # ROI Font Variant
        self.roi_font_variant_combo = QComboBox()
        roi_layout.addRow("Variant:", self.roi_font_variant_combo)

        roi_group.setLayout(roi_layout)
        left_col.addWidget(roi_group)
        
        # ROI Statistics Visibility Group
        stats_group = QGroupBox("ROI Statistics Visibility")
        stats_layout = QVBoxLayout()
        
        # Statistics checkboxes
        self.mean_checkbox = QCheckBox("Show Mean")
        self.std_checkbox = QCheckBox("Show Std Dev")
        self.min_checkbox = QCheckBox("Show Min")
        self.max_checkbox = QCheckBox("Show Max")
        self.pixels_checkbox = QCheckBox("Show Pixels")
        self.area_checkbox = QCheckBox("Show Area")
        
        stats_layout.addWidget(self.mean_checkbox)
        stats_layout.addWidget(self.std_checkbox)
        stats_layout.addWidget(self.min_checkbox)
        stats_layout.addWidget(self.max_checkbox)
        stats_layout.addWidget(self.pixels_checkbox)
        stats_layout.addWidget(self.area_checkbox)
        
        stats_group.setLayout(stats_layout)
        left_col.addWidget(stats_group)
        left_col.addStretch()
        
        # Measurement Settings Group
        measurement_group = QGroupBox("Measurement Settings")
        measurement_layout = QFormLayout()
        
        # Measurement Font Size with +/- buttons
        measurement_font_size_layout = QHBoxLayout()
        measurement_font_size_decrease_button = QPushButton("−")
        measurement_font_size_decrease_button.setMaximumWidth(30)
        measurement_font_size_decrease_button.clicked.connect(lambda: self.measurement_font_size_spinbox.setValue(max(4, self.measurement_font_size_spinbox.value() - 1)))
        
        self.measurement_font_size_spinbox = QSpinBox()
        self.measurement_font_size_spinbox.setRange(4, 24)
        self.measurement_font_size_spinbox.setValue(10)
        self.measurement_font_size_spinbox.setSuffix(" pt")
        
        measurement_font_size_increase_button = QPushButton("+")
        measurement_font_size_increase_button.setMaximumWidth(30)
        measurement_font_size_increase_button.clicked.connect(lambda: self.measurement_font_size_spinbox.setValue(min(24, self.measurement_font_size_spinbox.value() + 1)))
        
        measurement_font_size_layout.addWidget(measurement_font_size_decrease_button)
        measurement_font_size_layout.addWidget(self.measurement_font_size_spinbox)
        measurement_font_size_layout.addWidget(measurement_font_size_increase_button)
        measurement_font_size_layout.addStretch()
        
        measurement_layout.addRow("Font Size:", measurement_font_size_layout)
        
        # Measurement Line Thickness with +/- buttons
        measurement_line_thickness_layout = QHBoxLayout()
        measurement_line_thickness_decrease_button = QPushButton("−")
        measurement_line_thickness_decrease_button.setMaximumWidth(30)
        measurement_line_thickness_decrease_button.clicked.connect(lambda: self.measurement_line_thickness_spinbox.setValue(max(1, self.measurement_line_thickness_spinbox.value() - 1)))
        
        self.measurement_line_thickness_spinbox = QSpinBox()
        self.measurement_line_thickness_spinbox.setRange(1, 10)
        self.measurement_line_thickness_spinbox.setValue(2)
        self.measurement_line_thickness_spinbox.setSuffix(" px")
        
        measurement_line_thickness_increase_button = QPushButton("+")
        measurement_line_thickness_increase_button.setMaximumWidth(30)
        measurement_line_thickness_increase_button.clicked.connect(lambda: self.measurement_line_thickness_spinbox.setValue(min(10, self.measurement_line_thickness_spinbox.value() + 1)))
        
        measurement_line_thickness_layout.addWidget(measurement_line_thickness_decrease_button)
        measurement_line_thickness_layout.addWidget(self.measurement_line_thickness_spinbox)
        measurement_line_thickness_layout.addWidget(measurement_line_thickness_increase_button)
        measurement_line_thickness_layout.addStretch()
        
        measurement_layout.addRow("Line Thickness:", measurement_line_thickness_layout)
        
        # Measurement Color (unified for both font and line)
        measurement_color_layout = QHBoxLayout()
        self.measurement_color_label = QLabel()
        self.measurement_color_label.setMinimumSize(50, 30)
        self.measurement_color_label.setStyleSheet("background-color: rgb(0, 255, 0); border: 1px solid black;")
        self.measurement_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        measurement_color_button = QPushButton("Choose Color...")
        measurement_color_button.clicked.connect(lambda: self._choose_color("measurement"))
        
        measurement_color_layout.addWidget(self.measurement_color_label)
        measurement_color_layout.addWidget(measurement_color_button)
        measurement_color_layout.addStretch()
        
        measurement_layout.addRow("Color:", measurement_color_layout)
        
        # Measurement Font Family
        self.measurement_font_family_combo = QComboBox()
        self.measurement_font_family_combo.addItems(get_font_families())
        measurement_layout.addRow("Font:", self.measurement_font_family_combo)

        # Measurement Font Variant
        self.measurement_font_variant_combo = QComboBox()
        measurement_layout.addRow("Variant:", self.measurement_font_variant_combo)

        measurement_group.setLayout(measurement_layout)
        right_col.addWidget(measurement_group)
        
        # Text Annotation Settings Group
        text_group = QGroupBox("Text Annotation Settings")
        text_layout = QFormLayout()
        
        # Text Annotation Font Size with +/- buttons
        text_font_size_layout = QHBoxLayout()
        text_font_size_decrease_button = QPushButton("−")
        text_font_size_decrease_button.setMaximumWidth(30)
        text_font_size_decrease_button.clicked.connect(lambda: self.text_font_size_spinbox.setValue(max(4, self.text_font_size_spinbox.value() - 1)))
        
        self.text_font_size_spinbox = QSpinBox()
        self.text_font_size_spinbox.setRange(4, 24)
        self.text_font_size_spinbox.setValue(12)
        self.text_font_size_spinbox.setSuffix(" pt")
        
        text_font_size_increase_button = QPushButton("+")
        text_font_size_increase_button.setMaximumWidth(30)
        text_font_size_increase_button.clicked.connect(lambda: self.text_font_size_spinbox.setValue(min(24, self.text_font_size_spinbox.value() + 1)))
        
        text_font_size_layout.addWidget(text_font_size_decrease_button)
        text_font_size_layout.addWidget(self.text_font_size_spinbox)
        text_font_size_layout.addWidget(text_font_size_increase_button)
        text_font_size_layout.addStretch()
        
        text_layout.addRow("Font Size:", text_font_size_layout)
        
        # Text Annotation Color
        text_color_layout = QHBoxLayout()
        self.text_color_label = QLabel()
        self.text_color_label.setMinimumSize(50, 30)
        self.text_color_label.setStyleSheet("background-color: rgb(255, 255, 0); border: 1px solid black;")
        self.text_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_color_button = QPushButton("Choose Color...")
        text_color_button.clicked.connect(lambda: self._choose_color("text"))

        text_color_layout.addWidget(self.text_color_label)
        text_color_layout.addWidget(text_color_button)
        text_color_layout.addStretch()

        text_layout.addRow("Color:", text_color_layout)

        # Text Annotation Font Family
        self.text_font_family_combo = QComboBox()
        self.text_font_family_combo.addItems(get_font_families())
        text_layout.addRow("Font:", self.text_font_family_combo)

        # Text Annotation Font Variant
        self.text_font_variant_combo = QComboBox()
        text_layout.addRow("Variant:", self.text_font_variant_combo)

        text_group.setLayout(text_layout)
        right_col.addWidget(text_group)
        
        # Arrow Annotation Settings Group
        arrow_group = QGroupBox("Arrow Annotation Settings")
        arrow_layout = QFormLayout()
        
        # Arrow Annotation Color
        arrow_color_layout = QHBoxLayout()
        self.arrow_color_label = QLabel()
        self.arrow_color_label.setMinimumSize(50, 30)
        self.arrow_color_label.setStyleSheet("background-color: rgb(255, 255, 0); border: 1px solid black;")
        self.arrow_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        arrow_color_button = QPushButton("Choose Color...")
        arrow_color_button.clicked.connect(lambda: self._choose_color("arrow"))
        
        arrow_color_layout.addWidget(self.arrow_color_label)
        arrow_color_layout.addWidget(arrow_color_button)
        arrow_color_layout.addStretch()
        
        arrow_layout.addRow("Color:", arrow_color_layout)
        
        # Arrow size (arrowhead size and line thickness)
        arrow_size_layout = QHBoxLayout()
        arrow_size_decrease_button = QPushButton("−")
        arrow_size_decrease_button.setMaximumWidth(30)
        arrow_size_decrease_button.clicked.connect(lambda: self.arrow_size_spinbox.setValue(max(4, self.arrow_size_spinbox.value() - 1)))
        self.arrow_size_spinbox = QSpinBox()
        self.arrow_size_spinbox.setRange(4, 30)
        self.arrow_size_spinbox.setValue(6)
        self.arrow_size_spinbox.setSuffix(" px")
        arrow_size_increase_button = QPushButton("+")
        arrow_size_increase_button.setMaximumWidth(30)
        arrow_size_increase_button.clicked.connect(lambda: self.arrow_size_spinbox.setValue(min(30, self.arrow_size_spinbox.value() + 1)))
        arrow_size_layout.addWidget(arrow_size_decrease_button)
        arrow_size_layout.addWidget(self.arrow_size_spinbox)
        arrow_size_layout.addWidget(arrow_size_increase_button)
        arrow_size_layout.addStretch()
        arrow_layout.addRow("Size:", arrow_size_layout)
        
        arrow_group.setLayout(arrow_layout)
        right_col.addWidget(arrow_group)
        right_col.addStretch()
        
        columns_layout.addLayout(left_col)
        columns_layout.addLayout(right_col)
        layout.addLayout(columns_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._apply_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_settings(self) -> None:
        """Load current settings into the dialog."""
        # ROI settings
        roi_font_size = self.config_manager.get_roi_font_size()
        self.roi_font_size_spinbox.setValue(roi_font_size)
        
        roi_line_thickness = self.config_manager.get_roi_line_thickness()
        self.roi_line_thickness_spinbox.setValue(roi_line_thickness)
        
        # ROI color: prefer line color, fallback to font color
        roi_line_color = self.config_manager.get_roi_line_color()
        roi_font_color = self.config_manager.get_roi_font_color()
        # Use line color (prefer it), fallback to font color if they differ
        # If they're the same, use line color. If different, prefer line unless it's default
        if roi_line_color == roi_font_color:
            roi_color = roi_line_color
        else:
            # They differ - prefer line color (as per plan)
            roi_color = roi_line_color
        self._update_color_display("roi", *roi_color)
        self.roi_color = roi_color
        roi_family = self.config_manager.get_roi_font_family()
        idx = self.roi_font_family_combo.findText(roi_family)
        if idx >= 0:
            self.roi_font_family_combo.setCurrentIndex(idx)
        self._repopulate_variant_combo(
            self.roi_font_family_combo, self.roi_font_variant_combo,
            self.config_manager.get_roi_font_variant()
        )
        
        # Measurement settings
        measurement_font_size = self.config_manager.get_measurement_font_size()
        self.measurement_font_size_spinbox.setValue(measurement_font_size)
        
        measurement_line_thickness = self.config_manager.get_measurement_line_thickness()
        self.measurement_line_thickness_spinbox.setValue(measurement_line_thickness)
        
        # Measurement color: prefer line color, fallback to font color
        measurement_line_color = self.config_manager.get_measurement_line_color()
        measurement_font_color = self.config_manager.get_measurement_font_color()
        # Use line color (prefer it), fallback to font color if they differ
        # If they're the same, use line color. If different, prefer line
        if measurement_line_color == measurement_font_color:
            measurement_color = measurement_line_color
        else:
            # They differ - prefer line color (as per plan)
            measurement_color = measurement_line_color
        self._update_color_display("measurement", *measurement_color)
        self.measurement_color = measurement_color
        measurement_family = self.config_manager.get_measurement_font_family()
        idx = self.measurement_font_family_combo.findText(measurement_family)
        if idx >= 0:
            self.measurement_font_family_combo.setCurrentIndex(idx)
        self._repopulate_variant_combo(
            self.measurement_font_family_combo, self.measurement_font_variant_combo,
            self.config_manager.get_measurement_font_variant()
        )
        
        # Text annotation settings
        text_font_size = self.config_manager.get_text_annotation_font_size()
        self.text_font_size_spinbox.setValue(text_font_size)

        text_color = self.config_manager.get_text_annotation_color()
        self._update_color_display("text", *text_color)
        self.text_color = text_color

        text_family = self.config_manager.get_text_annotation_font_family()
        idx = self.text_font_family_combo.findText(text_family)
        if idx >= 0:
            self.text_font_family_combo.setCurrentIndex(idx)
        self._repopulate_variant_combo(
            self.text_font_family_combo, self.text_font_variant_combo,
            self.config_manager.get_text_annotation_font_variant()
        )

        # Arrow annotation settings
        arrow_color = self.config_manager.get_arrow_annotation_color()
        self._update_color_display("arrow", *arrow_color)
        self.arrow_color = arrow_color
        arrow_size = self.config_manager.get_arrow_annotation_size()
        self.arrow_size_spinbox.setValue(arrow_size)
        
        # ROI statistics visibility settings
        default_stats = self.config_manager.get_roi_default_visible_statistics()
        self.mean_checkbox.setChecked("mean" in default_stats)
        self.std_checkbox.setChecked("std" in default_stats)
        self.min_checkbox.setChecked("min" in default_stats)
        self.max_checkbox.setChecked("max" in default_stats)
        self.pixels_checkbox.setChecked("count" in default_stats)
        self.area_checkbox.setChecked("area" in default_stats)
    
    def _repopulate_variant_combo(
        self,
        family_combo: "QComboBox",
        variant_combo: "QComboBox",
        preferred_variant: Optional[str] = None,
    ) -> None:
        """Repopulate *variant_combo* based on the current family in *family_combo*."""
        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        variant_combo.blockSignals(True)
        current = preferred_variant or variant_combo.currentText() or "Bold"
        variant_combo.clear()
        variants = get_font_variants(family_combo.currentText())
        variant_combo.addItems(variants)
        idx = variant_combo.findText(current)
        variant_combo.setCurrentIndex(idx if idx >= 0 else 0)
        variant_combo.blockSignals(False)
        if DEBUG_FONT_VARIANT:
            debug_log(
                "annotation_options_dialog.py:_repopulate_variant_combo",
                "Populated annotation font variant combo",
                {
                    "family": family_combo.currentText(),
                    "preferred_variant": preferred_variant,
                    "current_before": current,
                    "variants": variants,
                    "selected_index": idx if idx >= 0 else 0,
                    "selected_variant": variant_combo.currentText(),
                    "combo_object": variant_combo.objectName() or variant_combo.__class__.__name__,
                },
                hypothesis_id="FONTVAR",
            )

    def _on_family_changed(self, family_combo: "QComboBox", variant_combo: "QComboBox") -> None:
        """Refresh available variants for a font family, then apply the live preview."""
        current_variant = variant_combo.currentText()
        self._repopulate_variant_combo(family_combo, variant_combo, current_variant)
        self._on_live_update()

    def _save_live_font_settings(self) -> None:
        """Persist font size/family/variant settings used by the live preview."""
        self.config_manager.set_roi_font_size(self.roi_font_size_spinbox.value())
        self.config_manager.set_roi_font_family(self.roi_font_family_combo.currentText())
        self.config_manager.set_roi_font_variant(self.roi_font_variant_combo.currentText())

        self.config_manager.set_measurement_font_size(self.measurement_font_size_spinbox.value())
        self.config_manager.set_measurement_font_family(self.measurement_font_family_combo.currentText())
        self.config_manager.set_measurement_font_variant(self.measurement_font_variant_combo.currentText())

        self.config_manager.set_text_annotation_font_size(self.text_font_size_spinbox.value())
        self.config_manager.set_text_annotation_font_family(self.text_font_family_combo.currentText())
        self.config_manager.set_text_annotation_font_variant(self.text_font_variant_combo.currentText())

    def _on_live_update(self) -> None:
        """Apply font changes immediately so annotation styling updates before OK."""
        self._save_live_font_settings()
        self.settings_changed.emit()

    def _update_color_display(self, color_type: str, r: int, g: int, b: int) -> None:
        """
        Update the color display label.
        
        Args:
            color_type: Type of color ("roi", "measurement", "text", "arrow")
            r: Red component
            g: Green component
            b: Blue component
        """
        if color_type == "roi":
            self.roi_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "measurement":
            self.measurement_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "text":
            self.text_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "arrow":
            self.arrow_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
    
    def _choose_color(self, color_type: str) -> None:
        """
        Open color picker dialog.
        
        Args:
            color_type: Type of color to choose ("roi", "measurement", "text", "arrow")
        """
        if color_type == "roi":
            r, g, b = self.roi_color
            title = "Choose ROI Color"
        elif color_type == "measurement":
            r, g, b = self.measurement_color
            title = "Choose Measurement Color"
        elif color_type == "text":
            r, g, b = self.text_color
            title = "Choose Text Annotation Color"
        elif color_type == "arrow":
            r, g, b = self.arrow_color
            title = "Choose Arrow Annotation Color"
        else:
            return
        
        color = QColorDialog.getColor(QColor(r, g, b), self, title)
        
        if color.isValid():
            new_color = (color.red(), color.green(), color.blue())
            if color_type == "roi":
                self.roi_color = new_color
            elif color_type == "measurement":
                self.measurement_color = new_color
            elif color_type == "text":
                self.text_color = new_color
            elif color_type == "arrow":
                self.arrow_color = new_color
            self._update_color_display(color_type, *new_color)
    
    def _apply_settings(self) -> None:
        """Apply settings and close dialog."""
        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        if DEBUG_FONT_VARIANT:
            debug_log(
                "annotation_options_dialog.py:_apply_settings",
                "Applying annotation options",
                {
                    "roi_font_family": self.roi_font_family_combo.currentText(),
                    "roi_font_variant": self.roi_font_variant_combo.currentText(),
                    "measurement_font_family": self.measurement_font_family_combo.currentText(),
                    "measurement_font_variant": self.measurement_font_variant_combo.currentText(),
                    "text_font_family": self.text_font_family_combo.currentText(),
                    "text_font_variant": self.text_font_variant_combo.currentText(),
                },
                hypothesis_id="FONTVAR",
            )
        # Save ROI settings
        self.config_manager.set_roi_font_size(self.roi_font_size_spinbox.value())
        self.config_manager.set_roi_line_thickness(self.roi_line_thickness_spinbox.value())
        # Set both font and line colors to the unified color
        self.config_manager.set_roi_font_color(*self.roi_color)
        self.config_manager.set_roi_line_color(*self.roi_color)
        self.config_manager.set_roi_font_family(self.roi_font_family_combo.currentText())
        self.config_manager.set_roi_font_variant(self.roi_font_variant_combo.currentText())
        
        # Save measurement settings
        self.config_manager.set_measurement_font_size(self.measurement_font_size_spinbox.value())
        self.config_manager.set_measurement_line_thickness(self.measurement_line_thickness_spinbox.value())
        # Set both font and line colors to the unified color
        self.config_manager.set_measurement_font_color(*self.measurement_color)
        self.config_manager.set_measurement_line_color(*self.measurement_color)
        self.config_manager.set_measurement_font_family(self.measurement_font_family_combo.currentText())
        self.config_manager.set_measurement_font_variant(self.measurement_font_variant_combo.currentText())
        
        # Save text annotation settings
        self.config_manager.set_text_annotation_font_size(self.text_font_size_spinbox.value())
        self.config_manager.set_text_annotation_color(*self.text_color)
        self.config_manager.set_text_annotation_font_family(self.text_font_family_combo.currentText())
        self.config_manager.set_text_annotation_font_variant(self.text_font_variant_combo.currentText())
        
        # Save arrow annotation settings
        self.config_manager.set_arrow_annotation_color(*self.arrow_color)
        self.config_manager.set_arrow_annotation_size(self.arrow_size_spinbox.value())
        
        # Save ROI statistics visibility settings
        selected_stats = []
        if self.mean_checkbox.isChecked():
            selected_stats.append("mean")
        if self.std_checkbox.isChecked():
            selected_stats.append("std")
        if self.min_checkbox.isChecked():
            selected_stats.append("min")
        if self.max_checkbox.isChecked():
            selected_stats.append("max")
        if self.pixels_checkbox.isChecked():
            selected_stats.append("count")
        if self.area_checkbox.isChecked():
            selected_stats.append("area")
        self.config_manager.set_roi_default_visible_statistics(selected_stats)
        
        # Emit signal to notify that settings were applied
        self.settings_applied.emit()
        
        self.accept()

    def reject(self) -> None:
        """Restore original values on Cancel so any live preview changes are undone."""
        self.config_manager.set_roi_font_size(self.original_roi_font_size)
        self.config_manager.set_roi_font_color(*self.original_roi_font_color)
        self.config_manager.set_roi_line_thickness(self.original_roi_line_thickness)
        self.config_manager.set_roi_line_color(*self.original_roi_line_color)
        self.config_manager.set_roi_font_family(self.original_roi_font_family)
        self.config_manager.set_roi_font_variant(self.original_roi_font_variant)

        self.config_manager.set_measurement_font_size(self.original_measurement_font_size)
        self.config_manager.set_measurement_font_color(*self.original_measurement_font_color)
        self.config_manager.set_measurement_line_thickness(self.original_measurement_line_thickness)
        self.config_manager.set_measurement_line_color(*self.original_measurement_line_color)
        self.config_manager.set_measurement_font_family(self.original_measurement_font_family)
        self.config_manager.set_measurement_font_variant(self.original_measurement_font_variant)

        self.config_manager.set_text_annotation_color(*self.original_text_annotation_color)
        self.config_manager.set_text_annotation_font_size(self.original_text_annotation_font_size)
        self.config_manager.set_text_annotation_font_family(self.original_text_annotation_font_family)
        self.config_manager.set_text_annotation_font_variant(self.original_text_annotation_font_variant)

        self.config_manager.set_arrow_annotation_color(*self.original_arrow_annotation_color)
        self.config_manager.set_arrow_annotation_size(self.original_arrow_annotation_size)
        self.settings_changed.emit()
        super().reject()

