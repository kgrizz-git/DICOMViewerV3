"""
Fusion Controls Widget

This module provides UI controls for image fusion configuration.

Inputs:
    - User interactions (enable/disable, series selection, parameter changes)
    - Available series list
    
Outputs:
    - Signals for fusion configuration changes
    - Visual feedback of fusion state
    
Requirements:
    - PySide6 for GUI components
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QCheckBox, QComboBox, QSlider, QGroupBox,
                                QSpinBox, QSizePolicy, QRadioButton, QButtonGroup)
from PySide6.QtCore import Qt, Signal
from typing import List, Tuple, Optional


class FusionControlsWidget(QWidget):
    """
    Widget for image fusion controls.
    
    Features:
    - Enable/disable fusion
    - Read-only base series display
    - Overlay series selection
    - Opacity control
    - Threshold control
    - Colormap selection
    - Overlay window/level controls
    - Status indicator
    """
    
    # Signals
    fusion_enabled_changed = Signal(bool)  # Emitted when fusion is enabled/disabled
    overlay_series_changed = Signal(str)  # Emitted when overlay series changes (series_uid)
    opacity_changed = Signal(float)  # Emitted when opacity changes (0.0-1.0)
    threshold_changed = Signal(float)  # Emitted when threshold changes (0.0-1.0)
    colormap_changed = Signal(str)  # Emitted when colormap changes
    overlay_window_level_changed = Signal(float, float)  # Emitted when overlay W/L changes (window, level)
    translation_offset_changed = Signal(float, float)  # Emitted when translation offset changes (x, y)
    resampling_mode_changed = Signal(str)  # Emitted when resampling mode changes ('auto', 'fast', 'high_accuracy')
    interpolation_method_changed = Signal(str)  # Emitted when interpolation method changes
    
    def __init__(self, parent=None):
        """
        Initialize fusion controls widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("fusion_controls_widget")
        
        # Track if we're updating controls programmatically
        self._updating = False
        
        self._create_ui()
        self._connect_signals()
        self._set_controls_enabled(False)
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Group box for visual grouping
        group_box = QGroupBox("Image Fusion")
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(5, 10, 5, 5)
        group_layout.setSpacing(8)
        
        # Enable fusion checkbox
        self.enable_checkbox = QCheckBox("Enable Fusion")
        self.enable_checkbox.setChecked(False)
        group_layout.addWidget(self.enable_checkbox)
        
<<<<<<< Updated upstream
        # Base series display (read-only)
        base_label = QLabel("Base Image:")
=======
        # Base series display (read-only text, not dropdown)
        base_label = QLabel("Base Series:")
>>>>>>> Stashed changes
        base_label.setStyleSheet("font-weight: bold;")
        group_layout.addWidget(base_label)
        
        self.base_series_display = QLabel("Not set")
        self.base_series_display.setStyleSheet("font-style: italic;")
        group_layout.addWidget(self.base_series_display)
        
<<<<<<< Updated upstream
        # Overlay series selection (wrapped for easy show/hide)
        self.overlay_section_widget = QWidget()
        overlay_section_layout = QVBoxLayout(self.overlay_section_widget)
        overlay_section_layout.setContentsMargins(0, 0, 0, 0)
        overlay_section_layout.setSpacing(3)
        
        overlay_label = QLabel("Overlay Image:")
        overlay_label.setStyleSheet("font-weight: bold;")
        overlay_section_layout.addWidget(overlay_label)
        
        self.overlay_series_combo = QComboBox()
        self.overlay_series_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_section_layout.addWidget(self.overlay_series_combo)
        
        group_layout.addWidget(self.overlay_section_widget)
        
        # Fusion adjustment controls (wrapped for visibility control)
        self.fusion_adjustment_widget = QWidget()
        fusion_adjustment_layout = QVBoxLayout(self.fusion_adjustment_widget)
        fusion_adjustment_layout.setContentsMargins(0, 0, 0, 0)
        fusion_adjustment_layout.setSpacing(8)
