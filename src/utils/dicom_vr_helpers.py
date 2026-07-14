"""
Shared DICOM Value Representation (VR) helpers for anonymization utilities.

Used by ``dicom_anonymizer`` and ``deep_anonymizer`` to classify element VRs
when deciding replace vs remove behavior.
"""

from __future__ import annotations


def is_text_vr(vr: str) -> bool:
    """Return True when *vr* denotes a string-like DICOM value representation."""
    text_vrs = ("LO", "PN", "SH", "ST", "LT", "UT", "CS", "IS", "DS")
    return vr in text_vrs


def is_date_vr(vr: str) -> bool:
    """Return True when *vr* denotes a date/time DICOM value representation."""
    return vr in ("DA", "TM", "DT")
