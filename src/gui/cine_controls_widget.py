"""
Cine Controls Widget

This module provides a widget for cine playback controls.

Inputs:
    - User interactions (play, pause, stop, speed, loop)
    - Playback state updates from CinePlayer
    
Outputs:
    - Signals for cine control actions
    - Visual feedback for playback state
    
Requirements:
    - PySide6 for GUI components
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QComboBox, QGroupBox, QSizePolicy, QSlider)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction


class CineControlsWidget(QWidget):
    """
    Widget for cine playback controls.
    
    Features:
    - Play button
    - Pause button
    - Stop button
    - Speed dropdown (0.25x, 0.5x, 1x, 2x, 4x)
    - Loop toggle button
    - FPS display label
    - Frame slider showing current frame out of total
    """
    
    # Signals
    play_requested = Signal()  # Emitted when play is requested
    pause_requested = Signal()  # Emitted when pause is requested
    stop_requested = Signal()  # Emitted when stop is requested
    speed_changed = Signal(float)  # Emitted when speed changes (speed multiplier)
    loop_toggled = Signal(bool)  # Emitted when loop is toggled
    frame_position_changed = Signal(int)  # Emitted when frame slider is moved (frame index)
    
    def __init__(self, parent=None):
        """
        Initialize the cine controls widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("cine_controls_widget")
        
        self._create_ui()
        self._set_controls_enabled(False)
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Group box for visual grouping
        group_box = QGroupBox("Cine Playback")
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(5, 10, 5, 5)
        group_layout.setSpacing(5)
        
        # Control buttons row
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)
        
        # Play button
        self.play_button = QPushButton("▶ Play")
        self.play_button.setToolTip("Play cine loop")
        self.play_button.clicked.connect(self._on_play_clicked)
        buttons_layout.addWidget(self.play_button)
        
        # Pause button
        self.pause_button = QPushButton("⏸ Pause")
        self.pause_button.setToolTip("Pause cine playback")
        self.pause_button.clicked.connect(self._on_pause_clicked)
        buttons_layout.addWidget(self.pause_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.setToolTip("Stop cine playback")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        buttons_layout.addWidget(self.stop_button)
        
        # Loop toggle button (moved next to stop button)
        self.loop_button = QPushButton("🔁 Loop")
        self.loop_button.setObjectName("cine_loop_button")
        self.loop_button.setCheckable(True)
        self.loop_button.setToolTip("Enable/disable looping")
        self.loop_button.clicked.connect(self._on_loop_toggled)
        buttons_layout.addWidget(self.loop_button)
        
        group_layout.addLayout(buttons_layout)
        
        # Speed, FPS, and Frame Slider row
        speed_fps_layout = QHBoxLayout()
        speed_fps_layout.setSpacing(5)
        
        # Speed dropdown
        speed_label = QLabel("Speed:")
        speed_fps_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "4x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.setToolTip("Playback speed multiplier")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        speed_fps_layout.addWidget(self.speed_combo)
        
        # FPS display (moved to same row as speed)
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setToolTip("Current frame rate")
        speed_fps_layout.addWidget(self.fps_label)
        
        # Frame slider
        frame_label = QLabel("Frame:")
        speed_fps_layout.addWidget(frame_label)
        
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setMaximum(0)
        self.frame_slider.setValue(0)
        self.frame_slider.setToolTip("Current frame / Total frames")
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self._on_frame_slider_changed)
        speed_fps_layout.addWidget(self.frame_slider, 1)  # Give slider stretch factor to take available space
        
        # Frame position label (e.g., "1 / 10")
        self.frame_position_label = QLabel("0 / 0")
        self.frame_position_label.setToolTip("Current frame / Total frames")
        self.frame_position_label.setMinimumWidth(50)
        speed_fps_layout.addWidget(self.frame_position_label)
        
        speed_fps_layout.addStretch()
        group_layout.addLayout(speed_fps_layout)
        
        layout.addWidget(group_box)
    
    def _on_play_clicked(self) -> None:
        """Handle play button click."""
        self.play_requested.emit()
    
    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        self.pause_requested.emit()
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_requested.emit()
    
    def _on_speed_changed(self, speed_text: str) -> None:
        """Handle speed dropdown change."""
        # Extract multiplier from text (e.g., "2x" -> 2.0)
        try:
            multiplier_str = speed_text.replace("x", "")
            multiplier = float(multiplier_str)
            self.speed_changed.emit(multiplier)
        except (ValueError, AttributeError):
            pass
    
    def _on_loop_toggled(self, checked: bool) -> None:
        """Handle loop toggle."""
        self.loop_toggled.emit(checked)
    
    def _on_frame_slider_changed(self, value: int) -> None:
        """Handle frame slider value change."""
        self.frame_position_changed.emit(value)
    
    def set_controls_enabled(self, enabled: bool) -> None:
        """
        Enable or disable cine controls.
        
        Args:
            enabled: True to enable controls, False to disable
        """
        self._set_controls_enabled(enabled)
    
    def _set_controls_enabled(self, enabled: bool) -> None:
        """
        Internal method to enable or disable controls.
        
        Args:
            enabled: True to enable controls, False to disable
        """
        self.play_button.setEnabled(enabled)
        # Pause button should only be enabled if controls are enabled AND playback is active
        # This will be managed by update_playback_state, so we disable it here
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(enabled)
        self.speed_combo.setEnabled(enabled)
        self.loop_button.setEnabled(enabled)
        self.frame_slider.setEnabled(enabled)
    
    def update_playback_state(self, is_playing: bool) -> None:
        """
        Update playback button state.
        
        Args:
            is_playing: True if playing, False if paused/stopped
        """
        if is_playing:
            # When playing, disable play button and enable pause button
            self.play_button.setEnabled(False)
            self.pause_button.setEnabled(True)
        else:
            # When paused/stopped, enable play button and disable pause button
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
    
    def update_fps_display(self, fps: float) -> None:
        """
        Update FPS display label.
        
        Args:
            fps: Frame rate in FPS
        """
        self.fps_label.setText(f"FPS: {fps:.1f}")
    
    def set_speed(self, speed_multiplier: float) -> None:
        """
        Set speed dropdown to specified multiplier.
        
        Args:
            speed_multiplier: Speed multiplier (0.25, 0.5, 1.0, 2.0, 4.0)
        """
        speed_text = f"{speed_multiplier}x"
        if speed_text in ["0.25x", "0.5x", "1x", "2x", "4x"]:
            self.speed_combo.setCurrentText(speed_text)
    
    def set_loop(self, enabled: bool) -> None:
        """
        Set loop button state.
        
        Args:
            enabled: True to enable looping, False to disable
        """
        self.loop_button.setChecked(enabled)
    
    def update_frame_position(self, current_frame: int, total_frames: int) -> None:
        """
        Update frame slider position and range.
        
        Args:
            current_frame: Current frame index (0-based)
            total_frames: Total number of frames
        """
        if total_frames <= 0:
            self.frame_slider.setMaximum(0)
            self.frame_slider.setValue(0)
            self.frame_position_label.setText("0 / 0")
            return
        
        # Block signals to prevent emitting when we programmatically update the slider
        self.frame_slider.blockSignals(True)
        self.frame_slider.setMaximum(max(0, total_frames - 1))
        self.frame_slider.setValue(max(0, min(current_frame, total_frames - 1)))
        self.frame_slider.blockSignals(False)
        
        # Update label (display 1-based frame numbers)
        self.frame_position_label.setText(f"{current_frame + 1} / {total_frames}")

