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

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox, QLineEdit, QLabel, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt
from typing import Optional

from utils.config_manager import ConfigManager


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
        self.search_edit.setPlaceholderText("Search in guide...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        # Prevent Enter key from closing dialog (it triggers default button)
        self.search_edit.returnPressed.connect(lambda: None)  # Do nothing on Enter
        
        # Prev/Next buttons
        self.prev_button = QPushButton("◀ Prev")
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_match)
        
        self.next_button = QPushButton("Next ▶")
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._on_next_match)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.prev_button)
        search_layout.addWidget(self.next_button)
        layout.addLayout(search_layout)
        
        # Text edit for guide content - use QTextBrowser for anchor link support
        self.text_edit = QTextBrowser()
        self.text_edit.setOpenExternalLinks(False)  # Don't open external links in browser
        self.text_edit.setReadOnly(True)
        # Set QTextBrowser background to match metadata panel in dark theme
        if theme == "dark":
            self.text_edit.setStyleSheet("QTextBrowser { background-color: #1e1e1e; }")
        
        # Store full content and set initial content
        self._full_content = self._get_guide_content()
        self.text_edit.setHtml(self._full_content)
        
        # Search navigation state
        self._search_match_positions = []  # List of cursor positions for matches
        self._current_match_index = -1  # Current match index (-1 = no match selected)
        layout.addWidget(self.text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)  # Close button triggers accept
        layout.addWidget(button_box)
    
    def _get_guide_content(self) -> str:
        """
        Get the formatted HTML content for the guide.
        
        Colors adapt to the application theme for better contrast and consistency.
        Content is cached per theme to improve load time.
        
        Returns:
            HTML formatted string with guide content
        """
        # Get current theme
        theme = self.config_manager.get_theme()
        
        # Clear cache if colors have changed (for theme updates)
        # Return cached content if available
        if theme in QuickStartGuideDialog._content_cache:
            return QuickStartGuideDialog._content_cache[theme]
        
        # Generate content for this theme
        # Define colors based on theme
        if theme == "dark":
            # Dark theme: light text on dark grey background (matches metadata panel)
            bg_color = "#1e1e1e"
            h1_color = "#ffffff"
            h2_color = "#e0e0e0"
            text_color = "#ffffff"
            strong_color = "#4a9eff"  # Light blue for better visibility on dark
            code_bg = "#1e1e1e"  # Match HTML content background for code blocks
            code_text = "#ffffff"
        else:
            # Light theme: dark text on light background
            bg_color = "#ffffff"
            h1_color = "#000000"
            h2_color = "#1a1a1a"
            text_color = "#000000"
            strong_color = "#2980b9"  # Blue for emphasis
            code_bg = "#ecf0f1"  # Light grey for code blocks
            code_text = "#000000"
        
        content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; background-color: {bg_color}; color: {text_color}; }}
                h1 {{ color: {h1_color}; font-size: 18px; margin-top: 20px; margin-bottom: 10px; }}
                h2 {{ color: {h2_color}; font-size: 16px; margin-top: 15px; margin-bottom: 8px; }}
                p {{ margin: 8px 0; }}
                ul {{ margin: 8px 0; padding-left: 25px; }}
                li {{ margin: 4px 0; }}
                strong {{ color: {strong_color}; }}
                code {{ background-color: {code_bg}; color: {code_text}; padding: 2px 4px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>DICOM Viewer V3 - Quick Start Guide</h1>
            
            <h2>Table of Contents</h2>
            <ul>
                <li><a href="#controls-overview">Controls Overview</a></li>
                <li><a href="#navigation">Navigation</a></li>
                <li><a href="#cine-playback">Cine Playback</a></li>
                <li><a href="#zoom-pan">Zoom and Pan</a></li>
                <li><a href="#histogram">Histogram Display</a></li>
                <li><a href="#measurements">Measurements</a></li>
                <li><a href="#rois">ROIs (Regions of Interest)</a></li>
                <li><a href="#intensity-projections">Intensity Projections (Combine Slices)</a></li>
                <li><a href="#image-inversion">Image Inversion</a></li>
                <li><a href="#window-level">Window/Level Adjustment</a></li>
                <li><a href="#mouse-modes">Mouse Modes</a></li>
                <li><a href="#scroll-wheel-modes">Scroll Wheel Modes</a></li>
                <li><a href="#keyboard-shortcuts">Keyboard Shortcuts</a></li>
                <li><a href="#customization">Customization</a></li>
                <li><a href="#additional-tips">Additional Tips</a></li>
                <li><a href="#exporting">Exporting Images</a></li>
                <li><a href="#metadata-tags">Metadata and Tags</a></li>
            </ul>
            
            <h2 id="controls-overview">Controls Overview</h2>
            <p>The application provides several ways to interact with DICOM images:</p>
            <ul>
                <li><strong>Toolbar:</strong> Quick access to common functions (Open, Reset View, etc.)</li>
                <li><strong>Menu Bar:</strong> File operations, view options, tools, and help</li>
                <li><strong>Context Menu:</strong> Right-click on the image for quick access to modes and options</li>
                <li><strong>Keyboard Shortcuts:</strong> Arrow keys for navigation, Delete key for removing items</li>
            </ul>
            
            <h2 id="navigation">Navigation</h2>
            <h3>Slice Navigation</h3>
            <ul>
                <li><strong>Arrow Keys:</strong> <code>↑</code> (Up) for next slice, <code>↓</code> (Down) for previous slice</li>
                <li><strong>Scroll Wheel:</strong> When Scroll Wheel Mode is set to "Slice", scroll to navigate through slices</li>
            </ul>
            
            <h3>Series Navigation</h3>
            <ul>
                <li><strong>Arrow Keys:</strong> <code>←</code> (Left) for previous series, <code>→</code> (Right) for next series</li>
                <li><strong>Context Menu:</strong> Right-click and select "Prev Series" or "Next Series"</li>
            </ul>
            
            <h2 id="cine-playback">Cine Playback</h2>
            <p>For multi-frame DICOM series, use the cine controls widget to play through frames automatically:</p>
            <ul>
                <li><strong>Play:</strong> Start automatic playback through all frames</li>
                <li><strong>Pause:</strong> Pause playback at current frame</li>
                <li><strong>Stop:</strong> Stop playback and return to first frame</li>
                <li><strong>Loop:</strong> Toggle continuous looping (when enabled, playback restarts from first frame after reaching the end)</li>
                <li><strong>Speed:</strong> Adjust playback speed (0.25x, 0.5x, 1x, 2x, 4x)</li>
                <li><strong>Frame Slider:</strong> Drag to jump to a specific frame, or watch it move automatically during playback</li>
                <li><strong>Setting Cine Limits:</strong> Right-click on the frame slider/progress bar to set cine start/end limits (applies to both looping and non-looping playback)</li>
                <li><strong>Frame Position:</strong> Shows current frame number and total frames (e.g., "5 / 20")</li>
                <li><strong>FPS Display:</strong> Shows current frame rate during playback</li>
                <li><strong>Context Menu:</strong> Right-click on image → "Loop Cine" to toggle loop mode</li>
            </ul>
            <p><strong>Note:</strong> Cine controls are only available for multi-frame DICOM series. Manual slice navigation pauses playback automatically.</p>
            
            <h2 id="zoom-pan">Zoom and Pan</h2>
            <ul>
                <li><strong>Zoom:</strong> 
                    <ul>
                        <li>Scroll wheel (when Scroll Wheel Mode is set to "Zoom")</li>
                        <li>Zoom mode: Left-click and drag vertically to zoom in/out</li>
                        <li>Zooming is centered on the viewport center</li>
                    </ul>
                </li>
                <li><strong>Pan:</strong> 
                    <ul>
                        <li>Pan mode: Left-click and drag to move the image</li>
                        <li>Scrollbars: Use horizontal/vertical scrollbars when image is larger than viewport</li>
                    </ul>
                </li>
                <li><strong>Reset View:</strong> Press <code>V</code> key or right-click context menu → "Reset View (V)" to restore initial zoom and position for the focused subwindow</li>
                <li><strong>Reset All Views:</strong> Press <code>A</code> key or right-click context menu → "Reset All Views (A)" to reset zoom, pan, and window/level for all subwindows simultaneously</li>
            </ul>
            
            <h2 id="histogram">Histogram Display</h2>
            <p>View pixel value distribution for the currently focused image:</p>
            <ul>
                <li><strong>Open Histogram:</strong> Press <code>H</code> key to open the histogram dialog</li>
                <li><strong>Features:</strong>
                    <ul>
                        <li>Shows pixel value distribution as a histogram</li>
                        <li>Displays a red dashed box overlay indicating the current window center and width</li>
                        <li>Automatically tracks the focused subwindow and updates when:
                            <ul>
                                <li>Focus changes to a different subwindow</li>
                                <li>Slice changes in the focused subwindow</li>
                                <li>Window/level settings change</li>
                            </ul>
                        </li>
                        <li>Reflects whether raw or rescaled pixel values are being used</li>
                    </ul>
                </li>
                <li><strong>Scale Toggle:</strong> Use the "Linear Scale" / "Log Scale" button to switch between linear and logarithmic y-axis scaling</li>
                <li><strong>Window/Level Indicator:</strong> The red dashed box shows the current window center (box center) and window width (box width)</li>
            </ul>
            
            <h2 id="measurements">Measurements</h2>
            <h3>Creating Measurements</h3>
            <ul>
                <li>Set mouse mode to <strong>"Measure"</strong> (toolbar, context menu, or menu bar)</li>
                <li>Left-click to start a measurement</li>
                <li>Move mouse to see real-time distance</li>
                <li>Left-click again to finish the measurement</li>
                <li>Measurements show distance in pixels, mm, or cm based on DICOM pixel spacing</li>
            </ul>
            
            <h3>Selecting and Deleting Measurements</h3>
            <ul>
                <li>Set mouse mode to <strong>"Select"</strong></li>
                <li>Left-click on a measurement to select it (highlighted in yellow)</li>
                <li>Press <code>Delete</code> key to delete selected measurement</li>
                <li>Or right-click on measurement → "Delete measurement"</li>
                <li>Right-click on image → "Clear Measurements" to remove all measurements</li>
            </ul>
            
            <h2 id="rois">ROIs (Regions of Interest)</h2>
            <h3>Creating ROIs</h3>
            <ul>
                <li><strong>Ellipse ROI:</strong> Set mode to "Ellipse ROI", then left-click and drag to draw an ellipse</li>
                <li><strong>Rectangle ROI:</strong> Set mode to "Rectangle ROI", then left-click and drag to draw a rectangle</li>
                <li><strong>Window/Level ROI:</strong> Set mode to "Window/Level ROI", draw ROI to automatically adjust window/level based on ROI pixel values</li>
            </ul>
            
            <h3>Selecting and Deleting ROIs</h3>
            <ul>
                <li>Set mouse mode to <strong>"Select"</strong></li>
                <li>Left-click on an ROI to select it (highlighted in yellow)</li>
                <li>Press <code>Delete</code> key to delete selected ROI</li>
                <li>Or right-click on ROI → "Delete ROI"</li>
            </ul>
            
            <h2 id="intensity-projections">Intensity Projections (Combine Slices)</h2>
            <p>Combine multiple slices to create intensity projections:</p>
            <ul>
                <li><strong>Access:</strong> Use the "Combine Slices" widget in the right panel, or right-click on image → "Combine..."</li>
                <li><strong>Enable:</strong> Check "Enable Combine Slices" to activate projection mode</li>
                <li><strong>Projection Types:</strong>
                    <ul>
                        <li><strong>Average (AIP):</strong> Average intensity across combined slices</li>
                        <li><strong>Maximum (MIP):</strong> Maximum intensity across combined slices</li>
                        <li><strong>Minimum (MinIP):</strong> Minimum intensity across combined slices</li>
                    </ul>
                </li>
                <li><strong>Slice Count:</strong> Choose how many slices to combine (2, 3, 4, 6, or 8)</li>
                <li><strong>Scrolling:</strong> When projection mode is enabled, scrolling through slices shows projections that shift one slice at a time
                    <ul>
                        <li>Example: With 4 slices combined, slice 0 shows slices 0-3, slice 1 shows slices 1-4, slice 2 shows slices 2-5, etc.</li>
                    </ul>
                </li>
                <li><strong>Reset:</strong> Projection mode is automatically disabled when:
                    <ul>
                        <li>Opening new files or series</li>
                        <li>Selecting Reset View</li>
                        <li>Closing files</li>
                    </ul>
                </li>
            </ul>
            
            <h2 id="image-inversion">Image Inversion</h2>
            <ul>
                <li><strong>Toggle Inversion:</strong> Press <code>I</code> key or right-click → "Invert Image (I)"</li>
                <li>Inverts image colors (grayscale or RGB)</li>
                <li>Inversion state is preserved per series</li>
            </ul>
            
            <h2 id="window-level">Window/Level Adjustment</h2>
            <h3>Window/Level Presets</h3>
            <ul>
                <li>DICOM files may contain multiple window/level presets (WindowWidth and WindowCenter arrays)</li>
                <li>First preset (W1, C1) is loaded by default</li>
                <li>Right-click on image → <strong>"Window/Level Presets"</strong> submenu to switch between presets</li>
                <li>Status bar shows which preset is currently loaded (e.g., "Window/Level: Default" or "Window/Level: Preset 2")</li>
                <li>If no presets are found in DICOM tags, window center uses median pixel value and width uses range (max-min)</li>
            </ul>
            
            <h3>Right Mouse Drag Method</h3>
            <ul>
                <li>Right-click and hold on the image (not on ROI or measurement)</li>
                <li>Drag <strong>vertically</strong> to adjust window center (up = higher center, down = lower center)</li>
                <li>Drag <strong>horizontally</strong> to adjust window width (right = wider, left = narrower)</li>
                <li>Release right mouse button to finish adjustment</li>
                <li>If you don't drag (just click), the context menu will appear instead</li>
            </ul>
            
            <h3>Window/Level ROI Method</h3>
            <ul>
                <li>Set mouse mode to <strong>"Window/Level ROI"</strong></li>
                <li>Draw a rectangle ROI over the region of interest</li>
                <li>Window/level will automatically adjust based on pixel values within the ROI</li>
            </ul>
            
            <h3>Manual Adjustment</h3>
            <ul>
                <li>Use the Window/Level controls panel on the right side</li>
                <li>Adjust Center and Width sliders or enter values directly</li>
                <li>Toggle between Raw Pixel Values and Rescaled Values as needed</li>
            </ul>
            
            <h2 id="mouse-modes">Mouse Modes</h2>
            <p>Change mouse mode via toolbar, menu bar, or context menu:</p>
            <ul>
                <li><strong>Select:</strong> Click to select ROIs and measurements for deletion</li>
                <li><strong>Ellipse ROI:</strong> Draw elliptical regions of interest</li>
                <li><strong>Rectangle ROI:</strong> Draw rectangular regions of interest</li>
                <li><strong>Measure:</strong> Create distance measurements between two points</li>
                <li><strong>Zoom:</strong> Left-click and drag vertically to zoom in/out</li>
                <li><strong>Pan:</strong> Left-click and drag to move the image around</li>
                <li><strong>Window/Level ROI:</strong> Draw ROI to auto-adjust window/level</li>
            </ul>
            
            <h2 id="scroll-wheel-modes">Scroll Wheel Modes</h2>
            <p>Change via context menu → "Scroll Wheel Mode":</p>
            <ul>
                <li><strong>Slice:</strong> Scroll wheel navigates through slices (default)</li>
                <li><strong>Zoom:</strong> Scroll wheel zooms in/out on the image</li>
            </ul>
            
            <h2 id="keyboard-shortcuts">Keyboard Shortcuts</h2>
            <p>Quick access to modes and functions:</p>
            <ul>
                <li><strong><code>P</code>:</strong> Pan mode (move the image around)</li>
                <li><strong><code>Z</code>:</strong> Zoom mode (click and drag vertically to zoom)</li>
                <li><strong><code>R</code>:</strong> Rectangle ROI mode (draw rectangular regions of interest)</li>
                <li><strong><code>E</code>:</strong> Ellipse ROI mode (draw elliptical regions of interest)</li>
                <li><strong><code>M</code>:</strong> Measure mode (create distance measurements)</li>
                <li><strong><code>S</code>:</strong> Select mode (select ROIs and measurements)</li>
                <li><strong><code>W</code>:</strong> Window/Level ROI mode (auto-adjust from ROI)</li>
                <li><strong><code>C</code>:</strong> Clear all measurements on current slice</li>
                <li><strong><code>D</code>:</strong> Delete all ROIs on current slice</li>
                <li><strong><code>V</code>:</strong> Reset view (restore initial zoom, pan, and window/level for focused subwindow)</li>
                <li><strong><code>A</code>:</strong> Reset all views (reset zoom, pan, and window/level for all subwindows)</li>
                <li><strong><code>H</code>:</strong> Open histogram dialog (shows pixel value distribution with window/level overlay)</li>
                <li><strong><code>N</code>:</strong> Toggle series navigator bar visibility</li>
                <li><strong><code>I</code>:</strong> Invert image colors</li>
                <li><strong><code>Spacebar</code>:</strong> Toggle overlay visibility
                    <ul>
                        <li>First press: Hides corner text overlays</li>
                        <li>Second press: Hides all text including measurements and annotations</li>
                        <li>Third press: Shows everything again</li>
                    </ul>
                </li>
                <li><strong><code>↑</code> / <code>↓</code>:</strong> Navigate slices (Up = next, Down = previous)</li>
                <li><strong><code>←</code> / <code>→</code>:</strong> Navigate series (Left = previous, Right = next)</li>
                <li><strong><code>Delete</code>:</strong> Delete selected ROI or measurement</li>
                <li><strong><code>Ctrl+T</code>:</strong> View/Edit DICOM Tags</li>
                <li><strong><code>Shift+Ctrl+T</code>:</strong> Export DICOM Tags</li>
            </ul>
            
            <h2 id="customization">Customization</h2>
            <h3>ROI and Measurement Appearance</h3>
            <p>Customize the appearance of ROIs and measurements via <strong>View → Annotation Options</strong>:</p>
            <ul>
                <li><strong>ROI Settings:</strong> Adjust font size, font color, line thickness, and line color for ROI statistics overlays</li>
                <li><strong>Measurement Settings:</strong> Adjust font size, font color, line thickness, and line color for measurement lines and text</li>
                <li>Changes apply immediately to all existing and new ROIs/measurements</li>
                <li>Your preferences are saved and remembered between sessions</li>
            </ul>
            
            <h2 id="additional-tips">Additional Tips</h2>
            <ul>
                <li>All measurements and ROIs are preserved when navigating between slices in the same series</li>
                <li>Use the context menu (right-click) for quick access to common functions</li>
                <li>The status bar shows current slice information, window/level preset name, and loading progress</li>
                <li>Status bar updates in real-time during file loading, showing number of studies, series, and files loaded</li>
                <li>Overlay metadata can be customized and toggled on/off via View → Overlay Configuration or with the <code>Spacebar</code> key</li>
                <li>Export selected DICOM tags to Excel or CSV via Tools → Export Tags</li>
                <li>Settings can be adjusted via Tools → Settings</li>
                <li><strong>Annotations:</strong> The viewer automatically displays DICOM annotations including Presentation States, Key Object Selection Documents, and embedded overlays/graphic annotations</li>
            </ul>
            
            <h2 id="exporting">Exporting Images</h2>
            <p>Export DICOM images to common formats:</p>
            <ul>
                <li>Access via <strong>File → Export</strong> menu</li>
                <li><strong>Export Formats:</strong>
                    <ul>
                        <li><strong>PNG:</strong> High-quality image format with transparency support</li>
                        <li><strong>JPEG:</strong> Compressed image format</li>
                        <li><strong>DICOM:</strong> Original DICOM format (preserves all metadata)</li>
                    </ul>
                </li>
                <li><strong>Selection:</strong> Use hierarchical checkboxes to select:
                    <ul>
                        <li>Entire studies</li>
                        <li>Individual series within studies</li>
                        <li>Specific slices/instances within series</li>
                    </ul>
                </li>
                <li><strong>Options for PNG/JPEG:</strong>
                    <ul>
                        <li>Window/Level: Use current viewer settings or dataset default</li>
                        <li>Include overlays and ROIs: Export with metadata text, ROIs, and measurements visible</li>
                        <li>Export at displayed resolution: Apply current zoom level for high-resolution output</li>
                    </ul>
                </li>
            <li>Exported files are organized in folders: <code>Patient ID / Study Date - Study Description / Series Number - Series Description</code></li>
            <li>The application remembers your last export directory</li>
        </ul>
        
        <h2 id="metadata-tags">Metadata and Tags</h2>
        <p>View and edit DICOM metadata tags, including private tags:</p>
        <ul>
            <li><strong>View/Edit Tags:</strong> Access via <strong>Tools → View/Edit DICOM Tags</strong> or press <code>Ctrl+T</code>
                <ul>
                    <li>Browse all DICOM tags in a tree view organized by groups</li>
                    <li>Edit individual tag values (double-click or use Edit button)</li>
                    <li>View private tags and vendor-specific data</li>
                    <li>Undo/redo changes using Edit menu</li>
                    <li><strong>Tag Filtering:</strong> Use the search box at the top to filter tags (case-insensitive search across tag number, name, VR, and value)</li>
                    <li>Search results update automatically as you type</li>
                    <li><strong>Copy Tag Information:</strong> Right-click on any tag item to access context menu with copy options:
                        <ul>
                            <li><strong>Copy Tag:</strong> Copy the tag number (e.g., "(0008,0010)")</li>
                            <li><strong>Copy Name:</strong> Copy the tag name (e.g., "Study Description")</li>
                            <li><strong>Copy VR:</strong> Copy the Value Representation (e.g., "LO")</li>
                            <li><strong>Copy Value:</strong> Copy the tag value</li>
                            <li><strong>Copy All:</strong> Copy all fields (Tag, Name, VR, Value) as tab-separated text</li>
                        </ul>
                    </li>
                    <li>You can also use <code>Ctrl+C</code> to copy the current column or all fields if no column is selected</li>
                </ul>
            </li>
            <li><strong>Metadata Panel (Left Side):</strong> Quick access to DICOM tags without opening the full tag viewer
                <ul>
                    <li><strong>Expand/Collapse Groups:</strong> Double-click on group headers (e.g., "Group 0008") to expand or collapse tag groups</li>
                    <li><strong>Context Menu:</strong> Right-click on a group header or tag item → "Expand" or "Collapse" to toggle group visibility</li>
                    <li><strong>Reorder Columns:</strong> Drag column headers horizontally to reorder columns (Tag, Name, VR, Value)</li>
                    <li>Column order preferences are saved and remembered between sessions</li>
                    <li><strong>Resize Columns:</strong> Drag column borders to adjust column widths (preferences are saved)</li>
                </ul>
            </li>
            <li><strong>Export Tags:</strong> Access via <strong>Tools → Export DICOM Tags</strong> or press <code>Shift+Ctrl+T</code>
                <ul>
                    <li>Export selected tags to Excel (.xlsx) or CSV format</li>
                    <li>Choose which tags to export</li>
                    <li>Export tags from multiple slices or entire series</li>
                </ul>
            </li>
            <li><strong>Tag Changes:</strong> Tag edits are preserved in memory and can be exported when exporting to DICOM format</li>
            <li><strong>Privacy View:</strong> Toggle privacy mode to mask patient-related DICOM tags
                <ul>
                    <li>Access via <strong>View → Privacy View</strong> menu, right-click context menu → "Privacy View (Cmd+P)", or press <code>Cmd+P</code> (Mac) / <code>Ctrl+P</code> (Windows/Linux)</li>
                    <li>When enabled, patient-related tags (Patient Name, Patient ID, Patient Date of Birth, etc.) are displayed as "PRIVACY MODE" in:
                        <ul>
                            <li>Metadata panel (left side)</li>
                            <li>Tag viewer dialog</li>
                            <li>Image overlays</li>
                        </ul>
                    </li>
                    <li>Privacy view only affects display - the underlying DICOM data remains unchanged</li>
                    <li>Privacy view state persists across application restarts</li>
                </ul>
            </li>
        </ul>
        </body>
        </html>
        """
        
        # Cache the content for this theme
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