=======
        # Overlay series selection (wrapped for visibility control)
        self.overlay_series_widget = QWidget()
        overlay_container_layout = QVBoxLayout(self.overlay_series_widget)
        overlay_container_layout.setContentsMargins(0, 0, 0, 0)
        overlay_container_layout.setSpacing(0)
        
        overlay_label = QLabel("Overlay Series:")
        overlay_label.setStyleSheet("font-weight: bold;")
        overlay_container_layout.addWidget(overlay_label)
        
        self.overlay_series_combo = QComboBox()
        self.overlay_series_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        overlay_container_layout.addWidget(self.overlay_series_combo)
        
        group_layout.addWidget(self.overlay_series_widget)
        
        # Opacity control (wrapped for visibility control)
        self.opacity_widget = QWidget()
        opacity_container_layout = QVBoxLayout(self.opacity_widget)
        opacity_container_layout.setContentsMargins(0, 0, 0, 0)
        opacity_container_layout.setSpacing(0)
>>>>>>> Stashed changes
        
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("Opacity:")
        opacity_layout.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        opacity_layout.addWidget(self.opacity_slider, 1)
        
        self.opacity_value_label = QLabel("50%")
        self.opacity_value_label.setMinimumWidth(40)
        self.opacity_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_layout.addWidget(self.opacity_value_label)
        
<<<<<<< Updated upstream
        fusion_adjustment_layout.addLayout(opacity_layout)
=======
        opacity_container_layout.addLayout(opacity_layout)
        group_layout.addWidget(self.opacity_widget)
        
        # Threshold control (wrapped for visibility control)
        self.threshold_widget = QWidget()
        threshold_container_layout = QVBoxLayout(self.threshold_widget)
        threshold_container_layout.setContentsMargins(0, 0, 0, 0)
        threshold_container_layout.setSpacing(0)
>>>>>>> Stashed changes
        
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold:")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(0)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(20)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(10)
        threshold_layout.addWidget(self.threshold_slider, 1)
        
        self.threshold_value_label = QLabel("20%")
        self.threshold_value_label.setMinimumWidth(40)
        self.threshold_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        threshold_layout.addWidget(self.threshold_value_label)
        
<<<<<<< Updated upstream
        fusion_adjustment_layout.addLayout(threshold_layout)
=======
        threshold_container_layout.addLayout(threshold_layout)
        group_layout.addWidget(self.threshold_widget)
        
        # Colormap selection (wrapped for visibility control)
        self.colormap_widget = QWidget()
        colormap_container_layout = QVBoxLayout(self.colormap_widget)
        colormap_container_layout.setContentsMargins(0, 0, 0, 0)
        colormap_container_layout.setSpacing(0)
>>>>>>> Stashed changes
        
        colormap_layout = QHBoxLayout()
        colormap_label = QLabel("Color Map:")
        colormap_layout.addWidget(colormap_label)
        
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems([
            'hot',
            'jet',
            'viridis',
            'plasma',
            'inferno',
            'rainbow',
            'cool',
            'spring'
        ])
        self.colormap_combo.setCurrentText('hot')
        colormap_layout.addWidget(self.colormap_combo, 1)
        
<<<<<<< Updated upstream
        fusion_adjustment_layout.addLayout(colormap_layout)
