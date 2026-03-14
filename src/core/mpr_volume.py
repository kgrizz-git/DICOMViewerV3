"""
MPR Volume

Represents a 3-D DICOM volume as a SimpleITK image with correct spatial
metadata, ready for arbitrary-plane resampling (MPR / oblique reconstruction).

Inputs:
    List[pydicom.Dataset] — sorted or unsorted slice datasets for one series.

Outputs:
    MprVolume instance containing a sitk.Image with correct origin, spacing,
    and direction cosines.  All public geometry is also available as NumPy
    arrays for downstream use by MprBuilder.

Raises:
    MprVolumeError — if the volume cannot be built (missing geometry,
                     too few slices, all-duplicate positions, inconsistent
                     pixel shapes, etc.).

Requirements:
    SimpleITK  (pip install SimpleITK)
    numpy
    pydicom
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from pydicom.dataset import Dataset

try:
    import SimpleITK as sitk
    _SITK_AVAILABLE = True
except ImportError:
    _SITK_AVAILABLE = False
    sitk = None  # type: ignore

from core.slice_geometry import SlicePlane, SliceStack
from utils.dicom_utils import (
    get_image_orientation,
    get_image_position,
    get_slice_location,
)
from utils.debug_flags import DEBUG_MPR

# Tolerance for treating two normals as the same orientation (dot product).
_ORIENTATION_GROUP_DOT_TOLERANCE = 0.99
# Tolerance for labeling a normal as a standard axis (Axial/Coronal/Sagittal).
_ORIENTATION_LABEL_DOT_TOLERANCE = 0.9


def _mpr_log(message: str) -> None:
    """Print an MPR debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")


class MprVolumeError(RuntimeError):
    """Raised when a 3-D MPR volume cannot be constructed."""


def normal_to_orientation_label(normal: np.ndarray) -> str:
    """
    Return a human-readable orientation label for a slice-plane normal.

    Standard DICOM patient orientations: Axial (normal ≈ ±Z), Coronal (≈ ±Y),
    Sagittal (≈ ±X). Otherwise returns "Oblique (x, y, z)".

    Args:
        normal: Unit normal vector (3,) from SlicePlane.normal.

    Returns:
        Label string, e.g. "Axial", "Coronal", "Sagittal", or "Oblique (0.0, 0.7, 0.7)".
    """
    n = np.asarray(normal, dtype=float).ravel()
    if n.size < 3:
        return "Oblique (unknown)"
    n = n[:3] / (float(np.linalg.norm(n[:3])) or 1e-10)
    if abs(float(np.dot(n, [0, 0, 1]))) >= _ORIENTATION_LABEL_DOT_TOLERANCE:
        return "Axial"
    if abs(float(np.dot(n, [0, 1, 0]))) >= _ORIENTATION_LABEL_DOT_TOLERANCE:
        return "Coronal"
    if abs(float(np.dot(n, [1, 0, 0]))) >= _ORIENTATION_LABEL_DOT_TOLERANCE:
        return "Sagittal"
    return f"Oblique ({n[0]:.2f}, {n[1]:.2f}, {n[2]:.2f})"


def has_slice_location_fallback_available(datasets: List[Dataset]) -> bool:
    """
    Return True if every dataset has ImageOrientationPatient and SliceLocation.

    Used to decide whether we can offer the user a fallback when
    ImagePositionPatient is missing (use SliceLocation for slice order/position).

    Args:
        datasets: List of pydicom Datasets.

    Returns:
        True if all have orientation and SliceLocation; False if empty or any lack them.
    """
    if not datasets:
        return False
    for ds in datasets:
        if get_image_orientation(ds) is None or get_slice_location(ds) is None:
            return False
    return True


