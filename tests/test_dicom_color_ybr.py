"""
Unit tests for ``core.dicom_color.convert_ybr_to_rgb`` and its helpers.

Expected outputs are computed independently from the documented formulas
(BT.601 for YBR_FULL/YBR_FULL_422/YBR_ICT, the DICOM Supplement 61 RCT
formula for YBR_RCT) rather than by re-calling the function under test, so
these tests catch regressions in the conversion math itself, not just the
control flow.

Test inputs use near-constant chroma channels (low variance relative to Y)
so the "does this already look like RGB?" heuristic in ``_detect_already_rgb``
does not trigger and the real conversion path runs — that heuristic has its
own dedicated tests further down.

Note: this project pins ``pydicom<3`` (see requirements.txt), so
``pydicom_convert_available`` is normally False. The pydicom-path tests here
monkeypatch ``pydicom_convert_available`` / ``convert_color_space`` directly
so they exercise that branch regardless of which pydicom is installed.
"""

from __future__ import annotations

import numpy as np

from core import dicom_color as dc


def _bt601_expected(ybr: np.ndarray) -> np.ndarray:
    """Independently compute the BT.601 YBR_FULL/YBR_FULL_422/YBR_ICT formula."""
    y = ybr[..., 0].astype(np.float32)
    cb = ybr[..., 1].astype(np.float32) - 128.0
    cr = ybr[..., 2].astype(np.float32) - 128.0
    r = y + 1.402 * cr
    g = y - 0.344136 * cb - 0.714136 * cr
    b = y + 1.772 * cb
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def _rct_expected(ybr: np.ndarray) -> np.ndarray:
    """Independently compute the DICOM Supplement 61 YBR_RCT formula."""
    y = ybr[..., 0].astype(np.float32)
    cb = ybr[..., 1].astype(np.float32)
    cr = ybr[..., 2].astype(np.float32)
    g = y - np.floor((cr + cb) / 4.0)
    r = cr + g
    b = cb + g
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def _low_variance_ybr(y_row: list[int], cb: int, cr: int, rows: int = 3) -> np.ndarray:
    """(rows, len(y_row), 3) uint8 array with near-constant chroma (bypasses the already-RGB heuristic)."""
    y = np.tile(np.array(y_row, dtype=np.uint8), (rows, 1))
    cb_arr = np.full((rows, len(y_row)), cb, dtype=np.uint8)
    cr_arr = np.full((rows, len(y_row)), cr, dtype=np.uint8)
    return np.stack([y, cb_arr, cr_arr], axis=2)


def test_no_photometric_interpretation_returns_original() -> None:
    arr = np.full((3, 3, 3), 77, dtype=np.uint8)
    out = dc.convert_ybr_to_rgb(arr, photometric_interpretation=None)
    assert np.array_equal(out, arr)


def test_ybr_rct_custom_conversion() -> None:
    ybr = _low_variance_ybr([50, 100, 150, 200], cb=130, cr=126, rows=4)
    out = dc.convert_ybr_to_rgb(ybr, photometric_interpretation="YBR_RCT")
    assert np.array_equal(out, _rct_expected(ybr))


def test_ybr_full_custom_fallback(monkeypatch) -> None:
    ybr = _low_variance_ybr([60, 120, 180], cb=132, cr=124)
    monkeypatch.setattr(dc, "pydicom_convert_available", False)
    out = dc.convert_ybr_to_rgb(ybr, photometric_interpretation="YBR_FULL")
    assert np.array_equal(out, _bt601_expected(ybr))


def test_ybr_full_uses_pydicom_when_available(monkeypatch) -> None:
    ybr = _low_variance_ybr([50, 100, 150], cb=130, cr=126)
    stub_output = np.full_like(ybr, 42)
    monkeypatch.setattr(dc, "pydicom_convert_available", True)
    monkeypatch.setattr(dc, "convert_color_space", lambda arr, src, dst: stub_output)
    out = dc.convert_ybr_to_rgb(ybr, photometric_interpretation="YBR_FULL")
    assert np.array_equal(out, stub_output)


