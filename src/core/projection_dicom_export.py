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
import pydicom.datadict
import pydicom.uid
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.uid import SecondaryCaptureImageStorage

from core.derived_dicom_io import (
    derived_series_number,
    fresh_file_meta,
    save_derived_dataset,
)
from core.dicom_processor import DICOMProcessor
from core.dicom_rescale import get_rescale_parameters
from core.dicom_rescale_encoding import float_to_int16_with_rescale
from core.multiframe_handler import is_multiframe
from utils.dicom_utils import (
    get_image_orientation,
    get_image_position,
    get_slice_thickness,
)
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)

# Distinct from the MPR export offset (+500) so the derived series stay apart.
PROJECTION_SERIES_NUMBER_OFFSET = 600
_PIXEL_DATA_TAG = 0x7FE00010

_REDUCERS = {"aip": np.mean, "mip": np.max, "minip": np.min}
# Pixel-description tags that no longer describe replaced pixel data.
_STALE_PIXEL_KEYWORDS = (
    "PixelPaddingValue",
    "PixelPaddingRangeLimit",
    "SmallestImagePixelValue",
    "LargestImagePixelValue",
    "ModalityLUTSequence",
    "VOILUTSequence",
    "LossyImageCompression",
    "LossyImageCompressionRatio",
    "LossyImageCompressionMethod",
)
_PROJECTION_NAMES = {
    "aip": "Average Intensity Projection (AIP)",
    "mip": "Maximum Intensity Projection (MIP)",
    "minip": "Minimum Intensity Projection (MinIP)",
}
_IMAGE_TYPE_VALUES = {"mip": "MIP", "aip": "AIP", "minip": "MINIP"}


def projection_series_number(source_series_number: Any) -> int:
    """Return the derived SeriesNumber: source + 600, or 601 when unusable."""
    return derived_series_number(source_series_number, PROJECTION_SERIES_NUMBER_OFFSET)


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
    """Write pixels as explicit OB/OW and sync the image-pixel attributes."""
    bits = pixels.dtype.itemsize * 8
    vr = "OB" if bits == 8 else "OW"
    ds[_PIXEL_DATA_TAG] = DataElement(_PIXEL_DATA_TAG, vr, pixels.tobytes())
    for keyword in _STALE_PIXEL_KEYWORDS:
        if keyword in ds:
            del ds[keyword]
    ds.Rows = pixels.shape[0]
    ds.Columns = pixels.shape[1]
    ds.BitsAllocated = bits
    ds.BitsStored = bits
    ds.HighBit = bits - 1
    ds.PixelRepresentation = 0 if np.issubdtype(pixels.dtype, np.unsignedinteger) else 1


def _sync_single_slice_file_meta(ds: Dataset) -> None:
    """Keep the source transfer syntax; only sync the media-storage instance UID."""
    meta = getattr(ds, "file_meta", None)
    if meta is None or "TransferSyntaxUID" not in meta:
        # No source syntax to keep; the retained PixelData is native.
        fresh_file_meta(ds)
        return
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID


def _project(projection_type: str, slab: list[Dataset], *, rescaled: bool) -> np.ndarray | None:
    """Reduce the slab in float64, over stored or rescaled (physical) values."""
    reducer = _REDUCERS.get(projection_type)
    if reducer is None:
        return None
    planes = []
    for s in slab:
        arr = DICOMProcessor.get_pixel_array(s)
        if arr is None or arr.ndim != 2:
            return None
        plane = arr.astype(np.float64)
        if rescaled:
            slope, intercept = _slice_rescale(s)
            plane = plane * slope + intercept
        planes.append(plane)
    return reducer(np.stack(planes, axis=0), axis=0)


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
    sop_class = getattr(src, "SOPClassUID", None)
    if not uid or not sop_class:
        return None  # both are Type 1 in a reference item
    item = Dataset()
    item.ReferencedSOPClassUID = sop_class
    item.ReferencedSOPInstanceUID = uid
    if _is_frame_wrapper(src):
        item.ReferencedFrameNumber = int(src._frame_index) + 1
    return item


