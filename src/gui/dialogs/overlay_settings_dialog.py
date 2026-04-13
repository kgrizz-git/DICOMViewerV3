"""
Overlay Settings Dialog

This module provides a dialog for customizing overlay font size/color and
viewer overlay element appearance.

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
    Dialog for customizing overlay font size/color and viewer overlay elements.

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
        self.resize(480, 420)

        # Store original values so we can revert on Cancel
        self._original_font_size = config_manager.get_overlay_font_size()
        self._original_font_color = config_manager.get_overlay_font_color()
        self._original_font_family = config_manager.get_overlay_font_family()
        self._original_font_variant = config_manager.get_overlay_font_variant()
        self._original_scale_markers_color = config_manager.get_scale_markers_color()
        self._original_direction_labels_color = config_manager.get_direction_labels_color()
        self._original_direction_label_size = config_manager.get_direction_label_size()
        self._original_major_tick_interval_mm = config_manager.get_scale_markers_major_tick_interval_mm()
        self._original_minor_tick_interval_mm = config_manager.get_scale_markers_minor_tick_interval_mm()
        self._original_show_scale_markers = config_manager.get_show_scale_markers()
        self._original_show_direction_labels = config_manager.get_show_direction_labels()
        self._original_slice_location_line_mode = config_manager.get_slice_location_line_mode()
        self._original_slice_location_line_width_px = (
            config_manager.get_slice_location_line_width_px()
        )

        if DEBUG_FONT_VARIANT:
            debug_log(
                "overlay_settings_dialog.py:__init__",
                "Overlay settings dialog constructed",
                {
                    "original_font_size": self._original_font_size,
                    "original_font_color": self._original_font_color,
                    "original_font_family": self._original_font_family,
                    "original_font_variant": self._original_font_variant,
                    "original_scale_markers_color": self._original_scale_markers_color,
                    "original_direction_labels_color": self._original_direction_labels_color,
                    "original_direction_label_size": self._original_direction_label_size,
                    "original_major_tick_interval_mm": self._original_major_tick_interval_mm,
                    "original_minor_tick_interval_mm": self._original_minor_tick_interval_mm,
                },
                hypothesis_id="FONTVAR",
            )

        self._create_ui()
        self._load_settings()

        # Live preview: update overlay as font size, family, or variant is adjusted
        self.font_size_spinbox.valueChanged.connect(self._on_live_update)
        self.font_family_combo.currentIndexChanged.connect(self._on_family_changed)
        self.font_variant_combo.currentIndexChanged.connect(self._on_live_update)
        self.direction_label_size_spinbox.valueChanged.connect(self._on_live_update)
        self.major_tick_interval_spinbox.valueChanged.connect(self._on_live_update)
        self.minor_tick_interval_spinbox.valueChanged.connect(self._on_live_update)
        self.slice_line_mode_combo.currentIndexChanged.connect(self._on_live_update)
        self.slice_line_width_spinbox.valueChanged.connect(self._on_live_update)

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

        viewer_overlay_group = QGroupBox("Viewer Overlay Elements")
        viewer_overlay_layout = QFormLayout()

        # Show/hide checkboxes
        from PySide6.QtWidgets import QCheckBox
        self.show_direction_labels_checkbox = QCheckBox("Show Direction Labels")
        self.show_scale_markers_checkbox = QCheckBox("Show Scale Markers")
        viewer_overlay_layout.addRow(self.show_direction_labels_checkbox)
        viewer_overlay_layout.addRow(self.show_scale_markers_checkbox)

        self.show_direction_labels_checkbox.stateChanged.connect(self._on_live_update)
        self.show_scale_markers_checkbox.stateChanged.connect(self._on_live_update)

        self.direction_label_size_spinbox = QSpinBox()
        self.direction_label_size_spinbox.setRange(6, 48)
        self.direction_label_size_spinbox.setValue(16)
        self.direction_label_size_spinbox.setSuffix(" pt")
        viewer_overlay_layout.addRow("Direction Label Size:", self.direction_label_size_spinbox)

        direction_color_layout = QHBoxLayout()
        self.direction_labels_color_label = QLabel()
        self.direction_labels_color_label.setMinimumSize(50, 30)
        self.direction_labels_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        direction_color_button = QPushButton("Choose Color...")
        direction_color_button.clicked.connect(self._choose_direction_labels_color)
        direction_color_layout.addWidget(self.direction_labels_color_label)
        direction_color_layout.addWidget(direction_color_button)
        direction_color_layout.addStretch()
        viewer_overlay_layout.addRow("Direction Labels Color:", direction_color_layout)

        scale_markers_color_layout = QHBoxLayout()
        self.scale_markers_color_label = QLabel()
        self.scale_markers_color_label.setMinimumSize(50, 30)
        self.scale_markers_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_markers_color_button = QPushButton("Choose Color...")
        scale_markers_color_button.clicked.connect(self._choose_scale_markers_color)
        scale_markers_color_layout.addWidget(self.scale_markers_color_label)
        scale_markers_color_layout.addWidget(scale_markers_color_button)
        scale_markers_color_layout.addStretch()
        viewer_overlay_layout.addRow("Scale Markers Color:", scale_markers_color_layout)

        self.major_tick_interval_spinbox = QSpinBox()
        self.major_tick_interval_spinbox.setRange(1, 100)
        self.major_tick_interval_spinbox.setValue(10)
        self.major_tick_interval_spinbox.setSuffix(" mm")
        viewer_overlay_layout.addRow("Major Tick Interval:", self.major_tick_interval_spinbox)

        self.minor_tick_interval_spinbox = QSpinBox()
        self.minor_tick_interval_spinbox.setRange(1, 100)
        self.minor_tick_interval_spinbox.setValue(5)
        self.minor_tick_interval_spinbox.setSuffix(" mm")
        viewer_overlay_layout.addRow("Minor Tick Interval:", self.minor_tick_interval_spinbox)

        # Help text for tick intervals
        from PySide6.QtWidgets import QLabel as QtLabel
        tick_help = QtLabel("<small>Major ticks are longer; minor ticks are shorter.</small>")
        tick_help.setTextFormat(Qt.TextFormat.RichText)
        viewer_overlay_layout.addRow(tick_help)

        viewer_overlay_group.setLayout(viewer_overlay_layout)
        layout.addWidget(viewer_overlay_group)

        # Slice Position Lines group
        slice_lines_group = QGroupBox("Slice Position Lines")
        slice_lines_layout = QFormLayout()

        self.slice_line_mode_combo = QComboBox()
        self.slice_line_mode_combo.addItem("Middle of Slice", "middle")
        self.slice_line_mode_combo.addItem("Begin and End of Slice (Slab Boundaries)", "begin_end")
        slice_lines_layout.addRow("Slice Position Line Mode:", self.slice_line_mode_combo)

        self.slice_line_width_spinbox = QSpinBox()
        self.slice_line_width_spinbox.setRange(1, 8)
        self.slice_line_width_spinbox.setValue(1)
        self.slice_line_width_spinbox.setToolTip(
            "Stroke width in pixels for lines showing where other windows' "
            "slice planes intersect this view (not DICOM slice thickness)."
        )
        slice_lines_layout.addRow("Slice Position Line Width (px):", self.slice_line_width_spinbox)

        mode_help = QLabel(
            "<small>Middle: one line at the centre plane. "
            "Begin/End: two lines at the slab boundaries "
            "(±½ slice thickness); falls back to Middle "
            "when thickness data is unavailable.</small>"
        )
        mode_help.setWordWrap(True)
        mode_help.setTextFormat(Qt.TextFormat.RichText)
        slice_lines_layout.addRow(mode_help)

        slice_lines_group.setLayout(slice_lines_layout)
        layout.addWidget(slice_lines_group)

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._apply_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        self.show_direction_labels_checkbox.blockSignals(True)
        self.show_scale_markers_checkbox.blockSignals(True)
        self.show_direction_labels_checkbox.setChecked(self.config_manager.get_show_direction_labels())
        self.show_scale_markers_checkbox.setChecked(self.config_manager.get_show_scale_markers())
        self.show_direction_labels_checkbox.blockSignals(False)
        self.show_scale_markers_checkbox.blockSignals(False)
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

        self.direction_label_size_spinbox.blockSignals(True)
        self.direction_label_size_spinbox.setValue(self.config_manager.get_direction_label_size())
        self.direction_label_size_spinbox.blockSignals(False)

        self.major_tick_interval_spinbox.blockSignals(True)
        self.major_tick_interval_spinbox.setValue(self.config_manager.get_scale_markers_major_tick_interval_mm())
        self.major_tick_interval_spinbox.blockSignals(False)

        self.minor_tick_interval_spinbox.blockSignals(True)
        self.minor_tick_interval_spinbox.setValue(self.config_manager.get_scale_markers_minor_tick_interval_mm())
        self.minor_tick_interval_spinbox.blockSignals(False)

        r, g, b = self.config_manager.get_direction_labels_color()
        self._update_direction_labels_color_display(r, g, b)
        self.current_direction_labels_color = (r, g, b)

        r, g, b = self.config_manager.get_scale_markers_color()
        self._update_scale_markers_color_display(r, g, b)
        self.current_scale_markers_color = (r, g, b)

        self.slice_line_mode_combo.blockSignals(True)
        current_mode = self.config_manager.get_slice_location_line_mode()
        mode_idx = self.slice_line_mode_combo.findData(current_mode)
        self.slice_line_mode_combo.setCurrentIndex(mode_idx if mode_idx >= 0 else 0)
        self.slice_line_mode_combo.blockSignals(False)

        self.slice_line_width_spinbox.blockSignals(True)
        self.slice_line_width_spinbox.setValue(
            self.config_manager.get_slice_location_line_width_px()
        )
        self.slice_line_width_spinbox.blockSignals(False)

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

    def _update_direction_labels_color_display(self, r: int, g: int, b: int) -> None:
        """Update the direction labels color swatch."""
        self.direction_labels_color_label.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        )

    def _update_scale_markers_color_display(self, r: int, g: int, b: int) -> None:
        """Update the scale markers color swatch."""
        self.scale_markers_color_label.setStyleSheet(
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

    def _choose_direction_labels_color(self) -> None:
        """Open color picker dialog for direction labels and apply the chosen color as a live preview."""
        r, g, b = self.current_direction_labels_color
        color = QColorDialog.getColor(QColor(r, g, b), self, "Choose Direction Labels Color")

        if color.isValid():
            self.current_direction_labels_color = (color.red(), color.green(), color.blue())
            self._update_direction_labels_color_display(*self.current_direction_labels_color)
            self._on_live_update()

    def _choose_scale_markers_color(self) -> None:
        """Open color picker dialog for scale markers and apply the chosen color as a live preview."""
        r, g, b = self.current_scale_markers_color
        color = QColorDialog.getColor(QColor(r, g, b), self, "Choose Scale Markers Color")

        if color.isValid():
            self.current_scale_markers_color = (color.red(), color.green(), color.blue())
            self._update_scale_markers_color_display(*self.current_scale_markers_color)
            self._on_live_update()

    def _on_live_update(self) -> None:
        self.config_manager.set_show_direction_labels(self.show_direction_labels_checkbox.isChecked())
        self.config_manager.set_show_scale_markers(self.show_scale_markers_checkbox.isChecked())
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
        self.config_manager.set_direction_label_size(self.direction_label_size_spinbox.value())
        self.config_manager.set_scale_markers_major_tick_interval_mm(self.major_tick_interval_spinbox.value())
        self.config_manager.set_scale_markers_minor_tick_interval_mm(self.minor_tick_interval_spinbox.value())
        r, g, b = self.current_direction_labels_color
        self.config_manager.set_direction_labels_color(r, g, b)
        r, g, b = self.current_scale_markers_color
        self.config_manager.set_scale_markers_color(r, g, b)
        mode = self.slice_line_mode_combo.currentData()
        if mode:
            self.config_manager.set_slice_location_line_mode(mode)
        self.config_manager.set_slice_location_line_width_px(
            self.slice_line_width_spinbox.value()
        )
        self.settings_changed.emit()

    def _apply_settings(self) -> None:
        """Persist settings, emit settings_applied, and close the dialog."""
        self.config_manager.set_show_direction_labels(self.show_direction_labels_checkbox.isChecked())
        self.config_manager.set_show_scale_markers(self.show_scale_markers_checkbox.isChecked())
        self.config_manager.set_overlay_font_size(self.font_size_spinbox.value())
        self.config_manager.set_overlay_font_family(self.font_family_combo.currentText())
        self.config_manager.set_overlay_font_variant(self.font_variant_combo.currentText())
        r, g, b = self.current_color
        self.config_manager.set_overlay_font_color(r, g, b)
        self.config_manager.set_direction_label_size(self.direction_label_size_spinbox.value())
        self.config_manager.set_scale_markers_major_tick_interval_mm(self.major_tick_interval_spinbox.value())
        self.config_manager.set_scale_markers_minor_tick_interval_mm(self.minor_tick_interval_spinbox.value())
        r, g, b = self.current_direction_labels_color
        self.config_manager.set_direction_labels_color(r, g, b)
        r, g, b = self.current_scale_markers_color
        self.config_manager.set_scale_markers_color(r, g, b)
        mode = self.slice_line_mode_combo.currentData()
        if mode:
            self.config_manager.set_slice_location_line_mode(mode)
        self.config_manager.set_slice_location_line_width_px(
            self.slice_line_width_spinbox.value()
        )
        self.settings_applied.emit()
        self.accept()

    def reject(self) -> None:
        """Restore original values on Cancel so the live preview is reverted."""
        self.config_manager.set_show_direction_labels(self._original_show_direction_labels)
        self.config_manager.set_show_scale_markers(self._original_show_scale_markers)
        self.config_manager.set_overlay_font_size(self._original_font_size)
        self.config_manager.set_overlay_font_family(self._original_font_family)
        self.config_manager.set_overlay_font_variant(self._original_font_variant)
        r, g, b = self._original_font_color
        self.config_manager.set_overlay_font_color(r, g, b)
        r, g, b = self._original_direction_labels_color
        self.config_manager.set_direction_labels_color(r, g, b)
        r, g, b = self._original_scale_markers_color
        self.config_manager.set_scale_markers_color(r, g, b)
        self.config_manager.set_direction_label_size(self._original_direction_label_size)
        self.config_manager.set_scale_markers_major_tick_interval_mm(self._original_major_tick_interval_mm)
        self.config_manager.set_scale_markers_minor_tick_interval_mm(self._original_minor_tick_interval_mm)
        self.config_manager.set_slice_location_line_mode(self._original_slice_location_line_mode)
        self.config_manager.set_slice_location_line_width_px(
            self._original_slice_location_line_width_px
        )
        self.settings_changed.emit()
        super().reject()