=======
        colormap_container_layout.addLayout(colormap_layout)
        group_layout.addWidget(self.colormap_widget)
        
        # Phase 2: Resampling controls (wrapped for visibility control)
        self.resampling_group = QGroupBox("Resampling (Phase 2)")
        self.resampling_group.setCheckable(False)
        resampling_layout = QVBoxLayout(self.resampling_group)
        resampling_layout.setContentsMargins(5, 10, 5, 5)
        resampling_layout.setSpacing(8)
        
        # Resampling mode selector (radio buttons)
        mode_label = QLabel("Resampling Mode:")
        mode_label.setStyleSheet("font-weight: bold;")
        resampling_layout.addWidget(mode_label)
        
        self.resampling_mode_group = QButtonGroup(self)
        self.auto_mode_radio = QRadioButton("Auto (Recommended)")
        self.auto_mode_radio.setChecked(True)  # Default
        self.auto_mode_radio.setToolTip("Automatically choose 2D or 3D based on compatibility")
        self.resampling_mode_group.addButton(self.auto_mode_radio, 0)
        resampling_layout.addWidget(self.auto_mode_radio)
        
        self.fast_mode_radio = QRadioButton("Fast Mode (2D)")
        self.fast_mode_radio.setToolTip("Force 2D resize for speed (may be inaccurate for different orientations)")
        self.resampling_mode_group.addButton(self.fast_mode_radio, 1)
        resampling_layout.addWidget(self.fast_mode_radio)
        
        self.high_accuracy_mode_radio = QRadioButton("High Accuracy (3D)")
        self.high_accuracy_mode_radio.setToolTip("Force 3D resampling for maximum accuracy")
        self.resampling_mode_group.addButton(self.high_accuracy_mode_radio, 2)
        resampling_layout.addWidget(self.high_accuracy_mode_radio)
        
        # Interpolation method selector
        interpolation_layout = QHBoxLayout()
        interpolation_label = QLabel("Interpolation:")
        interpolation_layout.addWidget(interpolation_label)
        
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.addItems(['linear', 'nearest', 'cubic', 'b-spline'])
        self.interpolation_combo.setCurrentText('linear')
        self.interpolation_combo.setToolTip("Interpolation method for 3D resampling")
        interpolation_layout.addWidget(self.interpolation_combo, 1)
        
        resampling_layout.addLayout(interpolation_layout)
        
        # Resampling status display
        self.resampling_status_label = QLabel("Status: Auto (2D Fast Mode)")
        self.resampling_status_label.setStyleSheet("font-size: 9pt; color: #555; font-style: italic;")
        self.resampling_status_label.setWordWrap(True)
        resampling_layout.addWidget(self.resampling_status_label)
        
        # Warning label (shown when 2D is selected but 3D is recommended)
        self.resampling_warning_label = QLabel("")
        self.resampling_warning_label.setStyleSheet("font-size: 9pt; color: orange; font-style: italic;")
        self.resampling_warning_label.setWordWrap(True)
        self.resampling_warning_label.setVisible(False)
        resampling_layout.addWidget(self.resampling_warning_label)
        
        group_layout.addWidget(self.resampling_group)
        
        # Overlay Window/Level controls (wrapped for visibility control)
        self.window_level_widget = QWidget()
        wl_container_layout = QVBoxLayout(self.window_level_widget)
        wl_container_layout.setContentsMargins(0, 0, 0, 0)
        wl_container_layout.setSpacing(0)
>>>>>>> Stashed changes
        
        wl_label = QLabel("Overlay Window/Level:")
        wl_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
<<<<<<< Updated upstream
        fusion_adjustment_layout.addWidget(wl_label)
        
        # Window control
        window_layout = QHBoxLayout()
        window_label = QLabel("Window:")
        window_layout.addWidget(window_label)
        
        self.overlay_window_spinbox = QSpinBox()
        self.overlay_window_spinbox.setMinimum(1)
        self.overlay_window_spinbox.setMaximum(100000)
        self.overlay_window_spinbox.setValue(1000)
        self.overlay_window_spinbox.setSingleStep(10)
        window_layout.addWidget(self.overlay_window_spinbox, 1)
        
        fusion_adjustment_layout.addLayout(window_layout)
        
        # Level control
=======
        wl_container_layout.addWidget(wl_label)
        
        # Level control (center) - appears first to match Window/Zoom/ROI tab
>>>>>>> Stashed changes
        level_layout = QHBoxLayout()
        level_label = QLabel("Level:")
        level_layout.addWidget(level_label)
        
        self.overlay_level_spinbox = QSpinBox()
        self.overlay_level_spinbox.setMinimum(-50000)
        self.overlay_level_spinbox.setMaximum(50000)
        self.overlay_level_spinbox.setValue(500)
        self.overlay_level_spinbox.setSingleStep(10)
        level_layout.addWidget(self.overlay_level_spinbox, 1)
        
<<<<<<< Updated upstream
        fusion_adjustment_layout.addLayout(level_layout)
=======
        wl_container_layout.addLayout(level_layout)