def get_orientation_groups(
    datasets: List[Dataset],
    use_slice_location_if_no_position: bool = False,
) -> List[Tuple[str, List[Dataset]]]:
    """
    Partition datasets by slice orientation (ImageOrientationPatient).

    Slices with the same orientation (parallel or anti-parallel normals) are
    grouped together. Used when a series has mixed orientations so the user
    can choose which group to use for MPR.

    Args:
        datasets: List of pydicom Datasets (e.g. one series).

    Returns:
        List of (label, list_of_datasets), where label is from
        normal_to_orientation_label (e.g. "Axial", "Coronal (12 images)" is
        not in the label; the caller adds count when displaying).
        Slices that fail SlicePlane.from_dataset are skipped and not included
        in any group. Groups are ordered by label for stable dialog ordering.
        use_slice_location_if_no_position: If True, planes without
            ImagePositionPatient are built using SliceLocation (0018,0050).
    """
    pairs: List[Tuple[Dataset, SlicePlane]] = []
    for ds in datasets:
        plane = SlicePlane.from_dataset(
            ds,
            use_slice_location_if_no_position=use_slice_location_if_no_position,
        )
        if plane is not None:
            pairs.append((ds, plane))

    if not pairs:
        return []

    # Group by orientation: two normals are same if |dot| >= tolerance.
    groups: List[List[Tuple[Dataset, SlicePlane]]] = []
    for ds, plane in pairs:
        n = plane.normal
        placed = False
        for g in groups:
            ref_n = g[0][1].normal
            if abs(float(np.dot(n, ref_n))) >= _ORIENTATION_GROUP_DOT_TOLERANCE:
                g.append((ds, plane))
                placed = True
                break
        if not placed:
            groups.append([(ds, plane)])

    # Build (label, datasets) and sort by label for stable ordering.
    result: List[Tuple[str, List[Dataset]]] = []
    for g in groups:
        label = normal_to_orientation_label(g[0][1].normal)
        ds_list = [ds for ds, _ in g]
        result.append((label, ds_list))
    result.sort(key=lambda x: x[0])
    return result


