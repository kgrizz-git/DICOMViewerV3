"""
QA / pylinac Config Mixin

Persists optional analysis parameters for pylinac-backed Tools menu workflows.
Values are read when opening the options dialog and written back when the user
accepts, so each analysis run passes fresh kwargs into ``analyze()`` (pylinac
does not store a global default for these in the viewer).

Mixin contract:
    Expects ``self.config`` (dict) and ``self.save_config()`` from ConfigManager.
"""

from __future__ import annotations

import math
from typing import Any, Callable, cast

# Matches pylinac 3.43.x ``ACRMRILarge.analyze(...)`` defaults.
ACR_MRI_LOW_CONTRAST_METHODS: tuple[str, ...] = (
    "Michelson",
    "Weber",
    "Ratio",
    "Difference",
    "Root Mean Square",
)
DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD: str = "Weber"
DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD: float = 0.001
DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER: float = 3.0
_MIN_LC_VIS_THRESHOLD: float = 0.0
_MAX_LC_VIS_THRESHOLD: float = 100.0
_MIN_LC_VIS_SANITY_MULTIPLIER: float = 0.01
_MAX_LC_VIS_SANITY_MULTIPLIER: float = 100.0

# Compare-mode multiplier sets — applied to pylinac defaults to produce combo items.
# Values are relative multipliers; e.g. 0.75 means "default × 0.75".
LC_COMPARE_MULTIPLIERS: tuple[float, ...] = (0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.25)
# Default multiplier indices (0-based within LC_COMPARE_MULTIPLIERS) for each row.
# Row 1 → 1.0 (index 3), Row 2 → 0.9 (index 2), Row 3 → 1.1 (index 4).
LC_COMPARE_ROW_DEFAULT_MULTIPLIER_INDICES: tuple[int, int, int] = (3, 2, 4)


class QaPylinacConfigMixin:
    """Config mixin: persisted pylinac-related QA options."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_config(self) -> None:
        save_func = cast(Callable[[], None], getattr(self, "save_config"))
        save_func()

    @staticmethod
    def _coerce_float(
        raw: Any,
        *,
        default: float,
        min_value: float,
        max_value: float,
    ) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(value):
            return default
        if value < min_value or value > max_value:
            return default
        return value

    def get_acr_mri_low_contrast_method(self) -> str:
        """
        Contrast algorithm passed to pylinac ``ACRMRILarge.analyze``.

        Returns:
            Stored method if valid, else the pylinac default (``Weber``).
        """
        raw = self._config().get("acr_mri_low_contrast_method")
        value = str(raw) if raw is not None else DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        if value not in ACR_MRI_LOW_CONTRAST_METHODS:
            return DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        return value

    def set_acr_mri_low_contrast_method(self, value: str) -> None:
        """
        Persist the MRI low-contrast contrast algorithm for the next run.

        Args:
            value: One of ``ACR_MRI_LOW_CONTRAST_METHODS``; invalid values fall
                back to the pylinac default.
        """
        method = str(value)
        if method not in ACR_MRI_LOW_CONTRAST_METHODS:
            method = DEFAULT_ACR_MRI_LOW_CONTRAST_METHOD
        self._config()["acr_mri_low_contrast_method"] = method
        self._save_config()

    def get_acr_mri_low_contrast_visibility_threshold(self) -> float:
        """
        Visibility threshold passed to pylinac ``ACRMRILarge.analyze`` for
        low-contrast detectability (Rose-style visibility vs threshold).

        Returns:
            Stored value, or the pylinac default (0.001) if missing/invalid.
        """
        return self._coerce_float(
            self._config().get("acr_mri_low_contrast_visibility_threshold"),
            default=DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
            min_value=_MIN_LC_VIS_THRESHOLD,
            max_value=_MAX_LC_VIS_THRESHOLD,
        )

    def set_acr_mri_low_contrast_visibility_threshold(self, value: float) -> None:
        """
        Persist the MRI low-contrast visibility threshold for the next run.

        Args:
            value: Clamped to [0.0, 100.0] before save. This is a viewer-side
                guardrail, not an upstream pylinac limit.
        """
        v = self._coerce_float(
            value,
            default=DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_THRESHOLD,
            min_value=_MIN_LC_VIS_THRESHOLD,
            max_value=_MAX_LC_VIS_THRESHOLD,
        )
        self._config()["acr_mri_low_contrast_visibility_threshold"] = v
        self._save_config()

    def get_acr_mri_low_contrast_visibility_sanity_multiplier(self) -> float:
        """
        Sanity cap multiplier passed to pylinac ``ACRMRILarge.analyze``.

        Returns:
            Stored multiplier, or the pylinac default (3.0) if missing/invalid.
        """
        return self._coerce_float(
            self._config().get("acr_mri_low_contrast_visibility_sanity_multiplier"),
            default=DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
            min_value=_MIN_LC_VIS_SANITY_MULTIPLIER,
            max_value=_MAX_LC_VIS_SANITY_MULTIPLIER,
        )

    def set_acr_mri_low_contrast_visibility_sanity_multiplier(
        self, value: float
    ) -> None:
        """
        Persist the MRI low-contrast sanity multiplier for the next run.

        Args:
            value: Clamped to [0.01, 100.0] before save.
        """
        v = self._coerce_float(
            value,
            default=DEFAULT_ACR_MRI_LOW_CONTRAST_VISIBILITY_SANITY_MULTIPLIER,
            min_value=_MIN_LC_VIS_SANITY_MULTIPLIER,
            max_value=_MAX_LC_VIS_SANITY_MULTIPLIER,
        )
        self._config()["acr_mri_low_contrast_visibility_sanity_multiplier"] = v
        self._save_config()

    def get_acr_qa_vanilla_pylinac(self) -> bool:
        """
        Whether ACR CT/MRI options dialogs default to stock ``ACRCT`` /
        ``ACRMRILarge`` (stricter slice-index rules) vs viewer integration classes.
        """
        return bool(self._config().get("acr_qa_vanilla_pylinac", False))

    def set_acr_qa_vanilla_pylinac(self, value: bool) -> None:
        """Persist vanilla-pylinac default for the next ACR QA options dialog."""
        self._config()["acr_qa_vanilla_pylinac"] = bool(value)
        self._save_config()