>>>>>>> Stashed changes
        
        # Window control (width) - appears second to match Window/Zoom/ROI tab
        window_layout = QHBoxLayout()
        window_label = QLabel("Window:")
        window_layout.addWidget(window_label)
        
        self.overlay_window_spinbox = QSpinBox()
        self.overlay_window_spinbox.setMinimum(1)
        self.overlay_window_spinbox.setMaximum(100000)
        self.overlay_window_spinbox.setValue(1000)
        self.overlay_window_spinbox.setSingleStep(10)
        window_layout.addWidget(self.overlay_window_spinbox, 1)
        
        wl_container_layout.addLayout(window_layout)
        group_layout.addWidget(self.window_level_widget)
        
        # Advanced section for spatial alignment (wrapped for visibility control)
        self.advanced_group = QGroupBox("Advanced Spatial Alignment")
        self.advanced_group.setCheckable(False)
        advanced_layout = QVBoxLayout(self.advanced_group)
        advanced_layout.setContentsMargins(5, 10, 5, 5)
        advanced_layout.setSpacing(8)
        
        # Calculated offset display
        self.calculated_offset_label = QLabel("Calculated Offset: X=0.0, Y=0.0 pixels")
        self.calculated_offset_label.setStyleSheet("font-size: 10pt; color: #555;")
        advanced_layout.addWidget(self.calculated_offset_label)
        
        # Scaling factors display
        self.scaling_factors_label = QLabel("Scaling: X=1.00, Y=1.00")
        self.scaling_factors_label.setStyleSheet("font-size: 10pt; color: #555;")
        advanced_layout.addWidget(self.scaling_factors_label)
        
        # X offset adjustment
        x_offset_layout = QHBoxLayout()
        x_offset_label = QLabel("X Offset:")
        x_offset_layout.addWidget(x_offset_label)
        
        self.x_offset_spinbox = QSpinBox()
        self.x_offset_spinbox.setMinimum(-500)
        self.x_offset_spinbox.setMaximum(500)
        self.x_offset_spinbox.setValue(0)
        self.x_offset_spinbox.setSingleStep(1)
        self.x_offset_spinbox.setSuffix(" px")
        x_offset_layout.addWidget(self.x_offset_spinbox, 1)
        
        advanced_layout.addLayout(x_offset_layout)
        
        # Y offset adjustment
        y_offset_layout = QHBoxLayout()
        y_offset_label = QLabel("Y Offset:")
        y_offset_layout.addWidget(y_offset_label)
        
        self.y_offset_spinbox = QSpinBox()
        self.y_offset_spinbox.setMinimum(-500)
        self.y_offset_spinbox.setMaximum(500)
        self.y_offset_spinbox.setValue(0)
        self.y_offset_spinbox.setSingleStep(1)
        self.y_offset_spinbox.setSuffix(" px")
        y_offset_layout.addWidget(self.y_offset_spinbox, 1)
        
        advanced_layout.addLayout(y_offset_layout)
        
        # Reset button
        from PySide6.QtWidgets import QPushButton
        self.reset_offset_button = QPushButton("Reset to Calculated")
        self.reset_offset_button.clicked.connect(self._on_reset_offset_clicked)
        advanced_layout.addWidget(self.reset_offset_button)
        
<<<<<<< Updated upstream
        fusion_adjustment_layout.addWidget(advanced_group)
        
        group_layout.addWidget(self.fusion_adjustment_widget)
=======
        group_layout.addWidget(self.advanced_group)
>>>>>>> Stashed changes
        
        # Store calculated offset for reset functionality
        self._calculated_offset_x = 0.0
        self._calculated_offset_y = 0.0
        
        # Track if user manually modified the offset
        self._user_modified_offset = False
        
        # Status indicator
        self.status_label = QLabel("Status: Disabled")
        self.status_label.setStyleSheet("color: gray; font-style: italic; margin-top: 5px;")
        self.status_label.setWordWrap(True)
        group_layout.addWidget(self.status_label)
        
        layout.addWidget(group_box)
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
<<<<<<< Updated upstream
=======
        # Base series is read-only display, no signal connection needed
