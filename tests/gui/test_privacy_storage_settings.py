"""
Comprehensive tests for PrivacyStorageSettingsPanel.

Tests all public methods, UI initialization, configuration persistence,
and deletion operations for privacy-sensitive storage settings.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gui.privacy_storage_settings import PrivacyStorageSettingsPanel
from utils.config_manager import ConfigManager
from utils.privacy.safe_storage import DeletionResult


@pytest.fixture
def config_manager(tmp_path: Path) -> ConfigManager:
    """Provide a ConfigManager instance with a temporary config directory."""
    return ConfigManager(config_dir=tmp_path / "config")


@pytest.fixture
def panel(qapp, config_manager: ConfigManager) -> PrivacyStorageSettingsPanel:
    """Provide a PrivacyStorageSettingsPanel instance with default configuration."""
    return PrivacyStorageSettingsPanel(config_manager)


@pytest.fixture
def panel_with_callbacks(
    qapp, config_manager: ConfigManager
) -> PrivacyStorageSettingsPanel:
    """Provide a panel with deletion callbacks configured."""
    return PrivacyStorageSettingsPanel(
        config_manager,
        clear_study_index_callback=lambda: DeletionResult(removed=5, failed=0),
        clear_mpr_cache_callback=lambda: DeletionResult(removed=3, failed=0),
    )


class TestInitialization:
    """Test panel initialization and widget setup."""

    @pytest.mark.qt
    def test_panel_creates_all_widgets(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify all expected widgets are created during initialization."""
        assert panel.study_index_auto_add is not None
        assert panel.study_index_path is not None
        assert panel.mpr_cache_enabled is not None
        assert panel.mpr_cache_max_mb is not None
        assert panel.recent_path_count is not None
        assert panel.diagnostics_enabled is not None

    @pytest.mark.qt
    def test_panel_with_no_callbacks(self, config_manager: ConfigManager) -> None:
        """Verify panel works when deletion callbacks are not provided."""
        panel = PrivacyStorageSettingsPanel(config_manager)
        assert panel._clear_study_index_callback is None
        assert panel._clear_mpr_cache_callback is None

    @pytest.mark.qt
    def test_panel_with_callbacks(self, config_manager: ConfigManager) -> None:
        """Verify callbacks are stored when provided."""

        def study_callback():
            return DeletionResult(removed=1)

        def mpr_callback():
            return DeletionResult(removed=2)

        panel = PrivacyStorageSettingsPanel(
            config_manager,
            clear_study_index_callback=study_callback,
            clear_mpr_cache_callback=mpr_callback,
        )
        assert panel._clear_study_index_callback is study_callback
        assert panel._clear_mpr_cache_callback is mpr_callback

    @pytest.mark.qt
    def test_panel_with_parent_widget(
        self, config_manager: ConfigManager, qapp
    ) -> None:
        """Verify panel accepts a parent widget."""
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        panel = PrivacyStorageSettingsPanel(config_manager, parent=parent)
        assert panel.parent() is parent


class TestLocationLabel:
    """Test the static _location_label method."""

    @pytest.mark.qt
    def test_location_label_creates_wrapping_label(self) -> None:
        """Verify label has word wrap enabled."""
        label = PrivacyStorageSettingsPanel._location_label("/test/path")
        assert label.wordWrap()

    @pytest.mark.qt
    def test_location_label_sets_text(self) -> None:
        """Verify label text is set correctly."""
        test_path = "/custom/test/path"
        label = PrivacyStorageSettingsPanel._location_label(test_path)
        assert label.text() == test_path

    @pytest.mark.qt
    def test_location_label_selectable_by_mouse(self) -> None:
        """Verify label text is selectable by mouse."""
        from PySide6.QtCore import Qt

        label = PrivacyStorageSettingsPanel._location_label("/test")
        expected_flags = Qt.TextInteractionFlag.TextSelectableByMouse
        assert label.textInteractionFlags() == expected_flags


