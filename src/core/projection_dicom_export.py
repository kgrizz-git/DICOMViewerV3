"""
Projection DICOM export — build and save derived AIP/MIP/MinIP datasets.

Qt-free. Builds a derived single-frame dataset from a slab of slices, gives it
a fresh ``file_meta`` when the pixels are replaced, and saves it so the file is
readable regardless of the source transfer syntax. The file-meta and series
numbering steps mirror ``core.mpr_dicom_export``.

Requirements: numpy, pydicom, ``core.dicom_processor``, ``utils.dicom_utils``.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import numpy as np
import pydicom.uid
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian

from core.dicom_processor import DICOMProcessor
from core.dicom_rescale import get_rescale_parameters
from core.dicom_rescale_encoding import float_to_int16_with_rescale
from utils.dicom_utils import get_slice_thickness
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)

# Distinct from the MPR export offset (+500) so the derived series stay apart.
PROJECTION_SERIES_NUMBER_OFFSET = 600
_PIXEL_DATA_TAG = 0x7FE00010

_PROJECTION_FUNCS = {
    "aip": "average_intensity_projection",
    "mip": "maximum_intensity_projection",
    "minip": "minimum_intensity_projection",
}
_PROJECTION_NAMES = {
    "aip": "Average Intensity Projection (AIP)",
    "mip": "Maximum Intensity Projection (MIP)",
    "minip": "Minimum Intensity Projection (MinIP)",
}
_IMAGE_TYPE_VALUES = {"mip": "MIP", "aip": "AIP", "minip": "MINIP"}


def projection_series_number(source_series_number: Any) -> int:
    """Return the derived SeriesNumber: source + 600, or 601 when unusable."""
    try:
        base = int(source_series_number) if source_series_number not in (None, "") else 1
    except (TypeError, ValueError):
        return PROJECTION_SERIES_NUMBER_OFFSET + 1
    return base + PROJECTION_SERIES_NUMBER_OFFSET


def _target_dtype(original_dtype: np.dtype, bits_stored: int) -> type:
    """Pick the integer dtype used to store the projection."""
    if not np.issubdtype(original_dtype, np.integer):
        return np.uint16  # unusual float source: default to uint16
    unsigned = np.issubdtype(original_dtype, np.unsignedinteger)
    if bits_stored <= 8:
        return np.uint8 if unsigned else np.int8
    if bits_stored <= 16:
        return np.uint16 if unsigned else np.int16
    return np.uint32 if unsigned else np.int32


def _to_integer_pixels(projection_array: np.ndarray, target_dtype: type) -> np.ndarray:
    """Round (not truncate), clip to the dtype range, and cast."""
    info = np.iinfo(target_dtype)
    return np.clip(np.rint(projection_array), info.min, info.max).astype(target_dtype)


def _apply_pixel_layout(ds: Dataset, pixels: np.ndarray) -> None:
    """Write pixels as explicit OW and sync the image-pixel attributes."""
    bits = pixels.dtype.itemsize * 8
    ds[_PIXEL_DATA_TAG] = DataElement(_PIXEL_DATA_TAG, "OW", pixels.tobytes())
    ds.Rows = pixels.shape[0]
    ds.Columns = pixels.shape[1]
    ds.BitsAllocated = bits
    ds.BitsStored = bits
    ds.HighBit = bits - 1
    ds.PixelRepresentation = 0 if np.issubdtype(pixels.dtype, np.unsignedinteger) else 1


def _fresh_file_meta(ds: Dataset) -> None:
    """Rebuild file_meta for natively encoded, replaced pixel data."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = pydicom.uid.UID(str(getattr(ds, "SOPClassUID", "")))
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = meta
    ds.is_implicit_VR = False
    ds.is_little_endian = True


def _sync_single_slice_file_meta(ds: Dataset) -> None:
    """Keep the source transfer syntax; only sync the media-storage instance UID."""
    meta = getattr(ds, "file_meta", None)
    if meta is None or "TransferSyntaxUID" not in meta:
        # No source syntax to keep; the retained PixelData is native.
        _fresh_file_meta(ds)
        return
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID


def _compute_projection(projection_type: str, slices: list[Dataset]) -> np.ndarray | None:
    func_name = _PROJECTION_FUNCS.get(projection_type)
    if func_name is None:
        return None
    return getattr(DICOMProcessor, func_name)(slices)


def _replace_pixels(ds: Dataset, source: Dataset, projection_array: np.ndarray) -> bool:
    """Replace pixels with the rounded projection. Return False if dtype is unknown."""
    original = DICOMProcessor.get_pixel_array(source)
    if original is None:
        return False
    target = _target_dtype(original.dtype, int(getattr(source, "BitsStored", 16)))
    _apply_pixel_layout(ds, _to_integer_pixels(projection_array, target))
    return True


def _slice_rescale(ds: Dataset) -> tuple[float, float]:
    """Return (slope, intercept) for a slice, defaulting to identity."""
    slope, intercept, _ = get_rescale_parameters(ds)
    return (1.0 if slope is None else float(slope), 0.0 if intercept is None else float(intercept))


def slab_rescale_is_uniform(slab: list[Dataset]) -> bool:
    """True when every slab slice shares one RescaleSlope/RescaleIntercept."""
    first = _slice_rescale(slab[0])
    return all(_slice_rescale(s) == first for s in slab[1:])


def _project_rescaled(projection_type: str, slab: list[Dataset]) -> np.ndarray | None:
    """Reduce the slab in rescaled (physical) space."""
    reducers = {"aip": np.mean, "mip": np.max, "minip": np.min}
    reducer = reducers.get(projection_type)
    if reducer is None:
        return None
    planes = []
    for s in slab:
        arr = DICOMProcessor.get_pixel_array(s)
        if arr is None:
            return None
        slope, intercept = _slice_rescale(s)
        planes.append(arr.astype(np.float64) * slope + intercept)
    return reducer(np.stack(planes, axis=0), axis=0)


def _replace_pixels_rescaled(ds: Dataset, physical: np.ndarray) -> None:
    """Re-encode a rescaled projection as int16 with computed slope/intercept."""
    stored, slope, intercept = float_to_int16_with_rescale(
        physical, float(np.min(physical)), float(np.max(physical))
    )
    _apply_pixel_layout(ds, stored)
    ds.RescaleSlope = slope
    ds.RescaleIntercept = intercept


def _sop_ref_item(src: Dataset) -> Dataset | None:
    uid = getattr(src, "SOPInstanceUID", None)
    if not uid:
        return None
    item = Dataset()
    item.ReferencedSOPClassUID = getattr(src, "SOPClassUID", "")
    item.ReferencedSOPInstanceUID = uid
    return item


def _set_derivation_metadata(
    ds: Dataset, slab: list[Dataset], source_series_uid: str, description: str
) -> None:
    """Add DerivationDescription, SourceImageSequence, ReferencedSeriesSequence."""
    ds.DerivationDescription = description[:1024]
    items = [i for i in (_sop_ref_item(s) for s in slab) if i is not None]
    if "SourceImageSequence" in ds:
        del ds.SourceImageSequence
    if items:
        ds.SourceImageSequence = Sequence(items)
    if "ReferencedSeriesSequence" in ds:
        del ds.ReferencedSeriesSequence
    if source_series_uid:
        ref = Dataset()
        ref.SeriesInstanceUID = source_series_uid
        ds.ReferencedSeriesSequence = Sequence([ref])


def _set_projection_pixels(
    ds: Dataset, source: Dataset, projection_type: str, slab: list[Dataset]
) -> bool:
    """Compute and store the projection; rescaled path only for mixed-rescale slabs."""
    if slab_rescale_is_uniform(slab):
        array = _compute_projection(projection_type, slab)
        return array is not None and _replace_pixels(ds, source, array)
    physical = _project_rescaled(projection_type, slab)
    if physical is None:
        return False
    _replace_pixels_rescaled(ds, physical)
    return True


