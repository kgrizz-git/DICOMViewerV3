"""
Tests for ``core.window_level_preset_handler.apply_window_level_preset``.

Verifies raw/rescaled conversion paths and control updates when choosing a context-menu preset.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from core.window_level_preset_handler import apply_window_level_preset


class _FakeVSM:
    def __init__(self) -> None:
        self.window_level_presets: List[Tuple[float, float, bool, Optional[str]]] = []
        self.use_rescaled_values: bool = False
        self.rescale_slope: Optional[float] = None
        self.rescale_intercept: Optional[float] = None
        self.current_preset_index: int = 0
        self.window_level_user_modified: bool = True
        self.current_window_center: Optional[float] = None
        self.current_window_width: Optional[float] = None

    def apply_window_level_from_context_menu_preset(
        self, center: float, width: float, preset_index: int
    ) -> None:
        self.current_preset_index = preset_index
        self.window_level_user_modified = False
        self.current_window_center = center
        self.current_window_width = width


class _FakeDicomProcessor:
    @staticmethod
    def convert_window_level_rescaled_to_raw(
        center: float, width: float, slope: float, intercept: float
    ) -> Tuple[float, float]:
        if slope == 0.0:
            return center, width
        return (center - intercept) / slope, width / slope

    @staticmethod
    def convert_window_level_raw_to_rescaled(
        center: float, width: float, slope: float, intercept: float
    ) -> Tuple[float, float]:
        return center * slope + intercept, width * slope


def test_apply_preset_no_conversion_when_modes_match() -> None:
    vsm = _FakeVSM()
    vsm.window_level_presets = [(100.0, 200.0, False, "Soft")]
    vsm.use_rescaled_values = False
    vsm.rescale_slope = 2.0
    vsm.rescale_intercept = -1000.0

    wlc = MagicMock()
    app = MagicMock()
    app.view_state_manager = vsm
    app.dicom_processor = _FakeDicomProcessor()
    app.window_level_controls = wlc
    app.image_viewer = MagicMock(current_zoom=1.5)
    app.main_window = MagicMock()
    app._schedule_histogram_wl_only = MagicMock()

    apply_window_level_preset(app, 0)

    wlc.set_window_level.assert_called_once_with(100.0, 200.0, block_signals=True)
    assert vsm.current_window_center == 100.0
    assert vsm.current_window_width == 200.0
    assert vsm.current_preset_index == 0
    assert vsm.window_level_user_modified is False
    app.main_window.update_zoom_preset_status.assert_called_once_with(1.5, "Soft")
    app._schedule_histogram_wl_only.assert_called_once()


def test_apply_preset_rescaled_to_raw() -> None:
    vsm = _FakeVSM()
    # Preset stored in rescaled space; viewer uses raw HU
    vsm.window_level_presets = [(0.0, 200.0, True, "Lung")]
    vsm.use_rescaled_values = False
    vsm.rescale_slope = 2.0
    vsm.rescale_intercept = -1000.0

    wlc = MagicMock()
    app = MagicMock()
    app.view_state_manager = vsm
    app.dicom_processor = _FakeDicomProcessor()
    app.window_level_controls = wlc
    app.image_viewer = None
    app.main_window = MagicMock()
    app._schedule_histogram_wl_only = MagicMock()

    apply_window_level_preset(app, 0)

    # raw_center = (0 - (-1000)) / 2 = 500, raw_width = 200 / 2 = 100
    wlc.set_window_level.assert_called_once_with(500.0, 100.0, block_signals=True)
    assert vsm.current_window_center == 500.0
    assert vsm.current_window_width == 100.0
    app._schedule_histogram_wl_only.assert_called_once()


def test_apply_preset_raw_to_rescaled() -> None:
    vsm = _FakeVSM()
    vsm.window_level_presets = [(500.0, 100.0, False, "Body")]
    vsm.use_rescaled_values = True
    vsm.rescale_slope = 2.0
    vsm.rescale_intercept = -1000.0

    wlc = MagicMock()
    app = MagicMock()
    app.view_state_manager = vsm
    app.dicom_processor = _FakeDicomProcessor()
    app.window_level_controls = wlc
    app.image_viewer = None
    app.main_window = MagicMock()
    app._schedule_histogram_wl_only = MagicMock()

    apply_window_level_preset(app, 0)

    # rescaled_center = 500 * 2 + (-1000) = 0, rescaled_width = 100 * 2 = 200
    wlc.set_window_level.assert_called_once_with(0.0, 200.0, block_signals=True)
    assert vsm.current_window_center == 0.0
    assert vsm.current_window_width == 200.0
    app._schedule_histogram_wl_only.assert_called_once()


@pytest.mark.parametrize("preset_index", [-1, 99])
def test_apply_preset_invalid_index_noop(preset_index: int) -> None:
    vsm = _FakeVSM()
    vsm.window_level_presets = [(1.0, 2.0, False, "A")]

    app = MagicMock()
    app.view_state_manager = vsm
    app.dicom_processor = _FakeDicomProcessor()
    app.window_level_controls = MagicMock()

    apply_window_level_preset(app, preset_index)

    app.window_level_controls.set_window_level.assert_not_called()
