"""Shared file-meta, series-numbering, and save helpers for derived DICOM.

Qt-free. Used by the projection export and the 3D Secondary Capture writer so
neither keeps its own copy. The file-meta and numbering steps mirror
``core.mpr_dicom_export``.

Requirements: pydicom.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pydicom.uid
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filewriter import dcmwrite
from pydicom.sequence import Sequence
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


def source_instance_refs(datasets: Iterable[Any]) -> list[tuple[str, str]]:
    """Return ``(SOPClassUID, SOPInstanceUID)`` per distinct source instance.

    Frame wrappers reference their parent instance once. Sources missing either
    UID are skipped, because both are Type 1 in a reference item.
    """
    seen: set[str] = set()
    refs: list[tuple[str, str]] = []
    for ds in datasets:
        base = getattr(ds, "_original_dataset", ds)
        uid = str(getattr(base, "SOPInstanceUID", "") or "")
        class_uid = str(getattr(base, "SOPClassUID", "") or "")
        if not uid or not class_uid or uid in seen:
            continue
        seen.add(uid)
        refs.append((class_uid, uid))
    return refs


def referenced_series_item(
    series_uid: str, refs: Iterable[tuple[str, str]]
) -> Dataset | None:
    """Return a ReferencedSeriesSequence item, or None without usable refs.

    The item always carries the Type 1 ReferencedInstanceSequence; with no
    complete class/instance reference there is nothing valid to write.
    """
    instances = []
    for class_uid, instance_uid in refs:
        if class_uid and instance_uid:
            item = Dataset()
            item.ReferencedSOPClassUID = class_uid
            item.ReferencedSOPInstanceUID = instance_uid
            instances.append(item)
    if not (series_uid and instances):
        return None
    ref = Dataset()
    ref.SeriesInstanceUID = series_uid
    ref.ReferencedInstanceSequence = Sequence(instances)
    return ref
