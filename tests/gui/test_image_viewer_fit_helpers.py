"""Tests for ImageViewer.compute_fit_zoom and is_effectively_fit_and_centered."""

from __future__ import annotations

import pytest
from PIL import Image

from gui.image_viewer import ImageViewer


@pytest.mark.qt
def test_compute_fit_zoom_none_without_image(qapp) -> None:
    viewer = ImageViewer()
    viewer.resize(200, 200)
    assert viewer.compute_fit_zoom() is None


@pytest.mark.qt
def test_compute_fit_zoom_matches_fit_to_view_math(qapp) -> None:
    """Rotation 0: fit zoom is min(viewport_w/img_w, viewport_h/img_h) using actual viewport."""
    viewer = ImageViewer()
    viewer.resize(400, 200)
    img = Image.new("L", (100, 100), 128)
    viewer.set_image(img, preserve_view=False)
    vp = viewer.viewport()
    vw, vh = float(vp.width()), float(vp.height())
    expected = min(vw / 100.0, vh / 100.0)
    fz = viewer.compute_fit_zoom()
    assert fz is not None
    assert abs(fz - expected) < 1e-3


@pytest.mark.qt
def test_is_effectively_fit_and_centered_true_after_fit(qapp) -> None:
    viewer = ImageViewer()
    viewer.resize(300, 300)
    img = Image.new("L", (100, 100), 0)
    viewer.set_image(img, preserve_view=False)
    assert viewer.is_effectively_fit_and_centered()


@pytest.mark.qt
def test_is_effectively_fit_and_centered_false_after_zoom_in(qapp) -> None:
    viewer = ImageViewer()
    viewer.resize(300, 300)
    img = Image.new("L", (100, 100), 0)
    viewer.set_image(img, preserve_view=False)
    viewer.zoom_in()
    assert not viewer.is_effectively_fit_and_centered()
