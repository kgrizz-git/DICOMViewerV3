"""
Slice Geometry Module

Provides 3D geometric primitives for DICOM slice planes and slice stacks in
patient coordinate space (millimetres).  All functions are pure (no Qt, no
display state, no I/O) so they can be tested in isolation.

Inputs:
    pydicom Dataset objects (for from_dataset / from_datasets constructors),
    or pre-built SlicePlane / SliceStack instances.

Outputs:
    SlicePlane, SliceStack instances; Optional int (slice index); Optional
    Tuple (point, direction) for plane-plane intersection; Optional Tuple
    (col1, row1, col2, row2) for 2-D line projection.

Requirements:
    numpy (already a project dependency)
    pydicom (already a project dependency)

Public API
----------
SlicePlane          – a single DICOM imaging plane (origin + orientation + spacing)
SliceStack          – ordered sequence of parallel SlicePlanes for one series
find_nearest_slice  – return the nearest original-dataset index in a stack for a
                      reference plane, with optional mm tolerance
plane_plane_intersection  – 3-D line where two planes meet (used by the deferred
                             slice-location-line feature)
project_line_to_2d  – convert that 3-D line to (col1, row1, col2, row2) pixel
                      coordinates in a target plane
"""

import bisect
from typing import List, Optional, Tuple

import numpy as np
from pydicom.dataset import Dataset

from utils.dicom_utils import (
    get_image_orientation,
    get_image_position,
    get_pixel_spacing,
    get_slice_location,
)


# ---------------------------------------------------------------------------
# SlicePlane
# ---------------------------------------------------------------------------

class SlicePlane:
    """
    A single DICOM imaging plane in 3-D patient space.

    Attributes:
        origin      (np.ndarray, shape (3,)): ImagePositionPatient — position
                    of the top-left pixel corner in mm.
        row_cosine  (np.ndarray, shape (3,)): ImageOrientationPatient[0:3] —
                    direction of increasing column index (first row direction).
        col_cosine  (np.ndarray, shape (3,)): ImageOrientationPatient[3:6] —
                    direction of increasing row index (first column direction).
        row_spacing (Optional[float]): PixelSpacing[0] — spacing between rows
                    (mm). None if not available.
        col_spacing (Optional[float]): PixelSpacing[1] — spacing between
                    columns (mm). None if not available.
        normal      (np.ndarray, property): row_cosine × col_cosine, normalised.
    """

    __slots__ = ("origin", "row_cosine", "col_cosine", "row_spacing", "col_spacing")

    def __init__(
        self,
        origin: np.ndarray,
        row_cosine: np.ndarray,
        col_cosine: np.ndarray,
        row_spacing: Optional[float] = None,
        col_spacing: Optional[float] = None,
    ) -> None:
        self.origin = np.asarray(origin, dtype=float)
        self.row_cosine = np.asarray(row_cosine, dtype=float)
        self.col_cosine = np.asarray(col_cosine, dtype=float)
        self.row_spacing = row_spacing
        self.col_spacing = col_spacing

    @property
    def normal(self) -> np.ndarray:
        """Unit normal vector: row_cosine × col_cosine, normalised."""
        n = np.cross(self.row_cosine, self.col_cosine)
        mag = float(np.linalg.norm(n))
        if mag < 1e-10:
            # Degenerate cosines — return a Z-axis fallback.
            return np.array([0.0, 0.0, 1.0])
        return n / mag

    @classmethod
    def from_dataset(
        cls,
        ds: Dataset,
        use_slice_location_if_no_position: bool = False,
    ) -> Optional["SlicePlane"]:
        """
        Build a SlicePlane from a pydicom Dataset.

        Returns None if position (ImagePositionPatient or SliceLocation fallback)
        or ImageOrientationPatient are missing or invalid.  Pixel spacing is
        filled in where available but is not required for construction.

        When use_slice_location_if_no_position is True and ImagePositionPatient
        is missing, origin is synthesized as SliceLocation * slice_normal so
        slice order and spacing can still be derived.

        Args:
            ds: pydicom Dataset for one slice.
            use_slice_location_if_no_position: If True and ImagePositionPatient
                is missing, use SliceLocation (0018,0050) to set origin along
                the slice normal (origin = SliceLocation * normal).

        Returns:
            SlicePlane instance, or None on failure.
        """
        orient = get_image_orientation(ds)
        if orient is None:
            return None
        row_cosine, col_cosine = orient

        # Reject degenerate direction cosines.
        if float(np.linalg.norm(row_cosine)) < 0.5 or float(np.linalg.norm(col_cosine)) < 0.5:
            return None

        origin = get_image_position(ds)
        if origin is None:
            if use_slice_location_if_no_position:
                slice_loc = get_slice_location(ds)
                if slice_loc is not None:
                    n = np.cross(row_cosine, col_cosine)
                    mag = float(np.linalg.norm(n))
                    if mag >= 1e-10:
                        normal = n / mag
                        origin = float(slice_loc) * normal
                else:
                    return None
            else:
                return None

        spacing = get_pixel_spacing(ds)
        row_spacing = float(spacing[0]) if spacing else None
        col_spacing = float(spacing[1]) if spacing else None

        return cls(
            origin=origin,
            row_cosine=row_cosine,
            col_cosine=col_cosine,
            row_spacing=row_spacing,
            col_spacing=col_spacing,
        )

    def __repr__(self) -> str:
        return (
            f"SlicePlane(origin={self.origin}, "
            f"normal={self.normal}, "
            f"row_spacing={self.row_spacing}, col_spacing={self.col_spacing})"
        )