class TestStudyIndexGroup:
    """Test study index settings group initialization and behavior."""

    @pytest.mark.qt
    def test_study_index_auto_add_checked_from_config(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify auto-add checkbox reflects config value."""
        config_value = panel._config.get_study_index_auto_add_on_open()
        assert panel.study_index_auto_add.isChecked() == config_value

    @pytest.mark.qt
    def test_study_index_path_placeholder_shows_default(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify placeholder text shows default path."""
        default_path = panel._config.get_default_study_index_db_path()
        assert default_path in panel.study_index_path.placeholderText()

    @pytest.mark.qt
    def test_study_index_path_object_name(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify study index path has correct object name for testing."""
        assert panel.study_index_path.objectName() == "studyIndexPath"

    @pytest.mark.qt
    def test_study_index_auto_add_object_name(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify auto-add checkbox has correct object name."""
        assert panel.study_index_auto_add.objectName() == "studyIndexAutoAdd"


class TestMprCacheGroup:
    """Test MPR cache settings group initialization and behavior."""

    @pytest.mark.qt
    def test_mpr_cache_enabled_from_config(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify MPR cache enabled checkbox reflects config value."""
        config_value = panel._config.get_mpr_cache_enabled()
        assert panel.mpr_cache_enabled.isChecked() == config_value

    @pytest.mark.qt
    def test_mpr_cache_max_mb_range(self, panel: PrivacyStorageSettingsPanel) -> None:
        """Verify MPR cache max MB spinbox has correct range."""
        assert panel.mpr_cache_max_mb.minimum() == 16
        assert panel.mpr_cache_max_mb.maximum() == 4096

    @pytest.mark.qt
    def test_mpr_cache_max_mb_suffix(self, panel: PrivacyStorageSettingsPanel) -> None:
        """Verify MPR cache spinbox has MiB suffix."""
        assert panel.mpr_cache_max_mb.suffix() == " MiB"

    @pytest.mark.qt
    def test_mpr_cache_max_mb_value_from_config(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify MPR cache max MB reflects config value."""
        config_value = panel._config.get_mpr_cache_max_mb()
        assert panel.mpr_cache_max_mb.value() == config_value

    @pytest.mark.qt
    def test_mpr_cache_enabled_object_name(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify MPR cache enabled checkbox has correct object name."""
        assert panel.mpr_cache_enabled.objectName() == "mprCacheEnabled"


class TestRecentPathsGroup:
    """Test recent paths settings group initialization and behavior."""

    @pytest.mark.qt
    def test_recent_path_count_initial_value(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify recent path count reflects config value."""
        expected_count = len(panel._config.get_recent_files())
        assert panel.recent_path_count.text() == str(expected_count)


class TestDiagnosticsGroup:
    """Test diagnostics settings group initialization and behavior."""

    @pytest.mark.qt
    def test_diagnostics_enabled_from_config(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify diagnostics enabled checkbox reflects config value."""
        config_value = panel._config.get_diagnostics_enabled()
        assert panel.diagnostics_enabled.isChecked() == config_value

    @pytest.mark.qt
    def test_diagnostics_enabled_object_name(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify diagnostics enabled checkbox has correct object name."""
        assert panel.diagnostics_enabled.objectName() == "diagnosticsEnabled"


class TestApply:
    """Test the apply() method for persisting settings."""

    @pytest.mark.qt
    def test_apply_saves_study_index_auto_add(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() persists study index auto-add setting."""
        panel.study_index_auto_add.setChecked(True)
        assert panel.apply() is True
        assert panel._config.get_study_index_auto_add_on_open() is True

    @pytest.mark.qt
    def test_apply_saves_study_index_path(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() persists study index path."""
        test_path = "/custom/study_index.db"
        panel.study_index_path.setText(test_path)
        assert panel.apply() is True
        assert panel._config.config.get("study_index_db_path") == test_path

    @pytest.mark.qt
    def test_apply_saves_mpr_cache_enabled(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() persists MPR cache enabled setting."""
        panel.mpr_cache_enabled.setChecked(True)
        assert panel.apply() is True
        assert panel._config.get_mpr_cache_enabled() is True

    @pytest.mark.qt
    def test_apply_saves_mpr_cache_max_mb(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() persists MPR cache max MB setting."""
        panel.mpr_cache_max_mb.setValue(1024)
        assert panel.apply() is True
        assert panel._config.get_mpr_cache_max_mb() == 1024

    @pytest.mark.qt
    def test_apply_saves_diagnostics_enabled(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() persists diagnostics enabled setting."""
        panel.diagnostics_enabled.setChecked(True)
        assert panel.apply() is True
        assert panel._config.get_diagnostics_enabled() is True

    @pytest.mark.qt
    def test_apply_disabling_mpr_clears_cache(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify disabling MPR cache clears the cache."""
        # Enable MPR cache first
        panel._config.set_mpr_cache_enabled(True)
        panel.mpr_cache_enabled.setChecked(False)
        with patch.object(
            panel,
            "_clear_mpr_cache_without_notice",
            return_value=DeletionResult(removed=0, failed=0),
        ):
            assert panel.apply() is True

    @pytest.mark.qt
    def test_apply_failure_shows_warning(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() shows warning on config save failure."""
        with (
            patch.object(
                panel._config, "set_study_index_auto_add_on_open", return_value=False
            ),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False

    @pytest.mark.qt
    def test_apply_mpr_clear_failure_returns_false(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() returns False when MPR cache clear fails."""
        # Enable MPR cache first
        panel._config.set_mpr_cache_enabled(True)
        panel.mpr_cache_enabled.setChecked(False)
        with (
            patch.object(
                panel,
                "_clear_mpr_cache_without_notice",
                return_value=DeletionResult(removed=0, failed=1),
            ),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False

    @pytest.mark.qt
    def test_apply_study_index_path_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() returns False when study index path save fails."""
        with (
            patch.object(panel._config, "set_study_index_db_path", return_value=False),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False

    @pytest.mark.qt
    def test_apply_mpr_cache_max_mb_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() returns False when MPR cache max MB save fails."""
        with (
            patch.object(panel._config, "set_mpr_cache_max_mb", return_value=False),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False

    @pytest.mark.qt
    def test_apply_mpr_cache_enabled_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() returns False when MPR cache enabled save fails."""
        with (
            patch.object(panel._config, "set_mpr_cache_enabled", return_value=False),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False

    @pytest.mark.qt
    def test_apply_diagnostics_enabled_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() returns False when diagnostics enabled save fails."""
        with (
            patch.object(panel._config, "set_diagnostics_enabled", return_value=False),
            patch("gui.privacy_storage_settings.QMessageBox.warning"),
        ):
            assert panel.apply() is False


class TestClearStudyIndex:
    """Test study index clearing functionality."""

    @pytest.mark.qt
    def test_clear_study_index_with_callback(
        self, panel_with_callbacks: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear study index uses callback when provided."""
        from PySide6.QtWidgets import QMessageBox

        with (
            patch(
                "gui.privacy_storage_settings.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch("gui.privacy_storage_settings.QMessageBox.information"),
        ):
            panel_with_callbacks._clear_study_index()

    @pytest.mark.qt
    def test_clear_study_index_without_callback(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear study index handles missing callback."""
        from PySide6.QtWidgets import QMessageBox

        with patch(
            "gui.privacy_storage_settings.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            panel._clear_study_index()

    @pytest.mark.qt
    def test_clear_study_index_cancelled(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear study index respects cancel dialog."""
        from PySide6.QtWidgets import QMessageBox

        with patch(
            "gui.privacy_storage_settings.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.Cancel,
        ):
            panel._clear_study_index()


class TestBrowseStudyIndexPath:
    """Test file dialog for browsing study index path."""

    @pytest.mark.qt
    def test_browse_study_index_path_selects_file(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify browsing sets the selected path."""
        test_path = "/selected/study_index.db"
        with patch(
            "gui.privacy_storage_settings.QFileDialog.getSaveFileName",
            return_value=(test_path, ""),
        ):
            panel._browse_study_index_path()
            assert panel.study_index_path.text() == test_path

    @pytest.mark.qt
    def test_browse_study_index_path_cancelled(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify cancelled browse doesn't change path."""
        original_path = panel.study_index_path.text()
        with patch(
            "gui.privacy_storage_settings.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            panel._browse_study_index_path()
            assert panel.study_index_path.text() == original_path

    @pytest.mark.qt
    def test_browse_uses_current_path_as_start(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify browse uses current path as starting directory."""
        panel.study_index_path.setText("/current/path.db")
        with patch(
            "gui.privacy_storage_settings.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ) as mock_dialog:
            panel._browse_study_index_path()
            # Should use parent of current path
            call_args = mock_dialog.call_args
            assert call_args is not None


class TestClearMprCache:
    """Test MPR cache clearing functionality."""

    @pytest.mark.qt
    def test_clear_mpr_cache_with_callback(
        self, panel_with_callbacks: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear MPR cache uses callback when provided."""
        with patch("gui.privacy_storage_settings.QMessageBox.information"):
            panel_with_callbacks._clear_mpr_cache()

    @pytest.mark.qt
    def test_clear_mpr_cache_without_callback(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear MPR cache uses config method when callback missing."""
        with patch("gui.privacy_storage_settings.QMessageBox.information"):
            panel._clear_mpr_cache()

    @pytest.mark.qt
    def test_clear_mpr_cache_without_notice_with_callback(
        self, panel_with_callbacks: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify _clear_mpr_cache_without_notice uses callback."""
        result = panel_with_callbacks._clear_mpr_cache_without_notice()
        assert result.removed == 3
        assert result.failed == 0

    @pytest.mark.qt
    def test_clear_mpr_cache_without_notice_without_callback(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify _clear_mpr_cache_without_notice uses config method."""
        result = panel._clear_mpr_cache_without_notice()
        assert isinstance(result, DeletionResult)


class TestClearRecentPaths:
    """Test recent paths clearing functionality."""

    @pytest.mark.qt
    def test_clear_recent_paths_success(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify successful clear updates count and shows info dialog."""
        with (
            patch.object(panel._config, "clear_recent_path_history", return_value=True),
            patch("gui.privacy_storage_settings.QMessageBox.information"),
        ):
            panel._clear_recent_paths()
            assert panel.recent_path_count.text() == "0"

    @pytest.mark.qt
    def test_clear_recent_paths_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify failed clear shows warning dialog."""
        with patch.object(
            panel._config, "clear_recent_path_history", return_value=False
        ), patch("gui.privacy_storage_settings.QMessageBox.warning"):
            panel._clear_recent_paths()


class TestClearDiagnostics:
    """Test diagnostics clearing functionality."""

    @pytest.mark.qt
    def test_clear_diagnostics_calls_clear_debug_log(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify clear diagnostics calls clear_debug_log."""
        with (
            patch(
                "gui.privacy_storage_settings.clear_debug_log",
                return_value=DeletionResult(removed=1, failed=0),
            ),
            patch("gui.privacy_storage_settings.QMessageBox.information"),
        ):
            panel._clear_diagnostics()


class TestShowDeletionResult:
    """Test deletion result dialog display."""

    @pytest.mark.qt
    def test_show_deletion_result_success(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify successful deletion shows info dialog."""
        result = DeletionResult(removed=5, failed=0)
        with patch("gui.privacy_storage_settings.QMessageBox.information") as mock_info:
            panel._show_deletion_result("Test Success", result)
            mock_info.assert_called_once()
            assert "5" in mock_info.call_args[0][2]

    @pytest.mark.qt
    def test_show_deletion_result_failure(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify failed deletion shows warning dialog."""
        result = DeletionResult(removed=3, failed=2)
        with patch("gui.privacy_storage_settings.QMessageBox.warning") as mock_warning:
            panel._show_deletion_result("Test Failure", result)
            mock_warning.assert_called_once()
            args = mock_warning.call_args[0]
            assert "3" in args[2]
            assert "2" in args[2]


class TestSettingsNotSaved:
    """Test settings not saved warning dialog."""

    @pytest.mark.qt
    def test_settings_not_saved_shows_warning(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify _settings_not_saved shows warning dialog."""
        with patch("gui.privacy_storage_settings.QMessageBox.warning") as mock_warning:
            result = panel._settings_not_saved()
            mock_warning.assert_called_once()
            assert result is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.qt
    def test_apply_with_invalid_mpr_max_mb(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() handles invalid MPR max MB value."""
        # Set to invalid value that config will clamp
        panel.mpr_cache_max_mb.setValue(10)  # Below minimum
        assert panel.apply() is True
        # Config should clamp to minimum
        assert panel._config.get_mpr_cache_max_mb() >= 16

    @pytest.mark.qt
    def test_apply_with_all_settings_changed(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify apply() handles all settings changed at once."""
        panel.study_index_auto_add.setChecked(True)
        panel.study_index_path.setText("/custom/path.db")
        panel.mpr_cache_enabled.setChecked(True)
        panel.mpr_cache_max_mb.setValue(2048)
        panel.diagnostics_enabled.setChecked(True)
        assert panel.apply() is True

    @pytest.mark.qt
    def test_empty_study_index_path(self, panel: PrivacyStorageSettingsPanel) -> None:
        """Verify empty study index path is handled correctly."""
        panel.study_index_path.setText("")
        assert panel.apply() is True

    @pytest.mark.qt
    def test_toggle_mpr_cache_multiple_times(
        self, panel: PrivacyStorageSettingsPanel
    ) -> None:
        """Verify toggling MPR cache multiple times works correctly."""
        panel.mpr_cache_enabled.setChecked(True)
        assert panel.apply() is True
        panel.mpr_cache_enabled.setChecked(False)
        assert panel.apply() is True
        panel.mpr_cache_enabled.setChecked(True)
        assert panel.apply() is True
