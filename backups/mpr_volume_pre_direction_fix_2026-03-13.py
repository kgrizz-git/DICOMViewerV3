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

from core.slice_geometry import SliceStack
from utils.dicom_utils import get_image_orientation, get_image_position
from utils.debug_flags import DEBUG_MPR


def _mpr_log(message: str) -> None:
    """Print an MPR debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")


class MprVolumeError(RuntimeError):
    """Raised when a 3-D MPR volume cannot be constructed."""


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
    def from_datasets(cls, datasets: List[Dataset]) -> "MprVolume":
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

        Returns:
            MprVolume instance.

        Raises:
            MprVolumeError: if the volume cannot be built.
        """
        if not _SITK_AVAILABLE:
            raise MprVolumeError(
                "SimpleITK is not installed. MPR requires SimpleITK."
            )

        if len(datasets) < 2:
            raise MprVolumeError(
                f"MPR requires at least 2 slices; got {len(datasets)}."
            )

        _mpr_log(f"MprVolume.from_datasets: received {len(datasets)} dataset(s)")

        # Step 1: Build initial stack to get sorted order and positions.
        initial_stack = SliceStack.from_datasets(datasets)
        if initial_stack is None:
            raise MprVolumeError(
                "Could not build 3-D geometry from this series. "
                "Ensure all slices have ImagePositionPatient and "
                "ImageOrientationPatient."
            )

        _mpr_log(
            "Initial source stack: "
            f"valid_slices={len(initial_stack.planes)} "
            f"normal={np.round(initial_stack.stack_normal, 4).tolist()} "
            f"slice_thickness={initial_stack.slice_thickness:.4f} mm"
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
        if len(deduped_datasets) < 2:
            raise MprVolumeError(
                "All slices have the same position — cannot build a volume."
            )

        removed_duplicates = len(sorted_datasets) - len(deduped_datasets)
        if removed_duplicates:
            _mpr_log(
                f"Deduplicated source slices: removed {removed_duplicates} duplicate position(s)"
            )

        # Step 4: Rebuild SliceStack from deduplicated list so geometry is
        # self-consistent (positions, slice_thickness, etc.).
        final_stack = SliceStack.from_datasets(deduped_datasets)
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
        It does NOT attempt to build the full volume.

        Args:
            datasets: Candidate dataset list.

        Returns:
            True if MPR should be possible, False otherwise.
        """
        if not _SITK_AVAILABLE:
            return False
        if len(datasets) < 2:
            return False
        count = 0
        for ds in datasets:
            if (
                get_image_position(ds) is not None
                and get_image_orientation(ds) is not None
            ):
                count += 1
                if count >= 2:
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

        # Direction cosines: row, col, normal — each as 3-element rows
        # (row-major 3×3 matrix stored as a flat 9-tuple).
        rc = plane0.row_cosine
        cc = plane0.col_cosine
        sn = stack.stack_normal
        direction = [
            rc[0], rc[1], rc[2],
            cc[0], cc[1], cc[2],
            sn[0], sn[1], sn[2],
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
