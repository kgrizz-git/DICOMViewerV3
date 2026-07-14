"""
Unit and integration tests for ``core.dicom_processor.DICOMProcessor.dataset_to_image``
and the pure helper functions it was decomposed into (Sonar complexity 280 -> under 15).

Most color-path tests pass an explicit ``window_center=127.5, window_width=255``
(a window spanning exactly [0, 255]) so that "expected" outputs can be computed by
calling ``apply_window_level`` / ``apply_color_window_level_luminance`` directly on
a known pre-window array -- these tests check that ``dataset_to_image`` wires pixel
data through those (already-existing, separately-owned) functions correctly, not
their internal floating-point arithmetic. Note ``apply_color_window_level_luminance``
truncates non-zero values down by ~1 even at this "identity" window, because its
scale factor is ``luminance / (luminance + epsilon)`` rather than exactly 1 --
that's a real characteristic of the existing function, not a rounding bug in these
tests, which is why expected values are computed by calling the function rather
than assumed to equal the input.

Both known bugs from the follow-up-commit plan are now fixed: the
``apply_rescale=False`` rescale leak (see ``resolve_window_level_and_rescale``
in ``core.dicom_window_level``) and 16-bit PALETTE COLOR LUTs being decoded as
8-bit (see ``read_palette_lut`` / ``apply_palette_luts`` in
``core.dicom_palette``).
"""

from __future__ import annotations

import numpy as np
from PIL import Image as PILImage
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.dicom_image_render import normalize_channels_to_uint8, normalize_to_uint8
from core.dicom_processor import DICOMProcessor
from core.dicom_window_level import (
    apply_color_window_level_luminance,
    apply_window_level,
    convert_window_level_units,
    resolve_window_level_and_rescale,
)

# ---------------------------------------------------------------------------
# Dataset builders (local to this file, per the repo's per-file convention --
# see tests/test_mpr_core.py, tests/test_volume_render_calibrated_data.py).
# ---------------------------------------------------------------------------


def _base_dataset(
    rows: int,
    cols: int,
    samples_per_pixel: int,
    photometric_interpretation: str,
    bits_allocated: int = 8,
    modality: str = "OT",
) -> Dataset:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.Modality = modality
    ds.Rows = rows
    ds.Columns = cols
    ds.SamplesPerPixel = samples_per_pixel
    ds.PhotometricInterpretation = photometric_interpretation
    ds.PixelRepresentation = 0
    ds.BitsAllocated = bits_allocated
    ds.BitsStored = bits_allocated
    ds.HighBit = bits_allocated - 1
    if samples_per_pixel > 1:
        ds.PlanarConfiguration = 0
    return ds


def _make_grayscale_dataset(
    pixel_values,
    window_center=None,
    window_width=None,
    rescale_slope=None,
    rescale_intercept=None,
    modality: str = "CT",
) -> Dataset:
    arr = np.asarray(pixel_values, dtype=np.uint16)
    ds = _base_dataset(arr.shape[0], arr.shape[1], 1, "MONOCHROME2", bits_allocated=16, modality=modality)
    if window_center is not None:
        ds.WindowCenter = window_center
    if window_width is not None:
        ds.WindowWidth = window_width
    if rescale_slope is not None:
        ds.RescaleSlope = rescale_slope
    if rescale_intercept is not None:
        ds.RescaleIntercept = rescale_intercept
    ds.PixelData = arr.tobytes()
    return ds


def _make_rgb_dataset(pixel_array) -> Dataset:
    arr = np.asarray(pixel_array, dtype=np.uint8)
    ds = _base_dataset(arr.shape[0], arr.shape[1], 3, "RGB", bits_allocated=8)
    ds.PixelData = arr.tobytes()
    return ds


def _make_multiframe_color_dataset(n_frames: int = 2, rows: int = 2, cols: int = 2) -> Dataset:
    frames = [np.full((rows, cols, 3), fill_value=(i + 1) * 40, dtype=np.uint8) for i in range(n_frames)]
    arr = np.stack(frames, axis=0)
    ds = _base_dataset(rows, cols, 3, "RGB", bits_allocated=8)
    ds.NumberOfFrames = n_frames
    ds.PixelData = arr.tobytes()
    return ds


