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

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from gui.wl_preset_menu import WLPresetMenuContext


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
        self.center_range: tuple[float, float] = (-10000.0, 10000.0)
        self.width_range: tuple[float, float] = (1.0, 10000.0)
        self.unit: str | None = None  # Unit string (e.g., "HU") to display in labels

        self._create_ui()

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Window Center
        center_layout = QVBoxLayout()

        # Row 1: Label and Spinbox (horizontal)
        center_row1 = QHBoxLayout()
        self.center_label = QLabel("Window Center:")
        self.center_label.setMinimumWidth(100)
        center_row1.addWidget(self.center_label)

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
        self.width_label = QLabel("Window Width:")
        self.width_label.setMinimumWidth(100)
        width_row1.addWidget(self.width_label)

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

        self.wl_presets_button: QPushButton | None = None
        self._wl_presets_row: QHBoxLayout | None = None

    def attach_wl_presets_menu(
        self,
        *,
        on_select: Callable[[int], None],
        get_context: Callable[[], "WLPresetMenuContext"] | None = None,
        get_legacy_presets: Callable[[], list[Any]] | None = None,
        on_manage: Callable[[], None] | None = None,
        row_layout: QHBoxLayout | None = None,
    ) -> QPushButton:
        """
        Add a Presets… menu button on ``row_layout`` (right pane top row) or below sliders.

        Call once after main window exposes preset context callbacks.
        """
        from gui.wl_preset_menu import create_wl_presets_menu_button

        target_row = row_layout if row_layout is not None else self._ensure_presets_fallback_row()
        if self.wl_presets_button is not None:
            if self._wl_presets_row is not None:
                self._wl_presets_row.removeWidget(self.wl_presets_button)
            self.wl_presets_button.deleteLater()
        self._wl_presets_row = target_row
        self.wl_presets_button = create_wl_presets_menu_button(
            self,
            on_select=on_select,
            get_context=get_context,
            get_legacy_presets=get_legacy_presets,
            on_manage=on_manage,
            label="Presets…",
            tooltip="Window/Level presets for the focused image pane",
        )
        target_row.addWidget(self.wl_presets_button)
        return self.wl_presets_button

    def _ensure_presets_fallback_row(self) -> QHBoxLayout:
        """Legacy placement below sliders when no top-row layout is supplied."""
        if self._wl_presets_row is not None:
            return self._wl_presets_row
        row = QHBoxLayout()
        row.addStretch()
        cast(QVBoxLayout, self.layout()).addLayout(row)
        self._wl_presets_row = row
        return row

    @staticmethod
    def _padded_ranges(
        center_range: tuple[float, float],
        width_range: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Expand ranges so spinboxes/sliders are usable on all modalities.

        The raw pixel span can be very small (e.g. PT raw 0–1000) which caps
        the spinbox max and makes the slider useless.  We pad the center range
        by 25 % of the span on each side and ensure the width range max is at
        least 2× the span.  A minimum absolute range of 200 prevents
        near-zero-span data from collapsing the controls.
        """
        c_min, c_max = center_range
        span = c_max - c_min
        pad = max(span * 0.25, 100.0)  # at least 100 units of padding
        padded_center = (c_min - pad, c_max + pad)

        w_min, w_max = width_range
        padded_width = (w_min, max(w_max, span * 2.0, 200.0))

        return padded_center, padded_width

    def set_ranges(self, center_range: tuple[float, float], width_range: tuple[float, float]) -> None:
        """
        Set the value ranges for window center and width.

        Applies padding so the controls remain usable even when the pixel
        value span is small (e.g. PT/BQML data).

        Args:
            center_range: (min, max) for window center
            width_range: (min, max) for window width
        """
        center_range, width_range = self._padded_ranges(center_range, width_range)
        self.center_range = center_range
        self.width_range = width_range

        self.center_spinbox.setRange(*center_range)
        self.width_spinbox.setRange(*width_range)

        # Reposition sliders to reflect current values within new ranges
        self._update_slider_ranges()

    def _update_slider_ranges(self) -> None:
        """Reposition sliders to reflect current values within the new ranges."""
        self.center_slider.blockSignals(True)
        self.width_slider.blockSignals(True)

        center_range_size = self.center_range[1] - self.center_range[0]
        if center_range_size > 0:
            pos = int((self.window_center - self.center_range[0]) / center_range_size * 1000)
            self.center_slider.setValue(max(0, min(1000, pos)))
        else:
            self.center_slider.setValue(500)

        width_range_size = self.width_range[1] - self.width_range[0]
        if width_range_size > 0:
            pos = int((self.window_width - self.width_range[0]) / width_range_size * 1000)
            self.width_slider.setValue(max(1, min(1000, pos)))
        else:
            self.width_slider.setValue(100)

        self.center_slider.blockSignals(False)
        self.width_slider.blockSignals(False)

    def set_unit(self, unit: str | None) -> None:
        """
        Set unit string to display in labels.
        
        Args:
            unit: Unit string (e.g., "HU") or None to hide units
        """
        self.unit = unit
        # Update labels
        if unit:
            self.center_label.setText(f"Window Center ({unit}):")
            self.width_label.setText(f"Window Width ({unit}):")
        else:
            self.center_label.setText("Window Center:")
            self.width_label.setText("Window Width:")

    def set_window_level(self, center: float, width: float, block_signals: bool = False,
                        unit: str | None = None) -> None:
        """
        Set window center and width values.
        
        Args:
            center: Window center value
            width: Window width value
            block_signals: If True, don't emit window_changed signal
            unit: Optional unit string to update labels (if provided, updates unit)
        """
        # Update unit if provided
        if unit is not None:
            self.set_unit(unit)
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
        Handle window center value change from spinbox.

        Args:
            value: New center value
        """
        self.window_center = value
        # Sync slider position
        self.center_slider.blockSignals(True)
        center_range_size = self.center_range[1] - self.center_range[0]
        if center_range_size > 0:
            pos = int((value - self.center_range[0]) / center_range_size * 1000)
            self.center_slider.setValue(max(0, min(1000, pos)))
        self.center_slider.blockSignals(False)
        self.window_changed.emit(self.window_center, self.window_width)

    def _on_width_changed(self, value: float) -> None:
        """
        Handle window width value change from spinbox.

        Args:
            value: New width value
        """
        self.window_width = value
        # Sync slider position
        self.width_slider.blockSignals(True)
        width_range_size = self.width_range[1] - self.width_range[0]
        if width_range_size > 0:
            pos = int((value - self.width_range[0]) / width_range_size * 1000)
            self.width_slider.setValue(max(1, min(1000, pos)))
        self.width_slider.blockSignals(False)
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

    def get_window_level(self) -> tuple[float, float]:
        """
        Get current window center and width.
        
        Returns:
            Tuple of (center, width)
        """
        return (self.window_center, self.window_width)

