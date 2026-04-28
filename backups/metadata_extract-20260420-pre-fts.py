"""
Extract denormalised study/series/instance fields from in-memory pydicom datasets.

Used after a successful load so we do not re-read pixel data from disk.
"""

from __future__ import annotations

import ast
import os
from typing import Any

from pydicom.dataset import Dataset


def repair_str_bytes_repr_artifact(s: str) -> str:
    """
    If ``s`` is the accidental Python form ``str(bytes)`` (``b'…'`` or ``b\"…\"``),
    decode the embedded bytes to a normal Unicode string.

    This fixes **legacy index rows** that stored the repr in SQLite, and guards
    odd tag paths that still stringify ``bytes`` incorrectly.
    """
    t = (s or "").strip()
    if len(t) < 3:
        return t
    if not (t.startswith("b'") or t.startswith('b"')):
        return t
    try:
        ev = ast.literal_eval(t)
    except (ValueError, SyntaxError, MemoryError):
        return s
    if isinstance(ev, (bytes, bytearray)):
        return bytes(ev).decode("latin-1", errors="replace").strip()
    return s


def _bytes_to_text(raw: bytes | bytearray) -> str:
    """Decode DICOM header bytes without using ``str(bytes)`` (which yields ``b'…'``)."""
    return bytes(raw).decode("latin-1", errors="replace").strip()


def _elem_to_str(val: Any) -> str:
    """
    Normalise a tag value to a plain Unicode string for the index.

    pydicom may expose ``bytes`` or ``PersonName.original_string`` as ``bytes``;
    ``str(b'x')`` would store the wrong literal ``b'x'`` in SQLite.
    """
    if val is None:
        return ""
    if isinstance(val, (bytes, bytearray)):
        return repair_str_bytes_repr_artifact(_bytes_to_text(val))
    if hasattr(val, "original_string"):
        inner = getattr(val, "original_string", None)
        if inner is not None:
            if isinstance(inner, (bytes, bytearray)):
                return repair_str_bytes_repr_artifact(_bytes_to_text(inner))
            try:
                return repair_str_bytes_repr_artifact(str(inner).strip())
            except Exception:
                pass
    try:
        return repair_str_bytes_repr_artifact(str(val).strip())
    except Exception:
        return ""


def dataset_to_index_row(
    ds: Dataset,
    *,
    file_path: str,
    study_root_path: str,
) -> dict[str, Any]:
    """
    Build a flat dict for one instance row in ``study_index_entry``.

    Args:
        ds: Loaded dataset (may include pixel data).
        file_path: Absolute filesystem path to the file.
        study_root_path: ``source_dir`` from the load pipeline (disambiguates duplicate UIDs).
    """
    fp = os.path.normpath(os.path.abspath(file_path))
    root = os.path.normpath(os.path.abspath(study_root_path))
    study_uid = _elem_to_str(getattr(ds, "StudyInstanceUID", None))
    series_uid = _elem_to_str(getattr(ds, "SeriesInstanceUID", None))
    sop_uid = _elem_to_str(getattr(ds, "SOPInstanceUID", None))
    return {
        "file_path": fp,
        "study_root_path": root,
        "study_uid": study_uid,
        "series_uid": series_uid,
        "sop_instance_uid": sop_uid,
        "patient_name": _elem_to_str(getattr(ds, "PatientName", None)),
        "patient_id": _elem_to_str(getattr(ds, "PatientID", None)),
        "accession_number": _elem_to_str(getattr(ds, "AccessionNumber", None)),
        "study_date": _elem_to_str(getattr(ds, "StudyDate", None)),
        "study_description": _elem_to_str(getattr(ds, "StudyDescription", None)),
        "modality": _elem_to_str(getattr(ds, "Modality", None)),
    }
