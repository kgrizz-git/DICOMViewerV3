"""
Tag-only stored pixel-value range helper for DICOM datasets.

Derives the full-scale stored pixel range from ``BitsStored``, ``BitsAllocated``,
and ``PixelRepresentation`` without scanning pixel data. Used by the bit-depth-aware
W/L preset generator.
"""

from __future__ import annotations

import logging

from pydicom.dataset import Dataset

_logger = logging.getLogger(__name__)


def get_stored_value_range(dataset: Dataset) -> tuple[float, float]:
    """Return ``(stored_min, stored_max)`` for raw stored pixels. Tag-only (no pixel scan).

    Rules:
    - ``BitsStored`` authoritative; ``HighBit`` used only for validation (warn if != BitsStored-1).
    - ``PixelRepresentation == 1`` → signed, else unsigned.
    - Unsigned N-bit: ``0 .. 2**bits_stored - 1``.
    - Signed   N-bit: ``-(2**(bits_stored-1)) .. 2**(bits_stored-1) - 1``.
    - Missing/zero/invalid ``BitsStored`` → fall back to ``BitsAllocated`` (clamped >= 1).
    - ``BitsStored > BitsAllocated`` (malformed) → clamp ``BitsStored = BitsAllocated``.
    - Guarantee ``stored_max > stored_min`` (never 0-width): if equal, ``stored_max += 1``.
    """
    bits_allocated = _get_tag_int(dataset, "BitsAllocated", default=16)
    if bits_allocated < 1:
        bits_allocated = 1

    bits_stored = _get_tag_int(dataset, "BitsStored", default=0)
    if bits_stored < 1:
        bits_stored = bits_allocated
    if bits_stored > bits_allocated:
        _logger.warning(
            "BitsStored (%d) > BitsAllocated (%d); clamping",
            bits_stored,
            bits_allocated,
        )
        bits_stored = bits_allocated

    high_bit = _get_tag_int(dataset, "HighBit", default=-1)
    if high_bit >= 0 and high_bit != bits_stored - 1:
        _logger.warning(
            "HighBit (%d) != BitsStored-1 (%d); using BitsStored",
            high_bit,
            bits_stored - 1,
        )

    pixel_rep = _get_tag_int(dataset, "PixelRepresentation", default=0)
    is_signed = pixel_rep == 1

    if is_signed:
        stored_min = -(2 ** (bits_stored - 1))
        stored_max = 2 ** (bits_stored - 1) - 1
    else:
        stored_min = 0
        stored_max = 2**bits_stored - 1

    if stored_max <= stored_min:
        stored_max = stored_min + 1

    return (float(stored_min), float(stored_max))


def _get_tag_int(dataset: Dataset, tag_name: str, *, default: int) -> int:
    value = getattr(dataset, tag_name, None)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
