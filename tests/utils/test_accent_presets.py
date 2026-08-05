"""Tests for accent_presets: color mapping presets and fallbacks."""

from __future__ import annotations

from utils.accent_presets import (
    ACCENT_PRESETS,
    AccentPreset,
    get_preset,
)


def test_accent_presets_contain_expected_keys() -> None:
    expected_keys = {"steel-blue", "violet", "navy", "garnet"}
    assert set(ACCENT_PRESETS.keys()) == expected_keys


def test_get_preset_returns_correct_preset_for_valid_ids() -> None:
    preset = get_preset("violet")
    assert isinstance(preset, AccentPreset)
    assert preset.label == "Violet"
    assert preset.accent == "#7c4dff"


def test_get_preset_fallback_for_invalid_id() -> None:
    preset = get_preset("invalid-preset-id")
    assert isinstance(preset, AccentPreset)
    assert preset.label == "Steel Blue"
    assert preset.accent == "#4285da"


def test_get_preset_fallback_for_none_or_empty_string() -> None:
    preset_none = get_preset(None)  # type: ignore[arg-type]
    preset_empty = get_preset("")
    assert preset_none.label == "Steel Blue"
    assert preset_empty.label == "Steel Blue"


def test_accent_preset_attributes() -> None:
    for _preset_id, preset in ACCENT_PRESETS.items():
        assert isinstance(preset, AccentPreset)
        assert len(preset.label) > 0
        assert preset.accent.startswith("#")
        assert preset.accent_light.startswith("#")
        assert preset.accent_dark.startswith("#")
        assert preset.accent_soft.startswith("#")
        assert preset.accent_muted.startswith("#")