def _make_ybr_dataset(
    photometric_interpretation: str = "YBR_FULL",
    y_row=(50, 100, 150),
    cb: int = 130,
    cr: int = 126,
    rows: int = 1,
) -> Dataset:
    """Low-variance chroma so ``_detect_already_rgb`` does not trigger (see
    tests/test_dicom_color_ybr.py, which documents this heuristic in detail)."""
    y = np.tile(np.array(y_row, dtype=np.uint8), (rows, 1))
    cb_arr = np.full((rows, len(y_row)), cb, dtype=np.uint8)
    cr_arr = np.full((rows, len(y_row)), cr, dtype=np.uint8)
    arr = np.stack([y, cb_arr, cr_arr], axis=2)
    ds = _base_dataset(rows, len(y_row), 3, photometric_interpretation, bits_allocated=8)
    ds.PixelData = arr.tobytes()
    return ds


def _make_palette_color_dataset(
    indices=(0, 1, 2, 3),
    bits_allocated: int = 8,
    short_green: bool = False,
    red_first_value: int = 0,
    green_first_value: int = 0,
    blue_first_value: int = 0,
) -> Dataset:
    """
    PALETTE COLOR dataset with 256-entry Red/Green/Blue LUTs written at
    ``bits_allocated`` bits per entry, each with its own descriptor
    first_value (DICOM PS3.3 C.7.6.3.1.5).
    """
    indexed = np.array(indices, dtype=np.uint8).reshape(1, len(indices))
    ds = _base_dataset(1, len(indices), 1, "PALETTE COLOR", bits_allocated=8)

    lut_dtype = np.uint8 if bits_allocated == 8 else np.uint16
    scale = 1 if bits_allocated == 8 else 257
    num_entries = 256
    max_value = np.iinfo(lut_dtype).max
    ramp = np.array([min(i * scale, max_value) for i in range(num_entries)], dtype=lut_dtype)

    green_entries = 2 if short_green else num_entries
    green_ramp = ramp[:green_entries]

    first_values = {"Red": red_first_value, "Green": green_first_value, "Blue": blue_first_value}
    for prefix, lut in (("Red", ramp), ("Green", green_ramp), ("Blue", ramp)):
        setattr(
            ds, f"{prefix}PaletteColorLookupTableDescriptor",
            [len(lut), first_values[prefix], bits_allocated],
        )
        setattr(ds, f"{prefix}PaletteColorLookupTableData", lut.tobytes())

    ds.PixelData = indexed.tobytes()
    return ds


# ---------------------------------------------------------------------------
# Independent reference formulas (not calling the code under test).
# ---------------------------------------------------------------------------


def _bt601_expected(ybr: np.ndarray) -> np.ndarray:
    y = ybr[..., 0].astype(np.float32)
    cb = ybr[..., 1].astype(np.float32) - 128.0
    cr = ybr[..., 2].astype(np.float32) - 128.0
    r = y + 1.402 * cr
    g = y - 0.344136 * cb - 0.714136 * cr
    b = y + 1.772 * cb
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 1. pixel_array is None
# ---------------------------------------------------------------------------


def test_pixel_array_none_returns_none() -> None:
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    assert DICOMProcessor.dataset_to_image(ds) is None


# ---------------------------------------------------------------------------
# 2-4. Grayscale window/level resolution
# ---------------------------------------------------------------------------


def test_grayscale_explicit_window_level() -> None:
    pixel_values = [[0, 64, 128, 192, 255]]
    ds = _make_grayscale_dataset(pixel_values)
    image = DICOMProcessor.dataset_to_image(ds, window_center=128, window_width=256)
    assert image is not None
    assert image.mode == "L"
    expected = apply_window_level(np.array(pixel_values, dtype=np.uint16), 128, 256)
    assert np.array_equal(np.asarray(image), expected)


def test_grayscale_dataset_derived_apply_rescale_true() -> None:
    raw = [[864, 964, 1064, 1164, 1264]]
    ds = _make_grayscale_dataset(
        raw, window_center=40, window_width=400, rescale_slope=1.0, rescale_intercept=-1024.0
    )
    image = DICOMProcessor.dataset_to_image(ds, apply_rescale=True)
    assert image is not None
    assert image.mode == "L"
    result = np.asarray(image)
    expected = apply_window_level(np.array(raw, dtype=np.uint16), 40, 400, 1.0, -1024.0)
    assert np.array_equal(result, expected)
    # Sanity check on conversion direction: a real gradient, not flat/black.
    assert result.max() > result.min()


