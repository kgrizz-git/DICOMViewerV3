"""
Settings Dialog

General application preferences, including local study index options.

Inputs:
    - User preference changes

Outputs:
    - Updated configuration settings

Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.study_cache import get_total_system_memory_mb
from gui.accent_presets import ACCENT_PRESETS, get_preset
from gui.privacy_storage_settings import PrivacyStorageSettingsPanel
from utils.config_manager import ConfigManager
from utils.privacy.safe_storage import DeletionResult

#: Mirrors the memory_floor_mb default StudyCache is constructed with in main.py.
_STUDY_LOAD_MEMORY_FLOOR_MB = 1024.0


class SettingsDialog(QDialog):
    """
    Settings dialog for application preferences.

    Overlay preferences remain under View → Overlay Settings; this dialog holds
    cross-cutting options such as the local study index.
    """

    settings_applied = Signal()

    def __init__(
        self,
        config_manager: ConfigManager,
        parent=None,
        manage_wl_presets_callback: Callable[[], None] | None = None,
        clear_study_index_callback: Callable[[], DeletionResult] | None = None,
        clear_mpr_cache_callback: Callable[[], DeletionResult] | None = None,
    ):
        super().__init__(parent)

        self.config_manager = config_manager
        self._manage_wl_presets_callback = manage_wl_presets_callback
        self._clear_study_index_callback = clear_study_index_callback
        self._clear_mpr_cache_callback = clear_mpr_cache_callback
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 420)

        self._create_ui()

    def _create_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)

        intro = QLabel(
            "Overlay preferences: <b>View → Overlay Settings</b> and "
            "<b>View → Overlay Tags Configuration</b>.<br>"
            "Annotation options: <b>View → Annotation Options</b>.<br>"
            "Privacy mode: <b>View → Privacy Mode</b>."
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        # ── Accent colour ──────────────────────────────────────────────────
        accent_group = QGroupBox("Accent colour")
        accent_form = QFormLayout(accent_group)

        self._accent_combo = QComboBox()
        current_accent = self.config_manager.get_accent()
        for key, preset in ACCENT_PRESETS.items():
            self._accent_combo.addItem(preset.label, userData=key)
            if key == current_accent:
                self._accent_combo.setCurrentIndex(self._accent_combo.count() - 1)

        self._accent_swatch = QLabel()
        self._accent_swatch.setFixedSize(32, 16)
        self._accent_swatch.setToolTip("Preview of the selected accent colour")
        self._update_accent_swatch()
        self._accent_combo.currentIndexChanged.connect(self._update_accent_swatch)

        accent_hint = QLabel(
            "Applied to buttons, menu highlights, slider fill, and focus rings. "
            "Garnet is intentionally distinct from the red used for privacy warnings."
        )
        accent_hint.setWordWrap(True)

        accent_row = QHBoxLayout()
        accent_row.addWidget(self._accent_combo)
        accent_row.addWidget(self._accent_swatch)
        accent_row.addStretch()

        accent_form.addRow("Style:", accent_row)
        accent_form.addRow(accent_hint)
        layout.addWidget(accent_group)

        # ── Toolbar ────────────────────────────────────────────────────────
        toolbar_group = QGroupBox("Toolbar")
        toolbar_form = QFormLayout(toolbar_group)

        self._toolbar_label_combo = QComboBox()
        _toolbar_label_options = [
            ("Icons only",          "icon_only"),
            ("Icons with labels",   "text_under_icon"),
            ("Labels only",         "text_only"),
        ]
        current_label_style = self.config_manager.get_toolbar_label_style()
        for label, key in _toolbar_label_options:
            self._toolbar_label_combo.addItem(label, userData=key)
            if key == current_label_style:
                self._toolbar_label_combo.setCurrentIndex(
                    self._toolbar_label_combo.count() - 1
                )

        toolbar_form.addRow("Button style:", self._toolbar_label_combo)
        toolbar_hint = QLabel(
            "\"Icons with labels\" shows a short name beneath each icon (7 pt). "
            "\"Labels only\" shows text buttons without icons."
        )
        toolbar_hint.setWordWrap(True)
        toolbar_form.addRow(toolbar_hint)
        layout.addWidget(toolbar_group)

        # ── Window / Level presets ─────────────────────────────────────────
        wl_group = QGroupBox("Window / Level")
        wl_layout = QVBoxLayout(wl_group)
        wl_hint = QLabel(
            "Built-in modality presets are read-only. Manage custom presets for CT, MR, and other modalities."
        )
        wl_hint.setWordWrap(True)
        wl_layout.addWidget(wl_hint)
        wl_manage_btn = QPushButton("Manage W/L Presets…")
        if self._manage_wl_presets_callback is not None:
            wl_manage_btn.clicked.connect(self._manage_wl_presets_callback)
        else:
            wl_manage_btn.setEnabled(False)
        wl_layout.addWidget(wl_manage_btn)
        layout.addWidget(wl_group)

        # ── Study load memory budget ──────────────────────────────────────
        memory_group = QGroupBox("Study Load Memory Budget")
        memory_form = QFormLayout(memory_group)
        memory_hint = QLabel(
            "Loaded studies are kept in memory up to this budget. When it would "
            "be exceeded, the oldest (least recently viewed) studies are "
            "unloaded to make room; the currently displayed study is never "
            "unloaded automatically."
        )
        memory_hint.setWordWrap(True)
        memory_form.addRow(memory_hint)

        self._memory_fraction_spin = QSpinBox()
        self._memory_fraction_spin.setRange(10, 90)
        self._memory_fraction_spin.setSingleStep(5)
        self._memory_fraction_spin.setSuffix(" %")
        self._memory_fraction_spin.setValue(
            round(self.config_manager.get_study_load_memory_fraction() * 100)
        )
        self._memory_fraction_spin.valueChanged.connect(
            self._update_memory_budget_preview
        )
        memory_form.addRow("Fraction of system RAM:", self._memory_fraction_spin)

        self._memory_budget_preview = QLabel()
        memory_form.addRow("Computed budget:", self._memory_budget_preview)
        self._update_memory_budget_preview()

        self._max_studies_cap_spin = QSpinBox()
        self._max_studies_cap_spin.setRange(1, 200)
        self._max_studies_cap_spin.setValue(
            self.config_manager.get_study_load_max_studies_cap()
        )
        memory_form.addRow(
            "Safety-net study count cap:", self._max_studies_cap_spin
        )
        cap_hint = QLabel(
            "Backstops the memory budget above against pathological cases "
            "(e.g. many very small studies); the budget is the primary limit."
        )
        cap_hint.setWordWrap(True)
        memory_form.addRow(cap_hint)

        layout.addWidget(memory_group)

        self._privacy_storage_panel = PrivacyStorageSettingsPanel(
            self.config_manager,
            clear_study_index_callback=self._clear_study_index_callback,
            clear_mpr_cache_callback=self._clear_mpr_cache_callback,
        )
        layout.addWidget(self._privacy_storage_panel)

        layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        outer.addWidget(button_box)

    def _update_accent_swatch(self) -> None:
        """Update the small colour swatch next to the accent combo."""
        key = self._accent_combo.currentData()
        if key:
            preset = get_preset(key)
            self._accent_swatch.setStyleSheet(
                f"background-color: {preset.accent}; "
                "border: 1px solid rgba(128,128,128,0.6); "
                "border-radius: 3px;"
            )

    def _update_memory_budget_preview(self) -> None:
        """Recompute the displayed budget preview from the current spin value."""
        total_ram_mb = get_total_system_memory_mb()
        fraction = self._memory_fraction_spin.value() / 100.0
        if total_ram_mb <= 0.0:
            self._memory_budget_preview.setText(
                "Total system RAM could not be determined; a fixed fallback "
                "threshold will be used instead."
            )
            return
        budget_mb = max(fraction * total_ram_mb, _STUDY_LOAD_MEMORY_FLOOR_MB)
        self._memory_budget_preview.setText(
            f"~{budget_mb / 1024.0:.1f} GB (of {total_ram_mb / 1024.0:.1f} GB total RAM)"
        )

    def _on_accept(self) -> None:
        accent_key = self._accent_combo.currentData()
        if accent_key:
            self.config_manager.set_accent(accent_key)
        toolbar_style = self._toolbar_label_combo.currentData()
        if toolbar_style:
            self.config_manager.set_toolbar_label_style(toolbar_style)
        if not self.config_manager.set_study_load_memory_fraction(
            self._memory_fraction_spin.value() / 100.0
        ):
            self._settings_not_saved()
            return
        if not self.config_manager.set_study_load_max_studies_cap(
            self._max_studies_cap_spin.value()
        ):
            self._settings_not_saved()
            return
        if not self._privacy_storage_panel.apply():
            return
        if not self.config_manager.save_config():
            self._settings_not_saved()
            return
        self.settings_applied.emit()
        self.accept()

    def _settings_not_saved(self) -> None:
        QMessageBox.warning(
            self,
            "Settings Not Saved",
            "The settings file could not be updated. Your changes were not confirmed.",
        )
