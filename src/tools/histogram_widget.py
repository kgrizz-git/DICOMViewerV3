"""
Histogram Widget

This module provides histogram display for whole slices or selected ROIs,
with window width and level indicators overlaid.

Inputs:
    - Pixel array data
    - Optional ROI mask
    - Window/level values
    
Outputs:
    - Histogram plot with window/level indicators
    
Requirements:
    - PySide6 for widget
    - matplotlib for plotting
    - numpy for calculations
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from typing import Optional
import numpy as np


class HistogramWidget(QWidget):
    """
    Widget for displaying image histograms.
    
    Features:
    - Display histogram for whole slice or ROI
    - Show window/level indicators
    - Update dynamically
    """
    
    def __init__(self, parent=None):
        """
        Initialize the histogram widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._create_ui()
        self.pixel_array: Optional[np.ndarray] = None
        self.roi_mask: Optional[np.ndarray] = None
        self.window_center: Optional[float] = None
        self.window_width: Optional[float] = None
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title_label = QLabel("Histogram")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        self.axes = self.figure.add_subplot(111)
        self.axes.set_xlabel("Pixel Value")
        self.axes.set_ylabel("Frequency")
        self.axes.grid(True, alpha=0.3)
    
    def set_pixel_array(self, pixel_array: np.ndarray) -> None:
        """
        Set the pixel array for histogram calculation.
        
        Args:
            pixel_array: Image pixel array
        """
        self.pixel_array = pixel_array
        self._update_histogram()
    
    def set_roi_mask(self, roi_mask: Optional[np.ndarray]) -> None:
        """
        Set ROI mask for histogram calculation.
        
        Args:
            roi_mask: Optional binary mask for ROI
        """
        self.roi_mask = roi_mask
        self._update_histogram()
    
    def set_window_level(self, center: Optional[float], width: Optional[float]) -> None:
        """
        Set window center and width for indicators.
        
        Args:
            center: Window center value
            width: Window width value
        """
        self.window_center = center
        self.window_width = width
        self._update_histogram()
    
    def _update_histogram(self) -> None:
        """Update the histogram display."""
        if self.pixel_array is None:
            return
        
        # Get pixels for histogram
        if self.roi_mask is not None:
            pixels = self.pixel_array[self.roi_mask]
        else:
            pixels = self.pixel_array.flatten()
        
        if len(pixels) == 0:
            return
        
        # Clear axes
        self.axes.clear()
        
        # Calculate histogram
        hist, bins = np.histogram(pixels, bins=256)
        bin_centers = (bins[:-1] + bins[1:]) / 2.0
        
        # Plot histogram
        self.axes.plot(bin_centers, hist, 'b-', linewidth=1.5, label='Histogram')
        self.axes.fill_between(bin_centers, 0, hist, alpha=0.3)
        
        # Add window/level indicators
        if self.window_center is not None and self.window_width is not None:
            window_min = self.window_center - self.window_width / 2.0
            window_max = self.window_center + self.window_width / 2.0
            
            # Vertical line for window center
            self.axes.axvline(self.window_center, color='r', linestyle='--', 
                            linewidth=2, label='Window Center')
            
            # Shaded region for window width
            self.axes.axvspan(window_min, window_max, alpha=0.2, color='red', 
                            label='Window Width')
        
        self.axes.set_xlabel("Pixel Value")
        self.axes.set_ylabel("Frequency")
        self.axes.legend(loc='upper right')
        self.axes.grid(True, alpha=0.3)
        
        # Refresh canvas
        self.canvas.draw()

