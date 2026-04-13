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

from PySide6.QtWidgets import (
    QCheckBox,
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
from PySide6.QtCore import Qt, Signal

from utils.config_manager import ConfigManager


class SettingsDialog(QDialog):
    """
    Settings dialog for application preferences.

    Overlay preferences remain under View → Overlay Settings; this dialog holds
    cross-cutting options such as the local study index.
    """

    settings_applied = Signal()

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)

        self.config_manager = config_manager
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
        self.config_manager.set_study_index_auto_add_on_open(
            self._study_index_auto_add.isChecked()
        )
        self.config_manager.set_study_index_db_path(self._study_index_db_path.text())
        self.config_manager.save_config()
        self.settings_applied.emit()
        self.accept()
