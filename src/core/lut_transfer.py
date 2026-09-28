"""
Sample the window/level ramp, the LUT, and their composition.

The viewport mapping is ``final(x) = LUT(P_inv(uint8(WL(x))))``. ``P_inv`` is
the XOR of MONOCHROME1 and the pane user-invert flag: ``255 - u`` when exactly
one is true. These helpers call ``apply_window_level`` and
``apply_lut_to_uint8`` so a preview cannot invent a second renderer.

Inputs:
    - Stored pixel samples, window center/width, a ``LookUpTable``
    - Photometric interpretation and the live user-invert flag

Outputs:
    - uint8 window samples and composed samples (grayscale ``(N,)`` or color ``(N, 3)``)

Requirements:
    - numpy
    - core.dicom_window_level.apply_window_level
    - core.lut_engine.apply_lut_to_uint8
    - core.photometric_polarity.is_monochrome1
"""

from __future__ import annotations

import numpy as np

from core.dicom_window_level import apply_window_level
from core.lut_engine import LookUpTable, apply_lut_to_uint8, linear_transfer
from core.photometric_polarity import is_monochrome1


def net_user_polarity_invert(photometric_interpretation: object, image_inverted: bool) -> bool:
    """True when exactly one of MONOCHROME1 and the user invert is set."""
    return bool(is_monochrome1(photometric_interpretation)) ^ bool(image_inverted)


def curves_are_one_line(
    lut: LookUpTable,
    photometric_interpretation: object,
    image_inverted: bool,
) -> bool:
    """Ramp and composed result coincide only for an uninverted linear LUT."""
    linear = (
        lut.lut_type == "grayscale_ramp"
        and lut.transfer_fn is linear_transfer
        and lut.control_points is None
    )
    return linear and not net_user_polarity_invert(photometric_interpretation, image_inverted)


def lut_samples(lut: LookUpTable | None) -> np.ndarray:
    """LUT over codes ``0..255``. Shape ``(256,)`` or ``(256, 3)``. ``None`` is identity."""
    codes = np.arange(256, dtype=np.uint8).reshape(1, 256)
    sampled = apply_lut_to_uint8(codes, lut)
    return np.ascontiguousarray(sampled[0])


def windowed_lut_trace(windowed: np.ndarray, lut: LookUpTable | None) -> np.ndarray | None:
    """LUT of already-windowed codes, with no polarity flip.

    ``None`` for a color map, which is drawn as a gradient rather than a line.
    The returned samples share the stored-value positions of ``windowed``.
    """
    applied = apply_lut_to_uint8(np.asarray(windowed, dtype=np.uint8).reshape(1, -1), lut)
    if applied.ndim == 3:
        return None
    return np.ascontiguousarray(applied.reshape(-1))


def sample_window_and_composed(
    stored_values: np.ndarray,
    window_center: float,
    window_width: float,
    lut: LookUpTable | None,
    photometric_interpretation: object,
    image_inverted: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``uint8(WL(x))`` and ``LUT(P_inv(u))`` for each stored sample.

    The stored array is copied before windowing because ``apply_window_level``
    can update a float64 buffer in place. Truncation matches that function's
    ``astype(np.uint8)`` (127.5 becomes 127, so the inverted code is 128).
    """
    stored = np.asarray(stored_values, dtype=np.float64).copy()
    windowed = apply_window_level(stored, window_center, window_width)
    polarized = windowed
    if net_user_polarity_invert(photometric_interpretation, image_inverted):
        polarized = np.asarray(255 - windowed, dtype=np.uint8)
    flat = polarized.reshape(1, -1)
    composed = apply_lut_to_uint8(flat, lut)
    if composed.ndim == 3:
        return windowed.reshape(-1), np.ascontiguousarray(composed[0])
    return windowed.reshape(-1), np.ascontiguousarray(composed.reshape(-1))
