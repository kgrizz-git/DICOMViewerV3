"""
DICOM PALETTE COLOR lookup-table handling.

Reads Red/Green/Blue palette color lookup tables from a dataset and applies
them to indexed pixel data to produce an RGB array.

Inputs:
    - pydicom Dataset with PaletteColorLookupTable* tags
    - Indexed pixel array (palette-color samples)

Outputs:
    - RGB uint8 array, or the original pixel array unchanged on failure

Requirements:
    - numpy, pydicom
"""
import logging
from collections.abc import Sequence
from typing import Any, cast

import numpy as np
from pydicom.dataset import Dataset

from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)


def read_palette_lut(dataset: Dataset, prefix: str) -> tuple[np.ndarray | None, int | None]:
    """
    Read one color's palette LUT and first_value from ``dataset``.

    ``prefix`` is one of "Red", "Green", "Blue". Returns ``(lut, first_value)``,
    where ``first_value`` is ``None`` only when that color's descriptor tag is
    absent.
    """
    descriptor_attr = f"{prefix}PaletteColorLookupTableDescriptor"
    data_attr = f"{prefix}PaletteColorLookupTableData"

    if not hasattr(dataset, descriptor_attr):
        return None, None

    desc = getattr(dataset, descriptor_attr)
    # A real 3-valued DICOM element comes back from pydicom as
    # ``pydicom.multival.MultiValue``, which subclasses MutableSequence, not
    # list/tuple -- so this must duck-type on Sequence rather than isinstance
    # against list/tuple (a prior version of this guard did that and always
    # missed real datasets; see dev-docs/TO_DO.md).
    if isinstance(desc, Sequence) and not isinstance(desc, (str, bytes)) and len(desc) >= 3:
        descriptor_items = cast(Sequence[Any], desc)
        first_value = int(descriptor_items[1])
        bits_allocated = int(descriptor_items[2])
    else:
        first_value = 0
        bits_allocated = 8

    lut = None
    if hasattr(dataset, data_attr):
        lut_data = getattr(dataset, data_attr)
        if isinstance(lut_data, bytes):
            lut = np.frombuffer(lut_data, dtype=np.uint8 if bits_allocated == 8 else np.uint16)
        elif isinstance(lut_data, (list, tuple)):
            lut = np.array(lut_data, dtype=np.uint16 if bits_allocated > 8 else np.uint8)

    return lut, first_value


def extract_indexed_array(pixel_array: np.ndarray) -> np.ndarray:
    """Reduce a palette-color pixel array to a 2D array of LUT indices."""
    if len(pixel_array.shape) == 3 and pixel_array.shape[2] == 1:
        # Single-frame grayscale indexed: (height, width, 1) -> (height, width)
        return pixel_array[:, :, 0]
    if len(pixel_array.shape) == 2:
        # Single-frame grayscale indexed: (height, width)
        return pixel_array
    if len(pixel_array.shape) == 4:
        # Multi-frame: take first frame
        return pixel_array[0, :, :, 0] if pixel_array.shape[3] == 1 else pixel_array[0, :, :]
    return pixel_array


def _apply_one_lut(indexed_array: np.ndarray, lut: np.ndarray, first_value: int, clamp_max: int) -> np.ndarray:
    """Map indices through a single channel's LUT, using that channel's own
    first_value (per DICOM PS3.3 C.7.6.3.1.5, each of Red/Green/Blue has its own).
    Indices are computed in a signed dtype so a negative first_value (or an index
    below it) does not wrap the way it would on an unsigned array. ``clamp_max`` is
    shared across channels (see apply_palette_luts) -- a Green/Blue LUT shorter
    than Red can still raise IndexError here, a known, deliberately-preserved
    quirk (dev-docs/TO_DO.md)."""
    indexed_signed = indexed_array.astype(np.int32) - first_value
    indexed_signed = np.clip(indexed_signed, 0, clamp_max)
    if lut.dtype == np.uint16:
        lut = (lut / 65535.0 * 255.0).astype(np.uint8)
    return lut[indexed_signed]


def apply_palette_luts(
    indexed_array: np.ndarray,
    red_lut: np.ndarray,
    green_lut: np.ndarray,
    blue_lut: np.ndarray,
    red_first_value: int,
    green_first_value: int,
    blue_first_value: int,
) -> np.ndarray:
    """Clamp indices against the Red LUT's length for all three channels (a known
    quirk, not fixed here -- see dev-docs/TO_DO.md), normalize 16-bit LUTs to
    8-bit, look up (each channel using its own first_value), and stack to RGB."""
    clamp_max = len(red_lut) - 1
    red_channel = _apply_one_lut(indexed_array, red_lut, red_first_value, clamp_max)
    green_channel = _apply_one_lut(indexed_array, green_lut, green_first_value, clamp_max)
    blue_channel = _apply_one_lut(indexed_array, blue_lut, blue_first_value, clamp_max)

    if len(indexed_array.shape) == 2:
        return np.stack([red_channel, green_channel, blue_channel], axis=2)
    return np.stack([red_channel, green_channel, blue_channel], axis=-1)


def convert_palette_color_to_rgb(pixel_array: np.ndarray, dataset: Dataset) -> tuple[np.ndarray, bool]:
    """
    Convert PALETTE COLOR indexed pixel data to RGB using the dataset's LUTs.

    Returns ``(new_or_original_pixel_array, did_convert_to_color)``. On any
    failure (missing/corrupt LUTs), returns the original ``pixel_array``
    unchanged and ``False`` -- the caller falls back to grayscale rendering.
    """
    try:
        red_lut, red_first = read_palette_lut(dataset, "Red")
        green_lut, green_first = read_palette_lut(dataset, "Green")
        blue_lut, blue_first = read_palette_lut(dataset, "Blue")

        if red_lut is None or green_lut is None or blue_lut is None:
            return pixel_array, False

        indexed_array = extract_indexed_array(pixel_array)
        rgb_array = apply_palette_luts(
            indexed_array, red_lut, green_lut, blue_lut,
            red_first or 0, green_first or 0, blue_first or 0,
        )
        return rgb_array, True
    except Exception as e:
        print_redacted(f"[PROCESSOR] Error applying palette color lookup: {e}")
        _logger.debug("%s", sanitized_format_exc())
        # Fallback: treat as grayscale if palette lookup fails
        return pixel_array, False
