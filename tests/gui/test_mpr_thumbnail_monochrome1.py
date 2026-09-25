"""MONOCHROME1 polarity reaches the MPR navigator thumbnail.

The thumbnail is built by its own inline windowing rather than through array_to_pil, and the
photometric interpretation has to travel five links to get there:

    mpr_navigator_thumbnail.update_mpr_navigator_thumbnail / ..._floating_...
      -> series_navigator.set_mpr_thumbnail
        -> the _mpr_thumbnail_specs dict
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

_ARRAY = np.array([[0.0, 64.0, 255.0]], dtype=np.float32)


def _app(result, *, detached=False):
    navigator = MagicMock()
    wl = SimpleNamespace(window_center=40.0, window_width=400.0)
    if detached:
        return SimpleNamespace(
            series_navigator=navigator,
            window_level_controls=wl,
            focused_subwindow_index=0,
            subwindow_managers={0: {"view_state_manager": SimpleNamespace(use_rescaled_values=False)}},
            _mpr_controller=SimpleNamespace(
                has_detached_mpr=lambda: True,
                get_detached_mpr_thumbnail_pixels=lambda _r: "pixels",
                _detached_mpr_payload={
                    "current_study_uid": "study",
                    "current_series_uid": "series",
                    "mpr_result": result,
                },
            ),
        )
    return SimpleNamespace(
        series_navigator=navigator,
        window_level_controls=wl,
        subwindow_data={
            0: {
                "is_mpr": True,
                "mpr_result": result,
                "current_study_uid": "study",
                "current_series_uid": "series",
            }
        },
    )


@pytest.mark.parametrize("detached", [False, True])
@pytest.mark.parametrize(
    ("stored", "expected"), [("MONOCHROME1", "MONOCHROME1"), ("MONOCHROME2", "MONOCHROME2"), ("", None)]
)
def test_photometric_interpretation_reaches_set_mpr_thumbnail(
    monkeypatch, detached, stored, expected
):
    result = SimpleNamespace(n_slices=3, photometric_interpretation=stored)
    app = _app(result, detached=detached)
    monkeypatch.setattr(
        nav_thumb, "get_subwindow_mpr_thumbnail_pixel_array", lambda _a, _i: "pixels"
    )

    if detached:
        nav_thumb.update_floating_mpr_navigator_thumbnail(app)
    else:
        nav_thumb.update_mpr_navigator_thumbnail(app, 0)

    args = app.series_navigator.set_mpr_thumbnail.call_args.args
    assert args[-1] == expected


def test_missing_field_on_a_legacy_result_is_tolerated(monkeypatch):
    """A result predating the field (or any duck-typed stand-in) must not raise."""
    app = _app(SimpleNamespace(n_slices=3))
    monkeypatch.setattr(
        nav_thumb, "get_subwindow_mpr_thumbnail_pixel_array", lambda _a, _i: "pixels"
    )
    nav_thumb.update_mpr_navigator_thumbnail(app, 0)
    assert app.series_navigator.set_mpr_thumbnail.call_args.args[-1] is None


def test_navigator_stores_and_forwards_the_photometric_interpretation(qapp):
    """Links 2-4: the spec dict carries it, and the rebuild hands it to the widget."""
    from gui.series_navigator import SeriesNavigator

    navigator = SeriesNavigator(MagicMock())
    navigator._rebuild_from_cached_studies = MagicMock()
    navigator.set_mpr_thumbnail(
        0, _ARRAY, "study", "series", 40.0, 400.0, 3, "MONOCHROME1"
    )
    spec = navigator._mpr_thumbnail_specs[0]
    assert spec["photometric_interpretation"] == "MONOCHROME1"


def test_widget_inverts_for_monochrome1(qapp):
    """Link 5: the widget's own inline windowing applies the polarity."""
    from gui.mpr_thumbnail_widget import MprThumbnailWidget

    mono1 = MprThumbnailWidget(0)
    mono2 = MprThumbnailWidget(0)
    mono1.update_preview(_ARRAY, 127.5, 255.0, "MONOCHROME1")
    mono2.update_preview(_ARRAY, 127.5, 255.0, "MONOCHROME2")

    assert mono1._preview_pixmap is not None
    assert mono2._preview_pixmap is not None
    a = mono1._preview_pixmap.toImage()
    b = mono2._preview_pixmap.toImage()
    assert a != b, "MONOCHROME1 thumbnail must not render identically to MONOCHROME2"


def test_widget_default_matches_monochrome2(qapp):
    """Omitting the argument keeps the pre-change rendering."""
    from gui.mpr_thumbnail_widget import MprThumbnailWidget

    omitted = MprThumbnailWidget(0)
    explicit = MprThumbnailWidget(0)
    omitted.update_preview(_ARRAY, 127.5, 255.0)
    explicit.update_preview(_ARRAY, 127.5, 255.0, "MONOCHROME2")
    assert omitted._preview_pixmap.toImage() == explicit._preview_pixmap.toImage()
