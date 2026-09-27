"""Window/level ramp, LUT, and composed-trace sampling."""

from __future__ import annotations

import numpy as np

from core.dicom_window_level import apply_window_level
from core.lut_catalog import colormap_lut, gamma_lut, inverse_lut, linear_lut
from core.lut_engine import apply_lut_to_uint8
from core.lut_transfer import (
    curves_are_one_line,
    lut_samples,
    sample_window_and_composed,
)
from gui.widgets.lut_transfer_function_widget import overlay_paths


def test_linear_monochrome2_collapses_to_the_window() -> None:
    stored = np.array([0.0, 50.0, 127.5, 200.0])
    windowed, composed = sample_window_and_composed(stored, 100.0, 200.0, linear_lut(), "MONOCHROME2", False)
    expected = apply_window_level(stored.copy(), 100.0, 200.0)
    assert np.array_equal(windowed, expected)
    assert np.array_equal(composed, expected)
    assert curves_are_one_line(linear_lut(), "MONOCHROME2", False)


def test_truncation_inverts_127_point_5_to_128() -> None:
    stored = np.array([127.5])
    _windowed, composed = sample_window_and_composed(stored, 127.5, 255.0, linear_lut(), "MONOCHROME1", False)
    assert int(composed[0]) == 128


def test_xor_cancels_before_the_lut() -> None:
    stored = np.array([0.0, 64.0, 127.5, 255.0])
    both, composed_both = sample_window_and_composed(stored, 127.5, 255.0, inverse_lut(), "MONOCHROME1", True)
    neither, composed_neither = sample_window_and_composed(stored, 127.5, 255.0, inverse_lut(), "MONOCHROME2", False)
    assert np.array_equal(composed_both, composed_neither)
    inverted = apply_lut_to_uint8((255 - both).reshape(1, -1), inverse_lut()).reshape(-1)
    assert not np.array_equal(composed_both, inverted)


def test_user_invert_without_monochrome1_flips_before_the_lut() -> None:
    stored = np.arange(8, dtype=np.float64)
    windowed, composed = sample_window_and_composed(stored, 3.5, 8.0, inverse_lut(), "MONOCHROME2", True)
    expected = apply_lut_to_uint8((255 - windowed).reshape(1, -1), inverse_lut()).reshape(-1)
    assert np.array_equal(composed, expected)
    assert not curves_are_one_line(linear_lut(), "MONOCHROME2", True)
    assert curves_are_one_line(linear_lut(), "MONOCHROME1", True)


def test_colormap_samples_are_rgb_and_overlay_uses_a_bar() -> None:
    samples = lut_samples(colormap_lut("hot"))
    assert samples.shape == (256, 3)
    paths = overlay_paths(colormap_lut("hot"), 40.0, 80.0, "MONOCHROME2", False, 0.0, 80.0)
    assert paths is not None
    assert paths.lut_colors is not None and paths.lut_colors.shape == (256, 3)
    assert paths.lut_trace is None
    assert paths.composed.shape == (256,)


def test_gamma_changes_the_composed_bytes() -> None:
    stored = np.linspace(0.0, 100.0, 16)
    _windowed, linear = sample_window_and_composed(stored, 50.0, 100.0, linear_lut(), "MONOCHROME2", False)
    _windowed, curved = sample_window_and_composed(stored, 50.0, 100.0, gamma_lut(2.2), "MONOCHROME2", False)
    assert not np.array_equal(linear, curved)
