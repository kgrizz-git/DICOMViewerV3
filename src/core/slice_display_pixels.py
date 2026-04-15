"""
Intensity projection pixel pipeline for slice display.

Builds a PIL image from a stack of DICOM slices (AIP/MIP/minIP) with optional
rescale and window/level.

Inputs: DICOMProcessor, projection parameters, study/series context, WL/rescale.
Outputs: PIL Image or None if projection cannot be formed.
Requirements: numpy, PIL, pydicom Dataset via study/series lists.
"""

from typing import Dict, List, Optional

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor


def create_slice_projection_pil_image(
    dicom_processor: DICOMProcessor,
    projection_type: str,
    projection_slice_count: int,
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    current_study_uid: str,
    current_series_uid: str,
    current_slice_index: int,
    window_center: Optional[float],
    window_width: Optional[float],
    use_rescaled_values: bool,
    rescale_slope: Optional[float],
    rescale_intercept: Optional[float],
) -> Optional[Image.Image]:
    """
    Create a projection image from multiple slices in the current series.

    Returns None if there are fewer than two slices in range or projection fails.
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

    projection_slices: List[Dataset] = []
    for i in range(start_slice, end_slice + 1):
        if 0 <= i < total_slices:
            projection_slices.append(series_datasets[i])

    if len(projection_slices) < 2:
        return None

    projection_array = None
    if projection_type == "aip":
        projection_array = dicom_processor.average_intensity_projection(
            projection_slices
        )
    elif projection_type == "mip":
        projection_array = dicom_processor.maximum_intensity_projection(
            projection_slices
        )
    elif projection_type == "minip":
        projection_array = dicom_processor.minimum_intensity_projection(
            projection_slices
        )

    if projection_array is None:
        return None

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

    try:
        if len(processed_array.shape) == 2:
            return Image.fromarray(processed_array, mode="L")
        if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
            return Image.fromarray(processed_array, mode="RGB")
        return Image.fromarray(processed_array)
    except Exception as e:
        print(f"Error converting projection array to PIL Image: {e}")
        return None


def compute_intensity_projection_raw_array(
    dicom_processor: DICOMProcessor,
    projection_type: str,
    projection_slice_count: int,
    series_datasets: List[Dataset],
    current_slice_index: int,
) -> Optional[np.ndarray]:
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
    projection_slices: List[Dataset] = []
    for i in range(start_slice, end_slice + 1):
        if 0 <= i < total_slices:
            projection_slices.append(series_datasets[i])
    if len(projection_slices) < 2:
        return None
    projection_array: Optional[np.ndarray] = None
    if projection_type == "aip":
        projection_array = dicom_processor.average_intensity_projection(projection_slices)
    elif projection_type == "mip":
        projection_array = dicom_processor.maximum_intensity_projection(projection_slices)
    elif projection_type == "minip":
        projection_array = dicom_processor.minimum_intensity_projection(projection_slices)
    return projection_array
