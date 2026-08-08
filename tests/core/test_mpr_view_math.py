"""
Tests for ``core.mpr_view_math`` — MPR view/display math helpers.

Focus on branch coverage for all conditional paths.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from core.mpr_view_math import (
    array_to_pil,
    auto_window_level,
    build_mpr_banner_text,
    compute_mpr_combine_range,
)


class TestComputeMprCombineRange:
    """Tests for compute_mpr_combine_range function."""

    def test_returns_zero_zero_when_no_slices(self) -> None:
        """Branch: n_slices <= 0 returns (0, 0)."""
        assert compute_mpr_combine_range(0, 5, 3) == (0, 0)
        assert compute_mpr_combine_range(-1, 5, 3) == (0, 0)
        assert compute_mpr_combine_range(-10, 5, 3) == (0, 0)

    def test_clamps_slice_index_below_zero(self) -> None:
        """Branch: slice_index < 0 is clamped to 0."""
        assert compute_mpr_combine_range(10, -5, 3) == (0, 2)
        assert compute_mpr_combine_range(10, -1, 5) == (0, 4)

    def test_clamps_slice_index_above_max(self) -> None:
        """Branch: slice_index >= n_slices is clamped to n_slices-1."""
        assert compute_mpr_combine_range(10, 15, 3) == (7, 9)
        assert compute_mpr_combine_range(10, 100, 5) == (5, 9)

    def test_clamps_n_planes_to_minimum_one(self) -> None:
        """Branch: n_planes < 1 is clamped to 1."""
        assert compute_mpr_combine_range(10, 5, 0) == (5, 5)
        assert compute_mpr_combine_range(10, 5, -5) == (5, 5)
        assert compute_mpr_combine_range(10, 5, -1) == (5, 5)

    def test_centers_slab_on_slice_index(self) -> None:
        """Normal case: slab centered on slice_index."""
        # Odd number of planes: perfect centering
        assert compute_mpr_combine_range(20, 10, 5) == (8, 12)
        # Even number of planes: offset centering
        assert compute_mpr_combine_range(20, 10, 4) == (8, 11)

    def test_clamps_start_when_negative(self) -> None:
        """Branch: start < 0 is clamped to 0, end adjusted."""
        # Near beginning of volume
        assert compute_mpr_combine_range(10, 0, 5) == (0, 4)
        assert compute_mpr_combine_range(10, 1, 5) == (0, 4)
        assert compute_mpr_combine_range(10, 2, 5) == (0, 4)

    def test_clamps_end_when_exceeds_n_slices(self) -> None:
        """Branch: end >= n_slices is clamped, start adjusted."""
        # Near end of volume
        assert compute_mpr_combine_range(10, 9, 5) == (5, 9)
        assert compute_mpr_combine_range(10, 8, 5) == (5, 9)
        assert compute_mpr_combine_range(10, 7, 5) == (5, 9)

    def test_single_slice_volume(self) -> None:
        """Edge case: volume with only one slice."""
        assert compute_mpr_combine_range(1, 0, 1) == (0, 0)
        assert compute_mpr_combine_range(1, 0, 5) == (0, 0)

    def test_large_slab_exceeds_volume(self) -> None:
        """Slab larger than volume clamps to full volume."""
        assert compute_mpr_combine_range(5, 2, 20) == (0, 4)
        assert compute_mpr_combine_range(5, 0, 10) == (0, 4)

    def test_float_slice_index_and_n_planes(self) -> None:
        """Branch: float inputs are converted to int."""
        assert compute_mpr_combine_range(10, 5.7, 3.2) == (4, 6)
        assert compute_mpr_combine_range(10, 5.9, 3.9) == (4, 6)

    def test_exact_boundaries(self) -> None:
        """Test exact boundary conditions."""
        # slice_index exactly at boundaries
        assert compute_mpr_combine_range(10, 0, 3) == (0, 2)
        assert compute_mpr_combine_range(10, 9, 3) == (7, 9)


class TestBuildMprBannerText:
    """Tests for build_mpr_banner_text function."""

    def test_basic_orientation_label(self) -> None:
        """Basic case: orientation label only."""
        data = {"mpr_orientation": "Axial"}
        assert build_mpr_banner_text(data) == "MPR - Axial"

    def test_default_orientation_when_missing(self) -> None:
        """Branch: missing orientation defaults to 'MPR'."""
        data = {}
        assert build_mpr_banner_text(data) == "MPR - MPR"

    def test_default_orientation_when_none(self) -> None:
        """Branch: None orientation defaults to 'MPR'."""
        data = {"mpr_orientation": None}
        assert build_mpr_banner_text(data) == "MPR - MPR"

    def test_default_orientation_when_empty_string(self) -> None:
        """Branch: empty string orientation defaults to 'MPR'."""
        data = {"mpr_orientation": ""}
        assert build_mpr_banner_text(data) == "MPR - MPR"

    def test_combine_disabled_omits_mode(self) -> None:
        """Branch: combine enabled False omits mode."""
        data = {"mpr_orientation": "Sagittal", "mpr_combine_enabled": False}
        assert build_mpr_banner_text(data) == "MPR - Sagittal"

    def test_combine_enabled_aip_mode(self) -> None:
        """Branch: combine enabled with AIP mode."""
        data = {
            "mpr_orientation": "Coronal",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "aip",
        }
        assert build_mpr_banner_text(data) == "MPR - Coronal (AIP)"

    def test_combine_enabled_mip_mode(self) -> None:
        """Branch: combine enabled with MIP mode."""
        data = {
            "mpr_orientation": "Axial",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "mip",
        }
        assert build_mpr_banner_text(data) == "MPR - Axial (MIP)"

    def test_combine_enabled_minip_mode(self) -> None:
        """Branch: combine enabled with MinIP mode."""
        data = {
            "mpr_orientation": "Sagittal",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "minip",
        }
        assert build_mpr_banner_text(data) == "MPR - Sagittal (MinIP)"

    def test_combine_enabled_unknown_mode_uppercases(self) -> None:
        """Branch: unknown mode is uppercased."""
        data = {
            "mpr_orientation": "Axial",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "custom",
        }
        assert build_mpr_banner_text(data) == "MPR - Axial (CUSTOM)"

    def test_combine_enabled_mode_none_defaults_to_aip(self) -> None:
        """Branch: None mode defaults to 'aip'."""
        data = {
            "mpr_orientation": "Coronal",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": None,
        }
        assert build_mpr_banner_text(data) == "MPR - Coronal (AIP)"

    def test_combine_enabled_mode_empty_defaults_to_aip(self) -> None:
        """Branch: empty mode defaults to 'aip'."""
        data = {
            "mpr_orientation": "Sagittal",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "",
        }
        assert build_mpr_banner_text(data) == "MPR - Sagittal (AIP)"

    def test_combine_enabled_missing_mode_defaults_to_aip(self) -> None:
        """Branch: missing mode defaults to 'aip'."""
        data = {
            "mpr_orientation": "Axial",
            "mpr_combine_enabled": True,
        }
        assert build_mpr_banner_text(data) == "MPR - Axial (AIP)"

    def test_mode_case_insensitive(self) -> None:
        """Branch: mode is converted to lowercase."""
        data = {
            "mpr_orientation": "Coronal",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "MIP",
        }
        assert build_mpr_banner_text(data) == "MPR - Coronal (MIP)"

    def test_combine_enabled_falsey_values(self) -> None:
        """Branch: falsey values for combine_enabled."""
        assert build_mpr_banner_text({"mpr_combine_enabled": 0}) == "MPR - MPR"
        assert build_mpr_banner_text({"mpr_combine_enabled": None}) == "MPR - MPR"
        assert build_mpr_banner_text({"mpr_combine_enabled": ""}) == "MPR - MPR"


class TestAutoWindowLevel:
    """Tests for auto_window_level function."""

    def test_normal_array(self) -> None:
        """Normal case: array with finite values."""
        arr = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        wc, ww = auto_window_level(arr)
        assert isinstance(wc, float)
        assert isinstance(ww, float)
        assert ww >= 1.0

    def test_empty_array_returns_defaults(self) -> None:
        """Branch: empty array returns (0.0, 1.0)."""
        arr = np.array([])
        wc, ww = auto_window_level(arr)
        assert wc == 0.0
        assert ww == 1.0

    def test_all_nan_returns_defaults(self) -> None:
        """Branch: all NaN returns (0.0, 1.0)."""
        arr = np.array([[np.nan, np.nan], [np.nan, np.nan]])
        wc, ww = auto_window_level(arr)
        assert wc == 0.0
        assert ww == 1.0

    def test_all_inf_returns_defaults(self) -> None:
        """Branch: all inf returns (0.0, 1.0)."""
        arr = np.array([[np.inf, np.inf], [np.inf, np.inf]])
        wc, ww = auto_window_level(arr)
        assert wc == 0.0
        assert ww == 1.0

    def test_mixed_nan_and_finite_uses_finite(self) -> None:
        """Branch: NaN values are filtered out."""
        arr = np.array([[1.0, np.nan, 3.0], [np.inf, 5.0, 6.0]])
        wc, ww = auto_window_level(arr)
        assert isinstance(wc, float)
        assert isinstance(ww, float)
        assert ww >= 1.0

    def test_width_floored_at_1_0(self) -> None:
        """Branch: width < 1.0 is floored to 1.0."""
        # Create array with very narrow range
        arr = np.array([[100.0, 100.001, 100.002]])
        wc, ww = auto_window_level(arr)
        assert ww >= 1.0

    def test_single_value_array(self) -> None:
        """Edge case: array with single value."""
        arr = np.array([[42.0]])
        wc, ww = auto_window_level(arr)
        assert wc == 42.0
        assert ww == 1.0  # Width floored at 1.0

    def test_constant_array(self) -> None:
        """Edge case: array with all same values."""
        arr = np.array([[5.0, 5.0, 5.0], [5.0, 5.0, 5.0]])
        wc, ww = auto_window_level(arr)
        assert wc == 5.0
        assert ww == 1.0  # Width floored at 1.0

    def test_wide_range_array(self) -> None:
        """Normal case: array with wide range."""
        arr = np.array([[0.0, 100.0, 200.0], [300.0, 400.0, 500.0]])
        wc, ww = auto_window_level(arr)
        assert isinstance(wc, float)
        assert isinstance(ww, float)
        assert ww > 1.0

    def test_negative_values(self) -> None:
        """Array with negative values."""
        arr = np.array([[-100.0, -50.0, 0.0], [50.0, 100.0, 150.0]])
        wc, ww = auto_window_level(arr)
        assert isinstance(wc, float)
        assert isinstance(ww, float)
        assert ww >= 1.0

    def test_multidimensional_array(self) -> None:
        """Branch: array is flattened via ravel."""
        arr = np.random.rand(10, 10, 10)  # 3D array
        wc, ww = auto_window_level(arr)
        assert isinstance(wc, float)
        assert isinstance(ww, float)
        assert ww >= 1.0


class TestArrayToPil:
    """Tests for array_to_pil function."""

    def test_normal_conversion(self) -> None:
        """Normal case: successful conversion."""
        arr = np.array([[0.0, 127.5, 255.0], [255.0, 127.5, 0.0]])
        img = array_to_pil(arr, 127.5, 255.0)
        assert img is not None
        assert isinstance(img, Image.Image)
        assert img.mode == "L"

    def test_returns_none_on_exception(self) -> None:
        """Branch: exception returns None."""
        # Pass invalid input to trigger exception
        img = array_to_pil(None, 127.5, 255.0)  # type: ignore[arg-type]
        assert img is None

    def test_zero_window_width(self) -> None:
        """Branch: window_width near zero uses 1e-6."""
        arr = np.array([[127.5, 127.5, 127.5]])
        img = array_to_pil(arr, 127.5, 0.0)
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_negative_window_width(self) -> None:
        """Branch: negative window_width uses 1e-6."""
        arr = np.array([[127.5, 127.5, 127.5]])
        img = array_to_pil(arr, 127.5, -10.0)
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_clipping_low_values(self) -> None:
        """Branch: values below 0 are clipped."""
        arr = np.array([[-100.0, 0.0, 100.0]])
        img = array_to_pil(arr, 0.0, 100.0)
        assert img is not None
        pixels = list(img.getdata())
        # All values should be in [0, 255]
        assert all(0 <= p <= 255 for p in pixels)

    def test_clipping_high_values(self) -> None:
        """Branch: values above 255 are clipped."""
        arr = np.array([[100.0, 300.0, 500.0]])
        img = array_to_pil(arr, 127.5, 100.0)
        assert img is not None
        pixels = list(img.getdata())
        # All values should be in [0, 255]
        assert all(0 <= p <= 255 for p in pixels)

    def test_window_center_adjustment(self) -> None:
        """Branch: window_center shifts the mapping."""
        arr = np.array([[0.0, 100.0, 200.0]])
        img1 = array_to_pil(arr, 100.0, 100.0)
        img2 = array_to_pil(arr, 150.0, 100.0)
        assert img1 is not None
        assert img2 is not None
        # Different centers should produce different results
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())
        assert pixels1 != pixels2

    def test_window_width_scaling(self) -> None:
        """Branch: window_width affects scaling."""
        arr = np.array([[0.0, 100.0, 200.0]])
        img1 = array_to_pil(arr, 100.0, 50.0)
        img2 = array_to_pil(arr, 100.0, 200.0)
        assert img1 is not None
        assert img2 is not None
        # Different widths should produce different results
        pixels1 = list(img1.getdata())
        pixels2 = list(img2.getdata())
        assert pixels1 != pixels2

    def test_integer_array(self) -> None:
        """Branch: integer array input."""
        arr = np.array([[0, 128, 255]], dtype=np.int32)
        img = array_to_pil(arr, 128.0, 255.0)
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_float32_array(self) -> None:
        """Branch: float32 array input."""
        arr = np.array([[0.0, 127.5, 255.0]], dtype=np.float32)
        img = array_to_pil(arr, 127.5, 255.0)
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_very_small_window_width(self) -> None:
        """Branch: very small window_width uses 1e-6."""
        arr = np.array([[127.5, 127.5, 127.5]])
        img = array_to_pil(arr, 127.5, 1e-10)
        assert img is not None
        assert isinstance(img, Image.Image)

    def test_large_array(self) -> None:
        """Branch: larger array conversion."""
        arr = np.random.rand(100, 100) * 255.0
        img = array_to_pil(arr, 127.5, 255.0)
        assert img is not None
        assert isinstance(img, Image.Image)
        assert img.size == (100, 100)

    def test_all_values_at_window_center(self) -> None:
        """Edge case: all values equal to window center."""
        arr = np.array([[127.5, 127.5, 127.5]])
        img = array_to_pil(arr, 127.5, 100.0)
        assert img is not None
        pixels = list(img.getdata())
        # Should map to middle of range
        assert all(p == 127 for p in pixels)

    def test_invalid_array_shape(self) -> None:
        """Branch: invalid array shape triggers exception."""
        # 1D array should still work
        arr = np.array([0.0, 127.5, 255.0])
        img = array_to_pil(arr, 127.5, 255.0)
        assert img is not None