def test_grayscale_dataset_derived_apply_rescale_false_with_embedded_window() -> None:
    # window/level is converted to raw units (1064, 400) and rescale_slope/intercept
    # do NOT reach pixel processing, so window and pixels are in the same (raw) unit
    # space -- a real gradient, not the black image the pre-fix rescale leak produced.
    raw = [[864, 964, 1064, 1164, 1264]]
    ds = _make_grayscale_dataset(
        raw, window_center=40, window_width=400, rescale_slope=1.0, rescale_intercept=-1024.0
    )
    image = DICOMProcessor.dataset_to_image(ds, apply_rescale=False)
    assert image is not None
    assert image.mode == "L"
    result = np.asarray(image)
    expected = apply_window_level(np.array(raw, dtype=np.uint16), 1064, 400)
    assert np.array_equal(result, expected)
    assert result.max() > result.min()


def test_grayscale_dataset_derived_apply_rescale_false_no_embedded_window() -> None:
    # No WindowCenter/WindowWidth tags -> window/level falls back to pixel min/max
    # (already in raw units, is_rescaled=False). Confirms the fix does not depend on
    # is_rescaled being True: rescale_slope/intercept must not leak here either.
    raw = [[864, 964, 1064, 1164, 1264]]
    ds = _make_grayscale_dataset(raw, rescale_slope=1.0, rescale_intercept=-1024.0)
    image = DICOMProcessor.dataset_to_image(ds, apply_rescale=False)
    assert image is not None
    assert image.mode == "L"
    result = np.asarray(image)
    expected = apply_window_level(np.array(raw, dtype=np.uint16), 1064, 400)
    assert np.array_equal(result, expected)
    assert result.max() > result.min()


# ---------------------------------------------------------------------------
# 5. RGB single-frame and multi-frame (first-frame-only take)
# ---------------------------------------------------------------------------


