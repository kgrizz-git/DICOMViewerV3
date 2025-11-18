"""
Overlay Settings Dialog

This module provides a dialog for customizing overlay font size and color.

Inputs:
    - User preference changes
    
Outputs:
    - Updated overlay configuration settings
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSpinBox, QColorDialog, QGroupBox,
                                QFormLayout, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import Optional

from utils.config_manager import ConfigManager


class OverlaySettingsDialog(QDialog):
    """
    Dialog for customizing overlay font size and color.
    
    Provides:
    - Overlay font size customization
    - Overlay font color customization
    """
    
    # Signal emitted when settings are applied
    settings_applied = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the overlay settings dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.setWindowTitle("Overlay Settings")
        self.setModal(True)
        self.resize(400, 200)
        
        # Store original values for cancel
        self.original_font_size = config_manager.get_overlay_font_size()
        self.original_font_color = config_manager.get_overlay_font_color()
        
        self._create_ui()
        self._load_settings()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Overlay Settings Group
        overlay_group = QGroupBox("Overlay Settings")
        overlay_layout = QFormLayout()
        
        # Font Size
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(1, 24)
        self.font_size_spinbox.setValue(10)
        self.font_size_spinbox.setSuffix(" pt")
        overlay_layout.addRow("Font Size:", self.font_size_spinbox)
        
        # Font Color
        color_layout = QHBoxLayout()
        self.color_label = QLabel()
        self.color_label.setMinimumSize(50, 30)
        self.color_label.setStyleSheet("background-color: rgb(255, 255, 0); border: 1px solid black;")
        self.color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        color_button = QPushButton("Choose Color...")
        color_button.clicked.connect(self._choose_color)
        
        color_layout.addWidget(self.color_label)
        color_layout.addWidget(color_button)
        color_layout.addStretch()
        
        overlay_layout.addRow("Font Color:", color_layout)
        
        overlay_group.setLayout(overlay_layout)
        layout.addWidget(overlay_group)
        
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
        # Font size
        font_size = self.config_manager.get_overlay_font_size()
        self.font_size_spinbox.setValue(font_size)
        
        # Font color
        r, g, b = self.config_manager.get_overlay_font_color()
        self._update_color_display(r, g, b)
        self.current_color = (r, g, b)
    
    def _update_color_display(self, r: int, g: int, b: int) -> None:
        """
        Update the color display label.
        
        Args:
            r: Red component
            g: Green component
            b: Blue component
        """
        self.color_label.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        )
    
    def _choose_color(self) -> None:
        """Open color picker dialog."""
        r, g, b = self.current_color
        color = QColorDialog.getColor(QColor(r, g, b), self, "Choose Overlay Font Color")
        
        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self._update_color_display(*self.current_color)
    
    def _apply_settings(self) -> None:
        """Apply settings and close dialog."""
        # Save font size
        font_size = self.font_size_spinbox.value()
        self.config_manager.set_overlay_font_size(font_size)
        
        # Save font color
        r, g, b = self.current_color
        self.config_manager.set_overlay_font_color(r, g, b)
        
        # Emit signal to notify that settings were applied
        self.settings_applied.emit()
        
        self.accept()

