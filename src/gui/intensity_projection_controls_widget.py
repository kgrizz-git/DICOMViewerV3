"""
Intensity Projection Controls Widget

This module provides a widget for intensity projection controls.

Inputs:
    - User interactions (enable/disable, projection type, slice count)
    
Outputs:
    - Signals for projection control actions
    
Requirements:
    - PySide6 for GUI components
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QComboBox, QGroupBox, QCheckBox)
from PySide6.QtCore import Qt, Signal, QTimer


class IntensityProjectionControlsWidget(QWidget):
    """
    Widget for intensity projection controls.
    
    Features:
    - Enable/disable toggle
    - Projection type selector (AIP, MIP, MinIP)
    - Slice count selector (2, 3, 4, 6, 8)
    """
    
    # Signals
    enabled_changed = Signal(bool)  # Emitted when enable/disable state changes
    projection_type_changed = Signal(str)  # Emitted when projection type changes ("aip", "mip", "minip")
    slice_count_changed = Signal(int)  # Emitted when slice count changes (2, 3, 4, 6, or 8)
    
    def __init__(self, parent=None):
        """
        Initialize the intensity projection controls widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setObjectName("intensity_projection_controls_widget")
        
        self._create_ui()
        self._set_controls_enabled(False)
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Group box for visual grouping
        group_box = QGroupBox("Combine Slices")
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(5, 10, 5, 5)
        group_layout.setSpacing(5)
        
        # Enable/disable checkbox
        self.enable_checkbox = QCheckBox("Enable Combine Slices")
        self.enable_checkbox.setToolTip("Enable intensity projection mode")
        self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
        group_layout.addWidget(self.enable_checkbox)
        
<<<<<<< Updated upstream
        # Projection + slice controls section (wrapped for show/hide)
        self.projection_section_widget = QWidget()
        projection_section_layout = QVBoxLayout(self.projection_section_widget)
        projection_section_layout.setContentsMargins(0, 0, 0, 0)
        projection_section_layout.setSpacing(5)
        
        # Projection type selector
=======
        # Projection type selector (wrapped for visibility control)
        self.projection_widget = QWidget()
        projection_container_layout = QVBoxLayout(self.projection_widget)
        projection_container_layout.setContentsMargins(0, 0, 0, 0)
        projection_container_layout.setSpacing(0)
        
>>>>>>> Stashed changes
        projection_layout = QHBoxLayout()
        projection_label = QLabel("Projection:")
        projection_layout.addWidget(projection_label)
        
        self.projection_combo = QComboBox()
        self.projection_combo.addItems(["Average (AIP)", "Maximum (MIP)", "Minimum (MinIP)"])
        self.projection_combo.setCurrentText("Average (AIP)")
        self.projection_combo.setToolTip("Select projection type")
        self.projection_combo.currentTextChanged.connect(self._on_projection_type_changed)
        projection_layout.addWidget(self.projection_combo)
        
<<<<<<< Updated upstream
        projection_section_layout.addLayout(projection_layout)
=======
        projection_container_layout.addLayout(projection_layout)
        group_layout.addWidget(self.projection_widget)
        
        # Slice count selector (wrapped for visibility control)
        self.slice_count_widget = QWidget()
        count_container_layout = QVBoxLayout(self.slice_count_widget)
        count_container_layout.setContentsMargins(0, 0, 0, 0)
        count_container_layout.setSpacing(0)
>>>>>>> Stashed changes
        
        count_layout = QHBoxLayout()
        count_label = QLabel("Slices:")
        count_layout.addWidget(count_label)
        
        self.slice_count_combo = QComboBox()
        self.slice_count_combo.addItems(["2", "3", "4", "6", "8"])
        self.slice_count_combo.setCurrentText("4")
        self.slice_count_combo.setToolTip("Number of slices to combine")
        self.slice_count_combo.currentTextChanged.connect(self._on_slice_count_changed)
        count_layout.addWidget(self.slice_count_combo)
        
