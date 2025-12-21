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

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QComboBox,
    QSlider,
    QGroupBox,
    QSpinBox,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
    QPlainTextEdit,
    QSpacerItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
from typing import List, Tuple


class FusionControlsWidget(QWidget):
    """
    Widget for image fusion controls.
    
    Features:
    - Enable/disable fusion
    - Base and overlay series selection
    - Opacity control
    - Threshold control
    - Colormap selection
    - Overlay window/level controls
    - Status indicator
    """
    
    # Signals
    fusion_enabled_changed = Signal(bool)  # Emitted when fusion is enabled/disabled
    base_series_changed = Signal(str)  # Emitted when base series changes (series_uid)
    overlay_series_changed = Signal(str)  # Emitted when overlay series changes (series_uid)
    opacity_changed = Signal(float)  # Emitted when opacity changes (0.0-1.0)
    threshold_changed = Signal(float)  # Emitted when threshold changes (0.0-1.0)
    colormap_changed = Signal(str)  # Emitted when colormap changes
    overlay_window_level_changed = Signal(float, float)  # Emitted when overlay W/L changes (window, level)
    translation_offset_changed = Signal(float, float)  # Emitted when translation offset changes (x, y)
    resampling_mode_changed = Signal(str)  # Emitted when resampling mode changes ('fast', 'high_accuracy')
    interpolation_method_changed = Signal(str)  # Emitted when interpolation method changes
    
    def __init__(self, config_manager=None, parent=None):
        """
        Initialize fusion controls widget.
        
        Args:
            config_manager: ConfigManager instance for theme access
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("fusion_controls_widget")
        
        # Store config manager for theme access
        self.config_manager = config_manager
        
        # Track if we're updating controls programmatically
        self._updating = False

        # Offset unit/spacing state (for Spatial Alignment)
        # Offsets are always stored internally in pixels; the unit toggle only
        # affects how values are displayed and what users type into the
        # spinboxes.
        self._offset_unit = "mm"  # "mm" or "px"
        self._row_spacing_mm = None  # Y spacing (row direction)
        self._col_spacing_mm = None  # X spacing (column direction)
        self._spacing_source = None  # e.g. "pixel_spacing", "reconDiameter_cols", ...
        self._can_use_mm = False
        self._use_3d_mode = False  # Track if 3D resampling mode is active
        
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
        
        # Base series display (read-only text, not dropdown)
        base_label = QLabel("Base Series:")
        base_label.setStyleSheet("font-weight: bold;")
        group_layout.addWidget(base_label)
        
        self.base_series_display = QLabel("Not set")
        self.base_series_display.setStyleSheet("font-style: italic;")
        group_layout.addWidget(self.base_series_display)
        
        # Overlay series selection (wrapped for visibility control). The fusion
        # status log is displayed directly beneath the overlay series dropdown
        # so that fusion-related messages are visually tied to the selected
        # overlay.
        self.overlay_series_widget = QWidget()
        overlay_container_layout = QVBoxLayout(self.overlay_series_widget)
        overlay_container_layout.setContentsMargins(0, 0, 0, 0)
        overlay_container_layout.setSpacing(0)
        
        overlay_label = QLabel("Overlay Series:")
        overlay_label.setStyleSheet("font-weight: bold;")
        overlay_container_layout.addWidget(overlay_label)
        
        self.overlay_series_combo = QComboBox()
        self.overlay_series_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        overlay_container_layout.addWidget(self.overlay_series_combo)

        # Fusion status area (fixed-height, scrollable log) placed directly
        # beneath the overlay series dropdown.
        self.status_container_widget = QWidget()
        status_container_layout = QVBoxLayout(self.status_container_widget)
        status_container_layout.setContentsMargins(0, 4, 0, 0)
        status_container_layout.setSpacing(2)

        # Use the same base font as the rest of the controls so the status box
        # text matches the application font size. The heading is bold; the log
        # text is regular weight.
        base_font = self.font()

        self.status_heading_label = QLabel("Fusion Status:")
        heading_font = QFont(base_font)
        heading_font.setBold(True)
        self.status_heading_label.setFont(heading_font)
        self.status_heading_label.setStyleSheet("margin-top: 2px;")
        status_container_layout.addWidget(self.status_heading_label)

        self.status_text_edit = QPlainTextEdit()
        self.status_text_edit.setReadOnly(True)
        self.status_text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.status_text_edit.setMaximumBlockCount(200)
        # Fixed height sized for ~2 lines of text, with scrollbar for overflow.
        # Colors are taken from the application palette so the widget respects
        # light/dark themes (white/black background with contrasting text).
        log_font = QFont(base_font)
        log_font.setBold(False)
        self.status_text_edit.setFont(log_font)
        self.status_text_edit.setFixedHeight(48)
        status_container_layout.addWidget(self.status_text_edit)

        overlay_container_layout.addWidget(self.status_container_widget)
        
        group_layout.addWidget(self.overlay_series_widget)
        
        # Opacity control (wrapped for visibility control)
        self.opacity_widget = QWidget()
        opacity_container_layout = QVBoxLayout(self.opacity_widget)
        opacity_container_layout.setContentsMargins(0, 0, 0, 0)
        opacity_container_layout.setSpacing(0)
        
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
        
        opacity_container_layout.addLayout(opacity_layout)
        group_layout.addWidget(self.opacity_widget)
        
        # Threshold control (wrapped for visibility control)
        self.threshold_widget = QWidget()
        threshold_container_layout = QVBoxLayout(self.threshold_widget)
        threshold_container_layout.setContentsMargins(0, 0, 0, 0)
        threshold_container_layout.setSpacing(0)
        
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
        
        threshold_container_layout.addLayout(threshold_layout)
        group_layout.addWidget(self.threshold_widget)
        
        # Colormap selection (wrapped for visibility control)
        self.colormap_widget = QWidget()
        colormap_container_layout = QVBoxLayout(self.colormap_widget)
        colormap_container_layout.setContentsMargins(0, 0, 0, 0)
        colormap_container_layout.setSpacing(0)
        
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
        self.fast_mode_radio = QRadioButton("Fast Mode (2D)")
        self.fast_mode_radio.setToolTip("Force 2D resize for speed (may be inaccurate for different orientations)")
        self.resampling_mode_group.addButton(self.fast_mode_radio, 0)
        resampling_layout.addWidget(self.fast_mode_radio)
        
        self.high_accuracy_mode_radio = QRadioButton("High Accuracy (3D)")
        self.high_accuracy_mode_radio.setChecked(True)  # Default - changed from auto
        self.high_accuracy_mode_radio.setToolTip("Force 3D resampling for maximum accuracy")
        self.resampling_mode_group.addButton(self.high_accuracy_mode_radio, 1)
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
        
        wl_label = QLabel("Overlay Window/Level:")
        wl_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        wl_container_layout.addWidget(wl_label)
        
        # Level control (center) - appears first to match Window/Zoom/ROI tab
        level_layout = QHBoxLayout()
        level_label = QLabel("Level:")
        level_layout.addWidget(level_label)
        
        self.overlay_level_spinbox = QSpinBox()
        self.overlay_level_spinbox.setMinimum(-50000)
        self.overlay_level_spinbox.setMaximum(50000)
        self.overlay_level_spinbox.setValue(500)
        self.overlay_level_spinbox.setSingleStep(10)
        level_layout.addWidget(self.overlay_level_spinbox, 1)
        
        wl_container_layout.addLayout(level_layout)
        
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
        
        # Spatial Alignment section (manual offsets + derived info)
        self.advanced_group = QGroupBox("Spatial Alignment")
        self.advanced_group.setCheckable(False)
        advanced_layout = QVBoxLayout(self.advanced_group)
        advanced_layout.setContentsMargins(5, 10, 5, 5)
        advanced_layout.setSpacing(8)
        
        # X offset adjustment
        x_offset_layout = QHBoxLayout()
        x_offset_layout.setSpacing(5)  # Explicit spacing
        x_offset_label = QLabel("X Offset:")
        # Set fixed width for label so Y label aligns beneath it
        x_offset_label.setFixedWidth(70)
        x_offset_layout.addWidget(x_offset_label)
        
        self.x_offset_spinbox = QSpinBox()
        self.x_offset_spinbox.setMinimum(-500)
        self.x_offset_spinbox.setMaximum(500)
        self.x_offset_spinbox.setValue(0)
        self.x_offset_spinbox.setSingleStep(1)
        # No unit suffix; the combo box indicates current unit.
        x_offset_layout.addWidget(self.x_offset_spinbox, 1)

        # Shared unit selector for X/Y offsets (mm or pixels). This controls how
        # the spinbox values are interpreted and displayed; internal storage is
        # always in pixels.
        self.offset_unit_combo = QComboBox()
        self.offset_unit_combo.addItems(["mm", "px"])
        self.offset_unit_combo.setCurrentText("mm")
        # Keep the combo visually compact next to the spinbox. Use fixed width
        # so we can match it exactly with a placeholder widget in the Y row.
        combo_width = 70
        self.offset_unit_combo.setFixedWidth(combo_width)
        x_offset_layout.addWidget(self.offset_unit_combo)
        
        advanced_layout.addLayout(x_offset_layout)
        
        # Y offset adjustment
        y_offset_layout = QHBoxLayout()
        y_offset_layout.setSpacing(5)  # Match X layout spacing
        y_offset_label = QLabel("Y Offset:")
        # Match X label width so spinboxes align vertically
        y_offset_label.setFixedWidth(70)
        y_offset_layout.addWidget(y_offset_label)
        
        self.y_offset_spinbox = QSpinBox()
        self.y_offset_spinbox.setMinimum(-500)
        self.y_offset_spinbox.setMaximum(500)
        self.y_offset_spinbox.setValue(0)
        self.y_offset_spinbox.setSingleStep(1)
        # Match X spinbox width so the numeric fields align vertically.
        y_offset_layout.addWidget(self.y_offset_spinbox, 1)
        
        # Add placeholder widget to match the combo box width exactly so Y spinbox aligns with X spinbox
        placeholder = QWidget()
        placeholder.setFixedWidth(combo_width)
        y_offset_layout.addWidget(placeholder)

        # Ensure X/Y spinboxes share the same width for a clean layout.
        spinbox_width = max(
            self.x_offset_spinbox.sizeHint().width(),
            self.y_offset_spinbox.sizeHint().width(),
        )
        self.x_offset_spinbox.setFixedWidth(spinbox_width)
        self.y_offset_spinbox.setFixedWidth(spinbox_width)

        advanced_layout.addLayout(y_offset_layout)
        
        # Reset button
        from PySide6.QtWidgets import QPushButton
        self.reset_offset_button = QPushButton("Reset to Calculated")
        self.reset_offset_button.clicked.connect(self._on_reset_offset_clicked)
        advanced_layout.addWidget(self.reset_offset_button)

        # Calculated offset display (always reported in pixels)
        self.calculated_offset_label = QLabel("2D Calculated Offset: X=0.0, Y=0.0 pixels")
        self.calculated_offset_label.setStyleSheet("font-size: 10pt; color: #555;")
        advanced_layout.addWidget(self.calculated_offset_label)
        
        # Scaling factors display
        self.scaling_factors_label = QLabel("2D Calculated Scaling: X=1.00, Y=1.00")
        self.scaling_factors_label.setStyleSheet("font-size: 10pt; color: #555;")
        advanced_layout.addWidget(self.scaling_factors_label)

        # Spacing / conversion info (small text at very bottom of the fusion widget)
        self.spacing_info_label = QLabel("")
        self.spacing_info_label.setStyleSheet("font-size: 9pt; color: #777;")
        self.spacing_info_label.setWordWrap(True)
        advanced_layout.addWidget(self.spacing_info_label)
        
        group_layout.addWidget(self.advanced_group)
        
        # Store calculated offset for reset functionality (always in pixels)
        self._calculated_offset_x = 0.0
        self._calculated_offset_y = 0.0
        
        # Track if user manually modified the offset
        self._user_modified_offset = False
        
        layout.addWidget(group_box)
        layout.addStretch()
    
    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        # Base series is read-only display, no signal connection needed
        self.overlay_series_combo.currentIndexChanged.connect(self._on_overlay_series_changed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        self.overlay_window_spinbox.valueChanged.connect(self._on_overlay_wl_changed)
        self.overlay_level_spinbox.valueChanged.connect(self._on_overlay_wl_changed)
        self.x_offset_spinbox.valueChanged.connect(self._on_translation_offset_changed)
        self.y_offset_spinbox.valueChanged.connect(self._on_translation_offset_changed)
        if hasattr(self, "offset_unit_combo"):
            self.offset_unit_combo.currentTextChanged.connect(self._on_offset_unit_changed)
        self.resampling_mode_group.buttonClicked.connect(self._on_resampling_mode_changed)
        self.interpolation_combo.currentTextChanged.connect(self._on_interpolation_method_changed)
    
    def _on_enable_toggled(self, checked: bool) -> None:
        """Handle enable checkbox toggle."""
        self._set_controls_enabled(checked)
        if not self._updating:
            self.fusion_enabled_changed.emit(checked)
    
    # Base series is read-only, so no handler needed for user changes
    # (Base is set programmatically based on current viewing series)
    
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
        if self._updating:
            return

        # Mark that user has manually modified the offset
        display_x = float(self.x_offset_spinbox.value())
        display_y = float(self.y_offset_spinbox.value())

        if self._offset_unit == "mm" and self._can_use_mm:
            x_px, y_px = self._mm_to_pixels(display_x, display_y)
        else:
            x_px, y_px = display_x, display_y

        self._user_modified_offset = True
        self._calculated_offset_x = x_px
        self._calculated_offset_y = y_px
        print(f"[OFFSET DEBUG] User changed offset to: X={x_px:.1f}px, Y={y_px:.1f}px")
        self.translation_offset_changed.emit(x_px, y_px)
    
    def _on_reset_offset_clicked(self) -> None:
        """Handle reset offset button click."""
        # Reset the user-modified flag since we're resetting to calculated
        self._user_modified_offset = False

        # Ensure internal offsets remain the stored calculated pixel offsets
        x_px = float(self._calculated_offset_x)
        y_px = float(self._calculated_offset_y)

        # Update spinboxes from internal pixel offsets according to current unit
        self._update_offset_spinboxes_from_pixels()

        print(f"[OFFSET DEBUG] Reset to calculated offset: X={x_px:.1f}px, Y={y_px:.1f}px")
        # Emit signal with calculated values (always in pixels)
        self.translation_offset_changed.emit(x_px, y_px)
    
    def _on_resampling_mode_changed(self, button: QRadioButton) -> None:
        """Handle resampling mode change."""
        if self._updating:
            return
        
        if button == self.fast_mode_radio:
            mode = 'fast'
        elif button == self.high_accuracy_mode_radio:
            mode = 'high_accuracy'
        else:
            return  # Should not happen, but handle gracefully
        
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
        # Hide/show overlay series selector when fusion is disabled
        self.overlay_series_widget.setVisible(enabled)
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
        self.fast_mode_radio.setEnabled(enabled)
        self.high_accuracy_mode_radio.setEnabled(enabled)
        self.interpolation_combo.setEnabled(enabled)
        
        # Overlay Window/Level controls
        self.window_level_widget.setVisible(enabled)
        self.overlay_window_spinbox.setEnabled(enabled)
        self.overlay_level_spinbox.setEnabled(enabled)
        
        # Spatial Alignment
        self.advanced_group.setVisible(enabled)
        self.x_offset_spinbox.setEnabled(enabled)
        self.y_offset_spinbox.setEnabled(enabled)
        self.reset_offset_button.setEnabled(enabled)
        if hasattr(self, "offset_unit_combo"):
            # Unit combo is only meaningful when mm spacing is available AND not in 3D mode
            self.offset_unit_combo.setEnabled(enabled and self._can_use_mm and not self._use_3d_mode)
    
    def set_offset_controls_enabled(self, enabled: bool) -> None:
        """
        Enable or disable offset controls independently of fusion enable state.
        
        Used to disable offset controls when 3D resampling is active (since 3D
        resampling handles alignment automatically and offset is not applied).
        
        Args:
            enabled: True to enable offset controls, False to disable
        """
        if not hasattr(self, "x_offset_spinbox"):
            return
        
        # Only disable if fusion is enabled (if fusion is disabled, _on_enable_toggled handles it)
        if self.enable_checkbox.isChecked():
            self.x_offset_spinbox.setEnabled(enabled)
            self.y_offset_spinbox.setEnabled(enabled)
            self.reset_offset_button.setEnabled(enabled)
            if hasattr(self, "offset_unit_combo"):
                # When disabled (3D mode), explicitly disable the dropdown regardless of _can_use_mm
                # When enabled (2D mode), enable based on mm availability
                if enabled:
                    self.offset_unit_combo.setEnabled(self._can_use_mm)
                else:
                    # Explicitly disable in 3D mode
                    self.offset_unit_combo.setEnabled(False)
        
        # Only set status to "Disabled" if fusion itself is disabled, not just offset controls
        # Offset controls can be disabled when 3D resampling is active, but fusion is still enabled
        if not enabled and not self.enable_checkbox.isChecked():
            # When fusion is disabled, record this in the scrollable status log
            # so the user can see when fusion was turned off.
            self.set_status("Disabled", severity="info")
    
    def update_series_lists(
        self,
        series_list: List[Tuple[str, str]],
        current_base_uid: str = "",
        current_overlay_uid: str = ""
    ) -> None:
        """
        Update the overlay series dropdown list.
        Base series is read-only display, updated via set_base_display().
        
        Args:
            series_list: List of (series_uid, display_name) tuples
            current_base_uid: Current base series UID (for display, not selection)
            current_overlay_uid: Current overlay series UID to select
        """
        # DEBUG
        # print(f"[FUSION CONTROLS DEBUG] update_series_lists called with {len(series_list)} series")
        
        self._updating = True
        
        # Save current overlay selection
        prev_overlay = self.overlay_series_combo.currentData()
        
        # Clear existing items (only overlay, base is read-only)
        self.overlay_series_combo.clear()
        
        # print(f"[FUSION CONTROLS DEBUG] Cleared overlay dropdown, now adding {len(series_list)} items")
        
        # Insert placeholder when there is no current or previous overlay
        placeholder_index = -1
        if not current_overlay_uid and not prev_overlay:
            self.overlay_series_combo.addItem("Empty - Please Select", "")
            placeholder_index = 0
        
        # Add series to overlay combo only
        for series_uid, display_name in series_list:
            # print(f"[FUSION CONTROLS DEBUG]   Adding: {display_name}")
            self.overlay_series_combo.addItem(display_name, series_uid)
        
        # Restore or set overlay selection
        if current_overlay_uid:
            index = self.overlay_series_combo.findData(current_overlay_uid)
            if index >= 0:
                self.overlay_series_combo.setCurrentIndex(index)
        elif prev_overlay:
            index = self.overlay_series_combo.findData(prev_overlay)
            if index >= 0:
                self.overlay_series_combo.setCurrentIndex(index)
        elif placeholder_index >= 0:
            self.overlay_series_combo.setCurrentIndex(placeholder_index)
        
        self._updating = False
    
    def set_status(self, status_text: str, severity: str = "info") -> None:
        """
        Update fusion status display.
        
        This appends the message to the scrollable status log that lives
        directly beneath the overlay series dropdown. All fusion status
        messages (info/warning/error) should flow through this method.
        
        Args:
            status_text: Status text to display
            severity: Severity level - "info", "warning", or "error"
        """
        # Append message to scrollable log, tagging severity. Normal messages
        # use a theme-aware text color (black on light backgrounds, white on
        # dark backgrounds), warnings are yellow, and errors are red.
        if self.status_text_edit is not None:
            if severity == "error":
                prefix = "[ERROR] "
            elif severity == "warning":
                prefix = "[WARNING] "
            else:
                prefix = "[INFO] "
            
            # Move cursor to end and insert formatted text
            cursor = self.status_text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)

            # Add a newline if there is already content
            if self.status_text_edit.toPlainText():
                cursor.insertText("\n")

            # Get theme from config manager
            theme = "light"  # Default to light theme
            if self.config_manager is not None:
                theme = self.config_manager.get_theme()
            
            # Set colors based on theme and severity
            char_format = QTextCharFormat()
            if severity == "error":
                # Errors: theme-specific red
                if theme == "dark":
                    char_format.setForeground(QColor(255, 50, 50))  # Bright red for dark theme
                else:
                    char_format.setForeground(QColor(200, 0, 0))  # Dark red for light theme
            elif severity == "warning":
                # Warnings: theme-specific color
                if theme == "dark":
                    char_format.setForeground(QColor(255, 200, 0))  # Yellow for dark theme
                else:
                    char_format.setForeground(QColor(255, 165, 0))  # Orange for light theme
            else:
                # Info: theme-specific text color
                if theme == "dark":
                    char_format.setForeground(QColor(255, 255, 255))  # White for dark theme
                else:
                    char_format.setForeground(QColor(0, 0, 0))  # Black for light theme

            cursor.insertText(f"{prefix}{status_text}", char_format)

            # Auto-scroll to the newest message
            self.status_text_edit.setTextCursor(cursor)
            self.status_text_edit.ensureCursorVisible()
    
    def clear_status(self) -> None:
        """
        Clear all messages from the fusion status box.
        """
        if self.status_text_edit is not None:
            self.status_text_edit.clear()
    
    def update_status_text_colors(self) -> None:
        """
        Update colors of all existing text in the fusion status box based on current theme.
        
        This method iterates through all text blocks in the status box, identifies
        severity prefixes ([INFO], [WARNING], [ERROR]), and applies theme-aware colors.
        Called when the theme changes to update already-printed text.
        """
        if self.status_text_edit is None:
            return
        
        # Get current theme from config manager
        theme = "light"  # Default to light theme
        if self.config_manager is not None:
            theme = self.config_manager.get_theme()
        
        # Get document and create cursor for iteration
        document = self.status_text_edit.document()
        if document is None:
            return
        
        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # Define color mapping based on theme and severity
        def get_color_for_severity(severity: str) -> QColor:
            """Get color for a given severity level based on current theme."""
            if severity == "error":
                if theme == "dark":
                    return QColor(255, 50, 50)  # Bright red for dark theme
                else:
                    return QColor(200, 0, 0)  # Dark red for light theme
            elif severity == "warning":
                if theme == "dark":
                    return QColor(255, 200, 0)  # Yellow for dark theme
                else:
                    return QColor(255, 165, 0)  # Orange for light theme
            else:  # info
                if theme == "dark":
                    return QColor(255, 255, 255)  # White for dark theme
                else:
                    return QColor(0, 0, 0)  # Black for light theme
        
        # Iterate through all blocks and update colors
        block = document.firstBlock()
        while block.isValid():
            block_text = block.text()
            
            # Check for severity prefixes in this block
            if "[ERROR]" in block_text:
                severity = "error"
                prefix = "[ERROR]"
            elif "[WARNING]" in block_text:
                severity = "warning"
                prefix = "[WARNING]"
            elif "[INFO]" in block_text:
                severity = "info"
                prefix = "[INFO]"
            else:
                # No prefix found, skip this block (shouldn't happen, but handle gracefully)
                block = block.next()
                continue
            
            # Find the position of the prefix in the block
            prefix_pos = block_text.find(prefix)
            if prefix_pos >= 0:
                # Calculate absolute position in document
                block_start = block.position()
                prefix_start = block_start + prefix_pos
                prefix_end = prefix_start + len(prefix)
                
                # Get the end of the block (or end of line if there's a newline)
                block_end = block_start + len(block_text)
                
                # Apply color to the entire line (from prefix to end of block)
                cursor.setPosition(prefix_start)
                cursor.setPosition(block_end, QTextCursor.MoveMode.KeepAnchor)
                
                # Create character format with appropriate color
                char_format = QTextCharFormat()
                char_format.setForeground(get_color_for_severity(severity))
                cursor.setCharFormat(char_format)
            
            block = block.next()
    
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
        # Store calculated offset internally in pixels
        self._calculated_offset_x = x
        self._calculated_offset_y = y
        self.calculated_offset_label.setText(f"2D Calculated Offset: X={x:.1f}, Y={y:.1f} pixels")
        
        print(f"[OFFSET DEBUG] set_calculated_offset called: X={x:.1f}, Y={y:.1f}")
        print(f"[OFFSET DEBUG]   Current spinbox values: X={self.x_offset_spinbox.value()}, Y={self.y_offset_spinbox.value()}")
        print(f"[OFFSET DEBUG]   User modified: {self._user_modified_offset}")
        
        # Update the spinboxes only if user hasn't manually modified them
        if not self._user_modified_offset:
            self._update_offset_spinboxes_from_pixels()
            print(f"[OFFSET DEBUG]   Updated spinboxes to calculated values (unit={self._offset_unit}, can_use_mm={self._can_use_mm})")
        else:
            print(f"[OFFSET DEBUG]   Keeping user-modified spinbox values")
    
    def set_scaling_factors(self, scale_x: float, scale_y: float) -> None:
        """
        Update display of scaling factors.
        
        Args:
            scale_x: Scaling factor in X direction
            scale_y: Scaling factor in Y direction
        """
        self.scaling_factors_label.setText(f"2D Calculated Scaling: X={scale_x:.2f}, Y={scale_y:.2f}")
    
    def get_translation_offset(self) -> Tuple[float, float]:
        """
        Get current translation offset from spinboxes.
        
        Returns:
            Tuple of (x_offset, y_offset) in pixels (internal representation)
        """
        display_x = float(self.x_offset_spinbox.value())
        display_y = float(self.y_offset_spinbox.value())

        if self._offset_unit == "mm" and self._can_use_mm:
            return self._mm_to_pixels(display_x, display_y)

        return (display_x, display_y)
    
    def has_user_modified_offset(self) -> bool:
        """Return True if user manually changed offset spinboxes."""
        return self._user_modified_offset
    
    def reset_user_modified_offset(self) -> None:
        """Clear user-modified flag so calculated offsets can overwrite spinboxes."""
        self._user_modified_offset = False

    # --- Offset spacing/unit helpers -------------------------------------------------

    def set_pixel_spacing(self, row_spacing_mm, col_spacing_mm, source: str | None) -> None:
        """
        Set pixel spacing information used for mm/px conversions.

        Args:
            row_spacing_mm: Row spacing (Y direction) in mm or None
            col_spacing_mm: Column spacing (X direction) in mm or None
            source: String describing spacing source (e.g. "pixel_spacing",
                    "fov_rows", "reconDiameter_cols"), or None
        """
        self._row_spacing_mm = row_spacing_mm
        self._col_spacing_mm = col_spacing_mm
        self._spacing_source = source
        self._can_use_mm = (
            self._row_spacing_mm is not None and self._col_spacing_mm is not None
        )

        # Enable/disable unit combo based on whether we can reliably convert to mm.
        # Also check if 3D mode is active (if so, keep it disabled)
        if hasattr(self, "offset_unit_combo"):
            # Only enable if mm is available AND 3D mode is not active
            self.offset_unit_combo.setEnabled(self._can_use_mm and not self._use_3d_mode)

            # If mm is no longer available, force display back to pixels.
            if not self._can_use_mm and self._offset_unit == "mm":
                self._offset_unit = "px"
                self.offset_unit_combo.setCurrentText("px")
                self._update_offset_spinboxes_from_pixels()

        # Update inline spacing/conversion description beneath Spatial Alignment.
        # Only update if not in 3D mode (3D mode message is set separately)
        if hasattr(self, "spacing_info_label") and not self._use_3d_mode:
            if self._can_use_mm and self._row_spacing_mm is not None and self._col_spacing_mm is not None:
                # Brief but explicit about what is being used.
                source_text = source or "unknown spacing source"
                self.spacing_info_label.setText(
                    f"Offset units: mm (row={self._row_spacing_mm:.3f} mm, "
                    f"col={self._col_spacing_mm:.3f} mm; source: {source_text})."
                )
            else:
                self.spacing_info_label.setText(
                    "Offset units: pixels only (no spacing available for mm)."
                )

    def _pixels_to_mm(self, x_px: float, y_px: float) -> Tuple[float, float]:
        """
        Convert pixel offsets (internal representation) to mm for display.
        """
        if not self._can_use_mm:
            return (x_px, y_px)

        col_spacing = self._col_spacing_mm or 1.0
        row_spacing = self._row_spacing_mm or 1.0
        x_mm = x_px * col_spacing
        y_mm = y_px * row_spacing
        return (x_mm, y_mm)

    def _mm_to_pixels(self, x_mm: float, y_mm: float) -> Tuple[float, float]:
        """
        Convert mm offsets (from UI) back to pixels (internal representation).
        """
        if not self._can_use_mm:
            return (x_mm, y_mm)

        col_spacing = self._col_spacing_mm or 1.0
        row_spacing = self._row_spacing_mm or 1.0
        x_px = x_mm / col_spacing
        y_px = y_mm / row_spacing
        return (x_px, y_px)

    def _on_offset_unit_changed(self, unit: str) -> None:
        """
        Handle change of offset display unit between mm and pixels.
        """
        if unit not in ("mm", "px"):
            return

        self._offset_unit = unit

        # Re-interpret current internal pixel offsets into the newly selected unit.
        self._update_offset_spinboxes_from_pixels()

    def _update_offset_spinboxes_from_pixels(self) -> None:
        """
        Update X/Y spinboxes from internal pixel offsets using current unit.
        """
        if not hasattr(self, "x_offset_spinbox") or not hasattr(self, "y_offset_spinbox"):
            return

        self._updating = True
        try:
            x_px = float(self._calculated_offset_x)
            y_px = float(self._calculated_offset_y)

            if self._offset_unit == "mm" and self._can_use_mm:
                x_mm, y_mm = self._pixels_to_mm(x_px, y_px)
                # One decimal place for mm display
                self.x_offset_spinbox.setValue(round(x_mm * 10) / 10.0)
                self.y_offset_spinbox.setValue(round(y_mm * 10) / 10.0)
            else:
                # Display in integer pixels
                self.x_offset_spinbox.setValue(int(round(x_px)))
                self.y_offset_spinbox.setValue(int(round(y_px)))
        finally:
            self._updating = False
    
    def get_resampling_mode(self) -> str:
        """Get current resampling mode ('fast', 'high_accuracy')."""
        if self.fast_mode_radio.isChecked():
            return 'fast'
        elif self.high_accuracy_mode_radio.isChecked():
            return 'high_accuracy'
        return 'high_accuracy'  # Default to high_accuracy instead of auto
    
    def set_resampling_mode(self, mode: str) -> None:
        """
        Set resampling mode.
        
        Args:
            mode: 'fast' or 'high_accuracy'
        """
        self._updating = True
        if mode == 'fast':
            self.fast_mode_radio.setChecked(True)
        elif mode == 'high_accuracy':
            self.high_accuracy_mode_radio.setChecked(True)
        else:
            # Default to high_accuracy for unknown modes
            self.high_accuracy_mode_radio.setChecked(True)
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
        Update resampling warning display.
        
        Args:
            mode_display: Mode display string (e.g., "Fast Mode (2D)" or "High Accuracy (3D)")
            reason: Reason string (e.g., "Compatible: same orientation")
            show_warning: Whether to show warning label
            warning_text: Warning text to display
        """
        # Show/hide warning only; summary text is handled by the main status log.
        if show_warning and warning_text:
            self.resampling_warning_label.setText(warning_text)
            self.resampling_warning_label.setVisible(True)
        else:
            self.resampling_warning_label.clear()
            self.resampling_warning_label.setVisible(False)
    
    def set_offset_status_text(self, use_3d_mode: bool) -> None:
        """
        Update the offset status text at the bottom of the fusion controls.
        
        Args:
            use_3d_mode: True if 3D resampling mode is active, False if 2D mode
        """
        if not hasattr(self, "spacing_info_label"):
            return
        
        # Track 3D mode state
        self._use_3d_mode = use_3d_mode
        
        # Update dropdown state based on 3D mode (must happen after _use_3d_mode is set)
        if hasattr(self, "offset_unit_combo"):
            if use_3d_mode:
                # Explicitly disable in 3D mode
                self.offset_unit_combo.setEnabled(False)
            else:
                # Enable based on mm availability in 2D mode
                self.offset_unit_combo.setEnabled(self._can_use_mm)
        
        if use_3d_mode:
            # 3D mode: alignment is automatic via DICOM metadata and SimpleITK resampling
            self.spacing_info_label.setText(
                "3D Fusion enabled - offsets and scaling determined by the SimpleITK resampling algorithm from ImagePositionPatient and pixel spacing metadata"
            )
        else:
            # 2D mode: show normal offset unit information
            if self._can_use_mm and self._row_spacing_mm is not None and self._col_spacing_mm is not None:
                source_text = self._spacing_source or "unknown spacing source"
                self.spacing_info_label.setText(
                    f"Offset units: mm (row={self._row_spacing_mm:.3f} mm, "
                    f"col={self._col_spacing_mm:.3f} mm; source: {source_text})."
                )
            else:
                self.spacing_info_label.setText(
                    "Offset units: pixels only (no spacing available for mm)."
                )

