"""
MPR geometry helpers — pure numpy / patient-space math for MPR output grids.

Extracted from ``mpr_builder`` (Phase 5C) so spacing, bounding-box projection,
and standard LPS planes live in a Qt-free / SimpleITK-call-free module. The
worker still reads ``sitk.Image`` size/origin/direction and passes primitives
here.

Inputs:
    Volume layout: origin, 3×3 direction matrix, size (voxels), spacing (mm).
    Output orientation: row cosine, column cosine, stack normal (unit vectors).
    Requested output in-plane spacing and inter-slice thickness (mm).

Outputs:
    ``MprOutputGrid`` — output origin, 2-D pixel size, slice count, axis ranges
    (for logging).
    ``standard_slice_planes_lps`` — axial / coronal / sagittal ``SlicePlane`` dict.
    ``stack_positions_along_normal`` — scalar positions for ``SliceStack``.

Requirements:
    numpy
    ``SlicePlane`` from ``core.slice_geometry`` (standard planes only)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from core.slice_geometry import SlicePlane


@dataclass(frozen=True)
class MprOutputGrid:
    """
    Output sampling grid for one MPR build (patient space + pixel counts).

    ``rows_px`` / ``cols_px`` follow the MPR builder convention: row axis aligns
    with ``output_col_cosine``, column axis with ``output_row_cosine`` (image
    y / x mapping as in the original ``_compute_output_grid``).
    """

    origin: np.ndarray
    rows_px: int
    cols_px: int
    n_slices: int
    row_axis_min: float
    row_axis_max: float
    col_axis_min: float
    col_axis_max: float
    normal_min: float
    normal_max: float


def compute_mpr_output_grid(
    volume_origin: np.ndarray,
    volume_direction: np.ndarray,
    volume_size_xyz: Tuple[int, int, int],
    volume_spacing_xyz: Tuple[float, float, float],
    output_row_cosine: np.ndarray,
    output_col_cosine: np.ndarray,
    output_normal: np.ndarray,
    output_spacing_mm: float,
    output_thickness_mm: float,
    max_dim: int = 2048,
    max_slices: int = 1024,
) -> MprOutputGrid:
    """
    Project the source volume AABB onto the output plane frame and derive pixel counts.

    Matches the historical ``MprBuilderWorker._compute_output_grid`` behavior.
    """
    origin = np.asarray(volume_origin, dtype=float).ravel()[:3]
    direction = np.asarray(volume_direction, dtype=float).reshape(3, 3)
    size = volume_size_xyz
    spacing = volume_spacing_xyz

    x_vec = direction[:, 0] * spacing[0] * size[0]
    y_vec = direction[:, 1] * spacing[1] * size[1]
    z_vec = direction[:, 2] * spacing[2] * size[2]

    corners: List[np.ndarray] = []
    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                c = origin + ix * x_vec + iy * y_vec + iz * z_vec
                corners.append(c)
    corners_arr = np.stack(corners, axis=0)

    out_row = np.asarray(output_row_cosine, dtype=float).ravel()[:3]
    out_col = np.asarray(output_col_cosine, dtype=float).ravel()[:3]
    out_n = np.asarray(output_normal, dtype=float).ravel()[:3]

    proj_col_axis = corners_arr @ out_row
    proj_row_axis = corners_arr @ out_col
    proj_n = corners_arr @ out_n

    col_min, col_max = float(proj_col_axis.min()), float(proj_col_axis.max())
    row_min, row_max = float(proj_row_axis.min()), float(proj_row_axis.max())
    n_min, n_max = float(proj_n.min()), float(proj_n.max())

    sp = max(float(output_spacing_mm), 1e-6)
    th = max(float(output_thickness_mm), 1e-6)

    rows_px = max(1, int(np.ceil((row_max - row_min) / sp)))
    cols_px = max(1, int(np.ceil((col_max - col_min) / sp)))
    n_slices = max(1, int(np.ceil((n_max - n_min) / th)))

    rows_px = min(rows_px, max_dim)
    cols_px = min(cols_px, max_dim)
    n_slices = min(n_slices, max_slices)

    out_origin = out_row * col_min + out_col * row_min + out_n * n_min

    return MprOutputGrid(
        origin=np.asarray(out_origin, dtype=float),
        rows_px=rows_px,
        cols_px=cols_px,
        n_slices=n_slices,
        row_axis_min=row_min,
        row_axis_max=row_max,
        col_axis_min=col_min,
        col_axis_max=col_max,
        normal_min=n_min,
        normal_max=n_max,
    )


def stack_positions_along_normal(
    planes: List[SlicePlane],
    stack_normal: np.ndarray,
) -> List[float]:
    """Per-plane scalar position along *stack_normal* (dot product with origin)."""
    n = np.asarray(stack_normal, dtype=float).ravel()[:3]
    return [float(np.dot(p.origin, n)) for p in planes]


def standard_slice_planes_lps() -> Dict[str, SlicePlane]:
    """
    Standard anatomical output planes in LPS (Left-Posterior-Superior) patient coordinates.

    Returns:
        ``{"axial", "coronal", "sagittal"}`` — same definitions as historic
        ``MprBuilder.standard_planes``.
    """
    axial = SlicePlane(
        origin=np.array([0.0, 0.0, 0.0]),
        row_cosine=np.array([1.0, 0.0, 0.0]),
        col_cosine=np.array([0.0, 1.0, 0.0]),
        row_spacing=1.0,
        col_spacing=1.0,
    )
    coronal = SlicePlane(
        origin=np.array([0.0, 0.0, 0.0]),
        row_cosine=np.array([1.0, 0.0, 0.0]),
        col_cosine=np.array([0.0, 0.0, -1.0]),
        row_spacing=1.0,
        col_spacing=1.0,
    )
    sagittal = SlicePlane(
        origin=np.array([0.0, 0.0, 0.0]),
        row_cosine=np.array([0.0, 1.0, 0.0]),
        col_cosine=np.array([0.0, 0.0, -1.0]),
        row_spacing=1.0,
        col_spacing=1.0,
    )
    return {"axial": axial, "coronal": coronal, "sagittal": sagittal}
