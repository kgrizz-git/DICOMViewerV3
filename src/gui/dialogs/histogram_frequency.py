"""
Pure helpers for series-wide histogram frequency and pixel-range computation.

Extracted from ``HistogramDialog._compute_series_global_frequency_max`` so the
dialog method stays thin orchestration. Inputs are datasets, rescale flags, and
optional callbacks; outputs are scalar max-frequency and global pixel bounds.

Requirements:
    - numpy
    - pydicom (Dataset type hints at call sites)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from core.multiframe_handler import (
    get_frame_count,
    get_frame_pixel_array,
    is_multiframe,
)

SeriesDatasetsFn = Callable[[], list[Dataset] | None]
StudiesFn = Callable[[], dict[str, Any] | None]
SeriesUidFn = Callable[[], str | None]
RescaleParamsFn = Callable[[], tuple[float | None, float | None, Any]]


def resolve_series_datasets(
    get_series_datasets: SeriesDatasetsFn | None,
    get_all_studies: StudiesFn | None,
    get_series_study_uid: SeriesUidFn | None,
    get_series_uid: SeriesUidFn | None,
) -> list[Dataset] | None:
    """Resolve datasets for the current series from callbacks."""
    datasets: list[Dataset] | None = None
    if get_series_datasets is not None:
        datasets = get_series_datasets() or None

    if (not datasets) and get_all_studies and get_series_study_uid and get_series_uid:
        studies = get_all_studies() or {}
        study_uid = get_series_study_uid()
        series_uid = get_series_uid()
        if study_uid and series_uid:
            series_dict = studies.get(study_uid, {})
            datasets = series_dict.get(series_uid)

    return datasets or None


def parse_rescale_slope_intercept(
    use_rescaled: bool,
    get_rescale_params: RescaleParamsFn | None,
) -> tuple[float, float]:
    """Return rescale slope and intercept (defaults 1.0 / 0.0) for a series."""
    rescale_slope = 1.0
    rescale_intercept = 0.0
    if use_rescaled and get_rescale_params:
        try:
            slope, intercept, _ = get_rescale_params()
            if slope is not None:
                rescale_slope = float(slope)
            if intercept is not None:
                rescale_intercept = float(intercept)
        except Exception:
            pass
    return rescale_slope, rescale_intercept


def accumulate_pixels_histogram_stats(
    pixels: np.ndarray,
    max_freq: float,
    global_x_min: float | None,
    global_x_max: float | None,
) -> tuple[float, float | None, float | None]:
    """
    Update max histogram frequency and global pixel min/max from one pixel array.

    ``pixels`` must already be float32 and rescaled when requested by the caller.
    Empty arrays are skipped without changing accumulators.
    """
    if pixels.size == 0:
        return max_freq, global_x_min, global_x_max

    hist, _ = np.histogram(pixels.flatten(), bins=256)
    if hist.size > 0:
        max_freq = max(max_freq, float(hist.max()))

    frame_min = float(pixels.min())
    frame_max = float(pixels.max())
    global_x_min = frame_min if global_x_min is None else min(global_x_min, frame_min)
    global_x_max = frame_max if global_x_max is None else max(global_x_max, frame_max)
    return max_freq, global_x_min, global_x_max


def _prepare_rescaled_pixels(
    frame_array: np.ndarray,
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
) -> np.ndarray:
    pixels = frame_array.astype(np.float32)
    if use_rescaled:
        pixels = pixels * rescale_slope + rescale_intercept
    return pixels


def _accumulate_frame_array_stats(
    frame_array: np.ndarray,
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
    max_freq: float,
    global_x_min: float | None,
    global_x_max: float | None,
) -> tuple[float, float | None, float | None]:
    pixels = _prepare_rescaled_pixels(
        frame_array, use_rescaled, rescale_slope, rescale_intercept
    )
    return accumulate_pixels_histogram_stats(
        pixels, max_freq, global_x_min, global_x_max
    )


def _accumulate_multiframe_dataset_stats(
    dataset: Dataset,
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
    max_freq: float,
    global_x_min: float | None,
    global_x_max: float | None,
) -> tuple[float, float | None, float | None]:
    num_frames = get_frame_count(dataset)
    for frame_index in range(max(0, num_frames)):
        frame_array = get_frame_pixel_array(dataset, frame_index)
        if frame_array is None:
            continue
        max_freq, global_x_min, global_x_max = _accumulate_frame_array_stats(
            frame_array,
            use_rescaled,
            rescale_slope,
            rescale_intercept,
            max_freq,
            global_x_min,
            global_x_max,
        )
    return max_freq, global_x_min, global_x_max


def _accumulate_standard_dataset_stats(
    dataset: Dataset,
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
    max_freq: float,
    global_x_min: float | None,
    global_x_max: float | None,
) -> tuple[float, float | None, float | None]:
    pixel_array = DICOMProcessor.get_pixel_array(dataset)
    if pixel_array is None:
        return max_freq, global_x_min, global_x_max

    frames = pixel_array if pixel_array.ndim == 3 else [pixel_array]
    for frame_array in frames:
        max_freq, global_x_min, global_x_max = _accumulate_frame_array_stats(
            frame_array,
            use_rescaled,
            rescale_slope,
            rescale_intercept,
            max_freq,
            global_x_min,
            global_x_max,
        )
    return max_freq, global_x_min, global_x_max


def _accumulate_dataset_stats(
    dataset: Dataset,
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
    max_freq: float,
    global_x_min: float | None,
    global_x_max: float | None,
) -> tuple[float, float | None, float | None]:
    if is_multiframe(dataset):
        return _accumulate_multiframe_dataset_stats(
            dataset,
            use_rescaled,
            rescale_slope,
            rescale_intercept,
            max_freq,
            global_x_min,
            global_x_max,
        )
    return _accumulate_standard_dataset_stats(
        dataset,
        use_rescaled,
        rescale_slope,
        rescale_intercept,
        max_freq,
        global_x_min,
        global_x_max,
    )


def compute_series_global_frequency_stats(
    datasets: list[Dataset],
    use_rescaled: bool,
    rescale_slope: float,
    rescale_intercept: float,
) -> tuple[float | None, float | None, float | None]:
    """
    Compute series-wide max histogram frequency and global pixel range.

    Returns ``(frequency_max, x_min, x_max)`` with ``None`` for unset values.
    """
    max_freq = 0.0
    global_x_min: float | None = None
    global_x_max: float | None = None

    for dataset in datasets:
        if dataset is None:
            continue
        try:
            max_freq, global_x_min, global_x_max = _accumulate_dataset_stats(
                dataset,
                use_rescaled,
                rescale_slope,
                rescale_intercept,
                max_freq,
                global_x_min,
                global_x_max,
            )
        except Exception:
            continue

    frequency_max = max_freq if max_freq > 0 else None
    x_min = None
    x_max = None
    if (
        global_x_min is not None
        and global_x_max is not None
        and global_x_max > global_x_min
    ):
        x_min = global_x_min
        x_max = global_x_max
    return frequency_max, x_min, x_max