class MprVolume:
    """
    A 3-D DICOM volume ready for MPR resampling.

    Attributes:
        sitk_image (sitk.Image):
            The volume with origin / spacing / direction cosines set.
            Pixel values are float32 (raw pixel data; rescale slope/intercept
            is NOT applied here — callers may apply it after resampling).
        source_datasets (List[Dataset]):
            Sorted, deduplicated source slices used to build the volume.
        slice_stack (SliceStack):
            Phase-1 geometry for the source series (positions, normal, etc.).
        pixel_spacing_mm (Tuple[float, float]):
            (row_spacing, col_spacing) in mm.
        slice_thickness_mm (float):
            Nominal inter-slice distance in mm derived from stack positions.
        rows (int):
            Pixel rows in each source slice.
        cols (int):
            Pixel columns in each source slice.
        origin (np.ndarray):
            Patient-space origin of the first slice (mm).
        row_cosine (np.ndarray):
            IOP row direction (unit vector).
        col_cosine (np.ndarray):
            IOP column direction (unit vector).
        normal (np.ndarray):
            Stack normal (unit vector, row × col).
    """

    def __init__(
        self,
        sitk_image: "sitk.Image",
        source_datasets: List[Dataset],
        slice_stack: SliceStack,
        pixel_spacing_mm: Tuple[float, float],
        slice_thickness_mm: float,
        rows: int,
        cols: int,
    ) -> None:
        self.sitk_image = sitk_image
        self.source_datasets = source_datasets
        self.slice_stack = slice_stack
        self.pixel_spacing_mm = pixel_spacing_mm
        self.slice_thickness_mm = slice_thickness_mm
        self.rows = rows
        self.cols = cols

        # Convenience geometry from first sorted plane.
        plane0 = slice_stack.planes[0]
        self.origin: np.ndarray = plane0.origin.copy()
        self.row_cosine: np.ndarray = plane0.row_cosine.copy()
        self.col_cosine: np.ndarray = plane0.col_cosine.copy()
        self.normal: np.ndarray = slice_stack.stack_normal.copy()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_datasets(
        cls,
        datasets: List[Dataset],
        use_slice_location_if_no_position: bool = False,
    ) -> "MprVolume":
        """
        Build an MprVolume from a list of pydicom Datasets.

        Steps:
          1. Build a SliceStack to obtain sorted order + positions.
          2. Reorder datasets to match the sorted order.
          3. Remove duplicate positions (tolerance 0.01 mm).
          4. Rebuild SliceStack from deduplicated list for consistent geometry.
          5. Construct a SimpleITK image.

        Args:
            datasets: Pydicom Datasets for one DICOM series (any order).
            use_slice_location_if_no_position: If True, slices without
                ImagePositionPatient are positioned using SliceLocation (0018,0050).

        Returns:
            MprVolume instance.

        Raises:
            MprVolumeError: if the volume cannot be built.
        """
        if not _SITK_AVAILABLE:
            raise MprVolumeError(
                "SimpleITK is not installed. MPR requires SimpleITK."
            )

        if len(datasets) < 1:
            raise MprVolumeError(
                "MPR requires at least one slice with valid geometry."
            )

        _mpr_log(f"MprVolume.from_datasets: received {len(datasets)} dataset(s)")

        # Step 1: Build initial stack to get sorted order and positions.
        initial_stack = SliceStack.from_datasets(
            datasets,
            use_slice_location_if_no_position=use_slice_location_if_no_position,
        )
        if initial_stack is None:
            raise MprVolumeError(
                "Could not build 3-D geometry from this series. "
                "Ensure all slices have ImagePositionPatient (or SliceLocation if "
                "using the fallback) and ImageOrientationPatient."
            )

        _mpr_log(
            "Initial source stack: "
            f"valid_slices={len(initial_stack.planes)} "
            f"normal={np.round(initial_stack.stack_normal, 4).tolist()} "
            f"slice_thickness={initial_stack.slice_thickness:.4f} mm"
        )

        # Step 1b: Reject series with mixed orientations (e.g. axial + coronal).
        # All slices must be parallel; otherwise the volume would be invalid.
        normal_ref = initial_stack.stack_normal
        for i, plane in enumerate(initial_stack.planes):
            dot = float(np.dot(plane.normal, normal_ref))
            if abs(dot) < 0.99:
                raise MprVolumeError(
                    "This series contains slices in different orientations. "
                    "MPR requires a single orientation (e.g. all axial). "
                    "Use a series where every slice has the same ImageOrientationPatient."
                )

        # Step 2: Reorder datasets to match sorted order.
        # initial_stack.original_indices[i] is the index into `datasets` for
        # sorted position i.
        sorted_datasets: List[Dataset] = [
            datasets[orig_idx] for orig_idx in initial_stack.original_indices
        ]
        sorted_positions: List[float] = list(initial_stack.positions)

        # Step 3: Deduplicate by position (keep first occurrence).
        deduped_datasets, deduped_positions = cls._deduplicate_sorted(
            sorted_datasets, sorted_positions
        )
        if len(deduped_datasets) < 1:
            raise MprVolumeError(
                "No slices with valid position remained after deduplication."
            )

        removed_duplicates = len(sorted_datasets) - len(deduped_datasets)
        if removed_duplicates:
            _mpr_log(
                f"Deduplicated source slices: removed {removed_duplicates} duplicate position(s)"
            )

        # Step 4: Rebuild SliceStack from deduplicated list so geometry is
        # self-consistent (positions, slice_thickness, etc.).
        final_stack = SliceStack.from_datasets(
            deduped_datasets,
            use_slice_location_if_no_position=use_slice_location_if_no_position,
        )
        if final_stack is None:
            raise MprVolumeError(
                "Failed to rebuild geometry after deduplication."
            )

        # Pixel spacing from the first plane.
        p0 = final_stack.planes[0]
        pixel_spacing_mm: Tuple[float, float] = (
            float(p0.row_spacing) if p0.row_spacing else 1.0,
            float(p0.col_spacing) if p0.col_spacing else 1.0,
        )

        # Image dimensions from the first dataset.
        first_ds = deduped_datasets[0]
        try:
            rows = int(first_ds.Rows)
            cols = int(first_ds.Columns)
        except AttributeError as exc:
            raise MprVolumeError(
                "Source datasets are missing Rows/Columns attributes."
            ) from exc

        # Step 5: Build SimpleITK image.
        sitk_image = cls._build_sitk_image(
            deduped_datasets, final_stack, pixel_spacing_mm
        )

        sitk_size = sitk_image.GetSize()
        sitk_spacing = sitk_image.GetSpacing()
        _mpr_log(
            "Built source volume: "
            f"rows={rows} cols={cols} slices={len(deduped_datasets)} "
            f"pixel_spacing(row,col)=({pixel_spacing_mm[0]:.4f},{pixel_spacing_mm[1]:.4f}) mm "
            f"slice_spacing={final_stack.slice_thickness:.4f} mm "
            f"sitk_size={sitk_size} sitk_spacing={tuple(round(v, 4) for v in sitk_spacing)}"
        )

        return cls(
            sitk_image=sitk_image,
            source_datasets=deduped_datasets,
            slice_stack=final_stack,
            pixel_spacing_mm=pixel_spacing_mm,
            slice_thickness_mm=final_stack.slice_thickness,
            rows=rows,
            cols=cols,
        )

    # ------------------------------------------------------------------
    # Quick pre-check (lightweight, no exception)
    # ------------------------------------------------------------------

    @staticmethod
    def available(datasets: List[Dataset]) -> bool:
        """
        Return True if datasets have the spatial metadata required for MPR.

        This is a fast pre-check used to enable/disable the MPR dialog button.
        Considers ImagePositionPatient, or ImageOrientationPatient + SliceLocation
        (fallback when position is missing). It does NOT attempt to build the volume.

        Args:
            datasets: Candidate dataset list.

        Returns:
            True if MPR should be possible, False otherwise.
        """
        if not _SITK_AVAILABLE:
            return False
        if len(datasets) < 1:
            return False
        for ds in datasets:
            if get_image_orientation(ds) is None:
                continue
            if get_image_position(ds) is not None:
                return True
            if get_slice_location(ds) is not None:
                return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate_sorted(
        sorted_datasets: List[Dataset],
        sorted_positions: List[float],
        tolerance_mm: float = 0.01,
    ) -> Tuple[List[Dataset], List[float]]:
        """
        Remove duplicate positions from an already-sorted dataset list.

        Keeps the first occurrence of each unique position (within tolerance).

        Args:
            sorted_datasets:  Datasets in ascending-position order.
            sorted_positions: Corresponding position values (mm).
            tolerance_mm:     Positions closer than this are considered equal.

        Returns:
            (deduped_datasets, deduped_positions) — parallel filtered lists.
        """
        if not sorted_datasets:
            return [], []

        deduped_ds: List[Dataset] = [sorted_datasets[0]]
        deduped_pos: List[float] = [sorted_positions[0]]

        for ds, pos in zip(sorted_datasets[1:], sorted_positions[1:]):
            if abs(pos - deduped_pos[-1]) >= tolerance_mm:
                deduped_ds.append(ds)
                deduped_pos.append(pos)

        return deduped_ds, deduped_pos

    @staticmethod
    def _build_sitk_image(
        sorted_datasets: List[Dataset],
        stack: SliceStack,
        pixel_spacing_mm: Tuple[float, float],
    ) -> "sitk.Image":
        """
        Build a SimpleITK image from sorted, deduplicated datasets.

        The SimpleITK image stores raw float32 pixel values without rescale
        slope/intercept applied.  The spatial metadata (origin, spacing,
        direction) is set from ``stack`` geometry.

        Args:
            sorted_datasets:  Datasets in stack-normal ascending order.
            stack:            Self-consistent SliceStack for these datasets.
            pixel_spacing_mm: (row_spacing, col_spacing) in mm.

        Returns:
            sitk.Image with correct spatial metadata.

        Raises:
            MprVolumeError on any failure.
        """
        # Extract and stack pixel arrays.
        pixel_arrays: List[np.ndarray] = []
        for ds in sorted_datasets:
            try:
                arr = ds.pixel_array.astype(np.float32)
                pixel_arrays.append(arr)
            except Exception as exc:
                raise MprVolumeError(
                    f"Cannot read pixel data: {exc}"
                ) from exc

        if not pixel_arrays:
            raise MprVolumeError("No pixel data extracted from datasets.")

        try:
            volume = np.stack(pixel_arrays, axis=0)  # shape: (z, y, x)
        except ValueError as exc:
            raise MprVolumeError(
                f"Slices have inconsistent shapes and cannot be stacked: {exc}"
            ) from exc

        try:
            sitk_image = sitk.GetImageFromArray(volume)
        except Exception as exc:
            raise MprVolumeError(
                f"SimpleITK image creation failed: {exc}"
            ) from exc

        # Origin: ImagePositionPatient of the first sorted slice.
        plane0 = stack.planes[0]
        origin = [float(plane0.origin[0]), float(plane0.origin[1]), float(plane0.origin[2])]
        sitk_image.SetOrigin(origin)

        # Spacing: SimpleITK uses (x, y, z) = (col_spacing, row_spacing, slice_spacing).
        col_sp = pixel_spacing_mm[1]
        row_sp = pixel_spacing_mm[0]
        slice_sp = max(stack.slice_thickness, 1e-6)  # guard against zero
        sitk_image.SetSpacing([col_sp, row_sp, slice_sp])

        # Direction cosines:
        #   SimpleITK expects a 3x3 direction matrix flattened in row-major
        #   order, where each COLUMN is the physical direction of one image
        #   axis.  For our volume:
        #     x-axis (columns) -> row_cosine
        #     y-axis (rows)    -> col_cosine
        #     z-axis (slices)  -> stack normal
        rc = plane0.row_cosine
        cc = plane0.col_cosine
        sn = stack.stack_normal
        direction = [
            rc[0], cc[0], sn[0],
            rc[1], cc[1], sn[1],
            rc[2], cc[2], sn[2],
        ]
        sitk_image.SetDirection(direction)

        _mpr_log(
            "Source volume metadata: "
            f"origin={tuple(round(v, 4) for v in origin)} "
            f"spacing={(round(col_sp, 4), round(row_sp, 4), round(slice_sp, 4))} "
            f"direction={[round(v, 4) for v in direction]}"
        )

        return sitk_image

    def __repr__(self) -> str:
        return (
            f"MprVolume(slices={len(self.source_datasets)}, "
            f"size={self.rows}×{self.cols}, "
            f"spacing=({self.pixel_spacing_mm[0]:.2f},{self.pixel_spacing_mm[1]:.2f})mm, "
            f"thickness={self.slice_thickness_mm:.2f}mm)"
        )
