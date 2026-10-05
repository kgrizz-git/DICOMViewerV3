"""
Display a slice through the LUTs a DICOM file embeds (the "From DICOM" option).

These are not display LUTs. Per PS3.3 C.11.1 a Modality LUT Sequence
(0028,3000) replaces rescale slope/intercept, and per C.11.2 a VOI LUT
Sequence (0028,3010) replaces window/level. So "From DICOM" maps stored
values through the Modality LUT (or rescale, when there is none) and then the
VOI LUT, instead of the current window. The result is the uint8 that window/level
would otherwise produce: photometric polarity, the user invert, and the active
display LUT are applied afterwards exactly as for a windowed slice.

pydicom 2.4's ``apply_modality_lut`` and ``apply_voi`` do the table lookups.
The VOI output spans ``0 .. 2**bits - 1`` for the LUT Descriptor's bits per
entry (8 or 10-16), and is scaled to ``0 .. 255`` with round-to-nearest.

Inputs:
    - A pydicom ``Dataset`` and its stored pixel array

Outputs:
    - Whether the dataset has a VOI LUT this build can apply, and the uint8
      display array (or ``None`` when the embedded VOI LUT cannot be applied)

Requirements:
    - numpy
    - pydicom (``pixel_data_handlers.util``)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from pydicom.pixel_data_handlers.util import apply_modality_lut, apply_voi

_logger = logging.getLogger(__name__)


def has_voi_lut(dataset: Any) -> bool:
    """True when the dataset embeds a VOI LUT Sequence with at least one item."""
    sequence = getattr(dataset, "VOILUTSequence", None) if dataset is not None else None
    return bool(sequence)


def voi_lut_supported(dataset: Any, index: int = 0) -> bool:
    """True when VOI LUT ``index`` exists and its descriptor is one this build applies.

    PS3.3 C.8.11.3.1.5 allows 8 or 10-16 bits per entry, and LUT Data must hold
    the number of entries the descriptor declares. A file that fails either
    falls back to window/level, so the UI must not offer it as applied.
    """
    if not has_voi_lut(dataset):
        return False
    try:
        item = dataset.VOILUTSequence[index]
        descriptor = item.LUTDescriptor
        bits = int(descriptor[2])
        if not (bits == 8 or 10 <= bits <= 16) or "LUTData" not in item:
            return False
        entries = int(descriptor[0]) or 2**16
        if entries < 0:
            return False
        if bits == 8 and entries > 256:
            # pydicom indexes an 8-bit LUT with a uint8 array, which wraps past 255.
            return False
        return _lut_entry_count(item) >= entries
    except (AttributeError, IndexError, TypeError, ValueError, KeyError):
        # A malformed descriptor is unsupported, never an error for the caller.
        return False


def _lut_entry_count(item: Any) -> int:
    """Entries actually present in LUT Data. OW holds packed 16-bit words."""
    value = item["LUTData"].value
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray)):
        return len(value) // 2
    if isinstance(value, int):
        return 1
    return len(value)


def dicom_voi_to_uint8(pixel_array: np.ndarray, dataset: Any, index: int = 0) -> np.ndarray | None:
    """Stored pixels through the Modality LUT (or rescale), then VOI LUT ``index``.

    Returns ``None`` when the dataset has no VOI LUT Sequence, or when its
    descriptor is unsupported, so the caller falls back to window/level. The
    Modality LUT alone does not make a display: without a VOI LUT the current
    window still applies, to the modality output.
    """
    if not voi_lut_supported(dataset, index):
        if has_voi_lut(dataset):
            _logger.warning(
                "Embedded VOI LUT is not supported; using window/level",
                extra={"operation": "dicom_lut.voi"},
            )
        return None
    try:
        modality = np.asarray(apply_modality_lut(pixel_array, dataset))
        if not np.issubdtype(modality.dtype, np.integer):
            # Rescale can return floats. The VOI LUT is indexed by integer
            # values, so round rather than truncate.
            modality = np.rint(modality).astype(np.int64)
        descriptor = dataset.VOILUTSequence[index].LUTDescriptor
        entries = int(descriptor[0]) or 2**16
        first = int(descriptor[1])
        # Clamp to the table's domain first (PS3.3 C.11.2.1.1: values below the
        # first map to the first entry, above the last to the last). pydicom
        # stores the index in the LUT's own dtype, so an 8-bit table would
        # otherwise wrap an input above 255 instead of clamping it.
        # Widen first: a negative first input value is legal, and an unsigned
        # Modality LUT output cannot hold it.
        modality = np.clip(modality.astype(np.int64), first, first + entries - 1)
        mapped = np.asarray(apply_voi(modality, dataset, index))
        bits = int(descriptor[2])
    except (
        NotImplementedError, ValueError, TypeError, IndexError, AttributeError, KeyError, OverflowError
    ) as error:
        _logger.warning(
            "Embedded VOI LUT could not be applied; using window/level",
            extra={"operation": "dicom_lut.voi", "error_class": type(error).__name__},
        )
        return None
    top = float(2**bits - 1)
    scaled = np.rint(mapped.astype(np.float64) * (255.0 / top))
    return np.clip(scaled, 0, 255).astype(np.uint8)
