"""
Volume 3D user preset helpers.

Serializes and validates user-saved 3D volume render settings (base transfer
function, opacity, window/level, threshold) for persistence via
``ConfigManager.get_volume_3d_user_presets()``.

Inputs:
    - Dict records from display config JSON.

Outputs:
    - Validated preset dicts; lookup helpers for built-in base presets.

Requirements:
    - ``core.volume_renderer.BUILTIN_PRESETS``
"""

from __future__ import annotations

from typing import Any

from core.volume_renderer import BUILTIN_PRESETS, TransferFunctionPreset

# Keys stored in each user preset record.
KEY_NAME = "name"
KEY_BASE_PRESET = "base_preset"
KEY_OPACITY = "opacity"
KEY_WINDOW = "window"
KEY_LEVEL = "level"
KEY_THRESHOLD = "threshold"
# V2 fields — missing in old records, normalized to safe defaults.
KEY_BACKGROUND = "background"
KEY_QUALITY = "quality"


def builtin_preset_by_name(name: str) -> TransferFunctionPreset | None:
    """Return a built-in transfer-function preset by name, or ``None``."""
    for preset in BUILTIN_PRESETS:
        if preset.name == name:
            return preset
    return None


def builtin_preset_names() -> list[str]:
    """Return ordered names of built-in transfer-function presets."""
    return [p.name for p in BUILTIN_PRESETS]


def normalize_user_preset(raw: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate and normalize a user preset dict read from config.

    Returns ``None`` if the record is invalid or references an unknown base preset.
    """
    if not isinstance(raw, dict):
        return None
    name = str(raw.get(KEY_NAME, "")).strip()
    base = str(raw.get(KEY_BASE_PRESET, "")).strip()
    if not name or not base or builtin_preset_by_name(base) is None:
        return None
    try:
        # Opacity is stored as a resolved percent (0-100).  It is a float so
        # the low-opacity range can be expressed with sub-percent precision
        # (e.g. 5.5%); legacy integer records parse unchanged.
        opacity = float(raw.get(KEY_OPACITY, 100.0))
        window = float(raw.get(KEY_WINDOW, 2000.0))
        level = float(raw.get(KEY_LEVEL, 0.0))
        threshold = int(raw.get(KEY_THRESHOLD, 0))
    except (TypeError, ValueError):
        return None
    opacity = max(0.0, min(100.0, opacity))
    threshold = max(-500, min(500, threshold))
    window = max(1.0, window)
    # V2 fields — safe defaults for records saved before these existed.
    background = str(raw.get(KEY_BACKGROUND, "Black")).strip() or "Black"
    quality = str(raw.get(KEY_QUALITY, "Normal")).strip() or "Normal"
    return {
        KEY_NAME: name,
        KEY_BASE_PRESET: base,
        KEY_OPACITY: opacity,
        KEY_WINDOW: window,
        KEY_LEVEL: level,
        KEY_THRESHOLD: threshold,
        KEY_BACKGROUND: background,
        KEY_QUALITY: quality,
    }


def normalize_user_presets(raw_list: Any) -> list[dict[str, Any]]:
    """Validate a list of user presets from config, dropping invalid entries."""
    if not isinstance(raw_list, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_list:
        norm = normalize_user_preset(item)
        if norm is None:
            continue
        key = norm[KEY_NAME].casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def snapshot_current_settings(
    *,
    name: str,
    base_preset: str,
    opacity: float,
    window: float,
    level: float,
    threshold: int,
    background: str = "Black",
    quality: str = "Normal",
) -> dict[str, Any]:
    """Build a config-ready preset dict from current viewer control values."""
    norm = normalize_user_preset(
        {
            KEY_NAME: name,
            KEY_BASE_PRESET: base_preset,
            KEY_OPACITY: opacity,
            KEY_WINDOW: window,
            KEY_LEVEL: level,
            KEY_THRESHOLD: threshold,
            KEY_BACKGROUND: background,
            KEY_QUALITY: quality,
        }
    )
    if norm is None:
        raise ValueError(f"Invalid preset snapshot for base preset {base_preset!r}")
    return norm


def upsert_user_preset(
    presets: list[dict[str, Any]], new_preset: dict[str, Any]
) -> list[dict[str, Any]]:
    """Replace an existing preset with the same name (case-insensitive) or append."""
    key = new_preset[KEY_NAME].casefold()
    updated = [p for p in presets if p[KEY_NAME].casefold() != key]
    updated.append(new_preset)
    return updated
