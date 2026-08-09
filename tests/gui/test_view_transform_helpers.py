"""Comprehensive tests for view_transform_helpers.py.

Tests cover graphics_view_uniform_zoom function with various scenarios:
- current_zoom attribute presence/absence
- Transform matrix values (m11, m12, m21, m22)
- Edge cases (small magnitudes, negative values, rotation, flip)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QTransform

# Import with module path for coverage tracking
from gui import view_transform_helpers

graphics_view_uniform_zoom = view_transform_helpers.graphics_view_uniform_zoom


@pytest.fixture
def mock_view():
    """Fixture providing a mock view object."""
    view = MagicMock()
    return view


@pytest.fixture
def mock_transform():
    """Fixture providing a mock QTransform."""
    transform = MagicMock(spec=QTransform)
    return transform


class TestGraphicsViewUniformZoomWithCurrentZoom:
    """Tests for graphics_view_uniform_zoom when view has current_zoom attribute."""

    def test_returns_current_zoom_when_positive_int(self, mock_view):
        """Should return current_zoom when it's a positive integer."""
        mock_view.current_zoom = 2
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_returns_current_zoom_when_positive_float(self, mock_view):
        """Should return current_zoom when it's a positive float."""
        mock_view.current_zoom = 1.5
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.5

    def test_returns_current_zoom_when_one(self, mock_view):
        """Should return current_zoom when it's exactly 1."""
        mock_view.current_zoom = 1
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0

    def test_ignores_current_zoom_when_zero(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is zero."""
        mock_view.current_zoom = 0
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 2.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_ignores_current_zoom_when_negative(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is negative."""
        mock_view.current_zoom = -1.5
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 3.0
        mock_transform.m12.return_value = 4.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_ignores_current_zoom_when_none(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is None."""
        mock_view.current_zoom = None
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0

    def test_ignores_current_zoom_when_string(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is a string."""
        mock_view.current_zoom = "2.0"
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 2.5
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.5

    def test_ignores_current_zoom_when_list(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is a list."""
        mock_view.current_zoom = [2.0]
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 3.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 3.0


class TestGraphicsViewUniformZoomWithTransform:
    """Tests for graphics_view_uniform_zoom using transform matrix."""

    def test_uses_m11_m12_hypot_when_m11_dominant(self, mock_view, mock_transform):
        """Should use hypot(m11, m12) when m11 is dominant."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 3.0
        mock_transform.m12.return_value = 4.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_uses_m11_m12_hypot_when_m12_dominant(self, mock_view, mock_transform):
        """Should use hypot(m11, m12) when m12 is dominant."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = 5.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_uses_m11_m12_hypot_equal_values(self, mock_view, mock_transform):
        """Should use hypot(m11, m12) when m11 and m12 are equal."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1.0
        mock_transform.m12.return_value = 1.0
        result = graphics_view_uniform_zoom(mock_view)
        assert abs(result - 1.41421356) < 1e-6

    def test_falls_back_to_m21_m22_when_m11_m12_too_small(self, mock_view, mock_transform):
        """Should fall back to m21, m22 when hypot(m11, m12) <= 1e-9."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1e-10
        mock_transform.m12.return_value = 1e-10
        mock_transform.m21.return_value = 2.0
        mock_transform.m22.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_uses_m21_m22_hypot_when_fallback_used(self, mock_view, mock_transform):
        """Should use hypot(m21, m22) when falling back from m11, m12."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = 0.0
        mock_transform.m21.return_value = 3.0
        mock_transform.m22.return_value = 4.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_returns_1_0_when_all_magnitudes_too_small(self, mock_view, mock_transform):
        """Should return 1.0 when all matrix values are very small."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1e-10
        mock_transform.m12.return_value = 1e-10
        mock_transform.m21.return_value = 1e-10
        mock_transform.m22.return_value = 1e-10
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0

    def test_returns_1_0_when_all_zeros(self, mock_view, mock_transform):
        """Should return 1.0 when all matrix values are zero."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = 0.0
        mock_transform.m21.return_value = 0.0
        mock_transform.m22.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0


class TestGraphicsViewUniformZoomRotationScenarios:
    """Tests for rotation scenarios (90°, 270° where m11 may be ~0)."""

    def test_90_degree_rotation_m11_zero(self, mock_view, mock_transform):
        """Should handle 90° rotation where m11 ≈ 0."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = -2.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_270_degree_rotation_m11_zero(self, mock_view, mock_transform):
        """Should handle 270° rotation where m11 ≈ 0."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = 2.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_45_degree_rotation(self, mock_view, mock_transform):
        """Should handle 45° rotation."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.7071
        mock_transform.m12.return_value = -0.7071
        result = graphics_view_uniform_zoom(mock_view)
        assert abs(result - 1.0) < 1e-4

    def test_180_degree_rotation(self, mock_view, mock_transform):
        """Should handle 180° rotation."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = -1.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0


class TestGraphicsViewUniformZoomFlipScenarios:
    """Tests for horizontal flip scenarios (negative m11)."""

    def test_horizontal_flip_negative_m11(self, mock_view, mock_transform):
        """Should handle horizontal flip with negative m11."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = -2.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_horizontal_flip_with_rotation(self, mock_view, mock_transform):
        """Should handle combined horizontal flip and rotation."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = -1.4142
        mock_transform.m12.return_value = -1.4142
        result = graphics_view_uniform_zoom(mock_view)
        assert abs(result - 2.0) < 1e-4

    def test_vertical_flip_negative_m22(self, mock_view, mock_transform):
        """Should handle vertical flip with negative m22 (fallback path)."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.0
        mock_transform.m12.return_value = 0.0
        mock_transform.m21.return_value = 0.0
        mock_transform.m22.return_value = -3.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 3.0


class TestGraphicsViewUniformZoomEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_small_positive_m11_m12(self, mock_view, mock_transform):
        """Should handle very small but positive m11, m12 values."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1e-8
        mock_transform.m12.return_value = 1e-8
        result = graphics_view_uniform_zoom(mock_view)
        assert result > 1e-9

    def test_threshold_exactly_1e_9(self, mock_view, mock_transform):
        """Should fall back to m21, m22 when hypot is exactly at threshold (not >)."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 1e-9
        mock_transform.m12.return_value = 0.0
        mock_transform.m21.return_value = 5.0
        mock_transform.m22.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_threshold_just_below_1e_9(self, mock_view, mock_transform):
        """Should fall back to m21, m22 when hypot is just below threshold."""
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 0.9e-9
        mock_transform.m12.return_value = 0.0
        mock_transform.m21.return_value = 5.0
        mock_transform.m22.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 5.0

    def test_large_zoom_values(self, mock_view):
        """Should handle very large zoom values."""
        mock_view.current_zoom = 1000.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1000.0

    def test_very_small_positive_zoom(self, mock_view):
        """Should handle very small positive zoom values."""
        mock_view.current_zoom = 0.001
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 0.001

    def test_fractional_zoom_values(self, mock_view):
        """Should handle fractional zoom values."""
        mock_view.current_zoom = 0.75
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 0.75


class TestGraphicsViewUniformZoomRealTransform:
    """Tests with real QTransform objects for integration testing."""

    def test_real_transform_identity(self, mock_view):
        """Should handle real identity transform."""
        transform = QTransform()
        mock_view.transform.return_value = transform
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0

    def test_real_transform_scale(self, mock_view):
        """Should handle real scale transform."""
        transform = QTransform()
        transform.scale(2.0, 2.0)
        mock_view.transform.return_value = transform
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_real_transform_rotate_90(self, mock_view):
        """Should handle real 90° rotation transform."""
        transform = QTransform()
        transform.rotate(90)
        mock_view.transform.return_value = transform
        result = graphics_view_uniform_zoom(mock_view)
        assert abs(result - 1.0) < 1e-6

    def test_real_transform_scale_and_rotate(self, mock_view):
        """Should handle combined scale and rotation."""
        transform = QTransform()
        transform.scale(3.0, 3.0)
        transform.rotate(45)
        mock_view.transform.return_value = transform
        result = graphics_view_uniform_zoom(mock_view)
        assert abs(result - 3.0) < 1e-6

    def test_real_transform_with_negative_scale(self, mock_view):
        """Should handle transform with negative scale (flip)."""
        transform = QTransform()
        transform.scale(-2.0, 2.0)
        mock_view.transform.return_value = transform
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0


class TestGraphicsViewUniformZoomAttributeError:
    """Tests for views without transform method or other attribute errors."""

    def test_view_without_transform_method(self, mock_view):
        """Should handle view without transform method gracefully."""
        mock_view.current_zoom = None
        mock_view.transform.side_effect = AttributeError("No transform method")
        with pytest.raises(AttributeError):
            graphics_view_uniform_zoom(mock_view)

    def test_view_without_current_zoom_or_transform(self):
        """Should fail when view has neither current_zoom nor transform."""
        view = object()
        with pytest.raises(AttributeError):
            graphics_view_uniform_zoom(view)


class TestGraphicsViewUniformZoomTypeHandling:
    """Tests for type handling of current_zoom attribute."""

    def test_current_zoom_bool_true(self, mock_view, mock_transform):
        """Should treat bool True as int (1), but reject because not > 0? No, bool is instance of int."""
        mock_view.current_zoom = True
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 2.0
        mock_transform.m12.return_value = 0.0
        # True is instance of int and > 0, so it should be used
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 1.0

    def test_current_zoom_bool_false(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is False."""
        mock_view.current_zoom = False
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 2.0
        mock_transform.m12.return_value = 0.0
        # False is instance of int but not > 0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 2.0

    def test_current_zoom_complex_number(self, mock_view, mock_transform):
        """Should fall back to transform when current_zoom is complex."""
        mock_view.current_zoom = 1 + 2j
        mock_view.transform.return_value = mock_transform
        mock_transform.m11.return_value = 3.0
        mock_transform.m12.return_value = 0.0
        result = graphics_view_uniform_zoom(mock_view)
        assert result == 3.0
