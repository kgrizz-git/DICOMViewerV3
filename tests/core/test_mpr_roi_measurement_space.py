"""MPR ROI statistics stay in measurement space when a pane selects a display LUT.

The plan's silent-failure guard: selecting a color LUT (or toggling invert) must
not change a single reported ROI statistic. The display LUT reaches the
thumbnail render kwargs; the measurement accessor stays raw/rescaled stored
values — no windowing, no polarity inversion, no user invert, no LUT.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

import core.mpr_navigator_thumbnail as mpr_navigator_thumbnail
from core.lut_catalog import colormap_lut, linear_lut
from core.mpr_session_types import MprDisplayState, MprViewMetadata


def _roi_stats(array: np.ndarray) -> tuple[float, float, float, float]:
    """Mean, std, min, max — the ROI statistics panel's core numbers."""
    return (
        float(np.mean(array)),
        float(np.std(array)),
        float(np.min(array)),
        float(np.max(array)),
    )


def _make_app(lut, inverted: bool) -> tuple[SimpleNamespace, np.ndarray, np.ndarray]:
    stored = np.linspace(-1000.0, 3000.0, 12 * 12, dtype=np.float32).reshape(12, 12)

    def apply_rescale(raw: np.ndarray) -> np.ndarray:
        return raw * 2.0 - 1024.0

    result = SimpleNamespace(
        n_slices=5,
        slices=[stored] * 5,
        photometric_interpretation="MONOCHROME1",
        apply_rescale=MagicMock(side_effect=apply_rescale),
    )
    view_state = SimpleNamespace(
        use_rescaled_values=True,
        current_series_identifier="series-1",
        series_defaults={"series-1": {"current_lut": lut, "image_inverted": inverted}},
        image_viewer=SimpleNamespace(image_inverted=inverted),
    )
    app = SimpleNamespace(
        subwindow_data={
            0: {
                "is_mpr": True,
                "mpr_result": result,
                "mpr_slice_index": 0,
                "current_study_uid": "st",
                "current_series_uid": "sr",
            }
        },
        subwindow_managers={0: {"view_state_manager": view_state}},
        focused_subwindow_index=0,
    )
    return app, stored, apply_rescale(stored)


def _tile_for_pane_view(lut, inverted: bool) -> dict:
    """The navigator spec produced for a view carrying *lut* / *inverted* display state."""
    shown: dict = {}

    class _Navigator:
        def mpr_tile_stamps(self) -> dict:
            return {}

        def reconcile_mpr_thumbnails(self, incoming: dict) -> bool:
            shown.update(incoming)
            return True

    meta = MprViewMetadata(
        view_id=1, session_id=1, creation_seq=1, pane_index=0, orientation="Axial",
        source_study_uid="st", source_series_uid="sr", n_slices=5, slice_index=0,
        photometric_interpretation="MONOCHROME1",
    )
    controller = SimpleNamespace(
        drag_origin="AbCdEfGhIjKlMnOpQr_-12",
        all_view_ids=lambda: [1],
        get_view_metadata=lambda _v: meta,
        get_view_display_state=lambda _v: MprDisplayState(lut=lut, inverted=inverted),
        get_view_thumbnail_pixels=lambda _v, _r=None: np.zeros((4, 4), dtype=np.float32),
    )
    mpr_navigator_thumbnail.sync_mpr_navigator_tiles(
        SimpleNamespace(series_navigator=_Navigator(), _mpr_controller=controller)
    )
    return shown[1]


def test_color_lut_reaches_the_display_but_not_the_measurement_array() -> None:
    hot = colormap_lut("hot")
    app, stored, rescaled = _make_app(hot, inverted=True)

    tile = _tile_for_pane_view(hot, inverted=True)
    assert tile["lut"] is hot
    assert tile["image_inverted"] is True

    measurement = mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(app, 0)
    assert measurement is not None
    assert measurement.dtype == np.float32
    # Exact rescaled stored values: no 8-bit quantization, no inversion, no LUT.
    np.testing.assert_array_equal(measurement, rescaled)
    assert not np.array_equal(measurement, np.clip(measurement, 0, 255))


def test_roi_statistics_are_identical_with_and_without_a_color_lut() -> None:
    plain_app, _stored_plain, plain_rescaled = _make_app(linear_lut(), inverted=False)
    lut_app, _stored_lut, lut_rescaled = _make_app(colormap_lut("hot"), inverted=True)

    plain = mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(plain_app, 0)
    luted = mpr_navigator_thumbnail.get_subwindow_mpr_pixel_array(lut_app, 0)
    assert plain is not None and luted is not None
    np.testing.assert_array_equal(plain, plain_rescaled)
    np.testing.assert_array_equal(luted, lut_rescaled)

    assert _roi_stats(plain) == _roi_stats(luted)
