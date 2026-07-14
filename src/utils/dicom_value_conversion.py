"""Value conversion helpers for DICOM tag editing."""

from __future__ import annotations

from typing import Any


def convert_dicom_value(value: Any, vr: str | None = None) -> Any:
    """Convert a UI/editor value according to the current lightweight VR rules."""
    if vr is None:
        return value

    vr = vr.upper()

    if vr in {"FL", "FD"}:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

    if vr in {"SL", "SS", "UL", "US"}:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value

    if vr in {
        "AE",
        "AS",
        "AT",
        "CS",
        "DA",
        "DS",
        "DT",
        "IS",
        "LO",
        "LT",
        "PN",
        "SH",
        "ST",
        "TM",
        "UI",
        "UT",
    }:
        return str(value) if value is not None else ""

    return value
