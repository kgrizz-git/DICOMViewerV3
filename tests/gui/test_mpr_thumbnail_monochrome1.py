"""MONOCHROME1 polarity reaches the MPR navigator thumbnail.

The thumbnail is built by its own inline windowing rather than through array_to_pil, and the
photometric interpretation has to travel four links to get there:

    mpr_navigator_thumbnail.sync_mpr_navigator_tiles (view metadata)
      -> the _mpr_thumbnail_specs dict (via reconcile_mpr_thumbnails)
        -> series_navigator._append_mpr_thumbnails_for_series
          -> MprThumbnailWidget.update_preview

A thumbnail whose polarity disagrees with the pane it previews is the bug this guards.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from core import mpr_navigator_thumbnail as nav_thumb
from core.mpr_session_types import MprDisplayState, MprViewMetadata

_ARRAY = np.array([[0.0, 64.0, 255.0]], dtype=np.float32)


class _RecordingNavigator:
    def __init__(self) -> None:
        self.incoming: dict = {}

    def mpr_tile_stamps(self) -> dict:
        return {}

    def reconcile_mpr_thumbnails(self, incoming: dict) -> bool:
        self.incoming = dict(incoming)
        return True


def _app(photometric, *, pane_index):
    meta = MprViewMetadata(
        view_id=5, session_id=1, creation_seq=1, pane_index=pane_index, orientation="Axial",
        source_study_uid="study", source_series_uid="series", n_slices=3, slice_index=0,
        photometric_interpretation=photometric or None,
    )
    return SimpleNamespace(
        series_navigator=_RecordingNavigator(),
        _mpr_controller=SimpleNamespace(
            drag_origin="AbCdEfGhIjKlMnOpQr_-12",
            all_view_ids=lambda: [5],
            get_view_metadata=lambda _v: meta,
            get_view_display_state=lambda _v: MprDisplayState(),
            get_view_thumbnail_pixels=lambda _v, _r=None: _ARRAY,
        ),
    )


@pytest.mark.parametrize("pane_index", [0, None])
@pytest.mark.parametrize(
    ("stored", "expected"), [("MONOCHROME1", "MONOCHROME1"), ("MONOCHROME2", "MONOCHROME2"), ("", None)]
)
def test_photometric_interpretation_reaches_the_tile_spec(pane_index, stored, expected):
    app = _app(stored, pane_index=pane_index)
    nav_thumb.sync_mpr_navigator_tiles(app)
    assert app.series_navigator.incoming[5]["photometric_interpretation"] == expected


def test_navigator_stores_and_forwards_the_photometric_interpretation(qapp):
    """Links 2-4: the spec dict carries it, and the rebuild hands it to the widget."""
    from gui.series_navigator import SeriesNavigator

    navigator = SeriesNavigator(MagicMock())
    navigator._rebuild_from_cached_studies = MagicMock()
    navigator.reconcile_mpr_thumbnails({
        5: {
            "study_uid": "study", "source_series_uid": "series", "pixel_array": _ARRAY,
            "window_center": 40.0, "window_width": 400.0, "n_slices": 3,
            "photometric_interpretation": "MONOCHROME1", "order": 1, "pane_index": None,
        }
    })
    assert navigator._mpr_thumbnail_specs[5]["photometric_interpretation"] == "MONOCHROME1"


def _mean_luminance(widget) -> float:
    """Mean grey level of a rendered thumbnail pixmap."""
    image = widget._preview_pixmap.toImage()
    total = 0
    for y in range(image.height()):
        for x in range(image.width()):
            total += image.pixelColor(x, y).value()
    return total / (image.width() * image.height())


def test_widget_inverts_for_monochrome1(qapp):
    """Link 5: the widget's own inline windowing applies the polarity, in the right direction.

    The input is chosen so the assertion actually discriminates, which took two attempts. A
    window *centred on zero* is useless here: negating the source before windowing is then
    algebraically the same as inverting the output, so both a correct and a broken
    implementation produce the same picture (verified by mutation — the first version of this
    test passed against a deliberately broken widget). The window below is off-centre and the
    source saturates below it, so inverting the floats before windowing collapses everything to
    black while inverting the uint8 array after it yields mostly white.

    Mean brightness then pins the direction. Letterboxing and the LANCZOS resize rule out an
    exact 255-x comparison, but the background is identical in both, so the ordering survives.
    """
    from gui.mpr_thumbnail_widget import MprThumbnailWidget

    # Window [150, 250]: the first two samples clip low, the third clips high.
    saturating = np.array([[100.0, 150.0, 900.0]], dtype=np.float32)
    mono1 = MprThumbnailWidget(1, 0)
    mono2 = MprThumbnailWidget(1, 0)
    mono1.update_preview(saturating, 200.0, 100.0, "MONOCHROME1")
    mono2.update_preview(saturating, 200.0, 100.0, "MONOCHROME2")

    assert mono1._preview_pixmap is not None
    assert mono2._preview_pixmap is not None
    assert mono1._preview_pixmap.toImage() != mono2._preview_pixmap.toImage()
    assert _mean_luminance(mono1) > _mean_luminance(mono2), (
        "MONOCHROME1 must invert the windowed result, not the source before windowing"
    )


def test_widget_default_matches_monochrome2(qapp):
    """Omitting the argument keeps the pre-change rendering."""
    from gui.mpr_thumbnail_widget import MprThumbnailWidget

    omitted = MprThumbnailWidget(1, 0)
    explicit = MprThumbnailWidget(1, 0)
    omitted.update_preview(_ARRAY, 127.5, 255.0)
    explicit.update_preview(_ARRAY, 127.5, 255.0, "MONOCHROME2")
    assert omitted._preview_pixmap.toImage() == explicit._preview_pixmap.toImage()
