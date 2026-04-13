"""
Study index configuration mixin.

Persists optional encrypted local study index settings: database file path
(user-configurable), and whether successful opens are recorded automatically.

Expects ``self.config`` and ``self.save_config()`` from ConfigManager.
"""

import os
from pathlib import Path
from typing import Any, Callable, cast


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
