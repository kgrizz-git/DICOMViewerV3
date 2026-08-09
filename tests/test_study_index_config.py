"""
Unit tests for ``utils.config.study_index_config.StudyIndexConfigMixin``.

The mixin expects a host providing ``self.config`` (dict), ``self.save_config()``
(which returns bool), ``self.config_dir`` (Path), and ``self.private_storage_dir``
(Path).
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.config.study_index_config import (
    STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT,
    StudyIndexConfigMixin,
)


def _make_host(tmp_path: Path) -> StudyIndexConfigMixin:
    class _Host(StudyIndexConfigMixin):
        def __init__(self) -> None:
            self.config: dict = {}
            self._loaded_config_keys: set[str] = set()
            self.config_dir = tmp_path
            self.private_storage_dir = tmp_path / "private"
            self.save_ok = True

        def save_config(self) -> bool:
            return self.save_ok

    return _Host()


class TestDbPath:
    def test_default_uses_protected_when_no_legacy(self, tmp_path):
        host = _make_host(tmp_path)
        path = host.get_default_study_index_db_path()
        assert path.endswith("study-index/study_index.sqlite")
        assert "private" in path

    def test_default_keeps_legacy_when_protected_absent(self, tmp_path):
        legacy = tmp_path / "study_index.sqlite"
        legacy.write_text("x")
        host = _make_host(tmp_path)
        assert host.get_default_study_index_db_path() == str(legacy)

    def test_default_uses_protected_when_both_exist(self, tmp_path):
        legacy = tmp_path / "study_index.sqlite"
        legacy.write_text("x")
        protected = tmp_path / "private" / "study-index" / "study_index.sqlite"
        protected.parent.mkdir(parents=True)
        protected.write_text("y")
        host = _make_host(tmp_path)
        assert host.get_default_study_index_db_path() == str(protected)

    def test_custom_path_normalized(self, tmp_path, monkeypatch):
        host = _make_host(tmp_path)
        monkeypatch.chdir(tmp_path)
        rel = os.path.normpath(os.path.abspath("custom db.sqlite"))
        host.set_study_index_db_path("sub/../custom db.sqlite")
        assert host.get_study_index_db_path() == rel

    def test_empty_custom_path_uses_default(self, tmp_path):
        host = _make_host(tmp_path)
        host.set_study_index_db_path("   ")
        assert host.get_study_index_db_path().endswith("study_index.sqlite")

    def test_set_path_rolls_back_on_save_failure(self, tmp_path):
        host = _make_host(tmp_path)
        host.save_ok = False
        assert host.set_study_index_db_path("x.sqlite") is False
        assert host._config().get("study_index_db_path", "") == ""

    def test_set_path_returns_true_on_success(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.set_study_index_db_path("x.sqlite") is True


class TestAutoAddOnOpen:
    def test_default_false(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.get_study_index_auto_add_on_open() is False

    def test_true_requires_consent_and_flag(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_on_open"] = True
        host.config["study_index_auto_add_consent"] = False
        assert host.get_study_index_auto_add_on_open() is False

    def test_true_when_both_set(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_on_open"] = True
        host.config["study_index_auto_add_consent"] = True
        assert host.get_study_index_auto_add_on_open() is True

    def test_non_bool_consent_false(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_consent"] = "yes"
        assert host.get_study_index_auto_add_on_open() is False

    def test_set_true_persists_consent(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.set_study_index_auto_add_on_open(True) is True
        assert host.config["study_index_auto_add_on_open"] is True
        assert host.config["study_index_auto_add_consent"] is True

    def test_set_false_persists_consent(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.set_study_index_auto_add_on_open(False) is True
        assert host.config["study_index_auto_add_on_open"] is False
        assert host.config["study_index_auto_add_consent"] is False

    def test_set_rolls_back_on_save_failure(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_on_open"] = "old"
        host.config["study_index_auto_add_consent"] = "oldconsent"
        host.save_ok = False
        assert host.set_study_index_auto_add_on_open(True) is False
        assert host.config["study_index_auto_add_on_open"] == "old"
        assert host.config["study_index_auto_add_consent"] == "oldconsent"

    def test_rolls_back_and_pops_consent_on_failure(self, tmp_path):
        host = _make_host(tmp_path)
        host.save_ok = False
        assert host.set_study_index_auto_add_on_open(True) is False
        assert "study_index_auto_add_consent" not in host.config


class TestConsentMetadata:
    def test_has_consent_false_initially(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.has_study_index_auto_add_consent() is False

    def test_has_consent_true_after_bool_set(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_consent"] = True
        assert host.has_study_index_auto_add_consent() is True

    def test_needs_consent_true_initially(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.needs_study_index_auto_add_consent() is True

    def test_needs_consent_false_after_recorded(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_auto_add_consent"] = False
        assert host.needs_study_index_auto_add_consent() is False

    def test_migration_true_when_legacy_without_consent(self, tmp_path):
        host = _make_host(tmp_path)
        host._loaded_config_keys = {"study_index_auto_add_on_open"}
        assert host.is_study_index_auto_add_consent_migration() is True

    def test_migration_false_when_consent_loaded(self, tmp_path):
        host = _make_host(tmp_path)
        host._loaded_config_keys = {
            "study_index_auto_add_on_open",
            "study_index_auto_add_consent",
        }
        assert host.is_study_index_auto_add_consent_migration() is False


class TestBrowserColumnOrder:
    def test_default_order(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.get_study_index_browser_column_order() == list(
            STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT
        )

    def test_unknown_ids_dropped(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_browser_column_order"] = [
            "patient_name",
            "bogus_id",
            "study_date",
        ]
        order = host.get_study_index_browser_column_order()
        assert "bogus_id" not in order
        assert order[0] == "patient_name"
        assert order[1] == "study_date"

    def test_missing_ids_appended_in_default_order(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_browser_column_order"] = ["study_date"]
        order = host.get_study_index_browser_column_order()
        assert order[0] == "study_date"
        assert set(order) == set(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)

    def test_non_list_raw_falls_back_to_default(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_browser_column_order"] = "not-a-list"
        assert host.get_study_index_browser_column_order() == list(
            STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT
        )

    def test_set_stores_cleaned_order(self, tmp_path):
        host = _make_host(tmp_path)
        host.set_study_index_browser_column_order(
            ["study_date", "bogus", "patient_name"]
        )
        stored = host.config["study_index_browser_column_order"]
        assert "bogus" not in stored
        assert stored[0] == "study_date"
        assert stored[1] == "patient_name"

    def test_set_appends_missing_ids(self, tmp_path):
        host = _make_host(tmp_path)
        host.set_study_index_browser_column_order(["patient_id"])
        stored = host.config["study_index_browser_column_order"]
        assert set(stored) == set(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)
        assert stored[0] == "patient_id"

    def test_set_duplicate_ids_are_deduplicated(self, tmp_path):
        # KNOWN DEFECT (POST_REVIEW_BUGFIXES_2026_08_08.md #21A): duplicate known
        # ids make len(cleaned) == len(known), so the append-missing branch is
        # skipped and duplicates are stored verbatim while other columns drop out.
        # Keep the intended contract as a strict xfail until the separate bugfix
        # branch implements the documented deduplication.
        host = _make_host(tmp_path)
        host.set_study_index_browser_column_order(
            ["patient_name"] * len(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)
        )
        stored = host.config["study_index_browser_column_order"]
        assert stored == list(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)

    def test_get_duplicate_ids_are_deduplicated(self, tmp_path):
        host = _make_host(tmp_path)
        host.config["study_index_browser_column_order"] = [
            "patient_name"
        ] * len(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)
        assert host.get_study_index_browser_column_order() == list(
            STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT
        )

    def test_set_writes_in_place_before_save(self, tmp_path):
        host = _make_host(tmp_path)
        host.save_ok = False
        host.set_study_index_browser_column_order(["patient_id"])
        # The mixin writes the cleaned order to config before persisting, so a
        # later save failure does not roll the in-place write back.
        assert host.config["study_index_browser_column_order"][0] == "patient_id"


class TestPassphraseWarning:
    def test_default_false(self, tmp_path):
        host = _make_host(tmp_path)
        assert host.get_study_index_passphrase_warning_dismissed() is False

    def test_set_true(self, tmp_path):
        host = _make_host(tmp_path)
        host.set_study_index_passphrase_warning_dismissed(True)
        assert host.get_study_index_passphrase_warning_dismissed() is True

    def test_set_false(self, tmp_path):
        host = _make_host(tmp_path)
        host.set_study_index_passphrase_warning_dismissed(False)
        assert host.get_study_index_passphrase_warning_dismissed() is False
