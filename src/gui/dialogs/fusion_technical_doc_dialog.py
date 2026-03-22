"""
Fusion Technical Documentation Dialog

This module provides a dialog displaying the technical documentation for image fusion,
including algorithms, options, and error analysis.

Inputs:
    - User opens Help menu and selects Fusion Technical Documentation
    
Outputs:
    - Displayed technical documentation with table of contents navigation
    
Requirements:
    - PySide6 for dialog components
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLineEdit, QLabel, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt
from typing import Optional

from pathlib import Path

from utils.config_manager import ConfigManager

_HELP_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "help"


class FusionTechnicalDocDialog(QDialog):
    """
    Technical documentation dialog for image fusion.
    
    Provides:
    - Detailed algorithm descriptions
    - Error analysis and accuracy estimates
    - Performance considerations
    - Table of contents navigation
    """
    
    # Class-level cache for HTML content by theme
    _content_cache: dict = {}  # {theme: html_content}
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QDialog] = None):
        """
        Initialize the Fusion Technical Documentation dialog.
        
        Args:
            config_manager: ConfigManager instance for theme detection
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        
        self.setWindowTitle("Image Fusion Technical Documentation")
        self.setModal(True)
        self.resize(900, 700)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Apply theme-based styling to dialog
        theme = self.config_manager.get_theme()
        if theme == "dark":
            # Set dark grey background for dark theme
            self.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        else:
            # Light theme - use default or white
            self.setStyleSheet("QDialog { background-color: #ffffff; }")
        
        # Search bar with Prev/Next buttons
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search in documentation...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        # Prevent Enter key from closing dialog (it triggers default button)
        self.search_edit.returnPressed.connect(lambda: None)  # Do nothing on Enter
        
        # Prev/Next buttons
        self.prev_button = QPushButton("â—€ Prev")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_match)
        
        self.next_button = QPushButton("Next â–¶")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._on_next_match)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.prev_button)
        search_layout.addWidget(self.next_button)
        layout.addLayout(search_layout)
        
        # Text edit for documentation content - use QTextBrowser for anchor link support
        self.text_edit = QTextBrowser()
        self.text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        self.text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            self.text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Store full content and set initial content
        self._full_content = self._get_doc_content()
        self.text_edit.setHtml(self._full_content)
        
        # Search navigation state
        self._search_match_positions = []  # List of cursor positions for matches
        self._current_match_index = -1  # Current match index (-1 = no match selected)
        layout.addWidget(self.text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)  # Close button triggers accept
        layout.addWidget(button_box)
    
    def _get_doc_content(self) -> str:
        """
        Get the formatted HTML content for the technical documentation.

        Colors adapt to the application theme. Content is loaded from
        ``resources/help/fusion_technical_doc.html`` and cached per theme.

        Returns:
            HTML formatted string with documentation content
        """
        theme = self.config_manager.get_theme()
        if theme in FusionTechnicalDocDialog._content_cache:
            return FusionTechnicalDocDialog._content_cache[theme]

        if theme == "dark":
            colors = dict(
                bg_color="#1e1e1e", h1_color="#ffffff", h2_color="#e0e0e0",
                h3_color="#d0d0d0", text_color="#ffffff", strong_color="#4a9eff",
                code_bg="#2b2b2b", code_text="#ffffff",
                table_border="#555555", table_header_bg="#333333",
            )
        else:
            colors = dict(
                bg_color="#ffffff", h1_color="#000000", h2_color="#1a1a1a",
                h3_color="#2a2a2a", text_color="#000000", strong_color="#2980b9",
                code_bg="#ecf0f1", code_text="#000000",
                table_border="#cccccc", table_header_bg="#e8e8e8",
            )

        template = (_HELP_DIR / "fusion_technical_doc.html").read_text(encoding="utf-8")
        content = template
        for key, val in colors.items():
            content = content.replace(f"{{{key}}}", val)

        FusionTechnicalDocDialog._content_cache[theme] = content
        return content
    
    def _on_search_text_changed(self, text: str) -> None:
        """
        Handle search text changes and filter documentation content.
        
        Args:
            text: Search text entered by user
        """
        if not text.strip():
            # If search is empty, show full content
            self.text_edit.setHtml(self._full_content)
            # Scroll to top
            self.text_edit.moveCursor(self.text_edit.textCursor().Start)
            self._search_match_positions = []
            self._current_match_index = -1
            self._update_navigation_buttons()
            return
        
        # Use QTextEdit's find functionality to search and highlight
        # First, set the full content
        self.text_edit.setHtml(self._full_content)
        
        # Find and highlight all occurrences (case-insensitive)
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        
        # Clear previous selection
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)
        
        # Find all matches and store positions
        self._search_match_positions = []
        while self.text_edit.find(text):
            match_cursor = self.text_edit.textCursor()
            # Store the start position of each match
            self._search_match_positions.append(match_cursor.selectionStart())
        
        # If matches found, go to first match
        if self._search_match_positions:
            self._current_match_index = 0
            cursor.setPosition(self._search_match_positions[0])
            self.text_edit.setTextCursor(cursor)
            # Highlight the first match
            cursor.setPosition(self._search_match_positions[0])
            cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(text))
            self.text_edit.setTextCursor(cursor)
        else:
            # No matches found, scroll to top
            cursor.movePosition(cursor.MoveOperation.Start)
            self.text_edit.setTextCursor(cursor)
            self._current_match_index = -1
        
        self._update_navigation_buttons()
    
    def _on_prev_match(self) -> None:
        """Navigate to previous search match."""
        if not self._search_match_positions or self._current_match_index <= 0:
            return
        
        self._current_match_index -= 1
        cursor = self.text_edit.textCursor()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        self.text_edit.setTextCursor(cursor)
        # Highlight the match
        search_text = self.search_edit.text()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(search_text))
        self.text_edit.setTextCursor(cursor)
        self._update_navigation_buttons()
    
    def _on_next_match(self) -> None:
        """Navigate to next search match."""
        if not self._search_match_positions:
            return
        
        if self._current_match_index < len(self._search_match_positions) - 1:
            self._current_match_index += 1
        else:
            # Wrap around to first match
            self._current_match_index = 0
        
        cursor = self.text_edit.textCursor()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        self.text_edit.setTextCursor(cursor)
        # Highlight the match
        search_text = self.search_edit.text()
        cursor.setPosition(self._search_match_positions[self._current_match_index])
        cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(search_text))
        self.text_edit.setTextCursor(cursor)
        self._update_navigation_buttons()
    
    def _update_navigation_buttons(self) -> None:
        """Update Prev/Next button states based on current match."""
        has_matches = len(self._search_match_positions) > 0
        self.prev_button.setEnabled(has_matches and self._current_match_index > 0)
        self.next_button.setEnabled(has_matches)
