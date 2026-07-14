"""Tests for transfer-function steepness (auto-Detail selection).

Pure logic — no VTK required.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.volume_render_presets import (
    PRESET_CT_BONE,
    PRESET_CT_FAT,
    PRESET_CT_SMOOTH_ANATOMY,
    PRESET_CT_SOFT_TISSUE,
    PRESET_GENERIC_INTENSITY,
    PRESET_MR_DEFAULT,
    STEEP_PRESET_THRESHOLD,
    TransferFunctionPreset,
    is_steep_preset,
    preset_steepness,
)


def test_steep_presets_score_above_threshold() -> None:
    # CT Fat (narrow ~50 HU band) and CT Bone (sharp onset) are steep.
    assert preset_steepness(PRESET_CT_FAT) >= STEEP_PRESET_THRESHOLD
    assert preset_steepness(PRESET_CT_BONE) >= STEEP_PRESET_THRESHOLD
    assert is_steep_preset(PRESET_CT_FAT) is True


def test_gentle_presets_score_below_threshold() -> None:
    for preset in (PRESET_CT_SOFT_TISSUE, PRESET_CT_SMOOTH_ANATOMY,
                   PRESET_MR_DEFAULT, PRESET_GENERIC_INTENSITY):
        assert preset_steepness(preset) < STEEP_PRESET_THRESHOLD, preset.name
        assert is_steep_preset(preset) is False


def test_fat_is_steeper_than_soft_tissue() -> None:
    assert preset_steepness(PRESET_CT_FAT) > preset_steepness(PRESET_CT_SOFT_TISSUE)


def test_degenerate_preset_returns_zero() -> None:
    one_point = TransferFunctionPreset(
        name="x", scalar_opacity=[(0.0, 0.5)], color=[(0.0, 1.0, 1.0, 1.0)]
    )
    empty = TransferFunctionPreset(name="y", scalar_opacity=[], color=[])
    assert preset_steepness(one_point) == 0.0
    assert preset_steepness(empty) == 0.0


def test_full_window_ramp_is_baseline_one() -> None:
    # A ramp spanning the whole window is the gentle baseline (window-normalized
    # steepness == 1.0), regardless of absolute scalar scale.
    small = TransferFunctionPreset(
        name="small", scalar_opacity=[(0.0, 0.0), (100.0, 1.0)],
        color=[(0.0, 0, 0, 0), (100.0, 1, 1, 1)],
    )
    big = TransferFunctionPreset(
        name="big", scalar_opacity=[(0.0, 0.0), (1000.0, 1.0)],
        color=[(0.0, 0, 0, 0), (1000.0, 1, 1, 1)],
    )
    assert preset_steepness(small) == 1.0
    assert preset_steepness(big) == 1.0


def test_narrow_feature_in_wide_window_is_steep() -> None:
    # The same opacity jump confined to a narrow band inside a wide window is
    # much steeper than one spread across the window.
    spread = TransferFunctionPreset(
        name="spread", scalar_opacity=[(0.0, 0.0), (100.0, 1.0)],
        color=[(0.0, 0, 0, 0), (100.0, 1, 1, 1)],
    )
    narrow_band = TransferFunctionPreset(
        name="narrow_band",
        scalar_opacity=[(0.0, 0.0), (40.0, 0.0), (50.0, 1.0), (100.0, 1.0)],
        color=[(0.0, 0, 0, 0), (40.0, 0, 0, 0), (50.0, 1, 1, 1), (100.0, 1, 1, 1)],
    )
    assert preset_steepness(narrow_band) > preset_steepness(spread)
