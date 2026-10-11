"""Display paths apply a LUT after net inversion and default to the linear ramp.

Covers the five builders: single-slice render, slice projection, MPR ``array_to_pil``,
export projection, and the MPR thumbnail preview. Linear and ``lut=None`` stay
byte-identical. MONOCHROME1 XOR the user invert cancels before the LUT.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtGui import QImage

from core.dicom_image_render import render_grayscale_image
from core.lut_catalog import inverse_lut, linear_lut
from core.lut_display import apply_user_invert_and_lut
from core.lut_series_state import focused_pane_lut, get_series_lut
from core.mpr_view_math import array_to_pil
from core.slice_display_pixels import create_slice_projection_pil_image
from gui.export_manager import ExportManager, ExportSliceRequest
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


def test_focused_pane_lut_prefers_mpr_override():
    from core.lut_catalog import sigmoid_lut
    from core.lut_series_state import set_mpr_lut_override

    series_lut = linear_lut()
    override = sigmoid_lut()
    view_state = type(
        "V",
        (),
        {
            "series_defaults": {"series-id": {"current_lut": series_lut}},
            "current_series_identifier": "series-id",
            "image_viewer": None,
        },
    )()
    _inverted, lut = focused_pane_lut(view_state)
    assert lut is series_lut
    set_mpr_lut_override(view_state, override)
    _inverted, lut = focused_pane_lut(view_state)
    assert lut is override


def test_color_array_skips_user_invert_and_lut():
    color = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    out = apply_user_invert_and_lut(color, image_inverted=True, lut=inverse_lut())
    assert np.array_equal(out, color)


def test_color_projection_is_not_display_final_and_export_inverts(tmp_path, monkeypatch):
    """A color projection is RGB. The viewer inverts it later; export must too."""
    rgb = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    studies, ds = _studies()
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"

    class _ColorProc(_FakeProc):
        def average_intensity_projection(self, slices):
            _ = slices
            return rgb.astype(np.float32)

    proc = _ColorProc()
    monkeypatch.setattr(
        "gui.export_rendering.DICOMProcessor.average_intensity_projection",
        staticmethod(proc.average_intensity_projection),
    )
    plain = create_slice_projection_pil_image(
        proc, "aip", 3, studies, "st", "sr", 0, None, None, False, None, None,
        image_inverted=True, lut=inverse_lut(),
    )
    untouched = create_slice_projection_pil_image(
        proc, "aip", 3, studies, "st", "sr", 0, None, None, False, None, None,
    )
    exported = create_projection_for_export(
        ds, studies, "st", "sr", 0, "aip", 3, None, None, False,
        image_inverted=True, lut=inverse_lut(),
    )
    assert plain is not None and untouched is not None and plain.mode == "RGB"
    assert np.array_equal(np.array(plain), np.array(untouched))
    assert exported is not None and np.array_equal(np.array(plain), np.array(exported))

    source = Image.fromarray(rgb, mode="RGB")
    monkeypatch.setattr(
        "gui.export_manager._er.create_projection_for_export",
        lambda *_args, **_kwargs: source.copy(),
    )
    out = tmp_path / "color-projection.png"
    ok, _info = ExportManager().export_slice(
        ExportSliceRequest(
            ds, str(out), "PNG",
            include_overlays=False,
            projection_enabled=True,
            projection_slice_count=2,
            studies=studies,
            study_uid="st",
            series_uid="sr",
            slice_index=0,
            image_inverted=True,
        )
    )
    assert ok is True
    saved = np.array(Image.open(out))
    assert np.array_equal(saved, 255 - rgb)


@pytest.mark.parametrize("photometric", ["MONOCHROME1", "MONOCHROME2"])
def test_user_invert_without_lut_matches_polarity_xor(photometric):
    alone = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation=photometric, image_inverted=False
    )
    extra = render_grayscale_image(
        _ARRAY, None, None, None, None, photometric_interpretation=photometric, image_inverted=True
    )
    assert np.array_equal(_gray(extra), 255 - _gray(alone))


def test_monochrome1_color_lut_expands_after_polarity():
    """Rows 1 and 2 under MONOCHROME1 plus a color LUT: RGB, polarity before LUT, never double-inverted."""
    from core.dicom_window_level import apply_window_level
    from core.lut_catalog import colormap_lut

    hot = colormap_lut("hot")
    row1 = render_grayscale_image(
        _ARRAY.astype(np.float32), 127.5, 255.0, None, None,
        photometric_interpretation="MONOCHROME1", lut=hot,
    )
    assert row1 is not None and row1.mode == "RGB"

    studies, _ds = _studies()
    row2 = create_slice_projection_pil_image(
        _FakeProc(), "aip", 3, studies, "st", "sr", 0, 40.0, 400.0, False, None, None,
        photometric_interpretation="MONOCHROME1", lut=hot,
    )
    assert row2 is not None and row2.mode == "RGB"

    # Both windows map this array to the identity, so the expected output is the
    # color table indexed by the polarity-inverted bytes.
    windowed = apply_window_level(_ARRAY.astype(np.float64), 127.5, 255.0)
    expected = hot.colormap[255 - windowed]
    assert np.array_equal(np.array(row1), expected)
    assert np.array_equal(np.array(row2), expected)
    # Polarity ran before the LUT expansion; indexing the uninverted bytes is a different image.
    assert not np.array_equal(np.array(row1), hot.colormap[_ARRAY])


def test_thumbnail_no_window_fallback_applies_lut(qapp):
    """Row 5 fallback: a None window normalizes, then the LUT still runs (plan: no-windowing branch)."""
    from core.display_normalize import normalize_to_uint8

    _ = qapp
    widget = MprThumbnailWidget(0)
    size = MprThumbnailWidget.THUMBNAIL_SIZE
    vals = np.linspace(0.0, 400.0, size * size, dtype=np.float32).reshape(size, size)

    widget.update_preview(vals, None, None, "MONOCHROME2")
    plain = _thumbnail_rgb_bytes(widget)
    widget.update_preview(vals, None, None, "MONOCHROME2", lut=inverse_lut())
    flipped = _thumbnail_rgb_bytes(widget)
    widget.update_preview(vals, size * 3.0, size / 2.0, "MONOCHROME2")
    windowed = _thumbnail_rgb_bytes(widget)

    normalized = normalize_to_uint8(vals)
    assert np.array_equal(plain, np.repeat(normalized[..., np.newaxis], 3, axis=2))
    assert np.array_equal(flipped, np.repeat((255 - normalized)[..., np.newaxis], 3, axis=2))
    # The None-window call really took the fallback, not an implicit window.
    assert not np.array_equal(plain, windowed)


def _thumbnail_rgb_bytes(widget):
    """Return the thumbnail's RGB bytes as an (H, W, 3) array.

    ``np.array`` copies: the QImage buffer dies with the local ``image``, so a
    ``frombuffer`` view would read freed memory once the helper returns.
    """
    image = widget._preview_pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    flat = np.frombuffer(
        image.bits(), dtype=np.uint8, count=image.height() * image.bytesPerLine()
    ).reshape(image.height(), image.bytesPerLine())
    return np.array(flat[:, : 3 * image.width()]).reshape(image.height(), image.width(), 3)
