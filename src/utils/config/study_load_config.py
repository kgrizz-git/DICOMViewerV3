"""
Study load memory budget configuration mixin.

Persists the settings that drive ``core.study_cache.StudyCache``'s primary
memory budget (a configurable fraction of total system RAM) and the
high-water study-count safety net that backstops it.

Expects ``self.config`` and ``self.save_config()`` from ConfigManager.
"""

from collections.abc import Callable
from typing import Any, cast

#: Fraction of total system RAM used as the memory budget, clamped to this range.
STUDY_LOAD_MEMORY_FRACTION_MIN = 0.1
STUDY_LOAD_MEMORY_FRACTION_MAX = 0.9

#: Safety-net study-count cap range.
STUDY_LOAD_MAX_STUDIES_CAP_MIN = 1
STUDY_LOAD_MAX_STUDIES_CAP_MAX = 200


class StudyLoadConfigMixin:
    """Config mixin: study-load memory budget fraction and study-count cap."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    def get_study_load_memory_fraction(self) -> float:
        """Fraction of total system RAM to use as the study-load memory budget.

        Clamped to ``[0.1, 0.9]``; falls back to the default (0.40) for
        missing or invalid stored values.
        """
        raw = self._config().get("study_load_memory_fraction", 0.40)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.40
        return max(STUDY_LOAD_MEMORY_FRACTION_MIN, min(STUDY_LOAD_MEMORY_FRACTION_MAX, value))

    def set_study_load_memory_fraction(self, fraction: float) -> bool:
        """Persist the memory-budget fraction, clamped to ``[0.1, 0.9]``."""
        try:
            clamped = max(
                STUDY_LOAD_MEMORY_FRACTION_MIN,
                min(STUDY_LOAD_MEMORY_FRACTION_MAX, float(fraction)),
            )
        except (TypeError, ValueError):
            clamped = 0.40
        config = self._config()
        previous = config.get("study_load_memory_fraction", 0.40)
        config["study_load_memory_fraction"] = clamped
        if self._save_study_load_config():
            return True
        config["study_load_memory_fraction"] = previous
        return False

    def get_study_load_max_studies_cap(self) -> int:
        """Safety-net cap on the number of loaded studies (default 20).

        Clamped to ``[1, 200]``; falls back to the default for missing or
        invalid stored values.
        """
        raw = self._config().get("study_load_max_studies_cap", 20)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return 20
        return max(STUDY_LOAD_MAX_STUDIES_CAP_MIN, min(STUDY_LOAD_MAX_STUDIES_CAP_MAX, value))

    def set_study_load_max_studies_cap(self, cap: int) -> bool:
        """Persist the study-count safety-net cap, clamped to ``[1, 200]``."""
        try:
            clamped = max(
                STUDY_LOAD_MAX_STUDIES_CAP_MIN,
                min(STUDY_LOAD_MAX_STUDIES_CAP_MAX, int(cap)),
            )
        except (TypeError, ValueError):
            clamped = 20
        config = self._config()
        previous = config.get("study_load_max_studies_cap", 20)
        config["study_load_max_studies_cap"] = clamped
        if self._save_study_load_config():
            return True
        config["study_load_max_studies_cap"] = previous
        return False

    def _save_study_load_config(self) -> bool:
        save_func = cast(Callable[[], bool], getattr(self, "save_config"))
        return save_func()
