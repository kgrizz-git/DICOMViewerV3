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
                                QPushButton, QComboBox, QGroupBox, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction


class CineControlsWidget(QWidget):
    """
    Widget for cine playback controls.
    
    Features:
    - Play/Pause button
    - Stop button
    - Speed dropdown (0.25x, 0.5x, 1x, 2x, 4x)
    - Loop toggle button
    - FPS display label
    """
    
    # Signals
    play_requested = Signal()  # Emitted when play is requested
    pause_requested = Signal()  # Emitted when pause is requested
    stop_requested = Signal()  # Emitted when stop is requested
    speed_changed = Signal(float)  # Emitted when speed changes (speed multiplier)
    loop_toggled = Signal(bool)  # Emitted when loop is toggled
    
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
        
        # Play/Pause button
        self.play_pause_button = QPushButton("▶ Play")
        self.play_pause_button.setToolTip("Play/Pause cine loop")
        self.play_pause_button.clicked.connect(self._on_play_pause_clicked)
        buttons_layout.addWidget(self.play_pause_button)
        
        # Stop button
        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.setToolTip("Stop cine playback")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        buttons_layout.addWidget(self.stop_button)
        
        buttons_layout.addStretch()
        group_layout.addLayout(buttons_layout)
        
        # Speed and Loop row
        speed_loop_layout = QHBoxLayout()
        speed_loop_layout.setSpacing(5)
        
        # Speed dropdown
        speed_label = QLabel("Speed:")
        speed_loop_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "4x"])
        self.speed_combo.setCurrentText("1x")
        self.speed_combo.setToolTip("Playback speed multiplier")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        speed_loop_layout.addWidget(self.speed_combo)
        
        speed_loop_layout.addStretch()
        
        # Loop toggle button
        self.loop_button = QPushButton("🔁 Loop")
        self.loop_button.setCheckable(True)
        self.loop_button.setToolTip("Enable/disable looping")
        self.loop_button.clicked.connect(self._on_loop_toggled)
        speed_loop_layout.addWidget(self.loop_button)
        
        group_layout.addLayout(speed_loop_layout)
        
        # FPS display
        fps_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setToolTip("Current frame rate")
        fps_layout.addWidget(self.fps_label)
        fps_layout.addStretch()
        group_layout.addLayout(fps_layout)
        
        layout.addWidget(group_box)
        layout.addStretch()
    
    def _on_play_pause_clicked(self) -> None:
        """Handle play/pause button click."""
        # Toggle between play and pause
        if self.play_pause_button.text() == "▶ Play" or self.play_pause_button.text() == "▶":
            self.play_requested.emit()
            self.play_pause_button.setText("⏸ Pause")
        else:
            self.pause_requested.emit()
            self.play_pause_button.setText("▶ Play")
    
    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        self.stop_requested.emit()
        self.play_pause_button.setText("▶ Play")
    
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
        self.play_pause_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.speed_combo.setEnabled(enabled)
        self.loop_button.setEnabled(enabled)
    
    def update_playback_state(self, is_playing: bool) -> None:
        """
        Update playback button state.
        
        Args:
            is_playing: True if playing, False if paused/stopped
        """
        if is_playing:
            self.play_pause_button.setText("⏸ Pause")
        else:
            self.play_pause_button.setText("▶ Play")
    
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

