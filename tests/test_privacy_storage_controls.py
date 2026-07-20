"""Focused tests for opt-in persistence, migration consent, and clear controls."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from core.study_index.index_service import LocalStudyIndexService
from gui.mpr_controller import MprController
from gui.privacy_storage_settings import PrivacyStorageSettingsPanel
from gui.study_index_consent import (
    StudyIndexFirstOpenDialog,
    StudyIndexOpenChoice,
    apply_first_open_choice,
    prompt_study_index_first_open,
)
from utils import debug_log as debug_log_module
from utils.config_manager import ConfigManager
from utils.privacy.safe_storage import DeletionResult


def _config(tmp_path: Path) -> ConfigManager:
    return ConfigManager(config_dir=tmp_path / "config")


def test_sensitive_persistence_defaults_are_off_without_consent(tmp_path: Path) -> None:
    config = _config(tmp_path)

    assert config.get_study_index_auto_add_on_open() is False
    assert config.needs_study_index_auto_add_consent() is True
    assert config.get_mpr_cache_enabled() is False
    assert config.get_diagnostics_enabled() is False


def test_malformed_persisted_enable_values_fail_closed(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "dicom_viewer_config.json").write_text(
        json.dumps(
            {
                "mpr_cache_enabled": "true",
                "diagnostics_enabled": 1,
                "study_index_auto_add_consent": True,
                "study_index_auto_add_on_open": "yes",
            }
        ),
        encoding="utf-8",
    )

    config = ConfigManager(config_dir=config_dir)

    assert config.get_mpr_cache_enabled() is False
    assert config.get_diagnostics_enabled() is False
    assert config.get_study_index_auto_add_on_open() is False


def test_config_storage_below_disposable_launch_root_is_allowed(
    monkeypatch, tmp_path: Path
) -> None:
    launch_dir = tmp_path / "root-like-launch"
    launch_dir.mkdir()
    monkeypatch.chdir(launch_dir)

    config = ConfigManager(config_dir=launch_dir / "private-config")

    assert config.save_config() is True
    assert config.config_path.exists()


def test_legacy_enabled_index_setting_fails_closed_until_migration_choice(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "dicom_viewer_config.json").write_text(
        json.dumps({"study_index_auto_add_on_open": True}),
        encoding="utf-8",
    )

    config = ConfigManager(config_dir=config_dir)

    assert config.is_study_index_auto_add_consent_migration() is True
    assert config.get_study_index_auto_add_on_open() is False


def test_apply_first_open_choice_never_records_consent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    apply_first_open_choice(config, StudyIndexOpenChoice.NEVER)
    assert config.has_study_index_auto_add_consent() is True
    assert config.get_study_index_auto_add_on_open() is False


def test_apply_first_open_choice_always_records_consent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    apply_first_open_choice(config, StudyIndexOpenChoice.ALWAYS)
    assert config.has_study_index_auto_add_consent() is True
    assert config.get_study_index_auto_add_on_open() is True


def test_apply_first_open_choice_one_time_options_leave_consent_unrecorded(
    tmp_path: Path,
) -> None:
    for choice in (StudyIndexOpenChoice.ADD_ONCE, StudyIndexOpenChoice.SKIP_ONCE):
        config = _config(tmp_path / choice.value)
        apply_first_open_choice(config, choice)
        # One-time actions must not record a persistent preference, so the
        # prompt appears again on a later load.
        assert config.needs_study_index_auto_add_consent() is True
        assert config.get_study_index_auto_add_on_open() is False


def test_prompt_returns_and_persists_choice(qapp, monkeypatch, tmp_path: Path) -> None:
    _ = qapp
    config = _config(tmp_path)

    def fake_exec(self):
        self.choice = StudyIndexOpenChoice.ADD_ONCE
        return 1

    monkeypatch.setattr(StudyIndexFirstOpenDialog, "exec", fake_exec)

    result = prompt_study_index_first_open(config, None)
    assert result is StudyIndexOpenChoice.ADD_ONCE
    # ADD_ONCE leaves consent unrecorded.
    assert config.needs_study_index_auto_add_consent() is True


def test_explicit_index_opt_in_persists(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.set_study_index_auto_add_on_open(True)

    reloaded = ConfigManager(config_dir=config.config_dir)

    assert reloaded.has_study_index_auto_add_consent() is True
    assert reloaded.get_study_index_auto_add_on_open() is True


def test_recent_path_clear_forgets_all_remembered_locations(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.set_last_path(str(tmp_path / "input"))
    config.set_last_export_path(str(tmp_path / "export"))
    config.set_last_pylinac_output_path(str(tmp_path / "report"))
    config.add_recent_file(str(tmp_path / "recent"))

    config.clear_recent_path_history()

    assert config.get_last_path() == ""
    assert config.get_last_export_path() == ""
    assert config.get_last_pylinac_output_path() == ""
    assert config.get_recent_files() == []


def test_mpr_storage_clear_covers_current_and_legacy_locations(tmp_path: Path) -> None:
    config = _config(tmp_path)
    current = config.get_mpr_cache_path()
    legacy = config.config_dir / "mpr_cache"
    current.mkdir(parents=True)
    legacy.mkdir(parents=True)
    for directory in (current, legacy):
        (directory / "entry.npz").write_bytes(b"pixels")
        (directory / "entry_meta.json").write_text("{}", encoding="utf-8")
        (directory / "unowned.txt").write_text("keep", encoding="utf-8")

    result = config.clear_mpr_cache_storage()
    assert result == DeletionResult(removed=4)
    assert (current / "unowned.txt").exists()
    assert (legacy / "unowned.txt").exists()


def test_mpr_controller_starts_disabled_and_removes_legacy_pixels(
    qapp, tmp_path: Path
) -> None:
    _ = qapp
    config = _config(tmp_path)
    legacy = config.config_dir / "mpr_cache"
    legacy.mkdir()
    (legacy / "entry.npz").write_bytes(b"pixels")

    controller = MprController(SimpleNamespace(config_manager=config))

    assert controller._cache is None
    assert not (legacy / "entry.npz").exists()

    config.set_mpr_cache_enabled(True)
    controller.apply_cache_settings()
    active_cache = controller._cache
    assert active_cache is not None
    controller.clear_persistent_cache()
    assert controller._cache is not None
    assert controller._cache is not active_cache


def test_study_index_clear_removes_only_database_sidecars(tmp_path: Path) -> None:
    config = _config(tmp_path)
    database = tmp_path / "index" / "study.sqlite"
    database.parent.mkdir()
    config.set_study_index_db_path(str(database))
    for path in (
        database,
        Path(f"{database}-journal"),
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
    ):
        path.write_bytes(b"encrypted")
    sibling = database.parent / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")

    service = LocalStudyIndexService(config)

    result = service.clear_all_data()
    assert result == DeletionResult(removed=4)
    assert not database.exists()
    assert not Path(f"{database}-journal").exists()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()
    assert sibling.exists()


def test_diagnostics_are_private_bounded_and_age_pruned(tmp_path: Path) -> None:
    path = tmp_path / "private" / "debug.jsonl"
    debug_log_module.configure_debug_logging(True, path=path)
    try:
        debug_log_module.debug_log("module:1", "event", {"count": 1})
        assert path.exists()
        if os.name != "nt":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600

        oversized = b"x" * (debug_log_module._MAX_DEBUG_LOG_BYTES + 1)
        assert debug_log_module._bounded_log_bytes(b"", oversized) == b""

        old_timestamp = int((debug_log_module.time.time() - 8 * 24 * 60 * 60) * 1000)
        current_timestamp = int(debug_log_module.time.time() * 1000)
        path.write_text(
            json.dumps({"timestamp": old_timestamp})
            + "\n"
            + json.dumps({"timestamp": current_timestamp})
            + "\n",
            encoding="utf-8",
        )
        assert debug_log_module.prune_debug_log(path=path) is True
        retained = path.read_text(encoding="utf-8")
        assert str(old_timestamp) not in retained
        assert str(current_timestamp) in retained
    finally:
        debug_log_module.configure_debug_logging(False, path=None)


def test_settings_panel_applies_opt_ins_and_clears_on_disable(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    _ = qapp
    config = _config(tmp_path)
    config.set_mpr_cache_enabled(True)
    cache_dir = config.get_mpr_cache_path()
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "entry.npz").write_bytes(b"pixels")
    config.add_recent_file(str(tmp_path / "recent"))

    panel = PrivacyStorageSettingsPanel(config)
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)
    panel.study_index_auto_add.setChecked(True)
    panel.mpr_cache_enabled.setChecked(False)
    panel.diagnostics_enabled.setChecked(True)
    panel._clear_recent_paths()
    assert panel.apply() is True

    assert config.get_study_index_auto_add_on_open() is True
    assert config.get_mpr_cache_enabled() is False
    assert not (cache_dir / "entry.npz").exists()
    assert config.get_diagnostics_enabled() is True
    assert config.get_recent_files() == []

    debug_log_module.configure_debug_logging(False, path=None)


def test_privacy_setter_rolls_back_when_persistence_fails(
    monkeypatch, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(config, "save_config", lambda: False)

    assert config.set_mpr_cache_enabled(True) is False
    assert config.get_mpr_cache_enabled() is False
    assert config.set_diagnostics_enabled(True) is False
    assert config.get_diagnostics_enabled() is False


def test_clear_counts_only_successful_unlinks_and_reports_failures(
    monkeypatch, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    cache_dir = config.get_mpr_cache_path()
    cache_dir.mkdir(parents=True)
    removable = cache_dir / "removable.npz"
    blocked = cache_dir / "blocked.npz"
    removable.write_bytes(b"pixels")
    blocked.write_bytes(b"pixels")

    from utils.config import privacy_storage_config as storage_module

    original_unlink = storage_module.secure_unlink

    def unlink_with_failure(path: Path) -> bool:
        if path == blocked:
            raise PermissionError("synthetic failure")
        return original_unlink(path)

    monkeypatch.setattr(storage_module, "secure_unlink", unlink_with_failure)

    result = config.clear_mpr_cache_storage()

    assert result == DeletionResult(removed=1, failed=1)
    assert not removable.exists()
    assert blocked.exists()


def test_recent_path_clear_failure_keeps_state_and_ui_count(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    _ = qapp
    config = _config(tmp_path)
    config.add_recent_file(str(tmp_path / "recent"))
    panel = PrivacyStorageSettingsPanel(config)
    warnings: list[str] = []
    monkeypatch.setattr(config, "save_config", lambda: False)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, *_args, **_kwargs: warnings.append(title),
    )

    panel._clear_recent_paths()

    assert config.get_recent_files()
    assert panel.recent_path_count.text() == "1"
    assert warnings == ["Locations Not Cleared"]


def test_settings_clear_feedback_reports_partial_failure(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    _ = qapp
    config = _config(tmp_path)
    warnings: list[tuple[str, str]] = []
    information: list[str] = []
    panel = PrivacyStorageSettingsPanel(
        config,
        clear_mpr_cache_callback=lambda: DeletionResult(removed=1, failed=1),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message, *_args, **_kwargs: warnings.append(
            (title, message)
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, *_args, **_kwargs: information.append(title),
    )

    panel._clear_mpr_cache()

    assert warnings == [
        (
            "MPR Cache Not Fully Cleared",
            "Removed 1 owned local file(s); 1 cleanup step(s) failed. "
            "Try again after closing active operations.",
        )
    ]
    assert information == []