def _unique_instance_refs(items: list[Dataset]) -> list[Dataset]:
    """Return one class/instance reference per distinct source instance."""
    seen: set[str] = set()
    refs: list[Dataset] = []
    for item in items:
        uid = str(item.ReferencedSOPInstanceUID)
        if uid in seen or not str(item.ReferencedSOPClassUID or ""):
            continue
        seen.add(uid)
        ref = Dataset()
        ref.ReferencedSOPClassUID = item.ReferencedSOPClassUID
        ref.ReferencedSOPInstanceUID = uid
        refs.append(ref)
    return refs


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
    instance_refs = _unique_instance_refs(items)
    if source_series_uid and instance_refs:
        ref = Dataset()
        ref.SeriesInstanceUID = source_series_uid
        ref.ReferencedInstanceSequence = Sequence(instance_refs)
        ds.ReferencedSeriesSequence = Sequence([ref])


def _set_projection_pixels(
    ds: Dataset, source: Dataset, projection_type: str, slab: list[Dataset]
) -> bool:
    """Compute and store the projection.

    The stored-value path needs a uniform, positive-slope rescale; otherwise the
    slab is reduced in rescaled space and re-encoded.
    """
    if slab_rescale_is_uniform(slab) and _slice_rescale(slab[0])[0] > 0:
        array = _project(projection_type, slab, rescaled=False)
        return array is not None and _replace_pixels(ds, source, array)
    physical = _project(projection_type, slab, rescaled=True)
    if physical is None:
        return False
    _replace_pixels_rescaled(ds, physical)
    return True


def projection_series_description(source_description: str, projection_type: str) -> str:
    """Return the derived SeriesDescription ("<source> - MIP"), capped at 64 chars."""
    label = projection_type.upper()
    desc = source_description
    if desc and not (desc == label or desc.endswith(f" - {label}")):
        desc = f"{desc} - {label}"
    elif not desc:
        desc = label
    return desc[:64]


def projection_folder_dataset(source: Dataset, projection_type: str) -> Dataset:
    """Return the tags that name a derived projection series folder.

    Matches what :func:`create_projection_dataset` writes, without building pixels.
    """
    view = Dataset()
    for keyword in ("PatientID", "StudyDate", "StudyDescription"):
        if keyword in source:
            setattr(view, keyword, getattr(source, keyword))
    view.SeriesNumber = projection_series_number(getattr(source, "SeriesNumber", None))
    view.SeriesDescription = projection_series_description(
        str(getattr(source, "SeriesDescription", "") or ""), projection_type
    )
    return view


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

    # Series-level: every file in the derived series carries the same description,
    # including a slab clipped to one slice at the series end.
    ds.SeriesDescription = projection_series_description(
        str(getattr(ds, "SeriesDescription", "") or ""), projection_type
    )
    if is_projection:
        ds.ImageType = ["DERIVED", "SECONDARY", _IMAGE_TYPE_VALUES.get(projection_type, "PROJECTION")]
    else:
        ds.ImageType = ["DERIVED", "SECONDARY"]
    if is_projection:
        kind = _PROJECTION_NAMES.get(projection_type, "Projection").split(" (")[0]
        return f"{kind} of {n_slices} slices, instances {start + 1}-{end + 1}"
    return f"Derived from instance {start + 1}"


_MULTIFRAME_DROP_KEYWORDS = (
    "NumberOfFrames",
    "PerFrameFunctionalGroupsSequence",
    "SharedFunctionalGroupsSequence",
    "SourceImageSequence",
    "ReferencedSeriesSequence",
    "DimensionIndexSequence",
    "DimensionOrganizationSequence",
    "DimensionOrganizationType",
    "ConcatenationUID",
    "ConcatenationFrameOffsetNumber",
    "InConcatenationNumber",
    "InConcatenationTotalNumber",
    "SOPInstanceUIDOfConcatenationSource",
    "FrameIncrementPointer",
    "RepresentativeFrameNumber",
    "FrameTime",
    "FrameTimeVector",
    "FrameDelay",
)


