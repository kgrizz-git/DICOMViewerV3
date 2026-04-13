"""
Study index configuration mixin.

Persists optional encrypted local study index settings: database file path
(user-configurable), and whether successful opens are recorded automatically.

Expects ``self.config`` and ``self.save_config()`` from ConfigManager.
"""

import os
from pathlib import Path
from typing import Any, Callable, cast

# Stable column ids for the grouped study index browser (QTableView); persisted in config.
STUDY_INDEX_BROWSER_COLUMN_IDS_DEFAULT: tuple[str, ...] = (
    "patient_name",
    "patient_id",
    "study_date",
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

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def _study_index_config_dir(self) -> Path:
        return cast(Path, getattr(self, "config_dir"))

    def get_default_study_index_db_path(self) -> str:
        """Default index DB path under the app config directory."""
        return str(self._study_index_config_dir() / "study_index.sqlite")

    def get_study_index_db_path(self) -> str:
        """Resolved DB path: user override or default."""
        custom = (self._config().get("study_index_db_path") or "").strip()
        if custom:
            return os.path.normpath(os.path.abspath(custom))
        return self.get_default_study_index_db_path()

    def set_study_index_db_path(self, path: str) -> None:
        """Set custom DB path, or empty string to use default."""
        self._config()["study_index_db_path"] = (path or "").strip()
        self._save_config()

    def get_study_index_auto_add_on_open(self) -> bool:
        return bool(self._config().get("study_index_auto_add_on_open", True))

    def set_study_index_auto_add_on_open(self, enabled: bool) -> None:
        self._config()["study_index_auto_add_on_open"] = bool(enabled)
        self._save_config()

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
