"""
Quick Window/Level Dialog

Provides a minimal dialog for entering window center and width values
(e.g. for CT window/level). User can type center, Tab to width, then Enter or OK to apply.

Inputs:
    - Initial window center and width (optional)
    - Center and width value ranges (from current view's WL controls)
    - Optional unit string for labels (e.g. "HU")

Outputs:
    - On OK: invokes apply_callback(center, width) with the entered values

Requirements:
    - PySide6 for dialog and spinboxes
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from gui.wl_preset_menu import WLPresetMenuContext


class QuickWindowLevelDialog(QDialog):
    """
    Small modal dialog to enter window center and width.
    Tab moves from center to width; Enter or OK applies, Escape cancels.
    """

    def __init__(
        self,
        parent=None,
        initial_center: float | None = None,
        initial_width: float | None = None,
        center_range: tuple[float, float] = (-10000.0, 10000.0),
        width_range: tuple[float, float] = (1.0, 10000.0),
        apply_callback: Callable[[float, float], None] | None = None,
        unit: str | None = None,
        on_preset_select: Callable[[int], None] | None = None,
        get_wl_preset_menu_context: Callable[[], "WLPresetMenuContext"] | None = None,
        get_legacy_wl_presets: Callable[[], list[Any]] | None = None,
        on_manage_wl_presets: Callable[[], None] | None = None,
    ):
        """
        Initialize the quick window/level dialog.

        Args:
            parent: Parent widget
            initial_center: Pre-fill value for window center (or None for 0)
            initial_width: Pre-fill value for window width (or None for 400)
            center_range: (min, max) for window center spinbox
            width_range: (min, max) for window width spinbox
            apply_callback: Called on OK with (center, width)
            unit: Optional unit string for labels (e.g. "HU")
            on_preset_select: Called with preset index when user picks a preset
            get_wl_preset_menu_context: Builds WLPresetMenuContext for the focused pane
            get_legacy_wl_presets: Fallback legacy preset tuples
            on_manage_wl_presets: Opens Manage W/L Presets dialog
        """
        super().__init__(parent)
        self.setWindowTitle("Quick Window/Level")
        self.setModal(True)
        self._apply_callback = apply_callback
        self._on_preset_select = on_preset_select

        center = initial_center if initial_center is not None else 0.0
        width = initial_width if initial_width is not None else 400.0

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Window Center
        self._center_label = QLabel(f"Window Center ({unit}):" if unit else "Window Center:")
        layout.addWidget(self._center_label)
        self._center_spinbox = QDoubleSpinBox()
        self._center_spinbox.setRange(*center_range)
        self._center_spinbox.setValue(center)
        self._center_spinbox.setDecimals(1)
        self._center_spinbox.setSingleStep(1.0)
        layout.addWidget(self._center_spinbox)

        # Window Width
        self._width_label = QLabel(f"Window Width ({unit}):" if unit else "Window Width:")
        layout.addWidget(self._width_label)
        self._width_spinbox = QDoubleSpinBox()
        self._width_spinbox.setRange(*width_range)
        self._width_spinbox.setValue(width)
        self._width_spinbox.setDecimals(1)
        self._width_spinbox.setSingleStep(1.0)
        layout.addWidget(self._width_spinbox)

        if on_preset_select is not None:
            presets_row = QHBoxLayout()
            presets_row.addStretch()
            from gui.wl_preset_menu import create_wl_presets_menu_button

            def _on_preset_chosen(index: int) -> None:
                if self._on_preset_select:
                    self._on_preset_select(index)
                self.accept()

            presets_btn = create_wl_presets_menu_button(
                self,
                on_select=_on_preset_chosen,
                get_context=get_wl_preset_menu_context,
                get_legacy_presets=get_legacy_wl_presets,
                on_manage=on_manage_wl_presets,
                label="Presets…",
                tooltip="Apply a window/level preset to the focused pane",
            )
            presets_row.addWidget(presets_btn)
            layout.addLayout(presets_row)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._center_spinbox.setFocus()

    def _on_accept(self) -> None:
        """Apply values and close."""
        center = self._center_spinbox.value()
        width = self._width_spinbox.value()
        if width <= 0:
            width = 1.0
        if self._apply_callback:
            self._apply_callback(center, width)
        self.accept()
