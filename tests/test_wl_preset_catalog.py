"""
Tests for window/level preset catalog and built-in modality tables.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

from core.wl_builtin_presets import get_builtin_presets, get_mr_hu_builtin_presets
from core.wl_preset_catalog import (
    WindowLevelPreset,
    build_preset_list,
    filter_user_preset_dicts,
    format_preset_display_values,
    format_preset_menu_label,
    format_preset_status_name,
    format_preset_tooltip,
    storage_space_label,
)


def test_get_builtin_presets_case_insensitive() -> None:
    ct = get_builtin_presets("ct")
    assert len(ct) >= 10
    assert ct[0][3] == "Abdomen"


def test_get_builtin_presets_unknown_uses_any() -> None:
    any_list = get_builtin_presets("ZZ")
    assert len(any_list) >= 2
    assert any_list[0][3] == "Default"


def test_get_builtin_presets_empty_modality_uses_any() -> None:
    assert get_builtin_presets("") == get_builtin_presets("ZZ")


def test_known_modality_does_not_include_any_entries() -> None:
    ct = get_builtin_presets("CT")
    names = [p[3] for p in ct]
    assert "Default" not in names or "Abdomen" in names


def test_xa_builtin_presets_no_dataset() -> None:
    xa = get_builtin_presets("XA")
    rf = get_builtin_presets("RF")
    assert len(xa) >= 1
    assert xa[0][2] is False
    assert xa == rf


def test_mr_builtin_defaults_are_raw() -> None:
    for _wc, _ww, is_rescaled, _name in get_builtin_presets("MR"):
        assert is_rescaled is False


def test_mr_hu_presets_are_rescaled() -> None:
    for _wc, _ww, is_rescaled, _name in get_mr_hu_builtin_presets():
        assert is_rescaled is True


def test_filter_user_presets_any_and_modality() -> None:
    entries = [
        {"name": "A", "modality": "ANY", "center": 1.0, "width": 2.0, "is_rescaled": True},
        {"name": "B", "modality": "MR", "center": 3.0, "width": 4.0, "is_rescaled": False},
        {"name": "C", "modality": "CT", "center": 5.0, "width": 6.0, "is_rescaled": True},
    ]
    mr_only = filter_user_preset_dicts(entries, "MR")
    assert len(mr_only) == 2
    assert {p.name for p in mr_only} == {"A", "B"}


def test_format_preset_menu_label_hu_and_raw() -> None:
    hu = WindowLevelPreset(40.0, 400.0, True, "Lung", "builtin", "CT")
    raw = WindowLevelPreset(500.0, 1000.0, False, "Brain T1", "builtin", "MR")
    assert "HU" in format_preset_menu_label(hu, unit="HU")
    assert "raw" in format_preset_menu_label(raw, unit="HU")
    assert " (W 400/C 40)" in format_preset_menu_label(hu, unit="HU")
    assert " (W 1000/C 500)" in format_preset_menu_label(raw, unit="HU")


@pytest.mark.parametrize("unit", [None, "", "UNSPECIFIED", "US"])
def test_format_preset_menu_label_omits_unknown_rescaled_unit(unit: str | None) -> None:
    preset = WindowLevelPreset(40.0, 400.0, True, "NORMAL", "dicom", "MR")

    label = format_preset_menu_label(preset, unit=unit)

    assert label.startswith("NORMAL (W 400/C 40)")
    assert "HU" not in label


def test_format_preset_menu_label_keeps_meaningful_non_hu_unit() -> None:
    preset = WindowLevelPreset(0.0, 5.0, True, "SUV 0-5", "builtin", "PT")
    assert (
        format_preset_menu_label(preset, unit="BQML")
        == "SUV 0-5 (BQML) (W 5/C 0)"
    )


def test_format_preset_display_values_rescaled_to_raw() -> None:
    """HU preset stored rescaled; viewer raw shows converted C/W."""
    preset = WindowLevelPreset(40.0, 400.0, True, "Lung", "builtin", "CT")
    c, w = format_preset_display_values(
        preset,
        use_rescaled=False,
        rescale_slope=1.0,
        rescale_intercept=-1000.0,
    )
    assert c == pytest.approx(1040.0)
    assert w == pytest.approx(400.0)


def test_format_preset_display_values_raw_to_rescaled() -> None:
    preset = WindowLevelPreset(500.0, 1000.0, False, "Brain T1", "builtin", "MR")
    c, w = format_preset_display_values(
        preset,
        use_rescaled=True,
        rescale_slope=2.0,
        rescale_intercept=-1000.0,
    )
    assert c == pytest.approx(0.0)
    assert w == pytest.approx(2000.0)


def test_format_preset_menu_label_viewer_mode_conversion() -> None:
    preset = WindowLevelPreset(40.0, 400.0, True, "Lung", "builtin", "CT")
    rescaled_label = format_preset_menu_label(
        preset,
        unit="HU",
        use_rescaled=True,
    )
    raw_label = format_preset_menu_label(
        preset,
        unit="HU",
        use_rescaled=False,
        rescale_slope=1.0,
        rescale_intercept=-1000.0,
    )
    assert rescaled_label == "Lung (HU) (W 400/C 40)"
    assert raw_label == "Lung (HU) (W 400/C 1040)"


def test_format_preset_tooltip_shows_stored_when_converted() -> None:
    preset = WindowLevelPreset(40.0, 400.0, True, "Lung", "builtin", "CT")
    tip = format_preset_tooltip(
        preset,
        unit="HU",
        use_rescaled=False,
        rescale_slope=1.0,
        rescale_intercept=-1000.0,
    )
    assert "Center 1040, Width 400" in tip
    assert "Stored: Center 40, Width 400 (HU)" in tip


def test_format_preset_tooltip_mentions_conversion() -> None:
    preset = WindowLevelPreset(0.0, 200.0, True, "Lung", "builtin", "CT")
    tip = format_preset_tooltip(
        preset,
        unit="HU",
        use_rescaled=False,
        rescale_slope=2.0,
        rescale_intercept=-1000.0,
    )
    assert "convert" in tip.lower()


def test_build_preset_list_merge_order() -> None:
    ds = Dataset()
    ds.Modality = "CT"
    ds.WindowCenter = 10
    ds.WindowWidth = 20
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 0

    dicom_processor = MagicMock()
    dicom_processor.get_window_level_presets_from_dataset.return_value = [
        (10.0, 20.0, True, "From DICOM"),
    ]

    config = MagicMock()
    config.get_wl_user_presets.return_value = [
        {"name": "Custom", "modality": "CT", "center": 1.0, "width": 2.0, "is_rescaled": True},
    ]

    merged = build_preset_list(
        ds,
        dicom_processor,
        config,
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )
    sources = [p.source for p in merged]
    assert sources[0] == "dicom"
    assert "builtin" in sources
    assert sources[-1] == "user"


def test_build_preset_list_mr_includes_hu_when_rescale() -> None:
    ds = Dataset()
    ds.Modality = "MR"

    dicom_processor = MagicMock()
    dicom_processor.get_window_level_presets_from_dataset.return_value = []

    config = MagicMock()
    config.get_wl_user_presets.return_value = []

    merged = build_preset_list(
        ds,
        dicom_processor,
        config,
        rescale_slope=2.0,
        rescale_intercept=-1000.0,
    )
    names = [p.name for p in merged if p.source == "builtin"]
    assert any("Brain T1" in (n or "") for n in names)
    assert any("(HU)" in (n or "") for n in names)


def test_storage_space_label() -> None:
    assert storage_space_label(WindowLevelPreset(0, 1, False, "x", "builtin"), unit="HU") == "raw"
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit="HU") == "HU"
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit="BQML") == "BQML"
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit=None) is None
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit="") is None
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit="UNSPECIFIED") is None
    assert storage_space_label(WindowLevelPreset(0, 1, True, "x", "builtin"), unit="US") is None


def test_format_preset_status_name_omits_unknown_rescaled_unit() -> None:
    preset = WindowLevelPreset(40.0, 400.0, True, "NORMAL", "dicom", "MR")
    assert format_preset_status_name(preset, unit=None) == "NORMAL"


def test_format_status_bar_wl_compact() -> None:
    from core.wl_preset_catalog import format_status_bar_wl

    assert format_status_bar_wl(40.0, 400.0) == "(W 400/C 40)"
    assert format_status_bar_wl(40.5, 400.0) == "(W 400/C 40.5)"
    assert format_status_bar_wl(40.0, 400.0, unit="HU") == "(W 400/C 40) (HU)"
    assert format_status_bar_wl(40.0, 400.0, unit="UNSPECIFIED") == "(W 400/C 40)"


def test_format_status_bar_wl_monochrome1_marker() -> None:
    from core.wl_preset_catalog import format_status_bar_wl

    assert format_status_bar_wl(40.0, 400.0, is_monochrome1=True) == "(W 400/C 40) (MI)"
    assert format_status_bar_wl(40.0, 400.0, unit="HU", is_monochrome1=True) == "(W 400/C 40) (HU) (MI)"


class TestCRDXNMHUGate:
    def _make_cr_dataset(self) -> Dataset:
        ds = Dataset()
        ds.Modality = "CR"
        ds.BitsAllocated = 16
        ds.BitsStored = 12
        ds.HighBit = 11
        ds.PixelRepresentation = 0
        return ds

    def test_cr_no_rescale_no_hu_presets(self) -> None:
        ds = self._make_cr_dataset()
        dicom_processor = MagicMock()
        dicom_processor.get_window_level_presets_from_dataset.return_value = []
        config = MagicMock()
        config.get_wl_user_presets.return_value = []

        merged = build_preset_list(ds, dicom_processor, config, rescale_slope=None, rescale_intercept=None)
        names = [p.name for p in merged if p.source == "builtin"]
        assert "Chest" not in names
        assert "Bone" not in names

    def test_cr_with_rescale_includes_hu_presets(self) -> None:
        ds = self._make_cr_dataset()
        ds.RescaleType = "HU"
        dicom_processor = MagicMock()
        dicom_processor.get_window_level_presets_from_dataset.return_value = []
        config = MagicMock()
        config.get_wl_user_presets.return_value = []

        merged = build_preset_list(ds, dicom_processor, config, rescale_slope=1.0, rescale_intercept=0.0)
        names = [p.name for p in merged if p.source == "builtin"]
        assert "Chest" in names
        assert "Bone" in names

    def test_cr_non_hu_rescale_excludes_hu_presets(self) -> None:
        """A calibrated non-HU CR image must not receive fixed-HU presets."""
        ds = self._make_cr_dataset()
        ds.RescaleType = "BQML"
        dicom_processor = MagicMock()
        dicom_processor.get_window_level_presets_from_dataset.return_value = []
        config = MagicMock()
        config.get_wl_user_presets.return_value = []

        merged = build_preset_list(ds, dicom_processor, config, rescale_slope=1.0, rescale_intercept=0.0)

        names = [p.name for p in merged if p.source == "builtin"]
        assert "Chest" not in names
        assert "Bone" not in names

    def test_nm_with_rescale_includes_gated_presets(self) -> None:
        ds = Dataset()
        ds.Modality = "NM"
        ds.BitsAllocated = 16
        ds.BitsStored = 16
        ds.HighBit = 15
        ds.PixelRepresentation = 0
        dicom_processor = MagicMock()
        dicom_processor.get_window_level_presets_from_dataset.return_value = []
        config = MagicMock()
        config.get_wl_user_presets.return_value = []

        merged = build_preset_list(ds, dicom_processor, config, rescale_slope=1.0, rescale_intercept=0.0)
        names = [p.name for p in merged if p.source == "builtin"]
        assert "rescaled Default" in names


class TestLabelingRawVsHU:
    def test_cr_raw_preset_label_is_raw(self) -> None:
        preset = WindowLevelPreset(2048.0, 4096.0, False, "Default", "builtin", "CR")
        assert storage_space_label(preset, unit="HU") == "raw"

    def test_cr_hu_gated_preset_label_is_hu(self) -> None:
        preset = WindowLevelPreset(-600.0, 1500.0, True, "Chest", "builtin", "CR")
        assert storage_space_label(preset, unit="HU") == "HU"

    def test_tooltip_no_hu_unless_gated(self) -> None:
        raw_preset = WindowLevelPreset(2048.0, 4096.0, False, "Default", "builtin", "CR")
        tip = format_preset_tooltip(raw_preset, unit="HU", use_rescaled=False)
        assert "HU" not in tip

    def test_tooltip_hu_when_gated(self) -> None:
        hu_preset = WindowLevelPreset(-600.0, 1500.0, True, "Chest", "builtin", "CR")
        tip = format_preset_tooltip(hu_preset, unit="HU", use_rescaled=False, rescale_slope=1.0, rescale_intercept=0.0)
        assert "HU" in tip