<<<<<<< Updated upstream
        projection_section_layout.addLayout(count_layout)
        
        group_layout.addWidget(self.projection_section_widget)
=======
        count_container_layout.addLayout(count_layout)
        group_layout.addWidget(self.slice_count_widget)
>>>>>>> Stashed changes
        
        layout.addWidget(group_box)
    
    def _on_enable_changed(self, state: int) -> None:
        """Handle enable checkbox state change."""
        enabled = (state == Qt.CheckState.Checked.value)
        # print(f"[DEBUG _on_enable_changed] Called from checkbox stateChanged signal: state={state}, enabled={enabled}")
        # print(f"[DEBUG _on_enable_changed] Checkbox.isChecked()={self.enable_checkbox.isChecked()}")
        self._set_controls_enabled(enabled)
        # print(f"[DEBUG _on_enable_changed] Emitting enabled_changed signal with enabled={enabled}")
        self.enabled_changed.emit(enabled)
        # print(f"[DEBUG _on_enable_changed] Signal emitted, checkbox.isChecked()={self.enable_checkbox.isChecked()}")
    
    def _on_projection_type_changed(self, text: str) -> None:
        """Handle projection type dropdown change."""
        # Map display text to internal type
        type_map = {
            "Average (AIP)": "aip",
            "Maximum (MIP)": "mip",
            "Minimum (MinIP)": "minip"
        }
        projection_type = type_map.get(text, "aip")
        self.projection_type_changed.emit(projection_type)
    
    def _on_slice_count_changed(self, text: str) -> None:
        """Handle slice count dropdown change."""
        try:
            count = int(text)
            self.slice_count_changed.emit(count)
        except (ValueError, AttributeError):
            pass
    
    def _set_controls_enabled(self, enabled: bool) -> None:
        """
        Enable or disable projection controls, and hide/show them.
        
        Args:
            enabled: True to enable and show controls, False to disable and hide
        """
        # Hide/show controls when disabled
        self.projection_widget.setVisible(enabled)
        self.projection_combo.setEnabled(enabled)
        
        self.slice_count_widget.setVisible(enabled)
        self.slice_count_combo.setEnabled(enabled)
        if hasattr(self, "projection_section_widget"):
            self.projection_section_widget.setVisible(enabled)
    
    def set_enabled(self, enabled: bool, keep_signals_blocked: bool = False) -> None:
        """
        Set enable checkbox state.
        
        Args:
            enabled: True to enable, False to disable
            keep_signals_blocked: If True, don't unblock signals at the end (caller will handle it)
        """
        # DEBUG: Log current state before change
        current_checked = self.enable_checkbox.isChecked()
        current_check_state = self.enable_checkbox.checkState()
        widget_visible = self.isVisible()
        widget_enabled = self.isEnabled()
        checkbox_visible = self.enable_checkbox.isVisible()
        checkbox_enabled = self.enable_checkbox.isEnabled()
        # print(f"[DEBUG set_enabled] Called with enabled={enabled}, keep_signals_blocked={keep_signals_blocked}")
        # print(f"[DEBUG set_enabled] Current state: isChecked={current_checked}, checkState={current_check_state}")
        # print(f"[DEBUG set_enabled] Widget visible={widget_visible}, enabled={widget_enabled}")
        # print(f"[DEBUG set_enabled] Checkbox visible={checkbox_visible}, enabled={checkbox_enabled}")
        
        # Check if state already matches - but still update to ensure visual state is correct
        # (needed for cases where checkbox state might be out of sync)
        if current_checked == enabled:
            # print(f"[DEBUG set_enabled] State already matches ({enabled}), but forcing update to ensure sync")
            # Don't return - continue to update to ensure visual state is correct
            pass
        
        # Block signals to prevent recursive updates
        was_blocked = self.enable_checkbox.signalsBlocked()
        self.enable_checkbox.blockSignals(True)
        
        # Use setCheckState to ensure proper state update
        check_state = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        self.enable_checkbox.setCheckState(check_state)
        after_setcheckstate = self.enable_checkbox.isChecked()
        # print(f"[DEBUG set_enabled] After setCheckState: isChecked={after_setcheckstate}")
        
        # Also use setChecked as a backup to ensure state is set
        self.enable_checkbox.setChecked(enabled)
        after_setchecked = self.enable_checkbox.isChecked()
        # print(f"[DEBUG set_enabled] After setChecked: isChecked={after_setchecked}")
        
        self._set_controls_enabled(enabled)
        
        # Restore signal blocking state only if caller didn't ask us to keep them blocked
        if not keep_signals_blocked and not was_blocked:
            # Before unblocking, verify the state is correct
            verify_state = self.enable_checkbox.isChecked()
            # print(f"[DEBUG set_enabled] Before unblocking: checkbox.isChecked()={verify_state}, target={enabled}")
            
            # Only unblock if state matches what we set it to
            if verify_state == enabled:
                self.enable_checkbox.blockSignals(False)
                # print(f"[DEBUG set_enabled] Unblocked signals (was_blocked={was_blocked}), state verified as {enabled}")
            else:
                # State doesn't match - something went wrong, keep signals blocked
                # print(f"[DEBUG set_enabled] ERROR: State mismatch! Expected {enabled}, got {verify_state}. Keeping signals blocked.")
                pass
        else:
            # print(f"[DEBUG set_enabled] Keeping signals blocked (keep_signals_blocked={keep_signals_blocked}, was_blocked={was_blocked})")
            pass
        
        # Force immediate repaint to ensure visual state is refreshed
        # Use QTimer to ensure update happens after current event processing
        QTimer.singleShot(0, lambda: (
            self.enable_checkbox.repaint(),
            self.repaint()
        ))
        
        # DEBUG: Final state check
        final_checked = self.enable_checkbox.isChecked()
        # print(f"[DEBUG set_enabled] Final state: isChecked={final_checked}")
    
    def set_projection_type(self, projection_type: str) -> None:
        """
        Set projection type dropdown.
        
        Args:
            projection_type: "aip", "mip", or "minip"
        """
        type_map = {
            "aip": "Average (AIP)",
            "mip": "Maximum (MIP)",
            "minip": "Minimum (MinIP)"
        }
        display_text = type_map.get(projection_type, "Average (AIP)")
        if display_text in ["Average (AIP)", "Maximum (MIP)", "Minimum (MinIP)"]:
            self.projection_combo.blockSignals(True)
            self.projection_combo.setCurrentText(display_text)
            self.projection_combo.blockSignals(False)
    
    def set_slice_count(self, count: int) -> None:
        """
        Set slice count dropdown.
        
        Args:
            count: Number of slices (2, 3, 4, 6, or 8)
        """
        count_text = str(count)
        if count_text in ["2", "3", "4", "6", "8"]:
            self.slice_count_combo.blockSignals(True)
            self.slice_count_combo.setCurrentText(count_text)
            self.slice_count_combo.blockSignals(False)
    
    def get_enabled(self) -> bool:
        """
        Get current enabled state.
        
        Returns:
            True if enabled, False otherwise
        """
        return self.enable_checkbox.isChecked()
    
    def get_projection_type(self) -> str:
        """
        Get current projection type.
        
        Returns:
            "aip", "mip", or "minip"
        """
        text = self.projection_combo.currentText()
        type_map = {
            "Average (AIP)": "aip",
            "Maximum (MIP)": "mip",
            "Minimum (MinIP)": "minip"
        }
        return type_map.get(text, "aip")
    
    def get_slice_count(self) -> int:
        """
        Get current slice count.
        
        Returns:
            Number of slices (2, 3, 4, 6, or 8)
        """
        try:
            return int(self.slice_count_combo.currentText())
        except (ValueError, AttributeError):
            return 4

