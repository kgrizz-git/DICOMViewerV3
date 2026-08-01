"""Tests for HistogramWidget pixel array, WL overlay, and log scale."""

from __future__ import annotations

import numpy as np
import pytest

from tools.histogram_widget import HistogramWidget


@pytest.mark.qt
def test_set_pixel_array_stores_and_draws(qapp) -> None:
    w = HistogramWidget()
    arr = np.arange(100, dtype=np.float32).reshape(10, 10)
    w.set_pixel_array(arr)
    assert w.pixel_array is arr
    # Clearing should not raise
    w.set_pixel_array(None)
    assert w.pixel_array is None


@pytest.mark.qt
def test_set_window_level_and_log_scale(qapp) -> None:
    w = HistogramWidget()
    w.set_pixel_array(np.linspace(0, 255, 64).reshape(8, 8))
    w.set_window_level(100.0, 50.0)
    assert w.window_center == 100.0
    assert w.window_width == 50.0
    w.set_log_scale(True)
    assert w.use_log_scale is True


@pytest.mark.qt
def test_roi_mask_and_global_range(qapp) -> None:
    w = HistogramWidget()
    pixels = np.ones((8, 8), dtype=np.float32) * 50
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True
    w.set_pixel_array(pixels)
    w.set_roi_mask(mask)
    assert w.roi_mask is mask
    w.set_global_frequency_max(1000.0)
    w.set_global_pixel_range(0.0, 100.0)
    assert w.global_frequency_max == 1000.0
    assert w.global_x_min == 0.0
    assert w.global_x_max == 100.0


@pytest.mark.qt
def test_font_tier_updates_title_stylesheet(qapp) -> None:
    w = HistogramWidget()
    w.update_font_sizes_for_size(200, 200)
    assert "7pt" in w._title_label.styleSheet() or "font-size" in w._title_label.styleSheet()
    w.update_font_sizes_for_size(800, 800)
    assert "12pt" in w._title_label.styleSheet()
