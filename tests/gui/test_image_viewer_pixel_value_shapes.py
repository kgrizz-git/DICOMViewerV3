"""Regression for ImageViewer._get_pixel_value_at_coords 3-D shape dispatch.

Covers single-frame color, multi-frame grayscale, and the collapsed ambiguous
3-D branch (former S3923 identical arms).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from gui.image_viewer import ImageViewer


@pytest.mark.qt
def test_pixel_value_single_frame_color_rgb(qapp, monkeypatch) -> None:
    viewer = ImageViewer()
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[1, 2] = (10, 20, 30)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = viewer._get_pixel_value_at_coords(ds, x=2, y=1, z=0, use_rescaled=False)
    assert "10" in out and "20" in out and "30" in out


@pytest.mark.qt
def test_pixel_value_multi_frame_grayscale(qapp, monkeypatch) -> None:
    viewer = ImageViewer()
    arr = np.zeros((3, 4, 4), dtype=np.float32)
    arr[2, 1, 1] = 42.0
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=1)
    out = viewer._get_pixel_value_at_coords(ds, x=1, y=1, z=2, use_rescaled=False)
    assert "42" in out


@pytest.mark.qt
def test_pixel_value_ambiguous_3d_keeps_full_array(qapp, monkeypatch) -> None:
    """Color spp but last dim != spp: collapsed else keeps the full array."""
    viewer = ImageViewer()
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    arr[1, 2, 0:3] = (7, 8, 9)
    monkeypatch.setattr(
        "core.dicom_processor.DICOMProcessor.get_pixel_array",
        staticmethod(lambda ds: arr),
    )
    ds = SimpleNamespace(SamplesPerPixel=3)
    out = viewer._get_pixel_value_at_coords(ds, x=2, y=1, z=0, use_rescaled=False)
    assert "7" in out and "8" in out and "9" in out
