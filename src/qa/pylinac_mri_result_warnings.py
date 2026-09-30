"""Warnings for ACR MRI values published by pylinac."""

from __future__ import annotations

import math
from typing import Any


def _warn_lc_score_mismatch(raw: dict[str, Any], analyzer: Any, warnings: list[str]) -> None:
    """Check the serialized score against the sum of per-slice scores."""
    try:
        slices = analyzer.low_contrast_multi_slice.slices.values()
        recomputed_score = sum(item.score for item in slices)
    except (AttributeError, TypeError, ValueError):
        return
    module = raw.get("low_contrast_multi_slice_module")
    structured = module.get("score") if isinstance(module, dict) else None
    if not isinstance(structured, (int, float)) or not math.isfinite(structured):
        return
    if math.isfinite(recomputed_score) and not math.isclose(
        recomputed_score, structured, rel_tol=1e-6, abs_tol=1e-6
    ):
        warnings.append("MRI low-contrast score differs from structured pylinac results.")


def _warn_mtf_extrapolation(raw: dict[str, Any], analyzer: Any, warnings: list[str]) -> None:
    """Flag MRI MTF@50% values beyond pylinac's measured line-pair range."""
    slice1 = raw.get("slice1")
    if not isinstance(slice1, dict):
        return
    live_slice = getattr(analyzer, "slice1", None)
    for axis in ("row", "col"):
        value = slice1.get(f"{axis}_mtf_50")
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        try:
            # Both pylinac MTF properties construct from this same spacing grid.
            spacings = live_slice.spacings
            if value > max(spacings):
                warnings.append(f"MRI {axis} MTF@50% was extrapolated by pylinac.")
        except (AttributeError, TypeError, ValueError):
            continue
