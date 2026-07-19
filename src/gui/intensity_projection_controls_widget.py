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

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_PROJ_LABEL_AIP = "Average (AIP)"
_PROJ_LABEL_MIP = "Maximum (MIP)"
_PROJ_LABEL_MINIP = "Minimum (MinIP)"
_PROJ_LABELS = (_PROJ_LABEL_AIP, _PROJ_LABEL_MIP, _PROJ_LABEL_MINIP)
_PROJ_LABEL_TO_TYPE = {
    _PROJ_LABEL_AIP: "aip",
    _PROJ_LABEL_MIP: "mip",
    _PROJ_LABEL_MINIP: "minip",
}
_PROJ_TYPE_TO_LABEL = {
    "aip": _PROJ_LABEL_AIP,
    "mip": _PROJ_LABEL_MIP,
    "minip": _PROJ_LABEL_MINIP,
}

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

        # Projection type selector (wrapped for visibility control)
        self.projection_widget = QWidget()
        projection_container_layout = QVBoxLayout(self.projection_widget)
        projection_container_layout.setContentsMargins(0, 0, 0, 0)
        projection_container_layout.setSpacing(0)

        projection_layout = QHBoxLayout()
        projection_label = QLabel("Projection:")
        projection_layout.addWidget(projection_label)

        self.projection_combo = QComboBox()
        self.projection_combo.addItems(list(_PROJ_LABELS))
        self.projection_combo.setCurrentText(_PROJ_LABEL_AIP)
        self.projection_combo.setToolTip("Select projection type")
        self.projection_combo.currentTextChanged.connect(self._on_projection_type_changed)
        projection_layout.addWidget(self.projection_combo)

        projection_container_layout.addLayout(projection_layout)
        group_layout.addWidget(self.projection_widget)

        # Slice count selector (wrapped for visibility control)
        self.slice_count_widget = QWidget()
        count_container_layout = QVBoxLayout(self.slice_count_widget)
        count_container_layout.setContentsMargins(0, 0, 0, 0)
        count_container_layout.setSpacing(0)

        count_layout = QHBoxLayout()
        count_label = QLabel("Slices:")
        count_layout.addWidget(count_label)

        self.slice_count_combo = QComboBox()
        self.slice_count_combo.addItems(["2", "3", "4", "6", "8"])
        self.slice_count_combo.setCurrentText("4")
        self.slice_count_combo.setToolTip("Number of slices to combine")
        self.slice_count_combo.currentTextChanged.connect(self._on_slice_count_changed)
        count_layout.addWidget(self.slice_count_combo)

        count_container_layout.addLayout(count_layout)
        group_layout.addWidget(self.slice_count_widget)

        layout.addWidget(group_box)

    def _on_enable_changed(self, state: int) -> None:
        """Handle enable checkbox state change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self._set_controls_enabled(enabled)
        self.enabled_changed.emit(enabled)

    def _on_projection_type_changed(self, text: str) -> None:
        """Handle projection type dropdown change."""
        # Map display text to internal type
        type_map = _PROJ_LABEL_TO_TYPE
        projection_type = type_map.get(text, "aip")
        self.projection_type_changed.emit(projection_type)

    def _on_slice_count_changed(self, text: str) -> None:
        """Handle slice count dropdown change."""
        try:
            count = int(text)
            self.slice_count_changed.emit(count)
        except (ValueError, AttributeError):
            return  # Ignore non-integer combo text

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

    def set_enabled(self, enabled: bool, keep_signals_blocked: bool = False) -> None:
        """
        Set enable checkbox state.
        
        Args:
            enabled: True to enable, False to disable
            keep_signals_blocked: If True, don't unblock signals at the end (caller will handle it)
        """
        self.enable_checkbox.checkState()
        self.isVisible()
        self.isEnabled()
        self.enable_checkbox.isVisible()
        self.enable_checkbox.isEnabled()

        # Always update checkbox visual state (may be out of sync even when
        # checked state already equals enabled).

        # Block signals to prevent recursive updates
        was_blocked = self.enable_checkbox.signalsBlocked()
        self.enable_checkbox.blockSignals(True)

        # Use setCheckState to ensure proper state update
        check_state = Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        self.enable_checkbox.setCheckState(check_state)
        self.enable_checkbox.isChecked()

        # Also use setChecked as a backup to ensure state is set
        self.enable_checkbox.setChecked(enabled)
        self.enable_checkbox.isChecked()

        self._set_controls_enabled(enabled)

        # Restore signal blocking state only if caller didn't ask us to keep them blocked
        if not keep_signals_blocked and not was_blocked:
            # Before unblocking, verify the state is correct
            verify_state = self.enable_checkbox.isChecked()

            # Only unblock if state matches what we set it to
            if verify_state == enabled:
                self.enable_checkbox.blockSignals(False)
            # else: state doesn't match — keep signals blocked

        # Force immediate repaint to ensure visual state is refreshed
        # Use QTimer to ensure update happens after current event processing
        QTimer.singleShot(0, lambda: (
            self.enable_checkbox.repaint(),
            self.repaint()
        ))

        # DEBUG: Final state check
        self.enable_checkbox.isChecked()

    def set_projection_type(self, projection_type: str) -> None:
        """
        Set projection type dropdown.
        
        Args:
            projection_type: "aip", "mip", or "minip"
        """
        type_map = _PROJ_TYPE_TO_LABEL
        display_text = type_map.get(projection_type, _PROJ_LABEL_AIP)
        if display_text in _PROJ_LABELS:
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
        type_map = _PROJ_LABEL_TO_TYPE
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

