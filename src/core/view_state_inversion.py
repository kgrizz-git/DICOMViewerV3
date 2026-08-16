"""Pure helpers for persisted manual image-inversion state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def get_persisted_user_inversion(
    defaults: Mapping[str, Any] | None, photometric_interpretation: str | None
) -> bool:
    """Return the user inversion half, safely migrating legacy MONOCHROME1 state."""
    if not defaults:
        return False
    if isinstance(photometric_interpretation, (list, tuple)):
        photometric_interpretation = photometric_interpretation[0] if photometric_interpretation else None
    pi = photometric_interpretation
    if (
        "image_inversion_schema_version" not in defaults
        and str(pi or "").strip().upper() == "MONOCHROME1"
    ):
        return False
    return bool(defaults.get("image_inverted", False))