def _set_descriptions(
    ds: Dataset, projection_type: str, n_slices: int, start: int, end: int, is_projection: bool
) -> str:
    """Set ImageComments, SeriesDescription, and ImageType; return the derivation text."""
    if is_projection:
        name = _PROJECTION_NAMES.get(projection_type, "Projection")
        info = f"{name} - {n_slices} slices (instances {start + 1} to {end + 1})"
    else:
        info = f"Derived from instance {start + 1} (part of projection export)"
    existing = getattr(ds, "ImageComments", "")
    ds.ImageComments = f"{existing}; {info}" if existing else info

    label = projection_type.upper()
    desc = getattr(ds, "SeriesDescription", "")
    ds.SeriesDescription = f"{desc} - {label}" if desc else label
    ds.ImageType = ["DERIVED", "SECONDARY", _IMAGE_TYPE_VALUES.get(projection_type, "PROJECTION")]
    if is_projection:
        kind = _PROJECTION_NAMES.get(projection_type, "Projection").split(" (")[0]
        return f"{kind} of {n_slices} slices, instances {start + 1}-{end + 1}"
    return f"Derived from instance {start + 1}"


def _set_combined_thickness(ds: Dataset, slices: list[Dataset]) -> None:
    thicknesses = [t for t in (get_slice_thickness(s) for s in slices) if t is not None]
    if thicknesses:
        ds.SliceThickness = sum(thicknesses)


def _slab_range(total: int, slice_index: int, count: int) -> tuple[int, int]:
    return max(0, slice_index), min(total - 1, slice_index + count - 1)


def create_projection_dataset(
    dataset: Dataset,
    studies: dict[str, dict[str, list[Dataset]]],
    study_uid: str,
    series_uid: str,
    slice_index: int,
    projection_type: str,
    projection_slice_count: int,
    use_rescaled_values: bool,
    new_series_uid: str | None = None,
    instance_number: int | None = None,
) -> Dataset | None:
    """
    Create a derived projection dataset for DICOM export.

    Args:
        dataset: Current dataset (metadata source; deep-copied).
        studies: Dictionary of studies.
        study_uid: Study UID of the source series.
        series_uid: Source series UID (key into ``studies``).
        slice_index: First slice of the slab.
        projection_type: "aip", "mip", or "minip".
        projection_slice_count: Slab size in slices.
        use_rescaled_values: Retained for API compatibility.
        new_series_uid: SeriesInstanceUID shared by the export run; a fresh
            UID is generated when omitted.
        instance_number: InstanceNumber within the new series.

    Returns:
        Derived Dataset, or None on failure.
    """
    _ = use_rescaled_values
    try:
        series = studies.get(study_uid, {}).get(series_uid)
        if not series:
            return None
        start, end = _slab_range(len(series), slice_index, projection_slice_count)
        slab = series[start:end + 1]
        if not slab:
            return None

        ds = copy.deepcopy(dataset)
        is_projection = len(slab) >= 2
        ds.SOPInstanceUID = pydicom.uid.generate_uid()
        if is_projection:
            if not _set_projection_pixels(ds, dataset, projection_type, slab):
                return None
            _fresh_file_meta(ds)
            _set_combined_thickness(ds, slab)
        else:
            _sync_single_slice_file_meta(ds)

        derivation = _set_descriptions(ds, projection_type, len(slab), start, end, is_projection)
        _set_derivation_metadata(
            ds, slab, str(getattr(dataset, "SeriesInstanceUID", "") or ""), derivation
        )
        if "SpacingBetweenSlices" in ds:
            del ds.SpacingBetweenSlices
        ds.SeriesInstanceUID = new_series_uid or pydicom.uid.generate_uid()
        ds.SeriesNumber = projection_series_number(getattr(dataset, "SeriesNumber", None))
        if instance_number is not None:
            ds.InstanceNumber = instance_number
        return ds
    except Exception as e:
        print_redacted(f"Error creating projection dataset: {e}")
        _logger.debug("%s", sanitized_format_exc())
        return None


def save_projection_dataset(ds: Dataset, output_path: str) -> None:
    """Save a derived dataset with a strict file_meta (source fallbacks lacking one save as-is)."""
    strict = "TransferSyntaxUID" in getattr(ds, "file_meta", {})
    dcmwrite(output_path, ds, write_like_original=not strict)
