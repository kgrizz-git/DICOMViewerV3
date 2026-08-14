"""Round-5 coverage tests for gui.image_viewer_view — zoom, set_image, inversion, pixel spacing, magnifier, panning."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from image_viewer_view_round5_helpers import create_image as _img
from image_viewer_view_round5_helpers import create_viewer as _viewer
from PIL import Image
from PySide6.QtGui import QTransform
from PySide6.QtTest import QSignalSpy

# ---------------------------------------------------------------------------
# zoom_in / zoom_out / reset_zoom / set_zoom
# ---------------------------------------------------------------------------

def test_zoom_in_then_out(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    initial = v.current_zoom
    v.zoom_in()
    assert v.current_zoom > initial
    v.reset_zoom()
    assert abs(v.current_zoom - 1.0) < 1e-6


def test_zoom_out_clamps_to_min_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.min_zoom = 0.5
    v.current_zoom = 0.6
    v.zoom_factor = 1.5
    v._apply_view_transform()
    v.zoom_out()
    assert v.current_zoom >= v.min_zoom


def test_zoom_in_clamps_to_max_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.max_zoom = 5.0
    v.current_zoom = 4.9
    v.zoom_factor = 1.5
    v._apply_view_transform()
    v.zoom_in()
    assert v.current_zoom <= v.max_zoom


def test_zoom_in_no_image_noop(qapp) -> None:
    v = _viewer(qapp)
    v.zoom_in()
    assert v.current_zoom == 1.0


def test_zoom_out_no_image_noop(qapp) -> None:
    v = _viewer(qapp)
    v.zoom_out()
    assert v.current_zoom == 1.0


def test_set_zoom_no_image_noop(qapp) -> None:
    v = _viewer(qapp)
    v.set_zoom(3.0)
    assert v.current_zoom == 1.0


def test_set_zoom_clamps(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.set_zoom(50.0)  # above max_zoom (10.0)
    assert v.current_zoom <= v.max_zoom
    v.set_zoom(0.001)  # below min_zoom (0.1)
    assert v.current_zoom >= v.min_zoom


def test_reset_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 3.0
    v._apply_view_transform()
    v.reset_zoom()
    assert abs(v.current_zoom - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# compute_fit_zoom
# ---------------------------------------------------------------------------

def test_compute_fit_zoom_no_image_returns_none(qapp) -> None:
    v = _viewer(qapp)
    assert v.compute_fit_zoom() is None


def test_compute_fit_zoom_empty_scene_rect(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.image_item = None
    assert v.compute_fit_zoom() is None


def test_compute_fit_zoom_with_image(qapp) -> None:
    v = _viewer(qapp)
    v.resize(400, 200)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    fz = v.compute_fit_zoom()
    assert fz is not None
    assert fz > 0


def test_compute_fit_zoom_with_rotation_90(qapp) -> None:
    v = _viewer(qapp)
    v.resize(400, 200)
    v.set_image(_img("L", (100, 200)), preserve_view=False)
    v._rotation_deg = 90
    fz = v.compute_fit_zoom()
    assert fz is not None
    assert fz > 0


# ---------------------------------------------------------------------------
# is_effectively_fit_and_centered
# ---------------------------------------------------------------------------

def test_is_effectively_fit_and_centered_no_image(qapp) -> None:
    v = _viewer(qapp)
    assert v.is_effectively_fit_and_centered() is False


def test_is_effectively_fit_and_centered_zoom_mismatch(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 5.0
    v._apply_view_transform()
    assert v.is_effectively_fit_and_centered() is False


# ---------------------------------------------------------------------------
# fit_to_view
# ---------------------------------------------------------------------------

def test_fit_to_view_no_image_noop(qapp) -> None:
    v = _viewer(qapp)
    v.fit_to_view()
    assert v.current_zoom == 1.0


def test_fit_to_view_with_image(qapp) -> None:
    v = _viewer(qapp)
    v.resize(400, 300)
    v.set_image(_img("L", (80, 80)), preserve_view=False)
    v.fit_to_view()
    fz = v.compute_fit_zoom()
    assert fz is not None
    assert abs(v.current_zoom - fz) < 1e-6


# ---------------------------------------------------------------------------
# set_image branches
# ---------------------------------------------------------------------------

def test_set_image_new_slice_no_inversion(qapp) -> None:
    v = _viewer(qapp)
    img = _img()
    v.set_image(img, preserve_view=False)
    assert v.image_item is not None
    assert v.image_inverted is False


def test_set_image_new_slice_with_apply_inversion_true(qapp) -> None:
    v = _viewer(qapp)
    img = _img()
    v.set_image(img, preserve_view=False, apply_inversion=True)
    assert v.image_inverted is True


def test_set_image_new_slice_with_apply_inversion_false(qapp) -> None:
    v = _viewer(qapp)
    img = _img()
    v.set_image(img, preserve_view=False, apply_inversion=False)
    assert v.image_inverted is False


def test_set_image_preserve_view_inversion_toggle(qapp) -> None:
    v = _viewer(qapp)
    img = _img()
    v.set_image(img, preserve_view=False)
    saved_zoom = v.current_zoom
    # Toggle inversion with preserve_view
    v.set_image(_img(), preserve_view=True, apply_inversion=True)
    assert v.image_inverted is True
    assert v.current_zoom == saved_zoom


def test_set_image_preserve_view_scroll_no_inversion(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 2.0
    v._apply_view_transform()
    saved_zoom = v.current_zoom
    # New slice with preserve_view=True, no apply_inversion
    v.set_image(_img(), preserve_view=True, apply_inversion=None)
    assert v.current_zoom == saved_zoom
    assert v.image_inverted is False


def test_set_image_preserve_view_scroll_inverted(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False, apply_inversion=True)
    v.current_zoom = 2.0
    v._apply_view_transform()
    # Scroll to new slice preserving inversion
    v.set_image(_img(), preserve_view=True, apply_inversion=None)
    assert v.image_inverted is True


def test_set_image_replaces_old_item(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    old_item = v.image_item
    v.set_image(_img(), preserve_view=False)
    assert v.image_item is not old_item


def test_set_image_rgb_mode(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("RGB"), preserve_view=False)
    assert v.image_item is not None


def test_set_image_other_mode_converts_to_rgb(qapp) -> None:
    v = _viewer(qapp)
    # RGBA mode triggers the else branch
    img = Image.new("RGBA", (32, 32), (128, 128, 128, 255))
    v.set_image(img, preserve_view=False)
    assert v.image_item is not None


def test_set_image_large_image_uses_2x_scene(qapp) -> None:
    """When image width > viewport width, scene rect is 2x image size."""
    v = _viewer(qapp, w=100, h=100)
    img = Image.new("L", (200, 200), 128)
    v.set_image(img, preserve_view=False)
    sr = v.scene.sceneRect()
    assert sr.width() >= 200 * 2.0 - 1


def test_set_image_small_image_uses_3x_plus_viewport(qapp) -> None:
    """When image width < viewport width, scene rect uses 3x + viewport at zoom 0.5."""
    v = _viewer(qapp, w=400, h=400)
    img = Image.new("L", (50, 50), 128)
    v.set_image(img, preserve_view=False)
    sr = v.scene.sceneRect()
    assert sr.width() > 50 * 3.0


# ---------------------------------------------------------------------------
# invert_image
# ---------------------------------------------------------------------------

def test_invert_image_no_original_noop(qapp) -> None:
    v = _viewer(qapp)
    v.original_image = None
    v.invert_image()
    assert v.image_inverted is False


def test_invert_image_toggles_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.invert_image()
    assert v.image_inverted is True
    v.invert_image()
    assert v.image_inverted is False


def test_invert_image_calls_callback(qapp) -> None:
    v = _viewer(qapp)
    states: list[bool] = []
    v.inversion_state_changed_callback = states.append
    v.set_image(_img(), preserve_view=False)
    v.invert_image()
    assert states == [True]
    v.invert_image()
    assert states == [True, False]


# ---------------------------------------------------------------------------
# _apply_inversion
# ---------------------------------------------------------------------------

def test_apply_inversion_grayscale(qapp) -> None:
    v = _viewer(qapp)
    img = Image.new("L", (10, 10), 100)
    inv = v._apply_inversion(img)
    assert inv.getpixel((0, 0)) == 155


def test_apply_inversion_rgb(qapp) -> None:
    v = _viewer(qapp)
    img = Image.new("RGB", (10, 10), (100, 150, 200))
    inv = v._apply_inversion(img)
    px = inv.getpixel((0, 0))
    assert px == (155, 105, 55)


def test_apply_inversion_other_mode(qapp) -> None:
    v = _viewer(qapp)
    img = Image.new("RGBA", (10, 10), (100, 150, 200, 255))
    inv = v._apply_inversion(img)
    # Converts to RGB then inverts
    assert inv.mode == "RGB"


def test_apply_inversion_exception_returns_original(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    img = Image.new("L", (10, 10), 50)
    def bad_array(*a, **kw):
        raise RuntimeError("injected error")

    monkeypatch.setattr(np, "array", bad_array)
    result = v._apply_inversion(img)
    assert result is img


# ---------------------------------------------------------------------------
# set_pixel_info_callbacks
# ---------------------------------------------------------------------------

def test_set_pixel_info_callbacks(qapp) -> None:
    v = _viewer(qapp)
    v.set_pixel_info_callbacks(lambda: None, lambda: 0, lambda: False)
    assert v.get_current_dataset_callback is not None
    assert v.get_current_slice_index_callback is not None
    assert v.get_use_rescaled_values_callback is not None


# ---------------------------------------------------------------------------
# _extract_pixel_spacing
# ---------------------------------------------------------------------------

def test_extract_pixel_spacing_valid(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(PixelSpacing=[0.5, 0.75])
    assert v._extract_pixel_spacing(ds) == (0.5, 0.75)


def test_extract_pixel_spacing_none(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(PixelSpacing=None)
    assert v._extract_pixel_spacing(ds) is None


def test_extract_pixel_spacing_too_short(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(PixelSpacing=[0.5])
    assert v._extract_pixel_spacing(ds) is None


def test_extract_pixel_spacing_invalid_values(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(PixelSpacing=["bad", "data"])
    assert v._extract_pixel_spacing(ds) is None


def test_extract_pixel_spacing_no_attribute(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace()
    assert v._extract_pixel_spacing(ds) is None


# ---------------------------------------------------------------------------
# _compute_direction_labels
# ---------------------------------------------------------------------------

def test_compute_direction_labels_no_iop(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace()
    assert v._compute_direction_labels(ds) is None


def test_compute_direction_labels_with_iop(qapp) -> None:
    v = _viewer(qapp)
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    labels = v._compute_direction_labels(ds)
    assert labels is not None
    assert "top" in labels


def test_compute_direction_labels_with_flip(qapp) -> None:
    v = _viewer(qapp)
    v._flip_h = True
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    labels = v._compute_direction_labels(ds)
    assert labels is not None


def test_compute_direction_labels_with_rotation(qapp) -> None:
    v = _viewer(qapp)
    v._rotation_deg = 90
    ds = SimpleNamespace(ImageOrientationPatient=[1, 0, 0, 0, 1, 0])
    labels = v._compute_direction_labels(ds)
    assert labels is not None


# ---------------------------------------------------------------------------
# _extract_image_region
# ---------------------------------------------------------------------------

def test_extract_image_region_no_image(qapp) -> None:
    v = _viewer(qapp)
    assert v._extract_image_region(0, 0, 100, 2.0) is None


def test_extract_image_region_valid(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    region = v._extract_image_region(50, 50, 30, 2.0)
    assert region is not None
    assert region.width() > 0


def test_extract_image_region_zero_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    region = v._extract_image_region(50, 50, 30, 1.0)
    assert region is not None


def test_extract_image_region_invalid_bounds(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (10, 10)), preserve_view=False)
    region = v._extract_image_region(100, 100, 5, 1.0)
    assert region is None


def test_extract_image_region_null_pixmap(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    from PySide6.QtGui import QPixmap
    v.image_item.setPixmap(QPixmap())
    region = v._extract_image_region(50, 50, 30, 2.0)
    assert region is None


# ---------------------------------------------------------------------------
# _render_scene_region
# ---------------------------------------------------------------------------

def test_render_scene_region_no_scene(qapp) -> None:
    v = _viewer(qapp)
    assert v._render_scene_region(0, 0, 100, 2.0) is None


def test_render_scene_region_valid(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    region = v._render_scene_region(50, 50, 30, 2.0)
    assert region is not None
    assert region.width() > 0


def test_render_scene_region_no_image_intersects_scene_rect(qapp) -> None:
    v = _viewer(qapp)
    region = v._render_scene_region(50, 50, 30, 1.0)
    assert region is None


def test_render_scene_region_empty_intersection(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img("L", (100, 100)), preserve_view=False)
    region = v._render_scene_region(10000, 10000, 10, 1.0)
    assert region is None


# ---------------------------------------------------------------------------
# get_viewport_center_scene
# ---------------------------------------------------------------------------

def test_get_viewport_center_scene(qapp) -> None:
    v = _viewer(qapp)
    v.resize(200, 200)
    v.show()
    center = v.get_viewport_center_scene()
    assert center is not None


# ---------------------------------------------------------------------------
# _check_transform_changed
# ---------------------------------------------------------------------------

def test_check_transform_changed_emits_signal(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 2.0
    v.last_transform = QTransform()
    emissions = QSignalSpy(v.transform_changed)
    v._check_transform_changed()
    assert emissions.wait(100)
    assert emissions.count() >= 1


# ---------------------------------------------------------------------------
# _on_scrollbar_changed
# ---------------------------------------------------------------------------

def test_on_scrollbar_changed_noop_when_same(qapp) -> None:
    v = _viewer(qapp)
    v.last_horizontal_scroll = 0
    v.last_vertical_scroll = 0
    emissions = QSignalSpy(v.transform_changed)
    v._on_scrollbar_changed()
    assert (v.last_horizontal_scroll, v.last_vertical_scroll) == (0, 0)
    assert emissions.count() == 0


def test_on_scrollbar_changed_detects_change(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.last_horizontal_scroll = 0
    v.last_vertical_scroll = 0
    emissions = QSignalSpy(v.transform_changed)
    v.horizontalScrollBar().setValue(10)
    v._on_scrollbar_changed()
    assert v.last_horizontal_scroll == 10
    assert v.last_vertical_scroll == 0
    assert emissions.count() == 1


# ---------------------------------------------------------------------------
# scrollContentsBy
# ---------------------------------------------------------------------------

def test_scrollContentsBy_repositions_slider(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    reposition = MagicMock()
    v._slider_overlay = MagicMock()
    monkeypatch.setattr(v, "_reposition_slider_overlay", reposition)
    v.scrollContentsBy(5, 5)
    reposition.assert_called_once()


# ---------------------------------------------------------------------------
# resizeEvent
# ---------------------------------------------------------------------------

def test_resizeEvent(qapp, monkeypatch) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    reposition_slider = MagicMock()
    reposition_placeholder = MagicMock()
    v._slider_overlay = MagicMock()
    v._no_pixel_placeholder_overlay = MagicMock()
    monkeypatch.setattr(v, "_reposition_slider_overlay", reposition_slider)
    monkeypatch.setattr(v, "_reposition_no_pixel_placeholder_overlay", reposition_placeholder)
    emissions = QSignalSpy(v.transform_changed)
    v.resize(500, 400)
    assert emissions.wait(100)
    assert reposition_slider.call_count >= 1
    assert reposition_placeholder.call_count >= 1
