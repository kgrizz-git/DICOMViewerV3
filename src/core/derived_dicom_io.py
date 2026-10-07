"""Shared file-meta, series-numbering, and save helpers for derived DICOM.

Qt-free. Used by the projection export and the 3D Secondary Capture writer so
neither keeps its own copy. The file-meta and numbering steps mirror
``core.mpr_dicom_export``.

Requirements: pydicom.
"""

from __future__ import annotations

from typing import Any

import pydicom.uid
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.uid import ExplicitVRLittleEndian


def derived_series_number(source_series_number: Any, offset: int) -> int:
    """Return the derived SeriesNumber: source + *offset*, or offset + 1 when unusable."""
    try:
        base = int(source_series_number) if source_series_number not in (None, "") else 1
    except (TypeError, ValueError):
        return offset + 1
    return base + offset


def fresh_file_meta(ds: Dataset) -> None:
    """Rebuild file_meta for natively encoded, replaced pixel data."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = pydicom.uid.UID(str(getattr(ds, "SOPClassUID", "")))
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = pydicom.uid.PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = meta
    ds.is_implicit_VR = False
    ds.is_little_endian = True


def save_derived_dataset(ds: Dataset, output_path: str) -> None:
    """Save a derived dataset with a strict file_meta (one lacking it saves as-is)."""
    meta = getattr(ds, "file_meta", None)
    strict = meta is not None and "TransferSyntaxUID" in meta
    dcmwrite(output_path, ds, write_like_original=not strict)
