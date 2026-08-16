"""Tests for core.wl_builtin_presets — built-in window/level presets per modality."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset

from core.wl_builtin_presets import (
    BUILTIN_PRESETS,
    MR_HU_PRESETS,
    WLPreset,
    get_builtin_presets,
    get_hu_gated_builtin_presets,
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
def test_get_builtin_presets_empty_modality_uses_any(modality):
    presets = get_builtin_presets(modality)
    assert len(presets) >= 2
    assert all(p[2] is False for p in presets)


def test_get_builtin_presets_returns_copy():
    presets = get_builtin_presets("CT")
    presets.clear()
    assert len(get_builtin_presets("CT")) == 11


def test_get_mr_hu_builtin_presets():
    presets = get_mr_hu_builtin_presets()
    assert len(presets) == 3
    assert all(p[2] is True for p in presets)


def test_preset_tuple_shape():
    for modality in ("CT", "MR", "PT"):
        presets = BUILTIN_PRESETS[modality]
        for preset in presets:
            assert len(preset) == 4, f"{modality}: {preset}"
            assert isinstance(preset, tuple)
            assert isinstance(preset[0], float)
            assert isinstance(preset[1], float)
            assert isinstance(preset[2], bool)
            assert isinstance(preset[3], str) or preset[3] is None


def test_any_fallback_present():
    presets = get_builtin_presets("ZZZ")
    assert len(presets) >= 2
    assert all(p[2] is False for p in presets)


def test_mr_hu_presets_all_rescaled():
    assert all(p[2] is True for p in MR_HU_PRESETS)


def test_wlpreset_type_alias():
    preset: WLPreset = (40.0, 400.0, True, "Test")
    assert preset == (40.0, 400.0, True, "Test")


def _make_dataset(*, bits_allocated: int = 16, bits_stored: int = 12, pixel_representation: int = 0) -> Dataset:
    ds = Dataset()
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_stored
    ds.HighBit = bits_stored - 1
    ds.PixelRepresentation = pixel_representation
    return ds


class TestBitDepthAwarePresets:
    def test_cr_with_dataset_is_rescaled_false(self):
        ds = _make_dataset(bits_stored=12)
        presets = get_builtin_presets("CR", dataset=ds)
        assert all(p[2] is False for p in presets)

    def test_dx_with_dataset_is_rescaled_false(self):
        ds = _make_dataset(bits_stored=10)
        presets = get_builtin_presets("DX", dataset=ds)
        assert all(p[2] is False for p in presets)

    def test_cr_no_dataset_uses_16bit_fallback(self):
        presets = get_builtin_presets("CR")
        assert len(presets) >= 2
        assert all(p[2] is False for p in presets)
        default = presets[0]
        assert default[0] == pytest.approx(32767.5)
        assert default[1] == pytest.approx(65535.0)

    def test_wide_is_1_5x_default_width(self):
        ds = _make_dataset(bits_stored=12)
        presets = get_builtin_presets("CR", dataset=ds)
        default = presets[0]
        wide = presets[1]
        assert wide[1] - default[1] == pytest.approx(0.5 * default[1])

    def test_10bit_dataset_range(self):
        ds = _make_dataset(bits_stored=10)
        presets = get_builtin_presets("MG", dataset=ds)
        default = presets[0]
        assert default[0] == pytest.approx(511.5)
        assert default[1] == pytest.approx(1023.0)

    def test_signed_dataset_range(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=16, pixel_representation=1)
        presets = get_builtin_presets("US", dataset=ds)
        default = presets[0]
        assert default[0] == pytest.approx(-0.5)
        assert default[1] == pytest.approx(65535.0)


class TestHUGatedPresets:
    def test_cr_dx_hu_gated(self):
        presets = get_hu_gated_builtin_presets("CR")
        assert len(presets) == 2
        assert all(p[2] is True for p in presets)
        names = [p[3] for p in presets]
        assert "Chest" in names
        assert "Bone" in names

    def test_nm_hu_gated_uses_nonzero_calibrated_window(self):
        presets = get_hu_gated_builtin_presets("NM")
        assert presets == [(500.0, 1000.0, True, "rescaled Default")]

    def test_nm_hu_gated(self):
        presets = get_hu_gated_builtin_presets("NM")
        assert len(presets) == 1
        assert presets[0][2] is True

    def test_unknown_modality_returns_empty(self):
        assert get_hu_gated_builtin_presets("CT") == []
        assert get_hu_gated_builtin_presets("MR") == []
