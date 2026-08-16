"""Focused unit tests for export_rendering pure helpers."""

from __future__ import annotations

import pytest
from PIL import Image
from pydicom.dataset import Dataset

from gui.export_rendering import (
    effective_scale_for_image,
    export_line_thickness_pixels,
    export_text_size_pixels,
    process_image_by_photometric_interpretation,
)


def test_effective_scale_clamps_large_images() -> None:
    assert effective_scale_for_image(64, 64, 2.0) == pytest.approx(2.0)
    # Very large image should not explode memory — scale reduced toward native.
    scaled = effective_scale_for_image(8000, 8000, 4.0)
    assert 0 < scaled <= 4.0
    assert scaled <= effective_scale_for_image(64, 64, 4.0)


def test_export_line_and_text_size_scale() -> None:
    thin = export_line_thickness_pixels(50, 512, 512, 1.0)
    thick = export_line_thickness_pixels(50, 512, 512, 2.0)
    assert thin >= 1
    assert thick >= thin
    small = export_text_size_pixels(50, 512, 512, 1.0)
    large = export_text_size_pixels(50, 512, 512, 2.0)
    assert small >= 8
    assert large >= small


def test_process_image_monochrome_passthrough() -> None:
    img = Image.new("L", (8, 8), 40)
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME2"
    out = process_image_by_photometric_interpretation(img, ds)
    assert out.size == (8, 8)
    assert out.mode in ("L", "RGB", "RGBA")


def test_process_image_monochrome1_is_noop() -> None:
    img = Image.new("L", (4, 4), 0)
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME1"
    out = process_image_by_photometric_interpretation(img, ds)
    px = out.getpixel((0, 0))
    if isinstance(px, tuple):
        assert px[0] == 0
    else:
        assert px == 0
