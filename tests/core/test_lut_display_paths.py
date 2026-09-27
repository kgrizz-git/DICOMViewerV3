"""Display paths apply a LUT after net inversion and default to the linear ramp.

Covers the five builders: single-slice render, slice projection, MPR ``array_to_pil``,
export projection, and the MPR thumbnail preview. Linear and ``lut=None`` stay
byte-identical. MONOCHROME1 XOR the user invert cancels before the LUT.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset
from PySide6.QtGui import QImage

from core.dicom_image_render import render_grayscale_image
from core.lut_catalog import inverse_lut, linear_lut
from core.lut_series_state import focused_pane_lut, get_series_lut
from core.mpr_view_math import array_to_pil
from core.slice_display_pixels import create_slice_projection_pil_image
from gui.export_rendering import create_projection_for_export
from gui.mpr_thumbnail_widget import MprThumbnailWidget

_ARRAY = np.array([[0, 64, 128, 200, 255]], dtype=np.uint8)


def _gray(image) -> np.ndarray:
    assert image is not None
    arr = np.array(image)
    if arr.ndim == 3:
        return arr[:, :, 0]
    return arr


def test_linear_lut_matches_omitted_lut():
    plain = render_grayscale_image(_ARRAY, None, None, None, None, photometric_interpretation="MONOCHROME2")
    linear = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation="MONOCHROME2", lut=linear_lut()
    )
    assert np.array_equal(_gray(plain), _gray(linear))


def test_inverse_lut_flips_single_slice_bytes():
    plain = render_grayscale_image(_ARRAY, None, None, None, None, photometric_interpretation="MONOCHROME2")
    flipped = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation="MONOCHROME2", lut=inverse_lut()
    )
    assert np.array_equal(_gray(flipped), 255 - _gray(plain))


def test_monochrome1_xor_user_invert_cancels_before_lut():
    baseline = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation="MONOCHROME2", lut=inverse_lut()
    )
    both = render_grayscale_image(
        _ARRAY, None, None, None, None,
        photometric_interpretation="MONOCHROME1", image_inverted=True, lut=inverse_lut(),
    )
    assert np.array_equal(_gray(baseline), _gray(both))


def test_mpr_array_to_pil_inverse_and_cancel():
    windowed = array_to_pil(_ARRAY.astype(np.float32), 127.5, 255.0, photometric_interpretation="MONOCHROME2")
    inverse = array_to_pil(
        _ARRAY.astype(np.float32), 127.5, 255.0, photometric_interpretation="MONOCHROME2", lut=inverse_lut()
    )
    both = array_to_pil(
        _ARRAY.astype(np.float32), 127.5, 255.0,
        photometric_interpretation="MONOCHROME1", image_inverted=True, lut=inverse_lut(),
    )
    assert not np.array_equal(_gray(windowed), _gray(inverse))
    assert np.array_equal(_gray(inverse), _gray(both))


class _FakeProc:
    def average_intensity_projection(self, slices):
        _ = slices
        return _ARRAY.astype(np.float32)

    maximum_intensity_projection = average_intensity_projection
    minimum_intensity_projection = average_intensity_projection

    def apply_window_level(self, array, window_center, window_width):
        _ = (window_center, window_width)
        return np.clip(array, 0, 255).astype(np.uint8)


def _studies():
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME2"
    return {"st": {"sr": [ds, ds, ds]}}, ds


def test_slice_and_export_projections_share_inverse_lut(monkeypatch):
    studies, ds = _studies()
    proc = _FakeProc()
    monkeypatch.setattr(
        "gui.export_rendering.DICOMProcessor.average_intensity_projection",
        staticmethod(proc.average_intensity_projection),
    )
    monkeypatch.setattr(
        "gui.export_rendering.DICOMProcessor.apply_window_level",
        staticmethod(proc.apply_window_level),
    )
    screen = create_slice_projection_pil_image(
        proc, "aip", 3, studies, "st", "sr", 0, 40.0, 400.0, False, None, None, lut=inverse_lut()
    )
    exported = create_projection_for_export(
        ds, studies, "st", "sr", 0, "aip", 3, 40.0, 400.0, False, lut=inverse_lut()
    )
    plain = create_slice_projection_pil_image(
        proc, "aip", 3, studies, "st", "sr", 0, 40.0, 400.0, False, None, None
    )
    assert np.array_equal(_gray(screen), _gray(exported))
    assert np.array_equal(_gray(screen), 255 - _gray(plain))


def test_thumbnail_inverse_changes_preview_pixels(qapp):
    _ = qapp
    widget = MprThumbnailWidget(0)
    widget.update_preview(_ARRAY.astype(np.float32), 127.5, 255.0, "MONOCHROME2")
    plain = widget._preview_pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    widget.update_preview(_ARRAY.astype(np.float32), 127.5, 255.0, "MONOCHROME2", lut=inverse_lut())
    flipped = widget._preview_pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    plain_px = np.frombuffer(plain.bits(), dtype=np.uint8).reshape(plain.height(), plain.bytesPerLine())
    flip_px = np.frombuffer(flipped.bits(), dtype=np.uint8).reshape(flipped.height(), flipped.bytesPerLine())
    assert not np.array_equal(plain_px, flip_px)


def test_missing_series_lut_is_linear():
    view_state = type("V", (), {"series_defaults": {}})()
    assert get_series_lut(view_state, "missing").name == linear_lut().name
    inverted, lut = focused_pane_lut(None)
    assert inverted is False
    assert lut.name == linear_lut().name


@pytest.mark.parametrize("photometric", ["MONOCHROME1", "MONOCHROME2"])
def test_user_invert_without_lut_matches_polarity_xor(photometric):
    alone = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation=photometric, image_inverted=False
    )
    extra = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation=photometric, image_inverted=True
    )
    assert np.array_equal(_gray(extra), 255 - _gray(alone))
