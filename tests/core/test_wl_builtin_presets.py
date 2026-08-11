"""Tests for core.wl_builtin_presets — built-in window/level presets per modality."""

from __future__ import annotations

import pytest

from core.wl_builtin_presets import (
    BUILTIN_PRESETS,
    MR_HU_PRESETS,
    WLPreset,
    get_builtin_presets,
    get_mr_hu_builtin_presets,
)


def test_get_builtin_presets_ct():
    presets = get_builtin_presets("CT")
    assert len(presets) == 11
    assert all(p[2] is True for p in presets)


def test_get_builtin_presets_mr():
    presets = get_builtin_presets("MR")
    assert len(presets) == 5
    assert all(p[2] is False for p in presets)


def test_get_builtin_presets_pt():
    presets = get_builtin_presets("PT")
    assert len(presets) == 2


@pytest.mark.parametrize("modality", ["ct", "Ct", "CT"])
def test_get_builtin_presets_case_insensitive(modality):
    assert get_builtin_presets(modality) == get_builtin_presets("CT")


def test_get_builtin_presets_whitespace():
    assert get_builtin_presets(" CT ") == get_builtin_presets("CT")


def test_get_builtin_presets_unknown_modality():
    assert get_builtin_presets("ZZZ") == get_builtin_presets(None)


@pytest.mark.parametrize("modality", ["", None])
def test_get_builtin_presets_empty_modality(modality):
    presets = get_builtin_presets(modality)
    assert presets == list(BUILTIN_PRESETS["ANY"])


def test_get_builtin_presets_returns_copy():
    presets = get_builtin_presets("CT")
    presets.clear()
    assert len(get_builtin_presets("CT")) == 11


def test_get_mr_hu_builtin_presets():
    presets = get_mr_hu_builtin_presets()
    assert len(presets) == 3
    assert all(p[2] is True for p in presets)


def test_preset_tuple_shape():
    for modality, presets in BUILTIN_PRESETS.items():
        for preset in presets:
            assert len(preset) == 4, f"{modality}: {preset}"
            assert isinstance(preset, tuple)
            assert isinstance(preset[0], float)
            assert isinstance(preset[1], float)
            assert isinstance(preset[2], bool)
            assert isinstance(preset[3], str) or preset[3] is None


def test_any_table_present():
    assert "ANY" in BUILTIN_PRESETS
    assert len(BUILTIN_PRESETS["ANY"]) >= 2


def test_mr_hu_presets_all_rescaled():
    assert all(p[2] is True for p in MR_HU_PRESETS)


def test_wlpreset_type_alias():
    preset: WLPreset = (40.0, 400.0, True, "Test")
    assert preset == (40.0, 400.0, True, "Test")
