"""
Shared DICOM Value Representation (VR) helpers for date anonymization.

Used by ``deep_anonymizer`` when applying date-removal or date-shifting rules.
"""

def is_date_vr(vr: str) -> bool:
    """Return True when *vr* denotes a date/time DICOM value representation."""
    return vr in ("DA", "TM", "DT")
