"""Unit tests for core.fusion_processor.FusionProcessor."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

import core.fusion_processor as fusion_processor
from core.fusion_processor import FusionProcessor


class TestNormalizeArray:
    def test_basic_normalization(self):
        array = np.array([0.0, 50.0, 100.0], dtype=np.float32)
        result = FusionProcessor.normalize_array(array, window=100.0, level=50.0)
        np.testing.assert_allclose(result, [0.0, 0.5, 1.0], atol=1e-6)

    def test_clips_out_of_range_values(self):
        array = np.array([-100.0, 200.0], dtype=np.float32)
        result = FusionProcessor.normalize_array(array, window=100.0, level=50.0)
        np.testing.assert_allclose(result, [0.0, 1.0])


class TestApplyThreshold:
    def test_creates_binary_mask(self):
        array = np.array([0.0, 0.3, 0.5, 0.8], dtype=np.float32)
        mask = FusionProcessor.apply_threshold(array, threshold=0.5)
        np.testing.assert_array_equal(mask, [0.0, 0.0, 1.0, 1.0])

    def test_mask_dtype_is_float32(self):
        array = np.array([1.0], dtype=np.float32)
        mask = FusionProcessor.apply_threshold(array, threshold=0.0)
        assert mask.dtype == np.float32


class TestApplyColormap:
    def setup_method(self):
        fusion_processor._COLORMAP_CACHE.clear()

    def teardown_method(self):
        fusion_processor._COLORMAP_CACHE.clear()

    def test_valid_colormap_returns_rgb_array(self):
        array = np.array([[0.0, 0.5], [1.0, 0.25]], dtype=np.float32)
        result = FusionProcessor.apply_colormap(array, "hot")
        assert result.shape == (2, 2, 3)
        assert result.dtype == np.float32

    def test_valid_colormap_is_cached(self):
        array = np.array([0.5], dtype=np.float32)
        FusionProcessor.apply_colormap(array, "viridis")
        assert "viridis" in fusion_processor._COLORMAP_CACHE

    def test_unknown_colormap_falls_back_to_hot(self, capsys):
        array = np.array([0.5], dtype=np.float32)
        result = FusionProcessor.apply_colormap(array, "not-a-real-colormap")
        captured = capsys.readouterr()
        assert "not found" in captured.out
        assert result.shape == (1, 3)

    def test_second_call_uses_cache_not_reimporting(self):
        array = np.array([0.5], dtype=np.float32)
        FusionProcessor.apply_colormap(array, "jet")
        cached_cmap = fusion_processor._COLORMAP_CACHE["jet"]
        FusionProcessor.apply_colormap(array, "jet")
        assert fusion_processor._COLORMAP_CACHE["jet"] is cached_cmap


class TestApplyTranslationOffset:
    def test_zero_offset_copies_overlay_into_matching_canvas(self):
        overlay = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = FusionProcessor._apply_translation_offset(overlay, 0.0, 0.0, (2, 2))
        np.testing.assert_array_equal(result, overlay)

    def test_positive_offset_shifts_right_and_down(self):
        overlay = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = FusionProcessor._apply_translation_offset(overlay, 1.0, 1.0, (3, 3))
        expected = np.array(
            [[0.0, 0.0, 0.0], [0.0, 1.0, 2.0], [0.0, 3.0, 4.0]], dtype=np.float32
        )
        np.testing.assert_array_equal(result, expected)

    def test_negative_offset_shifts_left_and_up(self):
        overlay = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = FusionProcessor._apply_translation_offset(overlay, -1.0, -1.0, (2, 2))
        expected = np.array([[4.0, 0.0], [0.0, 0.0]], dtype=np.float32)
        np.testing.assert_array_equal(result, expected)

    def test_offset_entirely_out_of_bounds_returns_zeros(self):
        overlay = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = FusionProcessor._apply_translation_offset(overlay, 100.0, 100.0, (2, 2))
        np.testing.assert_array_equal(result, np.zeros((2, 2), dtype=np.float32))

    def test_result_shape_matches_base_shape(self):
        overlay = np.ones((5, 5), dtype=np.float32)
        result = FusionProcessor._apply_translation_offset(overlay, 2.0, -1.0, (4, 6))
        assert result.shape == (4, 6)


class TestConvertArrayToPilImage:
    def test_grayscale_2d_array(self):
        array = np.zeros((4, 4), dtype=np.uint8)
        img = FusionProcessor.convert_array_to_pil_image(array)
        assert isinstance(img, Image.Image)
        assert img.mode == "L"

    def test_rgb_3d_array(self):
        array = np.zeros((4, 4, 3), dtype=np.uint8)
        img = FusionProcessor.convert_array_to_pil_image(array)
        assert img.mode == "RGB"

    def test_unsupported_shape_raises(self):
        array = np.zeros((4, 4, 5), dtype=np.uint8)
        with pytest.raises(ValueError, match="Unsupported array shape"):
            FusionProcessor.convert_array_to_pil_image(array)

    def test_1d_array_raises(self):
        array = np.zeros((4,), dtype=np.uint8)
        with pytest.raises(ValueError, match="Unsupported array shape"):
            FusionProcessor.convert_array_to_pil_image(array)


class TestCreateFusionImage:
    def _base_and_overlay(self, shape=(8, 8), base_val=100.0, overlay_val=50.0):
        base = np.full(shape, base_val, dtype=np.float64)
        overlay = np.full(shape, overlay_val, dtype=np.float64)
        return base, overlay

    def test_returns_uint8_rgb_array_matching_base_shape(self):
        base, overlay = self._base_and_overlay()
        fused = FusionProcessor.create_fusion_image(base, overlay)
        assert fused.shape == (8, 8, 3)
        assert fused.dtype == np.uint8

    def test_non_float32_inputs_are_converted(self):
        base = np.full((4, 4), 10, dtype=np.int16)
        overlay = np.full((4, 4), 5, dtype=np.int16)
        fused = FusionProcessor.create_fusion_image(base, overlay)
        assert fused.shape == (4, 4, 3)

    def test_float32_inputs_use_existing_dtype_path(self):
        base = np.linspace(0.0, 15.0, 16, dtype=np.float32).reshape(4, 4)
        overlay = np.linspace(15.0, 0.0, 16, dtype=np.float32).reshape(4, 4)
        fused = FusionProcessor.create_fusion_image(base, overlay)
        assert fused.shape == (4, 4, 3)

    def test_explicit_base_and_overlay_window_level(self):
        base, overlay = self._base_and_overlay()
        fused = FusionProcessor.create_fusion_image(
            base, overlay, base_wl=(200.0, 100.0), overlay_wl=(100.0, 50.0)
        )
        assert fused.shape == (8, 8, 3)

    def test_auto_normalize_when_base_is_uniform(self):
        base = np.full((4, 4), 42.0, dtype=np.float64)
        overlay = np.full((4, 4), 42.0, dtype=np.float64)
        fused = FusionProcessor.create_fusion_image(base, overlay)
        # Uniform arrays with equal min/max normalize to zero everywhere;
        # ensures the zeros_like fallback path executes without error.
        assert fused.shape == (4, 4, 3)

    def test_auto_normalize_when_base_is_non_uniform(self):
        base = np.array([[0.0, 50.0], [100.0, 150.0]], dtype=np.float32)
        overlay = np.array([[0.0, 25.0], [50.0, 100.0]], dtype=np.float32)
        fused = FusionProcessor.create_fusion_image(base, overlay, alpha=0.0)
        expected_gray = np.array([[0, 85], [170, 255]], dtype=np.uint8)
        expected_rgb = np.repeat(expected_gray[..., np.newaxis], 3, axis=2)
        np.testing.assert_array_equal(fused, expected_rgb)

    def test_pixel_spacing_scaling_resizes_overlay(self):
        base = np.full((10, 10), 100.0, dtype=np.float64)
        overlay = np.full((5, 5), 50.0, dtype=np.float64)
        fused = FusionProcessor.create_fusion_image(
            base,
            overlay,
            base_pixel_spacing=(1.0, 1.0),
            overlay_pixel_spacing=(2.0, 2.0),
        )
        assert fused.shape == (10, 10, 3)

    def test_shape_mismatch_without_spacing_falls_back_to_resize(self):
        base = np.full((10, 10), 100.0, dtype=np.float64)
        overlay = np.full((5, 5), 50.0, dtype=np.float64)
        fused = FusionProcessor.create_fusion_image(base, overlay)
        assert fused.shape == (10, 10, 3)

    def test_matching_shapes_without_spacing_skips_resize(self):
        base, overlay = self._base_and_overlay(shape=(6, 6))
        fused = FusionProcessor.create_fusion_image(base, overlay)
        assert fused.shape == (6, 6, 3)

    def test_skip_2d_resize_with_matching_shapes(self):
        base, overlay = self._base_and_overlay(shape=(6, 6))
        fused = FusionProcessor.create_fusion_image(base, overlay, skip_2d_resize=True)
        assert fused.shape == (6, 6, 3)

    def test_skip_2d_resize_with_mismatched_shapes_warns_and_resizes(self, capsys):
        base = np.full((10, 10), 100.0, dtype=np.float64)
        overlay = np.full((5, 5), 50.0, dtype=np.float64)
        fused = FusionProcessor.create_fusion_image(base, overlay, skip_2d_resize=True)
        captured = capsys.readouterr()
        assert "doesn't match base" in captured.out
        assert fused.shape == (10, 10, 3)

    def test_translation_offset_applied(self):
        base, overlay = self._base_and_overlay(shape=(6, 6))
        fused_no_offset = FusionProcessor.create_fusion_image(base, overlay)
        fused_with_offset = FusionProcessor.create_fusion_image(
            base, overlay, translation_offset=(2.0, 2.0)
        )
        assert fused_with_offset.shape == fused_no_offset.shape

    def test_debug_offset_enabled_prints_diagnostics(self, monkeypatch, capsys):
        monkeypatch.setattr(fusion_processor, "DEBUG_OFFSET", True)
        base = np.full((10, 10), 100.0, dtype=np.float64)
        overlay = np.full((5, 5), 50.0, dtype=np.float64)
        FusionProcessor.create_fusion_image(
            base,
            overlay,
            base_pixel_spacing=(1.0, 1.0),
            overlay_pixel_spacing=(2.0, 2.0),
            overlay_wl=(100.0, 50.0),
            translation_offset=(1.0, 1.0),
        )
        captured = capsys.readouterr()
        assert "base_pixel_spacing" in captured.out
        assert "[SCALING]" in captured.out
        assert "[TRANSLATION]" in captured.out
        assert "[OVERLAY W/L]" in captured.out

    def test_debug_offset_without_overlay_wl_prints_normalized_range_only(self, monkeypatch, capsys):
        monkeypatch.setattr(fusion_processor, "DEBUG_OFFSET", True)
        base = np.array([[0.0, 50.0], [100.0, 150.0]], dtype=np.float32)
        overlay = np.array([[0.0, 10.0], [20.0, 30.0]], dtype=np.float32)
        fused = FusionProcessor.create_fusion_image(
            base, overlay, alpha=0.5, threshold=0.0
        )
        captured = capsys.readouterr()
        assert fused.shape == (2, 2, 3)
        assert "overlay_normalized range" in captured.out
        assert "[OVERLAY W/L]" not in captured.out

    def test_full_alpha_with_threshold_zero_uses_normalized_overlay_colors(self):
        base = np.full((2, 2), 0.0, dtype=np.float32)
        overlay = np.array([[0.0, 50.0], [75.0, 100.0]], dtype=np.float32)
        fused = FusionProcessor.create_fusion_image(
            base, overlay, alpha=1.0, threshold=0.0, colormap="hot"
        )
        overlay_rgb = FusionProcessor.apply_colormap(
            np.array([[0.0, 0.5], [0.75, 1.0]], dtype=np.float32), "hot"
        )
        expected_pixel = np.clip(overlay_rgb[0, 0] * 255.0, 0, 255).astype(np.uint8)
        np.testing.assert_array_equal(fused[0, 0], expected_pixel)
