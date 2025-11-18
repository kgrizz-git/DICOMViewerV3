"""
Zoom Display Widget

This module provides a widget for displaying and controlling the current zoom level in the right panel.

Inputs:
    - Zoom level value from ImageViewer
    - User input via slider
    
Outputs:
    - Visual zoom level display
    - Zoom control signal
    
Requirements:
    - PySide6 for GUI components
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QDoubleSpinBox, QSlider, QSizePolicy)
from PySide6.QtCore import Qt, Signal


class ZoomDisplayWidget(QWidget):
    """
    Widget for displaying and controlling current zoom level.
    
    Features:
    - Displays zoom level as "X.XX"
    - Slider for controlling zoom
    - Styled to match right panel theme (window/level controls)
    - Always visible
    """
    
    # Signals
    zoom_changed = Signal(float)  # Emitted when zoom is changed via slider (zoom_value)
    
    def __init__(self, parent=None):
        """
        Initialize the zoom display widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.current_zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Row 1: Label and Spinbox (horizontal)
        zoom_row1 = QHBoxLayout()
        self.zoom_label = QLabel("Zoom:")
        self.zoom_label.setMinimumWidth(100)
        zoom_row1.addWidget(self.zoom_label)
        
        self.zoom_spinbox = QDoubleSpinBox()
        self.zoom_spinbox.setRange(self.min_zoom, self.max_zoom)
        self.zoom_spinbox.setValue(1.0)
        self.zoom_spinbox.setDecimals(2)
        self.zoom_spinbox.setSingleStep(0.01)  # Step size for up/down buttons (0.01 increments)
        # Allow editing so up/down buttons work - slider and spinbox both control zoom
        self.zoom_spinbox.valueChanged.connect(self._on_value_changed)
        zoom_row1.addWidget(self.zoom_spinbox)
        zoom_row1.addStretch()  # Push label and spinbox to the left
        layout.addLayout(zoom_row1)
        
        # Row 2: Slider (full width, below)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(0, 1000)
        self.zoom_slider.setValue(500)  # Default to zoom 1.0 (middle of range)
        # Use Expanding size policy to fill available width
        self.zoom_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.zoom_slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.zoom_slider)
    
    def _on_slider_changed(self, value: int) -> None:
        """
        Handle slider value change.
        
        Args:
            value: Slider value (0-1000)
        """
        # Convert slider value (0-1000) to zoom value (min_zoom to max_zoom)
        # Use logarithmic scale for better control (zoom is typically used logarithmically)
        # Linear mapping for simplicity
        zoom_range = self.max_zoom - self.min_zoom
        zoom_value = self.min_zoom + (value / 1000.0) * zoom_range
        
        # Clamp to range
        zoom_value = max(self.min_zoom, min(self.max_zoom, zoom_value))
        
        # Update spinbox (block signals to prevent recursive update)
        self.zoom_spinbox.blockSignals(True)
        self.zoom_spinbox.setValue(zoom_value)
        self.zoom_spinbox.blockSignals(False)
        
        # Update current zoom
        self.current_zoom = zoom_value
        
        # Emit signal to update image viewer
        self.zoom_changed.emit(zoom_value)
    
    def _on_value_changed(self, value: float) -> None:
        """
        Handle spinbox value change (from up/down buttons or direct editing).
        
        Args:
            value: New zoom value
        """
        # Clamp to range
        zoom_value = max(self.min_zoom, min(self.max_zoom, value))
        
        # Update current zoom
        self.current_zoom = zoom_value
        
        # Update slider (block signals to prevent recursive update)
        self.zoom_slider.blockSignals(True)
        # Convert zoom value to slider value (0-1000)
        zoom_range = self.max_zoom - self.min_zoom
        if zoom_range > 0:
            slider_value = int(((zoom_value - self.min_zoom) / zoom_range) * 1000)
            slider_value = max(0, min(1000, slider_value))
        else:
            slider_value = 500
        self.zoom_slider.setValue(slider_value)
        self.zoom_slider.blockSignals(False)
        
        # Emit signal to update image viewer
        self.zoom_changed.emit(zoom_value)
    
    def update_zoom(self, zoom_value: float) -> None:
        """
        Update the zoom display from external source (e.g., ImageViewer).
        
        Blocks signals to prevent circular updates.
        
        Args:
            zoom_value: Current zoom level
        """
        self.current_zoom = zoom_value
        
        # Update spinbox (block signals to prevent recursive update)
        self.zoom_spinbox.blockSignals(True)
        self.zoom_spinbox.setValue(zoom_value)
        self.zoom_spinbox.blockSignals(False)
        
        # Update slider (block signals to prevent recursive update)
        self.zoom_slider.blockSignals(True)
        # Convert zoom value to slider value (0-1000)
        zoom_range = self.max_zoom - self.min_zoom
        if zoom_range > 0:
            slider_value = int(((zoom_value - self.min_zoom) / zoom_range) * 1000)
            slider_value = max(0, min(1000, slider_value))
        else:
            slider_value = 500
        self.zoom_slider.setValue(slider_value)
        self.zoom_slider.blockSignals(False)

