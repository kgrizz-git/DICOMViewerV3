"""Tests for 3D volume render user preset helpers."""

from __future__ import annotations

from core.volume_3d_user_presets import (
    KEY_BACKGROUND,
    KEY_BASE_PRESET,
    KEY_NAME,
    KEY_OPACITY,
    KEY_QUALITY,
    KEY_THRESHOLD,
    normalize_user_preset,
    normalize_user_presets,
    snapshot_current_settings,
    upsert_user_preset,
)
from core.volume_renderer import PRESET_CT_BONE, PRESET_CT_SOFT_TISSUE


def test_normalize_user_preset_accepts_valid_record() -> None:
    raw = {
        "name": "My CT Head",
        "base_preset": PRESET_CT_BONE.name,
        "opacity": 80,
        "window": 1500.0,
        "level": 200.0,
        "threshold": -50,
    }
    norm = normalize_user_preset(raw)
    assert norm is not None
    assert norm[KEY_NAME] == "My CT Head"
    assert norm[KEY_BASE_PRESET] == PRESET_CT_BONE.name
    assert norm[KEY_OPACITY] == 80
    assert norm[KEY_THRESHOLD] == -50


def test_normalize_user_preset_rejects_unknown_base() -> None:
    assert normalize_user_preset({"name": "X", "base_preset": "Not Real"}) is None


def test_normalize_user_presets_drops_duplicates_case_insensitive() -> None:
    raw = [
        {"name": "A", "base_preset": PRESET_CT_BONE.name, "opacity": 100},
        {"name": "a", "base_preset": PRESET_CT_SOFT_TISSUE.name, "opacity": 50},
    ]
    out = normalize_user_presets(raw)
    assert len(out) == 1
    assert out[0][KEY_NAME] == "A"


def test_normalize_user_preset_accepts_legacy_int_opacity() -> None:
    # Records saved before opacity became a float must still load unchanged.
    norm = normalize_user_preset(
        {"name": "Legacy", "base_preset": PRESET_CT_BONE.name, "opacity": 80}
    )
    assert norm is not None
    assert norm[KEY_OPACITY] == 80


def test_normalize_user_preset_preserves_fractional_opacity() -> None:
    norm = normalize_user_preset(
        {"name": "Fine", "base_preset": PRESET_CT_BONE.name, "opacity": 5.5}
    )
    assert norm is not None
    assert norm[KEY_OPACITY] == 5.5


def test_normalize_user_preset_clamps_opacity_range() -> None:
    low = normalize_user_preset(
        {"name": "Lo", "base_preset": PRESET_CT_BONE.name, "opacity": -10}
    )
    high = normalize_user_preset(
        {"name": "Hi", "base_preset": PRESET_CT_BONE.name, "opacity": 250}
    )
    assert low is not None and low[KEY_OPACITY] == 0.0
    assert high is not None and high[KEY_OPACITY] == 100.0


def test_v2_fields_default_for_old_records() -> None:
    """Old records without background/quality get safe defaults."""
    norm = normalize_user_preset(
        {"name": "Old", "base_preset": PRESET_CT_BONE.name, "opacity": 80}
    )
    assert norm is not None
    assert norm[KEY_BACKGROUND] == "Black"
    assert norm[KEY_QUALITY] == "Normal"


def test_v2_fields_preserved_when_present() -> None:
    norm = normalize_user_preset(
        {"name": "V2", "base_preset": PRESET_CT_BONE.name, "opacity": 50,
         "background": "Dark Gray", "quality": "High"}
    )
    assert norm is not None
    assert norm[KEY_BACKGROUND] == "Dark Gray"
    assert norm[KEY_QUALITY] == "High"


def test_upsert_user_preset_replaces_same_name() -> None:
    first = snapshot_current_settings(
        name="Custom",
        base_preset=PRESET_CT_BONE.name,
        opacity=100,
        window=2000.0,
        level=0.0,
        threshold=0,
    )
    second = snapshot_current_settings(
        name="custom",
        base_preset=PRESET_CT_SOFT_TISSUE.name,
        opacity=40,
        window=800.0,
        level=100.0,
        threshold=20,
    )
    merged = upsert_user_preset([first], second)
    assert len(merged) == 1
    assert merged[0][KEY_BASE_PRESET] == PRESET_CT_SOFT_TISSUE.name
    assert merged[0][KEY_OPACITY] == 40
