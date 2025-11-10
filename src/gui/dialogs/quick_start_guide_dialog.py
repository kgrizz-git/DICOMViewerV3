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

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox)
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
        
        # Text edit for guide content
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(self._get_guide_content())
        layout.addWidget(text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)  # Close button triggers accept
        layout.addWidget(button_box)
    
    def _get_guide_content(self) -> str:
        """
        Get the formatted HTML content for the guide.
        
        Colors adapt to the application theme for better contrast and consistency.
        
        Returns:
            HTML formatted string with guide content
        """
        # Get current theme
        theme = self.config_manager.get_theme()
        
        # Define colors based on theme
        if theme == "dark":
            # Dark theme: light text on dark background
            bg_color = "#2b2b2b"
            h1_color = "#ffffff"
            h2_color = "#e0e0e0"
            text_color = "#ffffff"
            strong_color = "#4a9eff"  # Light blue for better visibility on dark
            code_bg = "#3c3c3c"  # Darker grey for code blocks
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
        
        return f"""
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
            
            <h2>Controls Overview</h2>
            <p>The application provides several ways to interact with DICOM images:</p>
            <ul>
                <li><strong>Toolbar:</strong> Quick access to common functions (Open, Reset View, etc.)</li>
                <li><strong>Menu Bar:</strong> File operations, view options, tools, and help</li>
                <li><strong>Context Menu:</strong> Right-click on the image for quick access to modes and options</li>
                <li><strong>Keyboard Shortcuts:</strong> Arrow keys for navigation, Delete key for removing items</li>
            </ul>
            
            <h2>Navigation</h2>
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
            
            <h2>Zoom and Pan</h2>
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
                <li><strong>Reset View:</strong> Press <code>V</code> key or right-click context menu → "Reset View (V)" to restore initial zoom and position</li>
            </ul>
            
            <h2>Measurements</h2>
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
            
            <h2>ROIs (Regions of Interest)</h2>
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
            
            <h2>Window/Level Adjustment</h2>
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
            
            <h2>Mouse Modes</h2>
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
            
            <h2>Scroll Wheel Modes</h2>
            <p>Change via context menu → "Scroll Wheel Mode":</p>
            <ul>
                <li><strong>Slice:</strong> Scroll wheel navigates through slices (default)</li>
                <li><strong>Zoom:</strong> Scroll wheel zooms in/out on the image</li>
            </ul>
            
            <h2>Keyboard Shortcuts</h2>
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
                <li><strong><code>V</code>:</strong> Reset view (restore initial zoom, pan, and window/level)</li>
                <li><strong><code>N</code>:</strong> Toggle series navigator bar visibility</li>
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
            </ul>
            
            <h2>Additional Tips</h2>
            <ul>
                <li>All measurements and ROIs are preserved when navigating between slices in the same series</li>
                <li>Use the context menu (right-click) for quick access to common functions</li>
                <li>The status bar shows current slice information and other details</li>
                <li>Overlay metadata can be customized and toggled on/off via View → Overlay Configuration or with the <code>Spacebar</code> key</li>
                <li>Export selected DICOM tags to Excel or CSV via Tools → Export Tags</li>
                <li>Settings can be adjusted via Tools → Settings</li>
            </ul>
            
            <h2>Exporting Images</h2>
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
        </body>
        </html>
        """
