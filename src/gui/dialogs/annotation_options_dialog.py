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
    - ROI font size and color customization
    - ROI line thickness and color customization
    - Measurement font size and color customization
    - Measurement line thickness and color customization
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
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # ROI Settings Group
        roi_group = QGroupBox("ROI Settings")
        roi_layout = QFormLayout()
        
        # ROI Font Size
        self.roi_font_size_spinbox = QSpinBox()
        self.roi_font_size_spinbox.setRange(4, 24)
        self.roi_font_size_spinbox.setValue(6)
        self.roi_font_size_spinbox.setSuffix(" pt")
        roi_layout.addRow("Font Size:", self.roi_font_size_spinbox)
        
        # ROI Font Color
        roi_font_color_layout = QHBoxLayout()
        self.roi_font_color_label = QLabel()
        self.roi_font_color_label.setMinimumSize(50, 30)
        self.roi_font_color_label.setStyleSheet("background-color: rgb(255, 255, 0); border: 1px solid black;")
        self.roi_font_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        roi_font_color_button = QPushButton("Choose Color...")
        roi_font_color_button.clicked.connect(lambda: self._choose_color("roi_font"))
        
        roi_font_color_layout.addWidget(self.roi_font_color_label)
        roi_font_color_layout.addWidget(roi_font_color_button)
        roi_font_color_layout.addStretch()
        
        roi_layout.addRow("Font Color:", roi_font_color_layout)
        
        # ROI Line Thickness
        self.roi_line_thickness_spinbox = QSpinBox()
        self.roi_line_thickness_spinbox.setRange(1, 10)
        self.roi_line_thickness_spinbox.setValue(2)
        self.roi_line_thickness_spinbox.setSuffix(" px")
        roi_layout.addRow("Line Thickness:", self.roi_line_thickness_spinbox)
        
        # ROI Line Color
        roi_line_color_layout = QHBoxLayout()
        self.roi_line_color_label = QLabel()
        self.roi_line_color_label.setMinimumSize(50, 30)
        self.roi_line_color_label.setStyleSheet("background-color: rgb(255, 0, 0); border: 1px solid black;")
        self.roi_line_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        roi_line_color_button = QPushButton("Choose Color...")
        roi_line_color_button.clicked.connect(lambda: self._choose_color("roi_line"))
        
        roi_line_color_layout.addWidget(self.roi_line_color_label)
        roi_line_color_layout.addWidget(roi_line_color_button)
        roi_line_color_layout.addStretch()
        
        roi_layout.addRow("Line Color:", roi_line_color_layout)
        
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
        
        # Measurement Font Size
        self.measurement_font_size_spinbox = QSpinBox()
        self.measurement_font_size_spinbox.setRange(4, 24)
        self.measurement_font_size_spinbox.setValue(10)
        self.measurement_font_size_spinbox.setSuffix(" pt")
        measurement_layout.addRow("Font Size:", self.measurement_font_size_spinbox)
        
        # Measurement Font Color
        measurement_font_color_layout = QHBoxLayout()
        self.measurement_font_color_label = QLabel()
        self.measurement_font_color_label.setMinimumSize(50, 30)
        self.measurement_font_color_label.setStyleSheet("background-color: rgb(0, 255, 0); border: 1px solid black;")
        self.measurement_font_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        measurement_font_color_button = QPushButton("Choose Color...")
        measurement_font_color_button.clicked.connect(lambda: self._choose_color("measurement_font"))
        
        measurement_font_color_layout.addWidget(self.measurement_font_color_label)
        measurement_font_color_layout.addWidget(measurement_font_color_button)
        measurement_font_color_layout.addStretch()
        
        measurement_layout.addRow("Font Color:", measurement_font_color_layout)
        
        # Measurement Line Thickness
        self.measurement_line_thickness_spinbox = QSpinBox()
        self.measurement_line_thickness_spinbox.setRange(1, 10)
        self.measurement_line_thickness_spinbox.setValue(2)
        self.measurement_line_thickness_spinbox.setSuffix(" px")
        measurement_layout.addRow("Line Thickness:", self.measurement_line_thickness_spinbox)
        
        # Measurement Line Color
        measurement_line_color_layout = QHBoxLayout()
        self.measurement_line_color_label = QLabel()
        self.measurement_line_color_label.setMinimumSize(50, 30)
        self.measurement_line_color_label.setStyleSheet("background-color: rgb(0, 255, 0); border: 1px solid black;")
        self.measurement_line_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        measurement_line_color_button = QPushButton("Choose Color...")
        measurement_line_color_button.clicked.connect(lambda: self._choose_color("measurement_line"))
        
        measurement_line_color_layout.addWidget(self.measurement_line_color_label)
        measurement_line_color_layout.addWidget(measurement_line_color_button)
        measurement_line_color_layout.addStretch()
        
        measurement_layout.addRow("Line Color:", measurement_line_color_layout)
        
        measurement_group.setLayout(measurement_layout)
        layout.addWidget(measurement_group)
        
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
        
        roi_font_color = self.config_manager.get_roi_font_color()
        self._update_color_display("roi_font", *roi_font_color)
        self.roi_font_color = roi_font_color
        
        roi_line_thickness = self.config_manager.get_roi_line_thickness()
        self.roi_line_thickness_spinbox.setValue(roi_line_thickness)
        
        roi_line_color = self.config_manager.get_roi_line_color()
        self._update_color_display("roi_line", *roi_line_color)
        self.roi_line_color = roi_line_color
        
        # Measurement settings
        measurement_font_size = self.config_manager.get_measurement_font_size()
        self.measurement_font_size_spinbox.setValue(measurement_font_size)
        
        measurement_font_color = self.config_manager.get_measurement_font_color()
        self._update_color_display("measurement_font", *measurement_font_color)
        self.measurement_font_color = measurement_font_color
        
        measurement_line_thickness = self.config_manager.get_measurement_line_thickness()
        self.measurement_line_thickness_spinbox.setValue(measurement_line_thickness)
        
        measurement_line_color = self.config_manager.get_measurement_line_color()
        self._update_color_display("measurement_line", *measurement_line_color)
        self.measurement_line_color = measurement_line_color
        
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
            color_type: Type of color ("roi_font", "roi_line", "measurement_font", "measurement_line")
            r: Red component
            g: Green component
            b: Blue component
        """
        if color_type == "roi_font":
            self.roi_font_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "roi_line":
            self.roi_line_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "measurement_font":
            self.measurement_font_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
        elif color_type == "measurement_line":
            self.measurement_line_color_label.setStyleSheet(
                f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
            )
    
    def _choose_color(self, color_type: str) -> None:
        """
        Open color picker dialog.
        
        Args:
            color_type: Type of color to choose ("roi_font", "roi_line", "measurement_font", "measurement_line")
        """
        if color_type == "roi_font":
            r, g, b = self.roi_font_color
            title = "Choose ROI Font Color"
        elif color_type == "roi_line":
            r, g, b = self.roi_line_color
            title = "Choose ROI Line Color"
        elif color_type == "measurement_font":
            r, g, b = self.measurement_font_color
            title = "Choose Measurement Font Color"
        elif color_type == "measurement_line":
            r, g, b = self.measurement_line_color
            title = "Choose Measurement Line Color"
        else:
            return
        
        color = QColorDialog.getColor(QColor(r, g, b), self, title)
        
        if color.isValid():
            new_color = (color.red(), color.green(), color.blue())
            if color_type == "roi_font":
                self.roi_font_color = new_color
            elif color_type == "roi_line":
                self.roi_line_color = new_color
            elif color_type == "measurement_font":
                self.measurement_font_color = new_color
            elif color_type == "measurement_line":
                self.measurement_line_color = new_color
            self._update_color_display(color_type, *new_color)
    
    def _apply_settings(self) -> None:
        """Apply settings and close dialog."""
        # Save ROI settings
        self.config_manager.set_roi_font_size(self.roi_font_size_spinbox.value())
        self.config_manager.set_roi_font_color(*self.roi_font_color)
        self.config_manager.set_roi_line_thickness(self.roi_line_thickness_spinbox.value())
        self.config_manager.set_roi_line_color(*self.roi_line_color)
        
        # Save measurement settings
        self.config_manager.set_measurement_font_size(self.measurement_font_size_spinbox.value())
        self.config_manager.set_measurement_font_color(*self.measurement_font_color)
        self.config_manager.set_measurement_line_thickness(self.measurement_line_thickness_spinbox.value())
        self.config_manager.set_measurement_line_color(*self.measurement_line_color)
        
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

