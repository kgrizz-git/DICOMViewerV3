"""
Viewport direction labels from DICOM ImageOrientationPatient (patient LPS).

Maps each screen edge to a 3D direction in patient space (DICOM LPS: X+ Left,
Y+ Posterior, Z+ Superior), then to one or two letters (L/R, P/A, S/I).

Inputs:
    - ``ImageOrientationPatient`` (6 floats): row direction, then column direction.
    - Optional significance threshold *T* (default 0.5).

Outputs:
    - ``dict`` with keys ``top``, ``bottom``, ``left``, ``right`` and string values,
      or ``None`` if IOP is missing/invalid.

Edge vectors (same as ``ImageViewerViewMixin`` historically):
    - Left / right: negative / positive **row** (IOP first triplet).
    - Top / bottom: negative / positive **column** (IOP second triplet).

When exactly one LPS axis has |component| >= *T* on that edge direction, a single
letter is shown (cardinal planes). When two or more axes meet the threshold,
letters are joined with a space, ordered by descending |component|.

Requirements: numpy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Minimum |LPS component| on an edge direction to include that axis in the label.
DEFAULT_SIGNIFICANCE_THRESHOLD = 0.5


def _normalize_vec(vec: np.ndarray) -> Optional[np.ndarray]:
    v = np.asarray(vec, dtype=np.float64).reshape(-1)
    if v.size != 3:
        return None
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return None
    return v / n


def label_lps_direction_vector(
    vec: Any,
    *,
    threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
) -> str:
    """
    Map a 3D direction in LPS to a label string (one or two letters).

    Args:
        vec:        3-vector (row/column direction or its negation).
        threshold:  Include an axis when |component| >= threshold.

    Returns:
        Empty string if *vec* is degenerate; else "L", "A R", etc.
    """
    v = _normalize_vec(vec)
    if v is None:
        return ""

    entries: List[Tuple[float, str]] = [
        (abs(float(v[0])), "L" if v[0] >= 0.0 else "R"),
        (abs(float(v[1])), "P" if v[1] >= 0.0 else "A"),
        (abs(float(v[2])), "S" if v[2] >= 0.0 else "I"),
    ]
    significant = [(a, ch) for a, ch in entries if a >= threshold]
    if len(significant) >= 2:
        significant.sort(key=lambda item: item[0], reverse=True)
        return " ".join(ch for _a, ch in significant)
    if len(significant) == 1:
        return significant[0][1]
    entries.sort(key=lambda item: item[0], reverse=True)
    return entries[0][1]


def compute_direction_labels_from_iop(
    iop: Optional[Sequence[Any]],
    *,
    threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
) -> Optional[Dict[str, str]]:
    """
    Build top/bottom/left/right labels from a 6-element ImageOrientationPatient.

    Args:
        iop:        Row (3) + column (3) direction cosines in LPS.
        threshold:  Significance threshold per axis (see module doc).

    Returns:
        Dict with keys ``left``, ``right``, ``top``, ``bottom``, or ``None``.
    """
    if iop is None or len(iop) < 6:
        return None
    try:
        row = np.array(
            [float(iop[0]), float(iop[1]), float(iop[2])], dtype=np.float64
        )
        col = np.array(
            [float(iop[3]), float(iop[4]), float(iop[5])], dtype=np.float64
        )
    except (TypeError, ValueError):
        return None

    return {
        "left": label_lps_direction_vector(-row, threshold=threshold),
        "right": label_lps_direction_vector(row, threshold=threshold),
        "top": label_lps_direction_vector(-col, threshold=threshold),
        "bottom": label_lps_direction_vector(col, threshold=threshold),
    }