>>>>>>> Stashed changes
        self.overlay_series_combo.currentIndexChanged.connect(self._on_overlay_series_changed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        self.overlay_window_spinbox.valueChanged.connect(self._on_overlay_wl_changed)
        self.overlay_level_spinbox.valueChanged.connect(self._on_overlay_wl_changed)
        self.x_offset_spinbox.valueChanged.connect(self._on_translation_offset_changed)
        self.y_offset_spinbox.valueChanged.connect(self._on_translation_offset_changed)
        self.resampling_mode_group.buttonClicked.connect(self._on_resampling_mode_changed)
        self.interpolation_combo.currentTextChanged.connect(self._on_interpolation_method_changed)
    
    def _on_enable_toggled(self, checked: bool) -> None:
        """Handle enable checkbox toggle."""
        self._set_controls_enabled(checked)
        if not self._updating:
            self.fusion_enabled_changed.emit(checked)
    
<<<<<<< Updated upstream
=======
    # Base series is read-only, so no handler needed for user changes
    # (Base is set programmatically based on current viewing series)
    
>>>>>>> Stashed changes
    def _on_overlay_series_changed(self, index: int) -> None:
        """Handle overlay series selection change."""
        if not self._updating and index >= 0:
            series_uid = self.overlay_series_combo.currentData()
            if series_uid:
                self.overlay_series_changed.emit(series_uid)
    
    def _on_opacity_changed(self, value: int) -> None:
        """Handle opacity slider change."""
        opacity = value / 100.0
        self.opacity_value_label.setText(f"{value}%")
        if not self._updating:
            self.opacity_changed.emit(opacity)
    
    def _on_threshold_changed(self, value: int) -> None:
        """Handle threshold slider change."""
        threshold = value / 100.0
        self.threshold_value_label.setText(f"{value}%")
        if not self._updating:
            self.threshold_changed.emit(threshold)
    
    def _on_colormap_changed(self, colormap: str) -> None:
        """Handle colormap selection change."""
        if not self._updating:
            self.colormap_changed.emit(colormap)
    
    def _on_overlay_wl_changed(self) -> None:
        """Handle overlay window/level change."""
        if not self._updating:
            window = float(self.overlay_window_spinbox.value())
            level = float(self.overlay_level_spinbox.value())
            self.overlay_window_level_changed.emit(window, level)
    
    def _on_translation_offset_changed(self) -> None:
        """Handle translation offset change."""
        if not self._updating:
            # Mark that user has manually modified the offset
            self._user_modified_offset = True
            x_offset = float(self.x_offset_spinbox.value())
            y_offset = float(self.y_offset_spinbox.value())
            # DEBUG - commented out
            # print(f"[OFFSET DEBUG] User changed offset to: X={x_offset:.1f}, Y={y_offset:.1f}")
            self.translation_offset_changed.emit(x_offset, y_offset)
    
    def _on_reset_offset_clicked(self) -> None:
        """Handle reset offset button click."""
        # Reset the user-modified flag since we're resetting to calculated
        self._user_modified_offset = False
        
        self._updating = True
        self.x_offset_spinbox.setValue(int(round(self._calculated_offset_x)))
        self.y_offset_spinbox.setValue(int(round(self._calculated_offset_y)))
        self._updating = False
        
        # DEBUG - commented out
        # print(f"[OFFSET DEBUG] Reset to calculated offset: X={self._calculated_offset_x:.1f}, Y={self._calculated_offset_y:.1f}")
        # Emit signal with calculated values
        self.translation_offset_changed.emit(self._calculated_offset_x, self._calculated_offset_y)
    
    def _on_resampling_mode_changed(self, button: QRadioButton) -> None:
        """Handle resampling mode change."""
        if self._updating:
            return
        
        if button == self.auto_mode_radio:
            mode = 'auto'
        elif button == self.fast_mode_radio:
            mode = 'fast'
        elif button == self.high_accuracy_mode_radio:
            mode = 'high_accuracy'
        else:
            return
        
        self.resampling_mode_changed.emit(mode)
    
    def _on_interpolation_method_changed(self, method: str) -> None:
        """Handle interpolation method change."""
        if not self._updating:
            self.interpolation_method_changed.emit(method)
    
    def _set_controls_enabled(self, enabled: bool) -> None:
        """
        Enable or disable fusion controls, and hide/show overlay controls.
        
        Args:
            enabled: True to enable and show controls, False to disable and hide overlay controls
        """
<<<<<<< Updated upstream
=======
        # Hide/show overlay series selector when fusion is disabled
        self.overlay_series_widget.setVisible(enabled)
>>>>>>> Stashed changes
        self.overlay_series_combo.setEnabled(enabled)
        
        # Hide/show overlay controls when fusion is disabled
        # Opacity, threshold, colormap
        self.opacity_widget.setVisible(enabled)
        self.opacity_slider.setEnabled(enabled)
        
        self.threshold_widget.setVisible(enabled)
        self.threshold_slider.setEnabled(enabled)
        
        self.colormap_widget.setVisible(enabled)
        self.colormap_combo.setEnabled(enabled)
        
        # Phase 2: Resampling controls
        self.resampling_group.setVisible(enabled)
        self.auto_mode_radio.setEnabled(enabled)
        self.fast_mode_radio.setEnabled(enabled)
        self.high_accuracy_mode_radio.setEnabled(enabled)
        self.interpolation_combo.setEnabled(enabled)
        
        # Overlay Window/Level controls
        self.window_level_widget.setVisible(enabled)
        self.overlay_window_spinbox.setEnabled(enabled)
        self.overlay_level_spinbox.setEnabled(enabled)
        
        # Advanced Spatial Alignment
        self.advanced_group.setVisible(enabled)
        self.x_offset_spinbox.setEnabled(enabled)
        self.y_offset_spinbox.setEnabled(enabled)
        self.reset_offset_button.setEnabled(enabled)
        
        # Hide/show sections when fusion is disabled/enabled
        if hasattr(self, "overlay_section_widget"):
            self.overlay_section_widget.setVisible(enabled)
        if hasattr(self, "fusion_adjustment_widget"):
            self.fusion_adjustment_widget.setVisible(enabled)
        
        if not enabled:
            self.status_label.setText("Status: Disabled")
            self.status_label.setStyleSheet("color: gray; font-style: italic; margin-top: 5px;")
    
    def update_series_lists(
        self,
        series_list: List[Tuple[str, str]],
        current_overlay_uid: str = ""
    ) -> None:
        """
        Update the overlay series dropdown list.
        Base series is read-only display, updated via set_base_display().
        
        Args:
            series_list: List of (series_uid, display_name) tuples
<<<<<<< Updated upstream
=======
            current_base_uid: Current base series UID (for display, not selection)
>>>>>>> Stashed changes
            current_overlay_uid: Current overlay series UID to select
        """
        # DEBUG
        print(f"[FUSION CONTROLS DEBUG] update_series_lists called with {len(series_list)} series")
        
        self._updating = True
        
<<<<<<< Updated upstream
        # Save current selections
        prev_overlay = self.overlay_series_combo.currentData()
        
        # Clear existing items
=======
        # Save current overlay selection
        prev_overlay = self.overlay_series_combo.currentData()
        
        # Clear existing items (only overlay, base is read-only)
>>>>>>> Stashed changes
        self.overlay_series_combo.clear()
        
        print(f"[FUSION CONTROLS DEBUG] Cleared overlay dropdown, now adding {len(series_list)} items")
        
<<<<<<< Updated upstream
        # Add series to overlay combo
=======
        # Add series to overlay combo only
>>>>>>> Stashed changes
        for series_uid, display_name in series_list:
            print(f"[FUSION CONTROLS DEBUG]   Adding: {display_name}")
            self.overlay_series_combo.addItem(display_name, series_uid)
        
<<<<<<< Updated upstream
=======
        # Restore or set overlay selection
>>>>>>> Stashed changes
        if current_overlay_uid:
            index = self.overlay_series_combo.findData(current_overlay_uid)
            if index >= 0:
                self.overlay_series_combo.setCurrentIndex(index)
        elif prev_overlay:
            index = self.overlay_series_combo.findData(prev_overlay)
            if index >= 0:
                self.overlay_series_combo.setCurrentIndex(index)
        
        self._updating = False
    
    def set_status(self, status_text: str, is_error: bool = False) -> None:
        """
        Update status label.
        
        Args:
            status_text: Status text to display
            is_error: True if this is an error status
        """
        self.status_label.setText(f"Status: {status_text}")
        if is_error:
            self.status_label.setStyleSheet("color: red; font-style: italic; margin-top: 5px;")
        else:
            self.status_label.setStyleSheet("color: green; font-style: italic; margin-top: 5px;")
    
<<<<<<< Updated upstream
    def revert_overlay_selection(self, preferred_uid: Optional[str], exclude_uid: Optional[str] = None) -> None:
        """
        Restore overlay combo to a valid selection.
        
        Args:
            preferred_uid: UID to re-select if available.
            exclude_uid: UID that must not be selected (e.g., base series).
        """
        self._updating = True
        target_index = -1
        
        if preferred_uid:
            idx = self.overlay_series_combo.findData(preferred_uid)
            if idx >= 0 and (exclude_uid is None or self.overlay_series_combo.itemData(idx) != exclude_uid):
                target_index = idx
        
        if target_index == -1:
            for i in range(self.overlay_series_combo.count()):
                data = self.overlay_series_combo.itemData(i)
                if exclude_uid is None or data != exclude_uid:
                    target_index = i
                    break
        
        if target_index >= 0:
            self.overlay_series_combo.setCurrentIndex(target_index)
        else:
            self.overlay_series_combo.setCurrentIndex(-1)
        
        self._updating = False
=======
    def get_selected_base_series(self) -> str:
        """Get currently selected base series UID (for compatibility, but base is read-only)."""
        # Base is read-only, this method kept for compatibility
        # Base UID should be tracked externally
        return ""
    
    def set_base_display(self, display_text: str) -> None:
        """
        Update read-only base series display.
        
        Args:
            display_text: Text to display (series name or "Not set")
        """
        if display_text:
            self.base_series_display.setText(display_text)
            self.base_series_display.setStyleSheet("")  # Normal style
        else:
            self.base_series_display.setText("Not set")
            self.base_series_display.setStyleSheet("font-style: italic;")  # "Not set" style
>>>>>>> Stashed changes
    
    def get_selected_overlay_series(self) -> str:
        """Get currently selected overlay series UID."""
        return self.overlay_series_combo.currentData() or ""
    
    def is_fusion_enabled(self) -> bool:
        """Check if fusion is enabled."""
        return self.enable_checkbox.isChecked()
    
    def set_fusion_enabled(self, enabled: bool) -> None:
        """
        Set fusion enabled state.
        
        Args:
            enabled: True to enable fusion, False to disable
        """
        self._updating = True
        self.enable_checkbox.setChecked(enabled)
        self._updating = False
    
    def set_base_display(self, display_text: str) -> None:
        """Update read-only base series display."""
        self.base_series_display.setText(display_text or "Not set")
    
    def get_opacity(self) -> float:
        """Get current opacity value (0.0-1.0)."""
        return self.opacity_slider.value() / 100.0
    
    def get_threshold(self) -> float:
        """Get current threshold value (0.0-1.0)."""
        return self.threshold_slider.value() / 100.0
    
    def get_colormap(self) -> str:
        """Get current colormap name."""
        return self.colormap_combo.currentText()
    
    def get_overlay_window_level(self) -> Tuple[float, float]:
        """Get overlay window/level values."""
        window = float(self.overlay_window_spinbox.value())
        level = float(self.overlay_level_spinbox.value())
        return (window, level)
    
    def set_overlay_window_level(self, window: float, level: float) -> None:
        """
        Set overlay window/level values.
        
        Args:
            window: Window width
            level: Window center/level
        """
        self._updating = True
        self.overlay_window_spinbox.setValue(int(window))
        self.overlay_level_spinbox.setValue(int(level))
        self._updating = False
    
    def set_calculated_offset(self, x: float, y: float) -> None:
        """
        Update display of calculated offset.
        
        Args:
            x: Calculated X offset in pixels
            y: Calculated Y offset in pixels
        """
        self._calculated_offset_x = x
        self._calculated_offset_y = y
        self.calculated_offset_label.setText(f"Calculated Offset: X={x:.1f}, Y={y:.1f} pixels")
        
        # DEBUG - commented out
        # print(f"[OFFSET DEBUG] set_calculated_offset called: X={x:.1f}, Y={y:.1f}")
        # print(f"[OFFSET DEBUG]   Current spinbox values: X={self.x_offset_spinbox.value()}, Y={self.y_offset_spinbox.value()}")
        # print(f"[OFFSET DEBUG]   User modified: {self._user_modified_offset}")
        
        # Update the spinboxes only if user hasn't manually modified them
        if not self._user_modified_offset:
            self._updating = True
            self.x_offset_spinbox.setValue(int(round(x)))
            self.y_offset_spinbox.setValue(int(round(y)))
            self._updating = False
            # DEBUG - commented out
            # print(f"[OFFSET DEBUG]   Updated spinboxes to calculated values")
        else:
            # DEBUG - commented out
            # print(f"[OFFSET DEBUG]   Keeping user-modified spinbox values")
            pass
    
    def has_user_modified_offset(self) -> bool:
        """Return True if user manually changed offset spinboxes."""
        return self._user_modified_offset
    
    def reset_user_modified_offset(self) -> None:
        """Clear user-modified flag so calculated offsets can overwrite spinboxes."""
        self._user_modified_offset = False
    
    def set_scaling_factors(self, scale_x: float, scale_y: float) -> None:
        """
        Update display of scaling factors.
        
        Args:
            scale_x: Scaling factor in X direction
            scale_y: Scaling factor in Y direction
        """
        self.scaling_factors_label.setText(f"Scaling: X={scale_x:.2f}, Y={scale_y:.2f}")
    
    def get_translation_offset(self) -> Tuple[float, float]:
        """
        Get current translation offset from spinboxes.
        
        Returns:
            Tuple of (x_offset, y_offset) in pixels
        """
        x_offset = float(self.x_offset_spinbox.value())
        y_offset = float(self.y_offset_spinbox.value())
        return (x_offset, y_offset)
    
    def has_user_modified_offset(self) -> bool:
        """Return True if user manually changed offset spinboxes."""
        return self._user_modified_offset
    
    def reset_user_modified_offset(self) -> None:
        """Clear user-modified flag so calculated offsets can overwrite spinboxes."""
        self._user_modified_offset = False
    
    def get_resampling_mode(self) -> str:
        """Get current resampling mode ('auto', 'fast', 'high_accuracy')."""
        if self.auto_mode_radio.isChecked():
            return 'auto'
        elif self.fast_mode_radio.isChecked():
            return 'fast'
        elif self.high_accuracy_mode_radio.isChecked():
            return 'high_accuracy'
        return 'auto'
    
    def set_resampling_mode(self, mode: str) -> None:
        """
        Set resampling mode.
        
        Args:
            mode: 'auto', 'fast', or 'high_accuracy'
        """
        self._updating = True
        if mode == 'fast':
            self.fast_mode_radio.setChecked(True)
        elif mode == 'high_accuracy':
            self.high_accuracy_mode_radio.setChecked(True)
        else:
            self.auto_mode_radio.setChecked(True)
        self._updating = False
    
    def get_interpolation_method(self) -> str:
        """Get current interpolation method."""
        return self.interpolation_combo.currentText()
    
    def set_interpolation_method(self, method: str) -> None:
        """
        Set interpolation method.
        
        Args:
            method: 'linear', 'nearest', 'cubic', or 'b-spline'
        """
        self._updating = True
        index = self.interpolation_combo.findText(method)
        if index >= 0:
            self.interpolation_combo.setCurrentIndex(index)
        self._updating = False
    
    def set_resampling_status(self, mode_display: str, reason: str, show_warning: bool = False, warning_text: str = "") -> None:
        """
        Update resampling status display.
        
        Args:
            mode_display: Mode display string (e.g., "Auto (2D Fast Mode)")
            reason: Reason string (e.g., "Compatible: same orientation")
            show_warning: Whether to show warning label
            warning_text: Warning text to display
        """
        status_text = f"Using: {mode_display}"
        if reason:
            status_text += f" - {reason}"
        self.resampling_status_label.setText(status_text)
        
        # Show/hide warning
        if show_warning and warning_text:
            self.resampling_warning_label.setText(warning_text)
            self.resampling_warning_label.setVisible(True)
        else:
            self.resampling_warning_label.setVisible(False)

