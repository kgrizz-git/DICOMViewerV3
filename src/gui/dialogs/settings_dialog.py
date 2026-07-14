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
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.accent_presets import ACCENT_PRESETS, get_preset
from utils.config_manager import ConfigManager


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
    ):
        super().__init__(parent)

        self.config_manager = config_manager
        self._manage_wl_presets_callback = manage_wl_presets_callback
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

        # ── Local study index ──────────────────────────────────────────────
        idx_group = QGroupBox("Local study index (encrypted)")
        idx_form = QFormLayout(idx_group)
        self._study_index_auto_add = QCheckBox(
            "Automatically add files to the study index when opened successfully"
        )
        self._study_index_auto_add.setChecked(
            self.config_manager.get_study_index_auto_add_on_open()
        )
        idx_form.addRow(self._study_index_auto_add)

        path_row = QHBoxLayout()
        self._study_index_db_path = QLineEdit()
        self._study_index_db_path.setText(
            self.config_manager.config.get("study_index_db_path", "") or ""
        )
        self._study_index_db_path.setPlaceholderText(
            "(default: next to your app config file)"
        )
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_study_index_db)
        default_btn = QPushButton("Use default path")
        default_btn.clicked.connect(self._clear_study_index_db_path)
        path_row.addWidget(self._study_index_db_path, stretch=1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(default_btn)
        path_wrap = QVBoxLayout()
        path_wrap.addLayout(path_row)
        hint = QLabel(
            "The index database is encrypted (SQLCipher). The encryption key is stored in "
            "your OS credential manager, not in this JSON config file."
        )
        hint.setWordWrap(True)
        path_wrap.addWidget(hint)
        idx_form.addRow("Database file:", path_wrap)
        layout.addWidget(idx_group)

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

    def _browse_study_index_db(self) -> None:
        start = (
            self._study_index_db_path.text().strip()
            or self.config_manager.get_default_study_index_db_path()
        )
        parent_dir = start
        import os

        if parent_dir and not os.path.isdir(parent_dir):
            parent_dir = os.path.dirname(parent_dir) or start
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Study index database file",
            start or self.config_manager.get_default_study_index_db_path(),
            "SQLite database (*.sqlite *.db);;All files (*.*)",
        )
        if path:
            self._study_index_db_path.setText(path)

    def _clear_study_index_db_path(self) -> None:
        self._study_index_db_path.setText("")

    def _on_accept(self) -> None:
        accent_key = self._accent_combo.currentData()
        if accent_key:
            self.config_manager.set_accent(accent_key)
        toolbar_style = self._toolbar_label_combo.currentData()
        if toolbar_style:
            self.config_manager.set_toolbar_label_style(toolbar_style)
        self.config_manager.set_study_index_auto_add_on_open(
            self._study_index_auto_add.isChecked()
        )
        self.config_manager.set_study_index_db_path(self._study_index_db_path.text())
        self.config_manager.save_config()
        self.settings_applied.emit()
        self.accept()
