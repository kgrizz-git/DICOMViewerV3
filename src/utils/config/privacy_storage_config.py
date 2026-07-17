"""Privacy-sensitive local storage preferences and bounded cleanup helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from utils.privacy.safe_storage import DeletionResult, secure_unlink


class PrivacyStorageConfigMixin:
    """Config mixin for opt-in caches, diagnostics, and disclosed locations."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_privacy_config(self) -> bool:
        save_func = cast(Callable[[], bool], getattr(self, "save_config"))
        return save_func()

    def _persist_privacy_value(self, key: str, value: object) -> bool:
        config = self._config()
        missing = object()
        previous = config.get(key, missing)
        config[key] = value
        if self._save_privacy_config():
            return True
        if previous is missing:
            config.pop(key, None)
        else:
            config[key] = previous
        return False

    def _privacy_storage_root(self) -> Path:
        return cast(Path, getattr(self, "private_storage_dir"))

    def get_mpr_cache_enabled(self) -> bool:
        """Return whether persistent derived-pixel caching was explicitly enabled."""

        return self._config().get("mpr_cache_enabled", False) is True

    def set_mpr_cache_enabled(self, enabled: bool) -> bool:
        return self._persist_privacy_value("mpr_cache_enabled", enabled is True)

    def get_mpr_cache_max_mb(self) -> int:
        raw = self._config().get("mpr_cache_max_mb", 500)
        try:
            return max(16, min(4096, int(raw)))
        except (TypeError, ValueError):
            return 500

    def set_mpr_cache_max_mb(self, max_mb: int) -> bool:
        return self._persist_privacy_value(
            "mpr_cache_max_mb", max(16, min(4096, int(max_mb)))
        )

    def get_mpr_cache_path(self) -> Path:
        """Return the private internal location for derived MPR pixels."""

        return self._privacy_storage_root() / "mpr-cache"

    def clear_mpr_cache_storage(self) -> DeletionResult:
        """Delete owned cache files and report successful and failed removals."""

        removed = 0
        failed = 0
        legacy = cast(Path, getattr(self, "config_dir")) / "mpr_cache"
        for directory in (self.get_mpr_cache_path(), legacy):
            if not directory.exists():
                continue
            for pattern in ("*.npz", "*_meta.json", ".mpr-cache-*.tmp"):
                for path in directory.glob(pattern):
                    if path.is_file() and not path.is_symlink():
                        try:
                            removed += int(secure_unlink(path))
                        except OSError:
                            failed += 1
        return DeletionResult(removed=removed, failed=failed)

    def get_diagnostics_enabled(self) -> bool:
        """Return whether protected, redacted diagnostics were explicitly enabled."""

        return self._config().get("diagnostics_enabled", False) is True

    def set_diagnostics_enabled(self, enabled: bool) -> bool:
        return self._persist_privacy_value("diagnostics_enabled", enabled is True)

    def get_diagnostics_log_path(self) -> Path:
        """Return the disclosed private diagnostics log location."""

        return self._privacy_storage_root() / "diagnostics" / "debug.jsonl"
