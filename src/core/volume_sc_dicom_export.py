"""3D render to a single-frame RGB Secondary Capture DICOM instance.

Qt-free: the GUI converts its ``QImage`` to an RGB uint8 array first. Patient,
general-study, and general-equipment attributes come from the template (the
first dataset of the series the 3D view was built from). Geometry and pixel
attributes of the source are never copied, because a rendered view has no
patient-space geometry.

Requirements: numpy, pydicom, ``core.derived_dicom_io``, ``utils.deep_anonymizer``.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

import numpy as np
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
from utils.deep_anonymizer import DeepAnonymizerOptions, DeepDICOMAnonymizer

# Distinct from MPR (+500) and projection (+600).
VOLUME_SC_SERIES_NUMBER_OFFSET = 700
_PIXEL_DATA_TAG = 0x7FE00010
_SERIES_SUFFIX = " - 3D"

_COPIED_KEYWORDS = (
    # Patient module
    "PatientName", "PatientID", "IssuerOfPatientID", "PatientBirthDate",
    "PatientSex", "PatientAge", "PatientWeight", "PatientSize",
    "OtherPatientIDs", "OtherPatientNames", "EthnicGroup", "PatientComments",
    # General study module
    "StudyInstanceUID", "StudyDate", "StudyTime", "ReferringPhysicianName",
    "StudyID", "AccessionNumber", "StudyDescription",
    # General equipment module
    "Manufacturer", "InstitutionName", "InstitutionAddress", "StationName",
    "InstitutionalDepartmentName", "ManufacturerModelName", "DeviceSerialNumber",
    "SoftwareVersions",
    # Encoding of the copied text
    "SpecificCharacterSet",
)


def qimage_rgb_array(width: int, height: int, data: bytes, bytes_per_line: int) -> np.ndarray:
    """Return an (H, W, 3) uint8 array from RGB888 rows that may be padded."""
    rows = np.frombuffer(data, dtype=np.uint8, count=height * bytes_per_line)
    return np.ascontiguousarray(rows.reshape(height, bytes_per_line)[:, : width * 3]).reshape(
        height, width, 3
    )


def volume_sc_series_description(source_description: str) -> str:
    """Return "<source> - 3D", capped at 64 characters (suffix kept)."""
    if not source_description:
        return "3D"
    return source_description[: 64 - len(_SERIES_SUFFIX)] + _SERIES_SUFFIX


def build_volume_sc_dataset(
    rgb: np.ndarray, template: Dataset, *, preset_name: str = "", blend_mode: str = ""
) -> Dataset:
    """Build the SC dataset from an (H, W, 3) uint8 array and a source template."""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError("RGB uint8 array of shape (rows, columns, 3) required")
    ds = Dataset()
    for keyword in _COPIED_KEYWORDS:
        value = getattr(template, keyword, None)
        if value is not None:
            setattr(ds, keyword, copy.deepcopy(value))
    now = datetime.now()
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.Modality = str(getattr(template, "Modality", "") or "OT")
    ds.SeriesNumber = derived_series_number(
        getattr(template, "SeriesNumber", None), VOLUME_SC_SERIES_NUMBER_OFFSET
    )
    ds.InstanceNumber = 1
    ds.SeriesDescription = volume_sc_series_description(
        str(getattr(template, "SeriesDescription", "") or "")
    )
    ds.ImageType = ["DERIVED", "SECONDARY"]
    ds.ConversionType = "WSD"
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    parts = ["3D volume rendering"]
    if preset_name:
        parts.append(f"preset: {preset_name}")
    if blend_mode:
        parts.append(f"blend: {blend_mode}")
    ds.DerivationDescription = ", ".join(parts)[:1024]
    source_series_uid = str(getattr(template, "SeriesInstanceUID", "") or "")
    if source_series_uid:
        ref = Dataset()
        ref.SeriesInstanceUID = source_series_uid
        ds.ReferencedSeriesSequence = Sequence([ref])
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    ds.PlanarConfiguration = 0
    ds.Rows = int(rgb.shape[0])
    ds.Columns = int(rgb.shape[1])
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    data = np.ascontiguousarray(rgb).tobytes()
    if len(data) % 2:
        data += b"\x00"
    ds[_PIXEL_DATA_TAG] = DataElement(_PIXEL_DATA_TAG, "OB", data)
    fresh_file_meta(ds)
    return ds


def deidentify_dataset(
    ds: Dataset, options: DeepAnonymizerOptions | None = None
) -> Dataset:
    """Deep-anonymize *ds* (standard-share defaults).

    The anonymizer syncs File Meta to the remapped UIDs and records the
    de-identifying application, so File Meta is not rebuilt afterwards.
    """
    return DeepDICOMAnonymizer(options or DeepAnonymizerOptions()).anonymize_batch([ds])[0]


def save_volume_sc(ds: Dataset, output_path: str) -> None:
    """Write the SC instance with a strict file_meta."""
    save_derived_dataset(ds, output_path)


def write_volume_sc(
    rgb: np.ndarray,
    template: Dataset,
    output_path: str,
    *,
    preset_name: str = "",
    blend_mode: str = "",
    deidentify: bool = True,
    options: Any = None,
) -> Dataset:
    """Build, optionally de-identify, and save; return the written dataset."""
    ds = build_volume_sc_dataset(rgb, template, preset_name=preset_name, blend_mode=blend_mode)
    if deidentify:
        ds = deidentify_dataset(ds, options)
    save_volume_sc(ds, output_path)
    return ds
