"""
Study index configuration mixin.

Persists optional encrypted local study index settings: database file path
(user-configurable), and whether successful opens are recorded automatically.

Expects ``self.config`` and ``self.save_config()`` from ConfigManager.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

# Stable column ids for the grouped study index browser (QTableView); persisted in config.
STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT: tuple[str, ...] = (
    "patient_name",
    "patient_id",
    "study_date",
    "indexed_at",
    "accession_number",
    "study_description",
    "study_root_path",
    "instance_count",
    "series_count",
    "modalities",
    "open_file_path",
    "study_uid",
)


class StudyIndexConfigMixin:
    """Config mixin: local study index (SQLCipher) path and auto-add-on-open."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_study_index_config(self) -> bool:
        save_func = cast(Callable[[], bool], getattr(self, "save_config"))
        return save_func()

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def _study_index_config_dir(self) -> Path:
        return cast(Path, getattr(self, "config_dir"))

    def get_default_study_index_db_path(self) -> str:
        """Return the protected default, preserving an existing legacy database."""

        legacy = self._study_index_config_dir() / "study_index.sqlite"
        private_root = cast(Path, getattr(self, "private_storage_dir"))
        protected = private_root / "study-index" / "study_index.sqlite"
        if legacy.exists() and not protected.exists():
            return str(legacy)
        return str(protected)

    def get_study_index_db_path(self) -> str:
        """Resolved DB path: user override or default."""
        custom = (self._config().get("study_index_db_path") or "").strip()
        if custom:
            return os.path.normpath(os.path.abspath(custom))
        return self.get_default_study_index_db_path()

    def set_study_index_db_path(self, path: str) -> bool:
        """Set custom DB path, or empty string to use default."""
        config = self._config()
        previous = config.get("study_index_db_path", "")
        config["study_index_db_path"] = (path or "").strip()
        if self._save_study_index_config():
            return True
        config["study_index_db_path"] = previous
        return False

    def get_study_index_auto_add_on_open(self) -> bool:
        consent = self._config().get("study_index_auto_add_consent")
        if not isinstance(consent, bool):
            return False
        return consent is True and self._config().get("study_index_auto_add_on_open") is True

    def set_study_index_auto_add_on_open(self, enabled: bool) -> bool:
        """Record an explicit user choice and apply it to automatic indexing."""

        config = self._config()
        previous_enabled = config.get("study_index_auto_add_on_open", False)
        previous_consent = config.get("study_index_auto_add_consent")
        config["study_index_auto_add_on_open"] = enabled is True
        config["study_index_auto_add_consent"] = enabled is True
        if self._save_study_index_config():
            return True
        config["study_index_auto_add_on_open"] = previous_enabled
        if previous_consent is None:
            config.pop("study_index_auto_add_consent", None)
        else:
            config["study_index_auto_add_consent"] = previous_consent
        return False

    def has_study_index_auto_add_consent(self) -> bool:
        """Return whether an explicit enable/disable choice has been recorded."""

        return isinstance(self._config().get("study_index_auto_add_consent"), bool)

    def needs_study_index_auto_add_consent(self) -> bool:
        """Return whether first-use or legacy migration consent is still required."""

        return not self.has_study_index_auto_add_consent()

    def is_study_index_auto_add_consent_migration(self) -> bool:
        """Return whether a legacy auto-add setting lacks explicit consent metadata."""

        loaded_keys = cast(set[str], getattr(self, "_loaded_config_keys", set()))
        return (
            "study_index_auto_add_on_open" in loaded_keys
            and "study_index_auto_add_consent" not in loaded_keys
        )

    def get_study_index_browser_column_order(self) -> list[str]:
        """
        Column order (left-to-right) for the grouped study index table.

        Unknown ids are dropped; any known ids missing from the stored list are
        appended in default order so new columns appear after upgrades.
        """
        raw = self._config().get("study_index_browser_column_order")
        if not isinstance(raw, list):
            raw = []
        known = set(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)
        out = [str(x) for x in raw if isinstance(x, str) and x in known]
        for cid in STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT:
            if cid not in out:
                out.append(cid)
        return out

    def set_study_index_browser_column_order(self, column_ids: list[str]) -> None:
        """Persist reorderable header order (list of stable column id strings)."""
        known = set(STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT)
        cleaned = [str(x) for x in column_ids if x in known]
        if len(cleaned) != len(known):
            for cid in STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT:
                if cid not in cleaned:
                    cleaned.append(cid)
        self._config()["study_index_browser_column_order"] = cleaned
        self._save_config()

    def get_study_index_passphrase_warning_dismissed(self) -> bool:
        """Return True if the user has asked not to see the passphrase warning again."""
        return bool(self._config().get("study_index_passphrase_warning_dismissed", False))

    def set_study_index_passphrase_warning_dismissed(self, dismissed: bool) -> None:
        """Persist the user's choice to suppress the passphrase warning."""
        self._config()["study_index_passphrase_warning_dismissed"] = bool(dismissed)
        self._save_config()
