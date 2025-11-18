"""
Settings Dialog

This module provides a settings dialog for customizing application preferences.
Currently empty - overlay settings have been moved to View → Overlay Settings.

Inputs:
    - User preference changes
    
Outputs:
    - Updated configuration settings
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                                QDialogButtonBox)
from PySide6.QtCore import Qt, Signal
from typing import Optional

from utils.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """
    Settings dialog for application preferences.
    
    Note: Overlay settings have been moved to View → Overlay Settings.
    This dialog is kept for future general settings.
    """
    
    # Signal emitted when settings are applied
    settings_applied = Signal()
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the settings dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 200)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Placeholder message
        message_label = QLabel("Settings dialog.\n\nOverlay settings are available via View → Overlay Settings.")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message_label)
        
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
        )
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

