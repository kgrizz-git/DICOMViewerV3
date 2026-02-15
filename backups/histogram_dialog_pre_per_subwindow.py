"""
Histogram Dialog

This module provides a dialog for displaying pixel value histograms
with window/level box overlay.

Inputs:
    - Current dataset
    - Current slice index
    - Window center and width
    - Use rescaled values flag
    
Outputs:
    - Histogram display with window/level overlay
    
Requirements:
    - PySide6 for dialog
    - HistogramWidget for display
    - DICOMProcessor for pixel array extraction
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
from typing import Optional, Callable
from pydicom.dataset import Dataset
from tools.histogram_widget import HistogramWidget
from core.dicom_processor import DICOMProcessor
from core.multiframe_handler import get_frame_pixel_array, is_multiframe
import numpy as np


class HistogramDialog(QDialog):
    """
    Dialog for displaying pixel value histograms.
    
    Features:
    - Shows histogram of current image
    - Overlays window/level box
    - Reflects rescaled vs raw pixel values
    """
    
    def __init__(
        self,
        parent=None,
        get_current_dataset: Optional[Callable[[], Optional[Dataset]]] = None,
        get_current_slice_index: Optional[Callable[[], int]] = None,
        get_window_center: Optional[Callable[[], Optional[float]]] = None,
        get_window_width: Optional[Callable[[], Optional[float]]] = None,
        get_use_rescaled: Optional[Callable[[], bool]] = None,
        get_rescale_params: Optional[Callable[[], tuple]] = None
    ):
        """
        Initialize the histogram dialog.
        
        Args:
            parent: Parent widget
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
            get_window_center: Callback to get current window center
            get_window_width: Callback to get current window width
            get_use_rescaled: Callback to get use_rescaled_values flag
            get_rescale_params: Callback to get (slope, intercept, type) tuple
        """
        super().__init__(parent)
        
        self.setWindowTitle("Pixel Value Histogram")
        self.setModal(False)  # Non-modal so it can stay open
        self.resize(600, 500)
        
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.get_window_center = get_window_center
        self.get_window_width = get_window_width
        self.get_use_rescaled = get_use_rescaled
        self.get_rescale_params = get_rescale_params
        self.use_log_scale = False
        
        self._create_ui()
        self.update_histogram()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Info label
        info_layout = QHBoxLayout()
        self.info_label = QLabel("Histogram of current image pixel values")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # Histogram widget
        self.histogram_widget = HistogramWidget(self)
        layout.addWidget(self.histogram_widget)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Value type indicator
        self.value_type_label = QLabel("")
        self.value_type_label.setStyleSheet("font-style: italic; color: gray;")
        controls_layout.addWidget(self.value_type_label)
        
        controls_layout.addStretch()
        
        # Log scale toggle button
        self.log_scale_button = QPushButton("Linear Scale")
        self.log_scale_button.setCheckable(True)
        self.log_scale_button.setChecked(False)
        self.log_scale_button.clicked.connect(self._on_log_scale_toggled)
        controls_layout.addWidget(self.log_scale_button)
        
        layout.addLayout(controls_layout)
    
    def update_histogram(self) -> None:
        """Update the histogram with current image data."""
        if not self.get_current_dataset:
            return
        
        dataset = self.get_current_dataset()
        if dataset is None:
            self.histogram_widget.set_pixel_array(None)
            self.info_label.setText("No image loaded")
            self.value_type_label.setText("")
            return
        
        # Get current slice index
        slice_index = 0
        if self.get_current_slice_index:
            slice_index = self.get_current_slice_index()
        
        # Get pixel array for current frame/slice
        pixel_array = None
        if is_multiframe(dataset):
            pixel_array = get_frame_pixel_array(dataset, slice_index)
        else:
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            # For single-frame, pixel_array might be 2D (height, width) or 3D (frames, height, width)
            if pixel_array is not None and len(pixel_array.shape) == 3:
                # Multi-frame but not detected as such, use first frame
                if slice_index < pixel_array.shape[0]:
                    pixel_array = pixel_array[slice_index]
                else:
                    pixel_array = pixel_array[0]
        
        if pixel_array is None:
            self.histogram_widget.set_pixel_array(None)
            self.info_label.setText("Failed to load pixel data")
            self.value_type_label.setText("")
            return
        
        # Apply rescale if needed
        use_rescaled = False
        if self.get_use_rescaled:
            use_rescaled = self.get_use_rescaled()
        
        if use_rescaled:
            # Get rescale parameters
            rescale_slope = 1.0
            rescale_intercept = 0.0
            if self.get_rescale_params:
                slope, intercept, _ = self.get_rescale_params()
                if slope is not None:
                    rescale_slope = slope
                if intercept is not None:
                    rescale_intercept = intercept
            
            # Apply rescale transformation
            pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
            value_type_text = "Showing rescaled pixel values"
        else:
            value_type_text = "Showing raw pixel values"
        
        # Update histogram widget
        self.histogram_widget.set_pixel_array(pixel_array)
        
        # Get window/level values
        window_center = None
        window_width = None
        if self.get_window_center:
            window_center = self.get_window_center()
        if self.get_window_width:
            window_width = self.get_window_width()
        
        self.histogram_widget.set_window_level(window_center, window_width)
        
        # Update info label
        self.info_label.setText(f"Histogram of current image (Slice {slice_index + 1})")
        self.value_type_label.setText(value_type_text)
    
    def _on_log_scale_toggled(self, checked: bool) -> None:
        """Handle log scale toggle."""
        self.use_log_scale = checked
        self.log_scale_button.setText("Log Scale" if checked else "Linear Scale")
        self.histogram_widget.set_log_scale(checked)
    
    def showEvent(self, event) -> None:
        """Handle show event to update histogram when dialog is shown."""
        super().showEvent(event)
        self.update_histogram()