def test_rgb_single_frame() -> None:
    arr = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
    ds = _make_rgb_dataset(arr)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"
    expected = apply_color_window_level_luminance(arr, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


def test_rgb_multiframe_takes_first_frame_only() -> None:
    ds = _make_multiframe_color_dataset(n_frames=2, rows=2, cols=2)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"
    first_frame = np.full((2, 2, 3), 40, dtype=np.uint8)
    expected = apply_color_window_level_luminance(first_frame, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


# ---------------------------------------------------------------------------
# 6. YBR end-to-end through dataset_to_image
# ---------------------------------------------------------------------------


def test_ybr_end_to_end_through_dataset_to_image(monkeypatch) -> None:
    import core.dicom_color as dc

    # Force the custom BT.601 path regardless of the installed pydicom version
    # (this repo pins pydicom<3, where the pydicom-native path is unavailable anyway).
    monkeypatch.setattr(dc, "pydicom_convert_available", False)

    y_row = (60, 120, 180, 150)  # 4 columns -> even PixelData length (3 would warn about padding)
    cb, cr = 132, 124
    ds = _make_ybr_dataset(photometric_interpretation="YBR_FULL", y_row=y_row, cb=cb, cr=cr, rows=1)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"

    ybr_arr = np.array([[[y, cb, cr] for y in y_row]], dtype=np.uint8)
    expected_rgb = _bt601_expected(ybr_arr)
    expected = apply_color_window_level_luminance(expected_rgb, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


# ---------------------------------------------------------------------------
# 7-9. PALETTE COLOR
# ---------------------------------------------------------------------------


def test_palette_color_8bit_valid() -> None:
    ds = _make_palette_color_dataset(indices=(0, 1, 2, 3), bits_allocated=8)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"

    ramp = np.array([min(i, 255) for i in range(256)], dtype=np.uint8)
    channel = ramp[[0, 1, 2, 3]]
    expected_rgb = np.stack([channel, channel, channel], axis=-1).reshape(1, 4, 3)
    expected = apply_color_window_level_luminance(expected_rgb, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


def test_palette_color_16bit_lut_correctly_decoded() -> None:
    # 16-bit LUT entry i == i*257 (0..65535). Once the descriptor is read
    # correctly (bits_allocated=16), the LUT is 256 uint16 entries and the
    # 16->8 normalization divides back down to the original ramp i.
    ds = _make_palette_color_dataset(indices=(0, 1, 2, 3), bits_allocated=16)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"

    ramp_u16 = np.array([min(i * 257, 65535) for i in range(256)], dtype=np.uint16)
    channel_u16 = ramp_u16[[0, 1, 2, 3]]
    channel = (channel_u16 / 65535.0 * 255.0).astype(np.uint8)
    assert list(channel) == [0, 1, 2, 3]
    expected_rgb = np.stack([channel, channel, channel], axis=-1).reshape(1, 4, 3)
    expected = apply_color_window_level_luminance(expected_rgb, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


def test_palette_color_per_channel_first_value() -> None:
    # Per DICOM PS3.3 C.7.6.3.1.5 each of Red/Green/Blue carries its own
    # first_value -- previously the code shared one (last-present-wins, so
    # Blue always won). Distinct shifts per channel must apply independently.
    ds = _make_palette_color_dataset(
        indices=(5, 5, 5, 5), bits_allocated=8,
        red_first_value=0, green_first_value=3, blue_first_value=5,
    )
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    assert image.mode == "RGB"

    ramp = np.array([min(i, 255) for i in range(256)], dtype=np.uint8)
    expected_rgb = np.zeros((1, 4, 3), dtype=np.uint8)
    expected_rgb[:, :, 0] = ramp[5 - 0]
    expected_rgb[:, :, 1] = ramp[5 - 3]
    expected_rgb[:, :, 2] = ramp[5 - 5]
    expected = apply_color_window_level_luminance(expected_rgb, 127.5, 255, None, None)
    assert np.array_equal(np.asarray(image), expected)


def test_palette_color_short_green_lut_falls_back_to_grayscale() -> None:
    ds = _make_palette_color_dataset(indices=(0, 1, 2, 3), bits_allocated=8, short_green=True)
    image = DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255)
    assert image is not None
    # A Green LUT shorter than Red raises IndexError inside the shared try/except,
    # which must be swallowed -- silent fallback to grayscale, no exception escapes.
    assert image.mode == "L"


# ---------------------------------------------------------------------------
# 10. Forced PIL failure
# ---------------------------------------------------------------------------


def test_pil_failure_returns_none_for_color(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ValueError("forced failure")

    monkeypatch.setattr(PILImage, "fromarray", _raise)
    ds = _make_rgb_dataset(np.zeros((2, 2, 3), dtype=np.uint8))
    assert DICOMProcessor.dataset_to_image(ds, window_center=127.5, window_width=255) is None


def test_pil_failure_returns_none_for_grayscale(monkeypatch) -> None:
    def _raise(*_args, **_kwargs):
        raise ValueError("forced failure")

    monkeypatch.setattr(PILImage, "fromarray", _raise)
    ds = _make_grayscale_dataset([[10, 20, 30, 40]])
    assert DICOMProcessor.dataset_to_image(ds, window_center=25, window_width=50) is None


# ---------------------------------------------------------------------------
# 11. Pure-function tests
# ---------------------------------------------------------------------------


def test_convert_window_level_units_all_combinations() -> None:
    # Not extracted from dataset -> passthrough regardless of apply_rescale/is_rescaled.
    assert convert_window_level_units(10, 20, False, True, True, 2.0, 5.0) == (10, 20)
    assert convert_window_level_units(10, 20, False, False, False, 2.0, 5.0) == (10, 20)

    # Extracted, apply_rescale=False, is_rescaled=True -> rescaled to raw.
    wc, ww = convert_window_level_units(40, 400, True, True, False, 2.0, -1024.0)
    assert (wc, ww) == ((40 - (-1024.0)) / 2.0, 400 / 2.0)

    # Extracted, apply_rescale=True, is_rescaled=False -> raw to rescaled.
    wc, ww = convert_window_level_units(40, 400, True, False, True, 2.0, -1024.0)
    assert (wc, ww) == (40 * 2.0 + (-1024.0), 400 * 2.0)

    # Extracted, apply_rescale matches is_rescaled -> no conversion needed.
    assert convert_window_level_units(40, 400, True, True, True, 2.0, -1024.0) == (40, 400)
    assert convert_window_level_units(40, 400, True, False, False, 2.0, -1024.0) == (40, 400)

    # Extracted but no rescale parameters available -> no conversion possible.
    assert convert_window_level_units(40, 400, True, True, False, None, None) == (40, 400)


def test_normalize_to_uint8_flat_array_wraps() -> None:
    flat = np.full((3, 3), 1000, dtype=np.float64)
    assert np.all(normalize_to_uint8(flat) == 232)


def test_normalize_channels_to_uint8_flat_channel_zeroed() -> None:
    flat = np.full((2, 2, 3), 1000, dtype=np.float64)
    assert np.all(normalize_channels_to_uint8(flat) == 0)


# ---------------------------------------------------------------------------
# 12. resolve_window_level_and_rescale -- the exposes_rescale trap, isolated
# ---------------------------------------------------------------------------


def test_resolve_window_level_and_rescale_shape_a_apply_rescale_false_no_leak() -> None:
    ds = _make_grayscale_dataset(
        [[864, 964, 1064, 1164, 1264]], rescale_slope=1.0, rescale_intercept=-1024.0
    )
    wc, ww, slope, intercept = resolve_window_level_and_rescale(
        ds, window_center=40, window_width=400, apply_rescale=False
    )
    assert (slope, intercept) == (None, None)
    assert (wc, ww) == (40, 400)  # explicit values pass through unchanged


def test_resolve_window_level_and_rescale_shape_b_apply_rescale_false_no_leak_is_rescaled() -> None:
    # Shape B, dataset carries WindowCenter/WindowWidth (is_rescaled=True branch).
    ds = _make_grayscale_dataset(
        [[864, 964, 1064, 1164, 1264]],
        window_center=40, window_width=400, rescale_slope=1.0, rescale_intercept=-1024.0,
    )
    wc, ww, slope, intercept = resolve_window_level_and_rescale(
        ds, window_center=None, window_width=None, apply_rescale=False
    )
    assert (slope, intercept) == (None, None)
    # Window/level converted from rescaled (HU) to raw units to match the unrescaled pixels.
    assert (wc, ww) == (1064, 400)


def test_resolve_window_level_and_rescale_shape_b_apply_rescale_false_no_leak_not_rescaled() -> None:
    # Shape B, no WindowCenter/WindowWidth tags (is_rescaled=False branch, falls back
    # to pixel min/max -- already in raw units).
    ds = _make_grayscale_dataset(
        [[864, 964, 1064, 1164, 1264]], rescale_slope=1.0, rescale_intercept=-1024.0
    )
    wc, ww, slope, intercept = resolve_window_level_and_rescale(
        ds, window_center=None, window_width=None, apply_rescale=False
    )
    assert (slope, intercept) == (None, None)
    assert (wc, ww) == (1064, 400)


# ---------------------------------------------------------------------------
# 13. Regression matrix over the two real call-site kwarg shapes
# ---------------------------------------------------------------------------


def test_regression_matrix_call_site_shapes() -> None:
    raw = [[864, 964, 1064, 1164, 1264]]
    ds = _make_grayscale_dataset(
        raw, window_center=40, window_width=400, rescale_slope=1.0, rescale_intercept=-1024.0
    )
    raw_arr = np.array(raw, dtype=np.uint16)

    # Shape A: explicit window/level (slice_display_manager.py, export_manager.py, ...).
    img_a_true = DICOMProcessor.dataset_to_image(ds, window_center=40, window_width=400, apply_rescale=True)
    img_a_false = DICOMProcessor.dataset_to_image(ds, window_center=40, window_width=400, apply_rescale=False)

    # Shape B: window/level from dataset (slice_display_manager.py, series_navigator.py).
    img_b_true = DICOMProcessor.dataset_to_image(ds, apply_rescale=True)
    img_b_false = DICOMProcessor.dataset_to_image(ds, apply_rescale=False)

    for img in (img_a_true, img_a_false, img_b_true, img_b_false):
        assert img is not None
        assert img.mode == "L"

    assert np.array_equal(
        np.asarray(img_a_true), apply_window_level(raw_arr, 40, 400, 1.0, -1024.0)
    )
    # Shape A + apply_rescale=False: explicit values assumed already raw (caller's
    # contract) -- no rescale reaches the pixels, renders all-white on this dataset.
    assert np.array_equal(np.asarray(img_a_false), apply_window_level(raw_arr, 40, 400, None, None))
    # Shape B + apply_rescale=True resolves to the same (wc, ww, slope, intercept) as shape A/true.
    assert np.array_equal(np.asarray(img_b_true), np.asarray(img_a_true))
    # Shape B + apply_rescale=False: window/level converted to raw units (1064, 400),
    # no rescale reaches the pixels -- a gradient, not the black image the pre-fix leak produced.
    assert np.array_equal(np.asarray(img_b_false), apply_window_level(raw_arr, 1064, 400))
    assert np.asarray(img_b_false).max() > np.asarray(img_b_false).min()
