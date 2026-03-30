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

import re

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLineEdit, QLabel, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt, QUrl
from typing import Optional

from pathlib import Path

from utils.config_manager import ConfigManager

_HELP_DIR = Path(__file__).parent.parent.parent.parent / "resources" / "help"


def _normalize_doc_text_encoding(html: str) -> str:
    """Repair common mojibake sequences in the bundled fusion HTML."""
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
        "Î±": "&alpha;",
        "â‰ˆ": "&asymp;",
    }
    for bad_text, fixed_text in replacements.items():
        html = html.replace(bad_text, fixed_text)
    html = html.replace(" ? ", " &rarr; ")
    html = html.replace("\n?\n", "\n&darr;\n")
    html = html.replace(
        "fused = base � (1 - a�mask) + overlay � (a�mask)",
        "fused = base &times; (1 - &alpha;&times;mask) + overlay &times; (&alpha;&times;mask)",
    )
    html = html.replace(
        "overlay = array1 � (1 - weight) + array2 � weight",
        "overlay = array1 &times; (1 - weight) + array2 &times; weight",
    )
    html = html.replace(
        "��0.5 overlay slices (�0.5 voxels in Z); ��0.5 mm at 1 mm slice spacing, ��1.5 mm at 3 mm slice spacing",
        "&plusmn;0.5 overlay slices (&plusmn;0.5 voxels in Z); &plusmn;0.5 mm at 1 mm slice spacing, &plusmn;1.5 mm at 3 mm slice spacing",
    )
    html = html.replace(
        "��0.5 pixels in x/y; ��0.5 mm at 1 mm pixels, ��0.25 mm at 0.5 mm pixels",
        "&plusmn;0.5 pixels in x/y; &plusmn;0.5 mm at 1 mm pixels, &plusmn;0.25 mm at 0.5 mm pixels",
    )
    html = html.replace(
        "�0.5 pixels in x/y (rounding); ��0.5 mm at 1 mm pixels, ��0.25 mm at 0.5 mm pixels",
        "&plusmn;0.5 pixels in x/y (rounding); &plusmn;0.5 mm at 1 mm pixels, &plusmn;0.25 mm at 0.5 mm pixels",
    )
    html = html.replace(
        "Spatial accuracy (native): ��0.5 pixels in x/y from scaling and translation rounding, �0 voxels in Z.",
        "Spatial accuracy (native): &plusmn;0.5 pixels in x/y from scaling and translation rounding, ~0 voxels in Z.",
    )
    html = html.replace(
        "Physical equivalent: ��0.5 mm at 1 mm spacing, ��0.25 mm at 0.5 mm spacing.",
        "Physical equivalent: &plusmn;0.5 mm at 1 mm spacing, &plusmn;0.25 mm at 0.5 mm spacing.",
    )
    html = html.replace(
        "<strong>Total algorithmic error:</strong> on the order of �0.5�1.0 pixels (��0.5�1.0 mm at 1 mm spacing).",
        "<strong>Total algorithmic error:</strong> on the order of 0.5-1.0 pixels (&plusmn;0.5-1.0 mm at 1 mm spacing).",
    )
    html = html.replace(
        "Spatial accuracy (native): ��0.5�1.0 pixels in x/y and up to �0.5 overlay slices in Z.",
        "Spatial accuracy (native): &plusmn;0.5-1.0 pixels in x/y and up to &plusmn;0.5 overlay slices in Z.",
    )
    html = html.replace(
        "Physical equivalent: ��0.5�1.5 mm total, depending on slice spacing (e.g., �1.5 mm at 3 mm slices).",
        "Physical equivalent: &plusmn;0.5-1.5 mm total, depending on slice spacing (for example, &plusmn;1.5 mm at 3 mm slices).",
    )
    html = html.replace(
        "<strong>Total algorithmic error:</strong> typically �1.0�2.5 mm.",
        "<strong>Total algorithmic error:</strong> typically 1.0-2.5 mm.",
    )
    html = html.replace(
        "��0.5 voxels per axis; ��0.87 voxels in 3D magnitude (��0.5�0.9 mm at 1 mm voxels)",
        "&plusmn;0.5 voxels per axis; &plusmn;0.87 voxels in 3D magnitude (&plusmn;0.5-0.9 mm at 1 mm voxels)",
    )
    html = html.replace(
        "��0.3�0.4 voxels per axis; ��0.5�0.7 voxels total (��0.5�0.7 mm at 1 mm voxels)",
        "&plusmn;0.3-0.4 voxels per axis; &plusmn;0.5-0.7 voxels total (&plusmn;0.5-0.7 mm at 1 mm voxels)",
    )
    html = html.replace(
        "Typically �0.1�0.5 mm with good metadata; can be overestimated by 10�30% or more with oblique slices and poor metadata",
        "Typically 0.1-0.5 mm with good metadata; can be overestimated by 10-30% or more with oblique slices and poor metadata",
    )
    html = html.replace(
        "Orientation errors usually &lt;0.1� for well-formed DICOM (<0.001 differences in direction cosines)",
        "Orientation errors usually &lt;0.1&deg; for well-formed DICOM (&lt;0.001 differences in direction cosines)",
    )
    html = html.replace(
        "Spatial accuracy (native): sub-voxel in all three dimensions, typically ��0.5�0.87 voxels total.",
        "Spatial accuracy (native): sub-voxel in all three dimensions, typically &plusmn;0.5-0.87 voxels total.",
    )
    html = html.replace(
        "Physical equivalent (1 mm isotropic voxels): ��0.6�1.0 mm total positional error.",
        "Physical equivalent (1 mm isotropic voxels): &plusmn;0.6-1.0 mm total positional error.",
    )
    html = html.replace(
        "Spatial accuracy: ��0.87 voxels from interpolation plus small spacing/orientation uncertainties.",
        "Spatial accuracy: &plusmn;0.87 voxels from interpolation plus small spacing/orientation uncertainties.",
    )
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
        
        # Text edit for documentation content - use QTextBrowser for anchor link support
        self.text_edit = QTextBrowser()
        self.text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        self.text_edit.setOpenLinks(False)
        self.text_edit.anchorClicked.connect(self._on_anchor_clicked)
        self.text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            self.text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Store full content and set initial content
        self._full_content = self._get_doc_content()
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
        template = _normalize_doc_text_encoding(template)
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
