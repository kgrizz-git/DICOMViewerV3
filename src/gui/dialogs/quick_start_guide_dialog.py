"""
Quick Start Guide Dialog

This module provides a Quick Start Guide dialog with comprehensive instructions
on how to use the DICOM viewer application.

IMPORTANT MAINTENANCE RULE:
    After making changes to functionality or controls in this project, this Quick Start
    Guide should be updated if necessary to reflect the changes. The guide content
    is in the _get_guide_content() method.

Inputs:
    - User opens Help menu and selects Quick Start Guide
    
Outputs:
    - Displayed guide with instructions
    
Requirements:
    - PySide6 for dialog components
"""

import re

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLineEdit, QLabel, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt, QUrl
from typing import Optional

from pathlib import Path

from utils.config_manager import ConfigManager

_HELP_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "help"


def _normalize_guide_text_encoding(html: str) -> str:
    """Repair common mojibake sequences in the bundled guide HTML."""
    replacements = {
        "â†’": "&rarr;",
        "â†": "&larr;",
        "â†‘": "&uarr;",
        "â†“": "&darr;",
        "â€¦": "...",
        "â€‘": "-",
        "â€“": "-",
        "â€”": "-",
        "â€˜": "'",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "â„¢": "TM",
        "Ã—": "&times;",
        "Â°": "&deg;",
        "Â±": "&plusmn;",
        "Ã": "&times;",
        "Î±": "&alpha;",
        "â‰ˆ": "&asymp;",
    }
    for bad_text, fixed_text in replacements.items():
        html = html.replace(bad_text, fixed_text)
    html = html.replace(" ? ", " &rarr; ")
    html = html.replace('<code>?</code> (Up)', '<code>&uarr;</code> (Up)')
    html = html.replace('<code>?</code> (Down)', '<code>&darr;</code> (Down)')
    html = html.replace('<code>?</code> (Left)', '<code>&larr;</code> (Left)')
    html = html.replace('<code>?</code> (Right)', '<code>&rarr;</code> (Right)')
    html = html.replace(
        '<code>?</code> / <code>?</code>:</strong> Navigate slices',
        '<code>&uarr;</code> / <code>&darr;</code>:</strong> Navigate slices',
    )
    html = html.replace(
        '<code>?</code> / <code>?</code>:</strong> Navigate series',
        '<code>&larr;</code> / <code>&rarr;</code>:</strong> Navigate series',
    )
    html = html.replace("Export ROI Statistics�", "Export ROI Statistics...")
    html = html.replace("1.5�, 2�, 4�", "1.5&times;, 2&times;, 4&times;")
    html = html.replace("<h2>Table of Contents</h2>", '<h2 id="table-of-contents">Table of Contents</h2>', 1)
    return html


def _extract_toc_sections(html: str) -> list[tuple[str, str]]:
    """Return unique section anchors in the order shown in the Table of Contents."""
    toc_match = re.search(
        r'<h2 id="table-of-contents">Table of Contents</h2>\s*<ul>(.*?)</ul>',
        html,
        re.DOTALL,
    )
    toc_html = toc_match.group(1) if toc_match else html
    sections: list[tuple[str, str]] = []
    seen_anchors: set[str] = set()
    for anchor, title in re.findall(r'<a href="#([^"]+)">([^<]+)</a>', toc_html):
        if anchor in seen_anchors:
            continue
        seen_anchors.add(anchor)
        sections.append((anchor, title.strip()))
    return sections


