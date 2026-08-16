"""Tests for MONOCHROME1 export polarity — screen == export (no double-inversion)."""

from __future__ import annotations

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_image_render import render_grayscale_image
from gui.export_rendering import process_image_by_photometric_interpretation


def _make_monochrome1_dataset() -> Dataset:
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME1"
    return ds


def test_export_monochrome1_matches_screen():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    screen_image = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME1")
    assert screen_image is not None

    export_image = process_image_by_photometric_interpretation(screen_image, _make_monochrome1_dataset())

    assert np.array_equal(np.array(screen_image), np.array(export_image))


def test_export_monochrome2_no_change():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    screen_image = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME2")
    assert screen_image is not None

    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME2"
    export_image = process_image_by_photometric_interpretation(screen_image, ds)

    assert np.array_equal(np.array(screen_image), np.array(export_image))
