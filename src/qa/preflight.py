"""
Preflight checks for Stage 1 QA (slice geometry, modality hints).

Operates on in-memory pydicom datasets (focused series) so slice positions can
be evaluated without re-reading files. Folder-based runs skip stack geometry
checks here (see caller message).
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from pydicom.dataset import Dataset


def collect_slice_position_warnings(datasets: List[Dataset]) -> List[str]:
    """
    Warn when ImagePositionPatient does not advance monotonically along the
    slice normal implied by ImageOrientationPatient, or when required tags are
    missing.

    Args:
        datasets: Ordered list of slice datasets as loaded in the viewer.

    Returns:
        List of user-facing warning strings (empty if no issues detected).
    """
    warnings: List[str] = []
    if len(datasets) < 2:
        return warnings

    zs: List[float] = []
    missing = False
    bad_orientation = False

    for ds in datasets:
        ipp = getattr(ds, "ImagePositionPatient", None)
        iop = getattr(ds, "ImageOrientationPatient", None)
        if ipp is None or iop is None:
            missing = True
            continue
        try:
            ipp_list = [float(x) for x in ipp]
            iop_list = [float(x) for x in iop]
        except (TypeError, ValueError):
            missing = True
            continue
        if len(ipp_list) < 3 or len(iop_list) < 6:
            missing = True
            continue

        row = np.array(iop_list[0:3], dtype=float)
        col = np.array(iop_list[3:6], dtype=float)
        normal = np.cross(row, col)
        norm_len = float(np.linalg.norm(normal))
        if norm_len < 1e-9:
            bad_orientation = True
            continue
        normal = normal / norm_len
        pos = np.array(ipp_list[0:3], dtype=float)
        zs.append(float(np.dot(pos, normal)))

    if missing:
        warnings.append(
            "Cannot verify monotonic slice positions: missing or invalid "
            "ImagePositionPatient / ImageOrientationPatient on one or more slices."
        )
        return warnings

    if bad_orientation:
        warnings.append(
            "Cannot verify monotonic slice positions: degenerate ImageOrientationPatient."
        )
        return warnings

    if len(zs) != len(datasets):
        warnings.append("Slice position preflight incomplete; continuing may yield incorrect stack order.")
        return warnings

    # Strict monotonic along normal; small tolerance for float noise
    tol = 1e-3
    increasing = all(zs[i] < zs[i + 1] - tol for i in range(len(zs) - 1))
    decreasing = all(zs[i] > zs[i + 1] + tol for i in range(len(zs) - 1))
    if not increasing and not decreasing:
        warnings.append(
            "Slice positions along the slice normal are not monotonic for this series order. "
            "Confirm order matches the acquisition before running analysis."
        )

    # Near-duplicate positions
    for i in range(len(zs) - 1):
        if abs(zs[i + 1] - zs[i]) < tol:
            warnings.append(
                "Duplicate or near-duplicate slice positions detected; verify instance ordering."
            )
            break

    return warnings


def modality_preflight_warning(modality: str, expected: str) -> Optional[str]:
    """Return a warning if modality is set and does not match expected (case-insensitive)."""
    if not modality or not expected:
        return None
    if modality.upper() != expected.upper():
        return (
            f"Focused series Modality is '{modality}' but this analysis targets {expected}. "
            "Results may be invalid if the phantom type does not match."
        )
    return None