def test_ybr_full_pydicom_failure_falls_back_to_custom(monkeypatch) -> None:
    ybr = _low_variance_ybr([50, 100, 150], cb=130, cr=126)

    def _raise(arr, src, dst):
        raise RuntimeError("simulated pydicom failure")

    monkeypatch.setattr(dc, "pydicom_convert_available", True)
    monkeypatch.setattr(dc, "convert_color_space", _raise)
    out = dc.convert_ybr_to_rgb(ybr, photometric_interpretation="YBR_FULL")
    assert np.array_equal(out, _bt601_expected(ybr))


def test_multiframe_matches_per_frame_conversion(monkeypatch) -> None:
    frame1 = _low_variance_ybr([50, 100, 150], cb=130, cr=126)
    frame2 = _low_variance_ybr([80, 120, 200], cb=129, cr=127)
    multi = np.stack([frame1, frame2], axis=0)

    monkeypatch.setattr(dc, "pydicom_convert_available", False)
    out_multi = dc.convert_ybr_to_rgb(multi, photometric_interpretation="YBR_FULL")
    out_f1 = dc.convert_ybr_to_rgb(frame1, photometric_interpretation="YBR_FULL")
    out_f2 = dc.convert_ybr_to_rgb(frame2, photometric_interpretation="YBR_FULL")

    assert out_multi.shape == (2, 3, 3, 3)
    assert np.array_equal(out_multi[0], out_f1)
    assert np.array_equal(out_multi[1], out_f2)


def test_unsupported_shape_falls_back_to_original() -> None:
    bad = np.zeros((5, 5), dtype=np.uint8)  # 2D: no channel dimension
    out = dc.convert_ybr_to_rgb(bad, photometric_interpretation="YBR_FULL")
    assert np.array_equal(out, bad)


def test_detect_already_rgb_true_for_rgb_like_data() -> None:
    """Data whose chroma channels vary as much as Y, and whose test-conversion
    produces unreasonable RGB stats, should be flagged as already-RGB (a
    JPEG2000/YBR_RCT decoder having converted it without updating the tag)."""
    y = np.array(
        [
            [128, 130, 145, 157, 102, 108],
            [149, 156, 114, 118, 152, 125],
            [116, 149, 115, 124, 138, 132],
            [105, 101, 151, 145, 150, 132],
            [149, 119, 127, 147, 107, 118],
            [107, 127, 158, 108, 122, 124],
        ],
        dtype=np.uint8,
    )
    cb = np.array(
        [
            [54, 12, 30, 15, 1, 45],
            [3, 16, 29, 29, 7, 58],
            [44, 57, 5, 43, 17, 32],
            [55, 16, 43, 9, 19, 58],
            [25, 30, 17, 6, 25, 37],
            [27, 46, 21, 36, 46, 55],
        ],
        dtype=np.uint8,
    )
    cr = np.array(
        [
            [223, 202, 240, 229, 248, 225],
            [220, 203, 225, 235, 243, 247],
            [212, 233, 245, 214, 219, 247],
            [232, 228, 237, 228, 254, 242],
            [203, 208, 230, 245, 203, 238],
            [242, 244, 248, 210, 231, 244],
        ],
        dtype=np.uint8,
    )
    rgb_like = np.stack([y, cb, cr], axis=2)

    assert dc._detect_already_rgb(rgb_like, "YBR_FULL", None) is True

    # convert_ybr_to_rgb should then return the array unchanged (no conversion applied).
    out = dc.convert_ybr_to_rgb(rgb_like, photometric_interpretation="YBR_FULL")
    assert np.array_equal(out, rgb_like)


def test_detect_already_rgb_false_for_low_variance_chroma() -> None:
    ybr = _low_variance_ybr([50, 100, 150], cb=130, cr=126)
    assert dc._detect_already_rgb(ybr, "YBR_FULL", None) is False
