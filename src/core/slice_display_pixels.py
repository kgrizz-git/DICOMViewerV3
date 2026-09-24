"""
Intensity projection pixel pipeline for slice display.

Builds a PIL image from a stack of DICOM slices (AIP/MIP/minIP) with optional
rescale and window/level.

Inputs: DICOMProcessor, projection parameters, study/series context, WL/rescale.
Outputs: PIL Image or None if projection cannot be formed.
Requirements: numpy, PIL, pydicom Dataset via study/series lists.
"""
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from core.photometric_polarity import (
    apply_monochrome1_polarity,
    dataset_photometric_interpretation,
)
from utils.privacy.console import print_redacted


def _compute_projection(
    dicom_processor: DICOMProcessor,
    projection_type: str,
    projection_slices: list[Dataset],
) -> np.ndarray | None:
    """Dispatch to the AIP/MIP/MinIP reducer for *projection_type*, or None if unrecognized."""
    reducers = {
        "aip": dicom_processor.average_intensity_projection,
        "mip": dicom_processor.maximum_intensity_projection,
        "minip": dicom_processor.minimum_intensity_projection,
    }
    reducer = reducers.get(projection_type)
    return None if reducer is None else reducer(projection_slices)


def create_slice_projection_pil_image(
    dicom_processor: DICOMProcessor,
    projection_type: str,
    projection_slice_count: int,
    current_studies: dict[str, dict[str, list[Dataset]]],
    current_study_uid: str,
    current_series_uid: str,
    current_slice_index: int,
    window_center: float | None,
    window_width: float | None,
    use_rescaled_values: bool,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    *,
    photometric_interpretation: str | None = None,
) -> Image.Image | None:
    """
    Create a projection image from multiple slices in the current series.

    Returns None if there are fewer than two slices in range or projection fails.

    MONOCHROME1 polarity is applied last, to the finalized 8-bit array, so the pane matches the
    single-slice viewer (which gets it from ``render_grayscale_image``). When
    *photometric_interpretation* is omitted it is read from the **series-first** dataset, matching
    the rule MPR uses, rather than from the slab-start slice.
    """
    if not current_studies or not current_study_uid or not current_series_uid:
        return None

    if (
        current_study_uid not in current_studies
        or current_series_uid not in current_studies[current_study_uid]
    ):
        return None

    series_datasets = current_studies[current_study_uid][current_series_uid]
    total_slices = len(series_datasets)

    if total_slices < 2:
        return None

    start_slice = max(0, current_slice_index)
    end_slice = min(
        total_slices - 1, current_slice_index + projection_slice_count - 1
    )

    if end_slice - start_slice + 1 < 2:
        return None

    projection_slices: list[Dataset] = []
    for i in range(start_slice, end_slice + 1):
        if 0 <= i < total_slices:
            projection_slices.append(series_datasets[i])

    if len(projection_slices) < 2:
        return None

    projection_array = _compute_projection(dicom_processor, projection_type, projection_slices)

    if projection_array is None:
        return None

    if photometric_interpretation is None:
        photometric_interpretation = dataset_photometric_interpretation(series_datasets[0])

    if use_rescaled_values and rescale_slope is not None and rescale_intercept is not None:
        projection_array = (
            projection_array.astype(np.float32) * float(rescale_slope)
            + float(rescale_intercept)
        )

    if window_center is not None and window_width is not None:
        processed_array = dicom_processor.apply_window_level(
            projection_array, window_center, window_width
        )
    else:
        processed_array = projection_array.astype(np.float32)
        if processed_array.max() > processed_array.min():
            processed_array = (
                (processed_array - processed_array.min())
                / (processed_array.max() - processed_array.min())
                * 255.0
            )
        processed_array = np.clip(processed_array, 0, 255).astype(np.uint8)

    processed_array = apply_monochrome1_polarity(processed_array, photometric_interpretation)

    try:
        if len(processed_array.shape) == 2:
            return Image.fromarray(processed_array, mode="L")
        if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
            return Image.fromarray(processed_array, mode="RGB")
        return Image.fromarray(processed_array)
    except Exception as e:
        print_redacted(f"Error converting projection array to PIL Image: {e}")
        return None


def compute_intensity_projection_raw_array(
    dicom_processor: DICOMProcessor,
    projection_type: str,
    projection_slice_count: int,
    series_datasets: list[Dataset],
    current_slice_index: int,
) -> np.ndarray | None:
    """
    Build a **raw** (pre–window/level) 2D numpy projection over a slice range, matching
    viewer / ROI projection slice bounds. Returns ``None`` if projection cannot be formed.

    Used by the histogram when **Use intensity projection pixels** is enabled so the
    distribution matches the combined-slice intensity path (AIP / MIP / MinIP).
    """
    total_slices = len(series_datasets)
    if total_slices < 2:
        return None
    start_slice = max(0, current_slice_index)
    end_slice = min(
        total_slices - 1, current_slice_index + projection_slice_count - 1
    )
    if end_slice - start_slice + 1 < 2:
        return None
    projection_slices: list[Dataset] = []
    for i in range(start_slice, end_slice + 1):
        if 0 <= i < total_slices:
            projection_slices.append(series_datasets[i])
    if len(projection_slices) < 2:
        return None
    return _compute_projection(dicom_processor, projection_type, projection_slices)
