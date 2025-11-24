"""
Disclaimer Dialog

This module provides a disclaimer dialog that must be accepted before using the application.

Inputs:
    - User launches application or selects Help → Disclaimer
    
Outputs:
    - User acceptance or cancellation
    - Preference to not show in future
    
Requirements:
    - PySide6 for dialog components
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
                                QPushButton)
from PySide6.QtCore import Qt
from typing import Optional

from utils.config_manager import ConfigManager


class DisclaimerDialog(QDialog):
    """
    Disclaimer dialog that must be accepted before using the application.
    
    Features:
    - Shows disclaimer message
    - "I accept" and "Exit" buttons
    - "Do not show in the future" checkbox
    """
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QDialog] = None, force_show: bool = False):
        """
        Initialize the disclaimer dialog.
        
        Args:
            config_manager: ConfigManager instance for storing preference
            parent: Parent widget
            force_show: If True, always show dialog regardless of preference
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.force_show = force_show
        self.dont_show_again = False
        
        self.setWindowTitle("Disclaimer")
        self.setModal(True)
        self.resize(500, 200)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Disclaimer message
        disclaimer_label = QLabel("DISCLAIMER: This DICOM viewer is not intended for diagnostic purposes.")
        disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disclaimer_label.setWordWrap(True)
        # Make the text bold and larger
        font = disclaimer_label.font()
        font.setPointSize(12)
        font.setBold(True)
        disclaimer_label.setFont(font)
        layout.addWidget(disclaimer_label)
        
        layout.addStretch()
        
        # "Do not show in the future" checkbox
        self.dont_show_checkbox = QCheckBox("Do not show in the future")
        # Initialize checkbox state from config when force_show is True
        if self.force_show:
            self.dont_show_checkbox.setChecked(self.config_manager.get_disclaimer_accepted())
        else:
            self.dont_show_checkbox.setChecked(False)
        # Connect checkbox to update config in real-time
        self.dont_show_checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self.dont_show_checkbox)
        
        # Buttons in horizontal layout to control order
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to the right
        
        # I accept button (left)
        self.accept_button = QPushButton("I accept")
        self.accept_button.setDefault(True)
        self.accept_button.clicked.connect(self._on_accept)
        button_layout.addWidget(self.accept_button)
        
        # Exit button (right)
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.reject)
        button_layout.addWidget(self.exit_button)
        
        layout.addLayout(button_layout)
    
    def _on_checkbox_toggled(self, checked: bool) -> None:
        """
        Handle checkbox toggle - update config immediately.
        
        Args:
            checked: True if checkbox is checked, False otherwise
        """
        self.config_manager.set_disclaimer_accepted(checked)
    
    def _on_accept(self) -> None:
        """Handle accept button click."""
        self.dont_show_again = self.dont_show_checkbox.isChecked()
        # Config is already updated via checkbox signal, but ensure it's saved
        if self.dont_show_again:
            self.config_manager.set_disclaimer_accepted(True)
        else:
            self.config_manager.set_disclaimer_accepted(False)
        self.accept()
    
    def should_show(self) -> bool:
        """
        Check if the disclaimer should be shown based on configuration.
        
        Returns:
            True if dialog should be shown, False otherwise
        """
        if self.force_show:
            return True
        return not self.config_manager.get_disclaimer_accepted()
    
    @staticmethod
    def show_disclaimer(config_manager: ConfigManager, parent=None, force_show: bool = False) -> bool:
        """
        Show the disclaimer dialog and handle user response.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
            force_show: If True, always show dialog regardless of preference
            
        Returns:
            True if user accepted, False if cancelled
        """
        # If not forcing show, check if we should skip
        if not force_show and config_manager.get_disclaimer_accepted():
            return True
        
        dialog = DisclaimerDialog(config_manager, parent, force_show=force_show)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            # User accepted
            if dialog.dont_show_again:
                config_manager.set_disclaimer_accepted(True)
            return True
        else:
            # User cancelled
            return False

