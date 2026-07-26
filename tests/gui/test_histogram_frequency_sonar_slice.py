"""
Characterization tests for histogram series-frequency helpers (Sonar S3776 slice).

Covers pure helpers extracted from ``HistogramDialog._compute_series_global_frequency_max``
into ``gui.dialogs.histogram_frequency``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gui.dialogs.histogram_frequency import (
    accumulate_pixels_histogram_stats,
    compute_series_global_frequency_stats,
    parse_rescale_slope_intercept,
    resolve_series_datasets,
)


def test_resolve_series_datasets_prefers_series_callback() -> None:
    dataset = MagicMock()
    studies = {"study-1": {"series-1": [dataset]}}

    result = resolve_series_datasets(
        lambda: [dataset],
        lambda: studies,
        lambda: "study-1",
        lambda: "series-1",
    )
    assert result == [dataset]


def test_resolve_series_datasets_falls_back_to_studies_map() -> None:
    dataset = MagicMock()
    studies = {"study-1": {"series-1": [dataset]}}

    result = resolve_series_datasets(
        lambda: None,
        lambda: studies,
        lambda: "study-1",
        lambda: "series-1",
    )
    assert result == [dataset]


def test_resolve_series_datasets_returns_none_when_unresolved() -> None:
    assert resolve_series_datasets(None, None, None, None) is None
    assert (
        resolve_series_datasets(
            lambda: [],
            lambda: {},
            lambda: None,
            lambda: "series-1",
        )
        is None
    )


def test_parse_rescale_slope_intercept_defaults_and_overrides() -> None:
    assert parse_rescale_slope_intercept(False, None) == (1.0, 0.0)
    assert parse_rescale_slope_intercept(
        True,
        lambda: (2.0, -100.0, "HU"),
    ) == (2.0, -100.0)
    assert parse_rescale_slope_intercept(
        True,
        lambda: (None, None, None),
    ) == (1.0, 0.0)
    assert parse_rescale_slope_intercept(True, lambda: (_ for _ in ()).throw(RuntimeError("bad"))) == (
        1.0,
        0.0,
    )


def test_accumulate_pixels_histogram_stats_skips_empty_and_tracks_range() -> None:
    max_freq, x_min, x_max = accumulate_pixels_histogram_stats(
        np.array([], dtype=np.float32),
        0.0,
        None,
        None,
    )
    assert max_freq == 0.0
    assert x_min is None
    assert x_max is None

    pixels = np.array([[0.0, 1.0], [1.0, 1.0]], dtype=np.float32)
    max_freq, x_min, x_max = accumulate_pixels_histogram_stats(
        pixels,
        0.0,
        None,
        None,
    )
    assert max_freq == pytest.approx(3.0)
    assert x_min == pytest.approx(0.0)
    assert x_max == pytest.approx(1.0)

    max_freq, x_min, x_max = accumulate_pixels_histogram_stats(
        pixels,
        max_freq,
        x_min,
        x_max,
    )
    assert max_freq == pytest.approx(3.0)
    assert x_min == pytest.approx(0.0)
    assert x_max == pytest.approx(1.0)


def test_compute_series_global_frequency_stats_standard_2d_and_3d() -> None:
    slice_a = np.array([[10, 20], [30, 40]], dtype=np.int16)
    slice_b = np.array([[50, 60], [70, 80]], dtype=np.int16)
    volume = np.stack([slice_a, slice_b])

    dataset_2d = MagicMock()
    dataset_3d = MagicMock()

    with (
        patch(
            "gui.dialogs.histogram_frequency.is_multiframe",
            side_effect=[False, False],
        ),
        patch(
            "gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array",
            side_effect=[slice_a, volume],
        ),
    ):
        freq_max, x_min, x_max = compute_series_global_frequency_stats(
            [dataset_2d, dataset_3d],
            use_rescaled=False,
            rescale_slope=1.0,
            rescale_intercept=0.0,
        )

    assert freq_max == pytest.approx(1.0)
    assert x_min == pytest.approx(10.0)
    assert x_max == pytest.approx(80.0)


def test_compute_series_global_frequency_stats_applies_rescale_and_skips_errors() -> None:
    good = np.array([[0, 100]], dtype=np.int16)
    dataset_ok = MagicMock()
    dataset_bad = MagicMock()

    with (
        patch("gui.dialogs.histogram_frequency.is_multiframe", return_value=False),
        patch(
            "gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array",
            side_effect=[RuntimeError("boom"), good],
        ),
    ):
        freq_max, x_min, x_max = compute_series_global_frequency_stats(
            [dataset_bad, dataset_ok],
            use_rescaled=True,
            rescale_slope=2.0,
            rescale_intercept=10.0,
        )

    assert freq_max == pytest.approx(1.0)
    assert x_min == pytest.approx(10.0)
    assert x_max == pytest.approx(210.0)


def test_compute_series_global_frequency_stats_multiframe_path() -> None:
    frame = np.array([[5, 5], [5, 5]], dtype=np.int16)
    dataset = MagicMock()

    with (
        patch("gui.dialogs.histogram_frequency.is_multiframe", return_value=True),
        patch("gui.dialogs.histogram_frequency.get_frame_count", return_value=2),
        patch(
            "gui.dialogs.histogram_frequency.get_frame_pixel_array",
            side_effect=[frame, None],
        ),
    ):
        freq_max, x_min, x_max = compute_series_global_frequency_stats(
            [dataset],
            use_rescaled=False,
            rescale_slope=1.0,
            rescale_intercept=0.0,
        )

    assert freq_max == pytest.approx(4.0)
    assert x_min is None
    assert x_max is None


def test_compute_series_global_frequency_stats_flat_range_returns_none_bounds() -> None:
    flat = np.full((2, 2), 7, dtype=np.int16)
    dataset = MagicMock()

    with (
        patch("gui.dialogs.histogram_frequency.is_multiframe", return_value=False),
        patch(
            "gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array",
            return_value=flat,
        ),
    ):
        freq_max, x_min, x_max = compute_series_global_frequency_stats(
            [dataset],
            use_rescaled=False,
            rescale_slope=1.0,
            rescale_intercept=0.0,
        )

    assert freq_max == pytest.approx(4.0)
    assert x_min is None
    assert x_max is None
