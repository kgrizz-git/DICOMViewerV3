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
from core.multiframe_handler import get_frame_pixel_array, is_multiframe, get_frame_count
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
        get_rescale_params: Optional[Callable[[], tuple]] = None,
        get_series_study_uid: Optional[Callable[[], Optional[str]]] = None,
        get_series_uid: Optional[Callable[[], Optional[str]]] = None,
        get_series_datasets: Optional[Callable[[], Optional[list]]] = None,
        get_all_studies: Optional[Callable[[], Optional[dict]]] = None,
        title_suffix: str = ""
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
            title_suffix: Optional suffix for window title (e.g. " (View 1)")
        """
        super().__init__(parent)
        
        base_title = "Pixel Value Histogram"
        self.setWindowTitle(base_title + title_suffix if title_suffix else base_title)
        self.setModal(False)  # Non-modal so it can stay open
        # Ensure the dialog is large enough to show the full histogram and labels
        self.resize(800, 600)
        self.setMinimumSize(700, 500)
        
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.get_window_center = get_window_center
        self.get_window_width = get_window_width
        self.get_use_rescaled = get_use_rescaled
        self.get_rescale_params = get_rescale_params
        self.get_series_study_uid = get_series_study_uid
        self.get_series_uid = get_series_uid
        self.get_series_datasets = get_series_datasets
        self.get_all_studies = get_all_studies
        self.use_log_scale = False
        self.series_global_frequency_max: Optional[float] = None
        self.series_global_x_min: Optional[float] = None
        self.series_global_x_max: Optional[float] = None
        self.series_identity: Optional[tuple] = None
        
        self._create_ui()
        self.update_histogram()
    
    def _compute_series_global_frequency_max(self, use_rescaled: bool) -> None:
        """
        Compute the maximum histogram frequency and global pixel range across
        all slices/frames in the current series. This is used to keep both the
        y-axis (frequency) and x-axis (pixel value) scales stable while browsing
        the series.
        """
        self.series_global_frequency_max = None
        self.series_global_x_min = None
        self.series_global_x_max = None

        # Resolve datasets for the current series
        datasets = None
        if self.get_series_datasets is not None:
            datasets = self.get_series_datasets() or None

        if (not datasets) and self.get_all_studies and self.get_series_study_uid and self.get_series_uid:
            studies = self.get_all_studies() or {}
            study_uid = self.get_series_study_uid()
            series_uid = self.get_series_uid()
            if study_uid and series_uid:
                series_dict = studies.get(study_uid, {})
                datasets = series_dict.get(series_uid)

        if not datasets:
            return

        # Prepare optional rescale parameters (assumed consistent within a series)
        rescale_slope = 1.0
        rescale_intercept = 0.0
        if use_rescaled and self.get_rescale_params:
            try:
                slope, intercept, _ = self.get_rescale_params()
                if slope is not None:
                    rescale_slope = float(slope)
                if intercept is not None:
                    rescale_intercept = float(intercept)
            except Exception:
                pass

        max_freq = 0.0
        global_x_min = None
        global_x_max = None

        for dataset in datasets:
            if dataset is None:
                continue
            try:
                if is_multiframe(dataset):
                    # Iterate over all frames in this dataset
                    num_frames = get_frame_count(dataset)
                    for frame_index in range(max(0, num_frames)):
                        frame_array = get_frame_pixel_array(dataset, frame_index)
                        if frame_array is None:
                            continue
                        pixels = frame_array.astype(np.float32)
                        if use_rescaled:
                            pixels = pixels * rescale_slope + rescale_intercept
                        if pixels.size == 0:
                            continue
                        hist, _ = np.histogram(pixels.flatten(), bins=256)
                        if hist.size > 0:
                            max_freq = max(max_freq, float(hist.max()))
                        # Track global pixel value range
                        frame_min = float(pixels.min())
                        frame_max = float(pixels.max())
                        global_x_min = frame_min if global_x_min is None else min(global_x_min, frame_min)
                        global_x_max = frame_max if global_x_max is None else max(global_x_max, frame_max)
                else:
                    pixel_array = DICOMProcessor.get_pixel_array(dataset)
                    if pixel_array is None:
                        continue
                    # Handle 2D or 3D arrays (frames, height, width)
                    if pixel_array.ndim == 3:
                        frames = pixel_array
                    else:
                        frames = [pixel_array]
                    for frame_array in frames:
                        pixels = frame_array.astype(np.float32)
                        if use_rescaled:
                            pixels = pixels * rescale_slope + rescale_intercept
                        if pixels.size == 0:
                            continue
                        hist, _ = np.histogram(pixels.flatten(), bins=256)
                        if hist.size > 0:
                            max_freq = max(max_freq, float(hist.max()))
                        # Track global pixel value range
                        frame_min = float(pixels.min())
                        frame_max = float(pixels.max())
                        global_x_min = frame_min if global_x_min is None else min(global_x_min, frame_min)
                        global_x_max = frame_max if global_x_max is None else max(global_x_max, frame_max)
            except Exception:
                # On any error, skip problematic dataset but continue with others
                continue

        if max_freq > 0:
            self.series_global_frequency_max = max_freq
        if global_x_min is not None and global_x_max is not None and global_x_max > global_x_min:
            self.series_global_x_min = global_x_min
            self.series_global_x_max = global_x_max
    
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
        
        # Log scale toggle button (label shows the target mode when clicked)
        self.log_scale_button = QPushButton("Log Scale")
        # Use a simple push button (non-checkable) to avoid highlight/checked state styling
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
        
        # Update series-wide global frequency max and pixel range (for stable axes) and apply to widget
        series_study_uid = self.get_series_study_uid() if self.get_series_study_uid else None
        series_uid = self.get_series_uid() if self.get_series_uid else None
        series_identity = (series_study_uid, series_uid, bool(use_rescaled))
        if series_identity != self.series_identity:
            self._compute_series_global_frequency_max(use_rescaled)
            self.series_identity = series_identity

        self.histogram_widget.set_global_frequency_max(self.series_global_frequency_max)
        self.histogram_widget.set_global_pixel_range(self.series_global_x_min, self.series_global_x_max)

        # Update histogram widget with current slice data
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
    
    def _on_log_scale_toggled(self, checked: bool = False) -> None:
        """Handle log scale toggle.

        Button text shows the mode that will be activated when clicked next,
        not the mode that is currently active.
        """
        # Toggle internal state explicitly rather than relying on button check state
        self.use_log_scale = not self.use_log_scale
        # When in log mode, next click will switch to linear, so label "Linear Scale"
        # When in linear mode, next click will switch to log, so label "Log Scale"
        self.log_scale_button.setText("Linear Scale" if self.use_log_scale else "Log Scale")
        self.histogram_widget.set_log_scale(self.use_log_scale)
    
    def showEvent(self, event) -> None:
        """Handle show event to update histogram when dialog is shown."""
        super().showEvent(event)
        self.update_histogram()