def _is_frame_wrapper(dataset: Dataset) -> bool:
    return hasattr(dataset, "_frame_index") and hasattr(dataset, "_original_dataset")


def _plain_frame_dataset(frame: Dataset) -> Dataset:
    """Copy a frame wrapper's visible metadata into a plain single-frame Dataset."""
    drop = {pydicom.datadict.tag_for_keyword(k) for k in _MULTIFRAME_DROP_KEYWORDS}
    drop.discard(None)
    drop.add(_PIXEL_DATA_TAG)
    ds = Dataset()
    for tag in list(frame.keys()):
        if tag not in drop:
            ds[tag] = copy.deepcopy(frame[tag])
    # The enhanced IOD does not describe a flattened frame; Modality is kept.
    ds.SOPClassUID = SecondaryCaptureImageStorage
    return ds


def _frame_pixels(frame: Dataset) -> np.ndarray | None:
    """Return the 2-D integer pixel array of one frame, or None if unusable."""
    arr = DICOMProcessor.get_pixel_array(frame)
    if arr is None or arr.ndim != 2 or not np.issubdtype(arr.dtype, np.integer):
        return None
    return arr


def _start_derived_dataset(dataset: Dataset) -> Dataset | None:
    """Return the working copy; None if a multi-frame source can't be flattened."""
    if _is_frame_wrapper(dataset):
        return _plain_frame_dataset(dataset)
    if is_multiframe(dataset):
        return None  # un-split multi-frame instance: pixel geometry is not 2-D
    return copy.deepcopy(dataset)


def _slab_step_extent(slab: list[Dataset]) -> tuple[np.ndarray, float] | None:
    """Return (slab center IPP, geometric extent in mm), or None without positions."""
    first, last = get_image_position(slab[0]), get_image_position(slab[-1])
    if first is None or last is None:
        return None
    delta = np.asarray(last, dtype=float) - np.asarray(first, dtype=float)
    orient = get_image_orientation(slab[0])
    if orient is not None:
        normal = np.cross(np.asarray(orient[0], dtype=float), np.asarray(orient[1], dtype=float))
        span = abs(float(np.dot(delta, normal)))
    else:
        span = float(np.linalg.norm(delta))
    one = get_slice_thickness(slab[0])
    if one is None:
        one = span / (len(slab) - 1)
    center = (np.asarray(first, dtype=float) + np.asarray(last, dtype=float)) / 2.0
    return center, span + float(one)


def _apply_slab_geometry(ds: Dataset, slab: list[Dataset]) -> str:
    """Set slab-center IPP and geometric thickness; return a description suffix."""
    if "SliceLocation" in ds:
        del ds.SliceLocation
    geometry = _slab_step_extent(slab)
    if geometry is None:
        thicknesses = [t for t in (get_slice_thickness(s) for s in slab) if t is not None]
        if thicknesses:
            ds.SliceThickness = sum(thicknesses)
        return ""
    center, extent = geometry
    ds.ImagePositionPatient = [round(float(v), 6) for v in center]
    ds.SliceThickness = round(extent, 6)
    return "; slab center at (" + ", ".join(f"{v:.2f}" for v in center) + ") mm"


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

        ds = _start_derived_dataset(dataset)
        if ds is None:
            return None
        is_projection = len(slab) >= 2
        ds.SOPInstanceUID = pydicom.uid.generate_uid()
        suffix = ""
        if is_projection:
            if not _set_projection_pixels(ds, dataset, projection_type, slab):
                return None
            fresh_file_meta(ds)
            suffix = _apply_slab_geometry(ds, slab)
        elif _is_frame_wrapper(dataset):
            pixels = _frame_pixels(dataset)
            if pixels is None:
                return None
            _apply_pixel_layout(ds, pixels)
            fresh_file_meta(ds)
        else:
            _sync_single_slice_file_meta(ds)

        derivation = _set_descriptions(ds, projection_type, len(slab), start, end, is_projection)
        _set_derivation_metadata(
            ds, slab, str(getattr(dataset, "SeriesInstanceUID", "") or ""), derivation + suffix
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
    save_derived_dataset(ds, output_path)