# ---------------------------------------------------------------------------
# SliceStack
# ---------------------------------------------------------------------------

class SliceStack:
    """
    An ordered sequence of SlicePlanes for one DICOM series, sorted by
    position along the stack normal (ascending).

    Attributes:
        planes          (List[SlicePlane]): planes sorted by position along
                        stack_normal.
        original_indices(List[int]): maps sorted index i → original dataset
                        index (i.e. the index into the ``datasets`` list passed
                        to from_datasets).  This value can be used directly as
                        ``current_slice_index`` in the application.
        stack_normal    (np.ndarray, shape (3,)): unit normal shared by all
                        planes (derived from the first valid plane).
        positions       (List[float]): dot(plane.origin, stack_normal) for each
                        sorted plane.  Monotonically non-decreasing.
        slice_thickness (float): nominal spacing between slices in mm.
    """

    __slots__ = (
        "planes", "original_indices", "stack_normal", "positions", "slice_thickness"
    )

    def __init__(
        self,
        planes: List[SlicePlane],
        original_indices: List[int],
        stack_normal: np.ndarray,
        positions: List[float],
        slice_thickness: float,
    ) -> None:
        self.planes = planes
        self.original_indices = original_indices
        self.stack_normal = np.asarray(stack_normal, dtype=float)
        self.positions = positions
        self.slice_thickness = slice_thickness

    @classmethod
    def from_datasets(
        cls,
        datasets: List[Dataset],
        use_slice_location_if_no_position: bool = False,
    ) -> Optional["SliceStack"]:
        """
        Build a SliceStack from a list of pydicom Datasets.

        Datasets that lack position (and SliceLocation when fallback is used)
        or ImageOrientationPatient are silently skipped.  Returns None if no
        valid planes remain.  A single valid plane is allowed (e.g. for a
        one-slice MPR volume).

        The stack normal is taken from the first valid plane; all planes are
        assumed to share the same orientation (standard for a DICOM series).
        Callers that build a 3-D volume (e.g. MPR) should reject or filter
        series where slices have different ImageOrientationPatient.

        Args:
            datasets: Ordered list of pydicom Datasets for one series.
            use_slice_location_if_no_position: If True, planes without
                ImagePositionPatient can be built using SliceLocation (0018,0050).

        Returns:
            SliceStack instance, or None on failure.
        """
        if len(datasets) < 1:
            return None

        planes_with_idx: List[Tuple[int, SlicePlane]] = []
        for i, ds in enumerate(datasets):
            plane = SlicePlane.from_dataset(
                ds,
                use_slice_location_if_no_position=use_slice_location_if_no_position,
            )
            if plane is not None:
                planes_with_idx.append((i, plane))

        if len(planes_with_idx) < 1:
            return None

        stack_normal = planes_with_idx[0][1].normal

        # Project each origin onto the stack normal and sort ascending.
        entries = [
            (orig_idx, plane, float(np.dot(plane.origin, stack_normal)))
            for orig_idx, plane in planes_with_idx
        ]
        entries.sort(key=lambda x: x[2])

        sorted_planes = [plane for _, plane, _ in entries]
        original_indices = [orig_idx for orig_idx, _, _ in entries]
        positions = [pos for _, _, pos in entries]

        slice_thickness = _compute_slice_thickness(datasets, positions)

        return cls(
            planes=sorted_planes,
            original_indices=original_indices,
            stack_normal=stack_normal,
            positions=positions,
            slice_thickness=slice_thickness,
        )

    def position_of(self, plane: SlicePlane) -> float:
        """Return the position of an arbitrary plane along this stack's normal (mm)."""
        return float(np.dot(plane.origin, self.stack_normal))

    def __repr__(self) -> str:
        return (
            f"SliceStack(n_slices={len(self.planes)}, "
            f"stack_normal={self.stack_normal}, "
            f"slice_thickness={self.slice_thickness:.3f}mm)"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_slice_thickness(datasets: List[Dataset], sorted_positions: List[float]) -> float:
    """
    Determine nominal slice thickness in mm.

    Priority:
    1. Median of consecutive inter-slice distances (most reliable for real data).
    2. SliceThickness tag from the first dataset that has it.
    3. Fallback: 1.0 mm.

    Args:
        datasets: Source datasets (used for SliceThickness tag lookup).
        sorted_positions: Positions along stack normal, already sorted ascending.

    Returns:
        Slice thickness in mm (> 0).
    """
    # 1. Inter-slice distances.
    if len(sorted_positions) >= 2:
        diffs = [
            abs(sorted_positions[i + 1] - sorted_positions[i])
            for i in range(len(sorted_positions) - 1)
        ]
        diffs = [d for d in diffs if d > 1e-6]
        if diffs:
            return float(np.median(diffs))

    # 2. SliceThickness tag.
    for ds in datasets:
        try:
            t = float(ds.SliceThickness)
            if t > 0:
                return t
        except (AttributeError, TypeError, ValueError):
            pass

    return 1.0


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def find_nearest_slice(
    ref_plane: SlicePlane,
    stack: SliceStack,
    tolerance_mm: Optional[float] = None,
) -> Optional[int]:
    """
    Find the original dataset index in *stack* whose plane is closest to
    *ref_plane* along the stack's normal direction.

    The comparison is performed entirely in 1-D (signed projection of the
    reference origin onto the stack normal), so this works for any angle
    between the two stacks.  In the extreme case where the stacks are
    perpendicular, many reference positions map to the same target slice —
    this is correct and expected.

    Args:
        ref_plane   : The reference imaging plane (e.g. the current slice in
                      another subwindow).
        stack       : The target SliceStack to search within.
        tolerance_mm: If given and the distance to the nearest plane exceeds
                      this value (mm), return None instead of the index.
                      Pass ``stack.slice_thickness * 0.5`` for the default
                      slice-sync tolerance.

    Returns:
        Original dataset index suitable for use as ``current_slice_index``,
        or None if the stack is empty or outside tolerance.
    """
    if not stack.positions:
        return None

    ref_pos = float(np.dot(ref_plane.origin, stack.stack_normal))

    # Binary search for the insertion point, then compare neighbours.
    idx = bisect.bisect_left(stack.positions, ref_pos)

    candidates = []
    if idx < len(stack.positions):
        candidates.append(idx)
    if idx - 1 >= 0:
        candidates.append(idx - 1)

    if not candidates:
        return None

    best = min(candidates, key=lambda i: abs(stack.positions[i] - ref_pos))
    min_dist = abs(stack.positions[best] - ref_pos)

    if tolerance_mm is not None and min_dist > tolerance_mm:
        return None

    return stack.original_indices[best]


def plane_plane_intersection(
    a: SlicePlane,
    b: SlicePlane,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Compute the 3-D line where two planes intersect.

    This function is implemented now for completeness and unit-testing but is
    only wired to the UI in the deferred "slice location line" feature.

    Args:
        a: First SlicePlane.
        b: Second SlicePlane.

    Returns:
        (point_on_line, unit_direction) where both are np.ndarray shape (3,),
        or None if the planes are parallel or near-coincident.
    """
    n1 = a.normal
    n2 = b.normal

    direction = np.cross(n1, n2)
    mag = float(np.linalg.norm(direction))
    if mag < 1e-8:
        return None  # planes are parallel or coincident

    direction = direction / mag

    # Find a point on the line.
    # The line satisfies:
    #   n1 · P = d1   (d1 = n1 · a.origin)
    #   n2 · P = d2   (d2 = n2 · b.origin)
    # Fix the coordinate axis most orthogonal to `direction` to zero, giving
    # a uniquely solvable 2×2 linear system in the remaining two coordinates.
    d1 = float(np.dot(n1, a.origin))
    d2 = float(np.dot(n2, b.origin))

    # Choose the axis with the largest absolute component in `direction`.
    # direction[i] equals (±) the determinant of the 2×2 submatrix formed by
    # the other two axes, so maximising |direction[i]| maximises the
    # conditioning of the 2×2 system and avoids near-singular solves.
    fixed_axis = int(np.argmax(np.abs(direction)))
    axes = [i for i in range(3) if i != fixed_axis]

    A = np.array([
        [n1[axes[0]], n1[axes[1]]],
        [n2[axes[0]], n2[axes[1]]],
    ], dtype=float)
    rhs = np.array([d1, d2], dtype=float)

    try:
        xy = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError:
        return None

    point = np.zeros(3, dtype=float)
    point[axes[0]] = float(xy[0])
    point[axes[1]] = float(xy[1])
    # point[fixed_axis] remains 0.0

    return (point, direction)


def project_line_to_2d(
    point: np.ndarray,
    direction: np.ndarray,
    plane: SlicePlane,
) -> Optional[Tuple[float, float, float, float]]:
    """
    Project a 3-D line onto the pixel coordinate system of a SlicePlane.

    Returns two pixel-space points at parametric positions t=0 and t=1000 mm
    along the line, giving ``(col1, row1, col2, row2)``.  The caller is
    responsible for clipping to the image extent before drawing.

    Pixel coordinate convention (matches DICOM / existing dicom_utils):
        col  = dot(P - origin, row_cosine) / col_spacing
        row  = dot(P - origin, col_cosine) / row_spacing

    This function is implemented for completeness but is only wired to the UI
    in the deferred "slice location line" feature.

    Args:
        point    : Any 3-D point on the line (np.ndarray shape (3,)).
        direction: Unit direction vector of the line (np.ndarray shape (3,)).
        plane    : Target SlicePlane; must have row_spacing and col_spacing.

    Returns:
        (col1, row1, col2, row2) in pixel coordinates, or None if the line is
        parallel to the plane normal, or if pixel spacing is unavailable.
    """
    if plane.row_spacing is None or plane.col_spacing is None:
        return None
    if plane.row_spacing <= 0 or plane.col_spacing <= 0:
        return None

    # If the line direction is nearly parallel to the plane normal,
    # the line appears as a point in 2-D — degenerate case.
    normal_dot = abs(float(np.dot(direction, plane.normal)))
    if normal_dot > 1.0 - 1e-6:
        return None

    def _to_pixel(p3d: np.ndarray) -> Tuple[float, float]:
        dp = p3d - plane.origin
        col = float(np.dot(dp, plane.row_cosine)) / plane.col_spacing
        row = float(np.dot(dp, plane.col_cosine)) / plane.row_spacing
        return col, row

    p1 = np.asarray(point, dtype=float)
    p2 = p1 + np.asarray(direction, dtype=float) * 1000.0  # 1000 mm span

    col1, row1 = _to_pixel(p1)
    col2, row2 = _to_pixel(p2)

    return (col1, row1, col2, row2)
