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
                                QFormLayout, QDialogButtonBox, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import Optional

from utils.config_manager import ConfigManager


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
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the annotation options dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.setWindowTitle("Annotation Options")
        self.setModal(True)
        self.resize(500, 500)
        
        # Store original values for cancel
        self._store_original_values()
        
        self._create_ui()
        self._load_settings()
    
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
        self.original_arrow_annotation_color = self.config_manager.get_arrow_annotation_color()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
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
        
        roi_group.setLayout(roi_layout)
        layout.addWidget(roi_group)
        
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
        layout.addWidget(stats_group)
        
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
        
        measurement_group.setLayout(measurement_layout)
        layout.addWidget(measurement_group)
        
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
        
        text_group.setLayout(text_layout)
        layout.addWidget(text_group)
        
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
        
        arrow_group.setLayout(arrow_layout)
        layout.addWidget(arrow_group)
        
        layout.addStretch()
        
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
        
        # Text annotation settings
        text_font_size = self.config_manager.get_text_annotation_font_size()
        self.text_font_size_spinbox.setValue(text_font_size)
        
        text_color = self.config_manager.get_text_annotation_color()
        self._update_color_display("text", *text_color)
        self.text_color = text_color
        
        # Arrow annotation settings
        arrow_color = self.config_manager.get_arrow_annotation_color()
        self._update_color_display("arrow", *arrow_color)
        self.arrow_color = arrow_color
        
        # ROI statistics visibility settings
        default_stats = self.config_manager.get_roi_default_visible_statistics()
        self.mean_checkbox.setChecked("mean" in default_stats)
        self.std_checkbox.setChecked("std" in default_stats)
        self.min_checkbox.setChecked("min" in default_stats)
        self.max_checkbox.setChecked("max" in default_stats)
        self.pixels_checkbox.setChecked("count" in default_stats)
        self.area_checkbox.setChecked("area" in default_stats)
    
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
        # Save ROI settings
        self.config_manager.set_roi_font_size(self.roi_font_size_spinbox.value())
        self.config_manager.set_roi_line_thickness(self.roi_line_thickness_spinbox.value())
        # Set both font and line colors to the unified color
        self.config_manager.set_roi_font_color(*self.roi_color)
        self.config_manager.set_roi_line_color(*self.roi_color)
        
        # Save measurement settings
        self.config_manager.set_measurement_font_size(self.measurement_font_size_spinbox.value())
        self.config_manager.set_measurement_line_thickness(self.measurement_line_thickness_spinbox.value())
        # Set both font and line colors to the unified color
        self.config_manager.set_measurement_font_color(*self.measurement_color)
        self.config_manager.set_measurement_line_color(*self.measurement_color)
        
        # Save text annotation settings
        self.config_manager.set_text_annotation_font_size(self.text_font_size_spinbox.value())
        self.config_manager.set_text_annotation_color(*self.text_color)
        
        # Save arrow annotation settings
        self.config_manager.set_arrow_annotation_color(*self.arrow_color)
        
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