class QuickStartGuideDialog(QDialog):
    """
    Quick Start Guide dialog with comprehensive instructions.
    
    Provides:
    - Controls overview
    - Navigation instructions
    - Measurement and ROI operations
    - Window/Level adjustment methods
    - Mouse modes explanation
    """
    
    # Class-level cache for HTML content by theme
    _content_cache: dict = {}  # {theme: html_content}
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QDialog] = None):
        """
        Initialize the Quick Start Guide dialog.
        
        Args:
            config_manager: ConfigManager instance for theme detection
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        
        self.setWindowTitle("Quick Start Guide")
        self.setModal(True)
        self.resize(700, 600)
        
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
        self.search_edit.setPlaceholderText("Search in guide to enable Prev/Next...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        # Prevent Enter key from closing dialog (it triggers default button)
        self.search_edit.returnPressed.connect(lambda: None)  # Do nothing on Enter
        
        # Prev/Next buttons
        self.prev_button = QPushButton("< Prev")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_match)
        
        self.next_button = QPushButton("Next >")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._on_next_match)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.prev_button)
        search_layout.addWidget(self.next_button)
        layout.addLayout(search_layout)

        section_layout = QHBoxLayout()
        section_label = QLabel("Sections:")
        self.toc_button = QPushButton("Table of Contents")
        self.toc_button.clicked.connect(self._scroll_to_table_of_contents)
        self.prev_section_button = QPushButton("Prev Section")
        self.prev_section_button.clicked.connect(self._on_prev_section)
        self.next_section_button = QPushButton("Next Section")
        self.next_section_button.clicked.connect(self._on_next_section)
        section_layout.addWidget(section_label)
        section_layout.addWidget(self.toc_button)
        section_layout.addWidget(self.prev_section_button)
        section_layout.addWidget(self.next_section_button)
        section_layout.addStretch()
        layout.addLayout(section_layout)
        
        # Text edit for guide content - use QTextBrowser for anchor link support
        self.text_edit = QTextBrowser()
        self.text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        self.text_edit.setOpenLinks(False)
        self.text_edit.anchorClicked.connect(self._on_anchor_clicked)
        self.text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            self.text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Store full content and set initial content
        self._full_content = self._get_guide_content()
        self._section_anchors = _extract_toc_sections(self._full_content)
        self._current_section_index = -1
        self.text_edit.setHtml(self._full_content)
        
        # Search navigation state
        self._search_match_positions = []  # List of cursor positions for matches
        self._current_match_index = -1  # Current match index (-1 = no match selected)
        self._update_section_buttons()
        layout.addWidget(self.text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)  # Close button triggers accept
        layout.addWidget(button_box)
    
    def _get_guide_content(self) -> str:
        """
        Get the formatted HTML content for the guide.

        Colors adapt to the application theme. Content is loaded from
        ``resources/help/quick_start_guide.html`` and cached per theme.

        Returns:
            HTML formatted string with guide content
        """
        theme = self.config_manager.get_theme()
        if theme in QuickStartGuideDialog._content_cache:
            return QuickStartGuideDialog._content_cache[theme]

        if theme == "dark":
            colors = dict(
                bg_color="#1e1e1e", h1_color="#ffffff", h2_color="#e0e0e0",
                text_color="#ffffff", strong_color="#4a9eff",
                code_bg="#1e1e1e", code_text="#ffffff",
            )
        else:
            colors = dict(
                bg_color="#ffffff", h1_color="#000000", h2_color="#1a1a1a",
                text_color="#000000", strong_color="#2980b9",
                code_bg="#ecf0f1", code_text="#000000",
            )

        template = (_HELP_DIR / "quick_start_guide.html").read_text(encoding="utf-8")
        template = _normalize_guide_text_encoding(template)
        content = template
        for key, val in colors.items():
            content = content.replace(f"{{{key}}}", val)

        QuickStartGuideDialog._content_cache[theme] = content
        return content
    
    def _on_search_text_changed(self, text: str) -> None:
        """
        Handle search text changes and filter guide content.
        
        Args:
            text: Search text entered by user
        """
        if not text.strip():
            # If search is empty, show full content
            self.text_edit.setHtml(self._full_content)
            # Scroll to top
            self.text_edit.moveCursor(self.text_edit.textCursor().MoveOperation.Start)
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

    def _on_anchor_clicked(self, url: QUrl) -> None:
        """Handle internal documentation anchor navigation."""
        anchor = url.fragment()
        if not anchor:
            return
        self.text_edit.scrollToAnchor(anchor)
        self._set_current_section(anchor)

    def _scroll_to_table_of_contents(self) -> None:
        """Scroll to the table of contents heading."""
        self.text_edit.scrollToAnchor("table-of-contents")
        self._set_current_section("table-of-contents")

    def _set_current_section(self, anchor: str) -> None:
        """Update section navigation state for the currently focused anchor."""
        if anchor == "table-of-contents":
            self._current_section_index = -1
            self._update_section_buttons()
            return

        for index, (section_anchor, _title) in enumerate(self._section_anchors):
            if section_anchor == anchor:
                self._current_section_index = index
                break
        self._update_section_buttons()

    def _on_prev_section(self) -> None:
        """Navigate to the previous top-level section."""
        if self._current_section_index <= 0:
            return
        self._current_section_index -= 1
        self.text_edit.scrollToAnchor(self._section_anchors[self._current_section_index][0])
        self._update_section_buttons()

    def _on_next_section(self) -> None:
        """Navigate to the next top-level section."""
        if self._current_section_index >= len(self._section_anchors) - 1:
            return
        self._current_section_index += 1
        self.text_edit.scrollToAnchor(self._section_anchors[self._current_section_index][0])
        self._update_section_buttons()
    
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

    def _update_section_buttons(self) -> None:
        """Update section-level navigation buttons."""
        has_sections = len(self._section_anchors) > 0
        self.toc_button.setEnabled(has_sections)
        self.prev_section_button.setEnabled(has_sections and self._current_section_index > 0)
        self.next_section_button.setEnabled(
            has_sections and self._current_section_index < len(self._section_anchors) - 1
        )
