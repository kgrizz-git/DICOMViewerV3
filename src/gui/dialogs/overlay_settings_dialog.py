"""
Overlay Settings Dialog

This module provides a dialog for customizing overlay font size and color.

Inputs:
    - User preference changes
    
Outputs:
    - Updated overlay configuration settings
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QSpinBox, QColorDialog, QGroupBox,
                                QFormLayout, QDialogButtonBox, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import Optional

from utils.config_manager import ConfigManager
from utils.bundled_fonts import get_font_families, get_font_variants


class OverlaySettingsDialog(QDialog):
    """
    Dialog for customizing overlay font size and color.

    Provides:
    - Overlay font size customization (live preview as value changes)
    - Overlay font color customization (live preview after color picker closes)

    Signals:
        settings_applied: Emitted when the user confirms with OK.
        settings_changed: Emitted on every interactive change (live preview).
            Both signals trigger the same overlay-refresh pipeline; the caller
            should connect both to the same callback.

    Cancel behaviour: on reject() the original values are restored to
    ConfigManager and settings_changed is emitted once so the overlay reverts.
    """

    # Emitted on OK (final confirmation)
    settings_applied = Signal()
    # Emitted on every live change (font-size step, colour pick)
    settings_changed = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        Initialize the overlay settings dialog.

        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)

        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log

        self.config_manager = config_manager
        self.setWindowTitle("Overlay Settings")
        self.setModal(True)
        self.resize(420, 260)

        # Store original values so we can revert on Cancel
        self._original_font_size = config_manager.get_overlay_font_size()
        self._original_font_color = config_manager.get_overlay_font_color()
        self._original_font_family = config_manager.get_overlay_font_family()
        self._original_font_variant = config_manager.get_overlay_font_variant()

        if DEBUG_FONT_VARIANT:
            debug_log(
                "overlay_settings_dialog.py:__init__",
                "Overlay settings dialog constructed",
                {
                    "original_font_size": self._original_font_size,
                    "original_font_color": self._original_font_color,
                    "original_font_family": self._original_font_family,
                    "original_font_variant": self._original_font_variant,
                },
                hypothesis_id="FONTVAR",
            )

        self._create_ui()
        self._load_settings()

        # Live preview: update overlay as font size, family, or variant is adjusted
        self.font_size_spinbox.valueChanged.connect(self._on_live_update)
        self.font_family_combo.currentIndexChanged.connect(self._on_family_changed)
        self.font_variant_combo.currentIndexChanged.connect(self._on_live_update)

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)

        # Overlay Settings Group
        overlay_group = QGroupBox("Overlay Settings")
        overlay_layout = QFormLayout()

        # Font Size
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(1, 24)
        self.font_size_spinbox.setValue(10)
        self.font_size_spinbox.setSuffix(" pt")
        overlay_layout.addRow("Font Size:", self.font_size_spinbox)

        # Font Family
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(get_font_families())
        overlay_layout.addRow("Font:", self.font_family_combo)

        # Font Variant
        self.font_variant_combo = QComboBox()
        overlay_layout.addRow("Variant:", self.font_variant_combo)

        # Font Color
        color_layout = QHBoxLayout()
        self.color_label = QLabel()
        self.color_label.setMinimumSize(50, 30)
        self.color_label.setStyleSheet("background-color: rgb(255, 255, 0); border: 1px solid black;")
        self.color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        color_button = QPushButton("Choose Color...")
        color_button.clicked.connect(self._choose_color)

        color_layout.addWidget(self.color_label)
        color_layout.addWidget(color_button)
        color_layout.addStretch()

        overlay_layout.addRow("Font Color:", color_layout)

        overlay_group.setLayout(overlay_layout)
        layout.addWidget(overlay_group)

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._apply_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        """Load current settings into the dialog."""
        # Block valueChanged so the initial load does not trigger a live update
        self.font_size_spinbox.blockSignals(True)
        font_size = self.config_manager.get_overlay_font_size()
        self.font_size_spinbox.setValue(font_size)
        self.font_size_spinbox.blockSignals(False)

        self.font_family_combo.blockSignals(True)
        current_family = self.config_manager.get_overlay_font_family()
        idx = self.font_family_combo.findText(current_family)
        if idx >= 0:
            self.font_family_combo.setCurrentIndex(idx)
        self.font_family_combo.blockSignals(False)

        self._populate_variant_combo(current_family, self.config_manager.get_overlay_font_variant())

        r, g, b = self.config_manager.get_overlay_font_color()
        self._update_color_display(r, g, b)
        self.current_color = (r, g, b)

    def _populate_variant_combo(self, family: str, current_variant: str = "Bold") -> None:
        """Repopulate the variant combo for *family*, preserving the selection when possible."""
        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        self.font_variant_combo.blockSignals(True)
        self.font_variant_combo.clear()
        variants = get_font_variants(family)
        self.font_variant_combo.addItems(variants)
        idx = self.font_variant_combo.findText(current_variant)
        self.font_variant_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.font_variant_combo.blockSignals(False)
        if DEBUG_FONT_VARIANT:
            debug_log(
                "overlay_settings_dialog.py:_populate_variant_combo",
                "Populated overlay font variant combo",
                {
                    "family": family,
                    "requested_variant": current_variant,
                    "variants": variants,
                    "selected_index": idx if idx >= 0 else 0,
                    "selected_variant": self.font_variant_combo.currentText(),
                },
                hypothesis_id="FONTVAR",
            )

    def _on_family_changed(self) -> None:
        """When the family changes, repopulate variants then trigger a live update."""
        family = self.font_family_combo.currentText()
        current_variant = self.font_variant_combo.currentText()
        self._populate_variant_combo(family, current_variant)
        self._on_live_update()

    def _update_color_display(self, r: int, g: int, b: int) -> None:
        """
        Update the color display label.

        Args:
            r: Red component
            g: Green component
            b: Blue component
        """
        self.color_label.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        )

    def _choose_color(self) -> None:
        """Open color picker dialog and apply the chosen color as a live preview."""
        r, g, b = self.current_color
        color = QColorDialog.getColor(QColor(r, g, b), self, "Choose Overlay Font Color")

        if color.isValid():
            self.current_color = (color.red(), color.green(), color.blue())
            self._update_color_display(*self.current_color)
            # Apply live preview immediately after the colour is chosen
            self._on_live_update()

    def _on_live_update(self) -> None:
        """
        Save current values to config and emit settings_changed for live preview.

        Called on every spinbox step, combo selection, and immediately after a colour is picked.
        """
        from utils.debug_flags import DEBUG_FONT_VARIANT
        from utils.debug_log import debug_log
        if DEBUG_FONT_VARIANT:
            debug_log(
                "overlay_settings_dialog.py:_on_live_update",
                "Overlay settings live update",
                {
                    "family_combo": self.font_family_combo.currentText(),
                    "variant_combo": self.font_variant_combo.currentText(),
                    "font_size": self.font_size_spinbox.value(),
                },
                hypothesis_id="FONTVAR",
            )
        self.config_manager.set_overlay_font_size(self.font_size_spinbox.value())
        self.config_manager.set_overlay_font_family(self.font_family_combo.currentText())
        self.config_manager.set_overlay_font_variant(self.font_variant_combo.currentText())
        r, g, b = self.current_color
        self.config_manager.set_overlay_font_color(r, g, b)
        self.settings_changed.emit()

    def _apply_settings(self) -> None:
        """Persist settings, emit settings_applied, and close the dialog."""
        self.config_manager.set_overlay_font_size(self.font_size_spinbox.value())
        self.config_manager.set_overlay_font_family(self.font_family_combo.currentText())
        self.config_manager.set_overlay_font_variant(self.font_variant_combo.currentText())
        r, g, b = self.current_color
        self.config_manager.set_overlay_font_color(r, g, b)
        self.settings_applied.emit()
        self.accept()

    def reject(self) -> None:
        """Restore original values on Cancel so the live preview is reverted."""
        self.config_manager.set_overlay_font_size(self._original_font_size)
        self.config_manager.set_overlay_font_family(self._original_font_family)
        self.config_manager.set_overlay_font_variant(self._original_font_variant)
        r, g, b = self._original_font_color
        self.config_manager.set_overlay_font_color(r, g, b)
        self.settings_changed.emit()
        super().reject()
