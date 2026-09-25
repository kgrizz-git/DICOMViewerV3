"""
Photometric-interpretation polarity helpers — the single owner of MONOCHROME1 display inversion.

``PhotometricInterpretation`` (0028,0004) is a *display* directive only. MONOCHROME1 means "the
minimum sample value is intended to be displayed as white after any VOI gray scale transformations
have been performed" (DICOM PS3.3 C.7.6.3.1.2); MONOCHROME2 means the minimum displays as black.
Neither implies anything about how the pixel data is stored, and neither is a licence to invert
stored values. The equivalent statement in the presentation chain is Presentation LUT Shape
(2050,0020): ``IDENTITY`` for MONOCHROME2, ``INVERSE`` for MONOCHROME1.

The only unconditional consequence, and the one this module implements, is that under MONOCHROME1
the highest stored value displays darkest. Tissue polarity (whether bone is a high or low value)
is declared separately by Pixel Intensity Relationship Sign (0028,1041) and must never be inferred
from this tag.

Pipeline order this module assumes, per PS3.3 C.11.2 plus C.7.6.3.1.2's "after any VOI gray scale
transformations": modality rescale, then window/level on stored values, then polarity inversion
last, on the finalized 8-bit array.

Inputs:
    - Photometric-interpretation values as ``str``, ``list``/``tuple`` (first element), or ``None``
    - pydicom ``Dataset``-like objects (anything answering ``getattr``, including the per-frame
      ``FrameDatasetWrapper`` proxy)
    - Finalized uint8 display arrays

Outputs:
    - Normalized upper-case PI strings, MONOCHROME1 predicates, and polarity-corrected arrays

Requirements:
    - numpy
"""

from __future__ import annotations

from typing import Any

import numpy as np

MONOCHROME1 = "MONOCHROME1"


def normalize_photometric_interpretation(value: Any) -> str:
    """Return the upper-cased photometric interpretation, or ``""`` when absent.

    Accepts a plain string, a ``list``/``tuple`` (first element wins, matching how multi-valued
    elements surface through pydicom), or ``None``.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        value = value[0]
    return str(value).strip().upper()


def is_monochrome1(value: Any) -> bool:
    """Return True when *value* normalizes to exactly ``MONOCHROME1``."""
    return normalize_photometric_interpretation(value) == MONOCHROME1


def dataset_photometric_interpretation(dataset: Any) -> str:
    """Return the normalized photometric interpretation read from *dataset*.

    Returns ``""`` for ``None`` or a dataset without the element. Uses ``getattr`` so per-frame
    wrappers that proxy metadata to a parent dataset resolve correctly.
    """
    if dataset is None:
        return ""
    return normalize_photometric_interpretation(getattr(dataset, "PhotometricInterpretation", None))


def apply_monochrome1_polarity(array: np.ndarray, photometric_interpretation: Any) -> np.ndarray:
    """Return *array* with MONOCHROME1 display polarity applied.

    For MONOCHROME1 returns ``255 - array`` as uint8; otherwise returns *array* unchanged. Only
    2-D grayscale arrays are inverted — a colour array cannot be MONOCHROME1, and the shape guard
    keeps a malformed dataset from silently inverting RGB samples.

    Always returns a new array when inverting (never mutates the caller's buffer), because the
    same array may flow onward to analysis paths that must stay in stored-value polarity.
    """
    if not is_monochrome1(photometric_interpretation):
        return array
    if array.ndim != 2:
        return array
    return 255 - array.astype(np.uint8)
