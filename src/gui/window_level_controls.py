"""
Window/Level Controls

This module provides controls for adjusting window width and level
with numerical input and mouse controls.

Inputs:
    - Window center and width values
    - User input (sliders, spinboxes, mouse)
    
Outputs:
    - Updated window/level values
    - Signals for value changes
    
Requirements:
    - PySide6 for GUI controls
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QDoubleSpinBox, QSlider, QPushButton, QSizePolicy)
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt, Signal
from typing import Optional


class WindowLevelControls(QWidget):
    """
    Widget for controlling window width and level.
    
    Provides:
    - Numerical input (spinboxes)
    - Slider controls
    - Mouse adjustment capability (via signals)
    """
    
    # Signals
    window_changed = Signal(float, float)  # (center, width)
    
    def __init__(self, parent=None):
        """
        Initialize window/level controls.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.window_center = 0.0
        self.window_width = 0.0
        self.center_range = (-10000.0, 10000.0)
        self.width_range = (1.0, 10000.0)
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Window Center
        center_layout = QVBoxLayout()
        
        # Row 1: Label and Spinbox (horizontal)
        center_row1 = QHBoxLayout()
        center_label = QLabel("Window Center:")
        center_label.setMinimumWidth(100)
        center_row1.addWidget(center_label)
        
        self.center_spinbox = QDoubleSpinBox()
        self.center_spinbox.setRange(*self.center_range)
        self.center_spinbox.setValue(0.0)
        self.center_spinbox.setDecimals(1)
        self.center_spinbox.setSingleStep(1.0)  # Step size for up/down buttons
        self.center_spinbox.valueChanged.connect(self._on_center_changed)
        center_row1.addWidget(self.center_spinbox)
        center_row1.addStretch()  # Push label and spinbox to the left
        center_layout.addLayout(center_row1)
        
        # Row 2: Slider (full width, below)
        self.center_slider = QSlider(Qt.Orientation.Horizontal)
        self.center_slider.setRange(0, 1000)
        self.center_slider.setValue(500)
        # Use Expanding size policy to fill available width
        self.center_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.center_slider.valueChanged.connect(self._on_center_slider_changed)
        center_layout.addWidget(self.center_slider)
        
        layout.addLayout(center_layout)
        
        # Window Width
        width_layout = QVBoxLayout()
        
        # Row 1: Label and Spinbox (horizontal)
        width_row1 = QHBoxLayout()
        width_label = QLabel("Window Width:")
        width_label.setMinimumWidth(100)
        width_row1.addWidget(width_label)
        
        self.width_spinbox = QDoubleSpinBox()
        self.width_spinbox.setRange(*self.width_range)
        self.width_spinbox.setValue(100.0)
        self.width_spinbox.setDecimals(1)
        self.width_spinbox.setSingleStep(1.0)  # Step size for up/down buttons
        self.width_spinbox.valueChanged.connect(self._on_width_changed)
        width_row1.addWidget(self.width_spinbox)
        width_row1.addStretch()  # Push label and spinbox to the left
        width_layout.addLayout(width_row1)
        
        # Row 2: Slider (full width, below)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 1000)
        self.width_slider.setValue(100)
        # Use Expanding size policy to fill available width
        self.width_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.width_slider.valueChanged.connect(self._on_width_slider_changed)
        width_layout.addWidget(self.width_slider)
        
        layout.addLayout(width_layout)
    
    def set_ranges(self, center_range: tuple, width_range: tuple) -> None:
        """
        Set the value ranges for window center and width.
        
        Args:
            center_range: (min, max) for window center
            width_range: (min, max) for window width
        """
        self.center_range = center_range
        self.width_range = width_range
        
        self.center_spinbox.setRange(*center_range)
        self.width_spinbox.setRange(*width_range)
        
        # Update slider ranges (normalized to 0-1000)
        self._update_slider_ranges()
    
    def _update_slider_ranges(self) -> None:
        """Update slider ranges based on current value ranges."""
        # Sliders are normalized to 0-1000
        # We'll map the actual ranges to slider positions
        pass  # Implementation can be added if needed
    
    def set_window_level(self, center: float, width: float, block_signals: bool = False) -> None:
        """
        Set window center and width values.
        
        Args:
            center: Window center value
            width: Window width value
            block_signals: If True, don't emit window_changed signal
        """
        # Block signals to prevent recursive updates
        self.center_spinbox.blockSignals(True)
        self.width_spinbox.blockSignals(True)
        self.center_slider.blockSignals(True)
        self.width_slider.blockSignals(True)
        
        self.window_center = center
        self.window_width = width
        
        self.center_spinbox.setValue(center)
        self.width_spinbox.setValue(width)
        
        # Update sliders (normalize to 0-1000 range)
        center_range_size = self.center_range[1] - self.center_range[0]
        if center_range_size > 0:
            center_normalized = int((center - self.center_range[0]) / center_range_size * 1000)
            center_normalized = max(0, min(1000, center_normalized))
        else:
            center_normalized = 500
        self.center_slider.setValue(center_normalized)
        
        width_range_size = self.width_range[1] - self.width_range[0]
        if width_range_size > 0:
            width_normalized = int((width - self.width_range[0]) / width_range_size * 1000)
            width_normalized = max(1, min(1000, width_normalized))
        else:
            width_normalized = 100
        self.width_slider.setValue(width_normalized)
        
        self.center_spinbox.blockSignals(False)
        self.width_spinbox.blockSignals(False)
        self.center_slider.blockSignals(False)
        self.width_slider.blockSignals(False)
        
        # Emit signal if not blocking
        if not block_signals:
            self.window_changed.emit(self.window_center, self.window_width)
    
    def _on_center_changed(self, value: float) -> None:
        """
        Handle window center value change.
        
        Args:
            value: New center value
        """
        self.window_center = value
        self.window_changed.emit(self.window_center, self.window_width)
    
    def _on_width_changed(self, value: float) -> None:
        """
        Handle window width value change.
        
        Args:
            value: New width value
        """
        self.window_width = value
        self.window_changed.emit(self.window_center, self.window_width)
    
    def _on_center_slider_changed(self, value: int) -> None:
        """
        Handle window center slider change.
        
        Args:
            value: Slider value (0-1000)
        """
        # Convert slider value to actual range
        center_range_size = self.center_range[1] - self.center_range[0]
        if center_range_size > 0:
            center = self.center_range[0] + (value / 1000.0) * center_range_size
        else:
            center = self.window_center
        
        # Update values without blocking signals (slider signals already handled)
        self.window_center = center
        self.center_spinbox.blockSignals(True)
        self.center_spinbox.setValue(center)
        self.center_spinbox.blockSignals(False)
        
        # Emit signal
        self.window_changed.emit(self.window_center, self.window_width)
    
    def _on_width_slider_changed(self, value: int) -> None:
        """
        Handle window width slider change.
        
        Args:
            value: Slider value (0-1000)
        """
        # Convert slider value to actual range
        width_range_size = self.width_range[1] - self.width_range[0]
        if width_range_size > 0:
            width = self.width_range[0] + (value / 1000.0) * width_range_size
        else:
            width = self.window_width
        
        # Update values without blocking signals (slider signals already handled)
        self.window_width = width
        self.width_spinbox.blockSignals(True)
        self.width_spinbox.setValue(width)
        self.width_spinbox.blockSignals(False)
        
        # Emit signal
        self.window_changed.emit(self.window_center, self.window_width)
    
    def get_window_level(self) -> tuple:
        """
        Get current window center and width.
        
        Returns:
            Tuple of (center, width)
        """
        return (self.window_center, self.window_width)

