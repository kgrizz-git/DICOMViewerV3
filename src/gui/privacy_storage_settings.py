"""Settings widgets for disclosed privacy-sensitive local storage."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.config_manager import ConfigManager
from utils.debug_log import clear_debug_log, configure_debug_logging
from utils.privacy.safe_storage import DeletionResult


class PrivacyStorageSettingsPanel(QWidget):
    """Disclose sensitive persistence and provide opt-in and clear controls."""

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: QWidget | None = None,
        *,
        clear_study_index_callback: Callable[[], DeletionResult] | None = None,
        clear_mpr_cache_callback: Callable[[], DeletionResult] | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config_manager
        self._clear_study_index_callback = clear_study_index_callback
        self._clear_mpr_cache_callback = clear_mpr_cache_callback
        self.study_index_auto_add = QCheckBox()
        self.study_index_path = QLineEdit()
        self.mpr_cache_enabled = QCheckBox()
        self.mpr_cache_max_mb = QSpinBox()
        self.recent_path_count = QLabel()
        self.diagnostics_enabled = QCheckBox()
        self._build_ui()

    @staticmethod
    def _location_label(path: str) -> QLabel:
        label = QLabel(path)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_study_index_group())
        layout.addWidget(self._build_mpr_cache_group())
        layout.addWidget(self._build_recent_paths_group())
        layout.addWidget(self._build_diagnostics_group())

    def _build_study_index_group(self) -> QGroupBox:
        group = QGroupBox("Local study index (encrypted)")
        form = QFormLayout(group)
        self.study_index_auto_add.setText(
            "Automatically add files after a successful open"
        )
        self.study_index_auto_add.setObjectName("studyIndexAutoAdd")
        self.study_index_auto_add.setChecked(
            self._config.get_study_index_auto_add_on_open()
        )
        form.addRow(self.study_index_auto_add)
        form.addRow(
            "Status:",
            QLabel(
                "Enabled"
                if self._config.get_study_index_auto_add_on_open()
                else "Disabled"
            ),
        )
        self.study_index_path.setText(
            str(self._config.config.get("study_index_db_path", "") or "")
        )
        self.study_index_path.setObjectName("studyIndexPath")
        self.study_index_path.setPlaceholderText(
            f"Default: {self._config.get_default_study_index_db_path()}"
        )
        path_row = QHBoxLayout()
        path_row.addWidget(self.study_index_path, stretch=1)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_study_index_path)
        path_row.addWidget(browse_button)
        default_button = QPushButton("Use default")
        default_button.clicked.connect(self.study_index_path.clear)
        path_row.addWidget(default_button)
        form.addRow("Database:", path_row)
        encryption = QLabel(
            "SQLCipher encrypted; key stored in the operating-system credential manager."
        )
        encryption.setWordWrap(True)
        form.addRow("Encryption:", encryption)
        clear_button = QPushButton("Clear index now…")
        clear_button.setObjectName("clearStudyIndexButton")
        clear_button.clicked.connect(self._clear_study_index)
        form.addRow(clear_button)
        return group

    def _build_mpr_cache_group(self) -> QGroupBox:
        group = QGroupBox("MPR derived-pixel disk cache")
        form = QFormLayout(group)
        disclosure = QLabel(
            "When enabled, reconstructed pixel arrays are retained locally to speed "
            "reopening an MPR. It is off until you opt in. Disabling clears it."
        )
        disclosure.setWordWrap(True)
        form.addRow(disclosure)
        self.mpr_cache_enabled.setText("Enable persistent MPR cache")
        self.mpr_cache_enabled.setObjectName("mprCacheEnabled")
        self.mpr_cache_enabled.setChecked(self._config.get_mpr_cache_enabled())
        form.addRow(self.mpr_cache_enabled)
        self.mpr_cache_max_mb.setRange(16, 4096)
        self.mpr_cache_max_mb.setSuffix(" MiB")
        self.mpr_cache_max_mb.setValue(self._config.get_mpr_cache_max_mb())
        form.addRow("Maximum retained:", self.mpr_cache_max_mb)
        form.addRow(
            "Location:", self._location_label(str(self._config.get_mpr_cache_path()))
        )
        clear_button = QPushButton("Clear MPR cache now")
        clear_button.setObjectName("clearMprCacheButton")
        clear_button.clicked.connect(self._clear_mpr_cache)
        form.addRow(clear_button)
        return group

    def _build_recent_paths_group(self) -> QGroupBox:
        group = QGroupBox("Remembered file locations")
        form = QFormLayout(group)
        disclosure = QLabel(
            "The private application config remembers up to 20 recent inputs and the "
            "last input, export, and report folders. These paths are not encrypted."
        )
        disclosure.setWordWrap(True)
        form.addRow(disclosure)
        form.addRow("Config:", self._location_label(str(self._config.config_path)))
        self.recent_path_count.setText(str(len(self._config.get_recent_files())))
        form.addRow("Recent items:", self.recent_path_count)
        clear_button = QPushButton("Clear remembered locations now")
        clear_button.setObjectName("clearRecentPathsButton")
        clear_button.clicked.connect(self._clear_recent_paths)
        form.addRow(clear_button)
        return group

    def _build_diagnostics_group(self) -> QGroupBox:
        group = QGroupBox("Redacted diagnostics")
        form = QFormLayout(group)
        disclosure = QLabel(
            "Diagnostics are off by default. When enabled, central redaction is applied; "
            "storage is capped at 2 MiB and entries expire after 7 days."
        )
        disclosure.setWordWrap(True)
        form.addRow(disclosure)
        self.diagnostics_enabled.setText("Enable redacted diagnostics")
        self.diagnostics_enabled.setObjectName("diagnosticsEnabled")
        self.diagnostics_enabled.setChecked(self._config.get_diagnostics_enabled())
        form.addRow(self.diagnostics_enabled)
        form.addRow(
            "Location:",
            self._location_label(str(self._config.get_diagnostics_log_path())),
        )
        clear_button = QPushButton("Clear diagnostics now")
        clear_button.setObjectName("clearDiagnosticsButton")
        clear_button.clicked.connect(self._clear_diagnostics)
        form.addRow(clear_button)
        return group

    def apply(self) -> bool:
        """Persist explicit choices, surfacing any persistence or cleanup failure."""

        if not self._config.set_study_index_auto_add_on_open(
            self.study_index_auto_add.isChecked()
        ):
            return self._settings_not_saved()
        if not self._config.set_study_index_db_path(self.study_index_path.text()):
            return self._settings_not_saved()
        was_mpr_enabled = self._config.get_mpr_cache_enabled()
        mpr_enabled = self.mpr_cache_enabled.isChecked()
        if not self._config.set_mpr_cache_max_mb(self.mpr_cache_max_mb.value()):
            return self._settings_not_saved()
        if not self._config.set_mpr_cache_enabled(mpr_enabled):
            return self._settings_not_saved()
        if was_mpr_enabled and not mpr_enabled:
            result = self._clear_mpr_cache_without_notice()
            if not result.success:
                self._show_deletion_result("MPR Cache Not Fully Cleared", result)
                return False
        diagnostics_enabled = self.diagnostics_enabled.isChecked()
        if not self._config.set_diagnostics_enabled(diagnostics_enabled):
            return self._settings_not_saved()
        configure_debug_logging(
            diagnostics_enabled,
            path=self._config.get_diagnostics_log_path(),
        )
        return True

    def _settings_not_saved(self) -> bool:
        QMessageBox.warning(
            self,
            "Settings Not Saved",
            "The settings file could not be updated. Review the choices and try again.",
        )
        return False

    def _show_deletion_result(self, failure_title: str, result: DeletionResult) -> None:
        if result.success:
            QMessageBox.information(
                self,
                "Local Data Cleared",
                f"Removed {result.removed} owned local file(s).",
            )
            return
        QMessageBox.warning(
            self,
            failure_title,
            f"Removed {result.removed} owned local file(s); "
            f"{result.failed} cleanup step(s) failed. "
            "Try again after closing active operations.",
        )

    def _clear_study_index(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Clear Local Study Index",
            "Remove all indexed metadata and remembered file locations from the encrypted "
            "study-index database? Original DICOM files are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        result = (
            self._clear_study_index_callback()
            if self._clear_study_index_callback is not None
            else DeletionResult(failed=1)
        )
        self._show_deletion_result("Index Not Fully Cleared", result)

    def _browse_study_index_path(self) -> None:
        current = self.study_index_path.text().strip()
        start = current or self._config.get_default_study_index_db_path()
        parent = Path(start).expanduser().parent
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Study index database file",
            str(parent),
            "SQLite database (*.sqlite *.db);;All files (*.*)",
        )
        if selected:
            self.study_index_path.setText(selected)

    def _clear_mpr_cache_without_notice(self) -> DeletionResult:
        if self._clear_mpr_cache_callback is not None:
            return self._clear_mpr_cache_callback()
        return self._config.clear_mpr_cache_storage()

    def _clear_mpr_cache(self) -> None:
        self._show_deletion_result(
            "MPR Cache Not Fully Cleared",
            self._clear_mpr_cache_without_notice(),
        )

    def _clear_recent_paths(self) -> None:
        if self._config.clear_recent_path_history():
            self.recent_path_count.setText("0")
            QMessageBox.information(
                self,
                "Remembered Locations Cleared",
                "Remembered input, export, report, and recent-item locations were cleared.",
            )
            return
        QMessageBox.warning(
            self,
            "Locations Not Cleared",
            "The settings file could not be updated, so remembered locations were not cleared.",
        )

    def _clear_diagnostics(self) -> None:
        self._show_deletion_result(
            "Diagnostics Not Cleared",
            clear_debug_log(path=self._config.get_diagnostics_log_path()),
        )
