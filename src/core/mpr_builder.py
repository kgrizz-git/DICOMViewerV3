"""
MPR Builder

Resamples a 3-D DICOM volume (MprVolume) onto an arbitrary family of
parallel planes, producing an ordered list of 2-D NumPy arrays (one per
output slice).

The resampling is executed in a background QThread so the UI stays
responsive.  Callers subscribe to ``progress``, ``finished``, and
``error`` Qt signals.

Inputs:
    MprVolume   — source volume with SimpleITK image + geometry.
    SlicePlane  — output plane (defines orientation / normal of the
                  MPR family; origin is ignored — the full bounding box
                  is covered automatically).
    output_spacing_mm (float)     — in-plane pixel spacing of output (mm).
    output_thickness_mm (float)   — inter-slice spacing of output (mm).
    interpolation (str)           — "linear" (default), "nearest", "cubic".

Outputs:
    MprResult   — list of 2-D float32 NumPy arrays, output SliceStack,
                  and rescale parameters from the source series.

Requirements:
    SimpleITK (pip install SimpleITK)
    numpy
    PySide6 (for QThread, Signal)
    pydicom

Output grid math and standard LPS planes: ``core.mpr_geometry`` (Phase 5C).
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QThread, Signal

sitk: Any = None
sitk_available: bool = False
try:
    import SimpleITK as _sitk

    sitk = _sitk
    sitk_available = True
except ImportError:
    pass

from core.mpr_geometry import (
    compute_mpr_output_grid,
    stack_positions_along_normal,
    standard_slice_planes_lps,
)
from core.mpr_volume import MprVolume, MprVolumeError
from core.slice_geometry import SlicePlane, SliceStack
from utils.debug_flags import DEBUG_MPR


def _mpr_log(message: str) -> None:
    """Print an MPR debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class MprResult:
    """
    Output of a successful MprBuilder run.

    Attributes:
        slices (List[np.ndarray]):
            Ordered list of 2-D float32 NumPy arrays (one per output slice).
        slice_stack (SliceStack):
            Phase-1 geometry for the MPR output — allows slice-sync and
            bounding-box queries.
        output_spacing_mm (tuple[float, float]):
            (row_spacing, col_spacing) of the output in mm.
        output_thickness_mm (float):
            Inter-slice spacing of the output in mm.
        source_volume (MprVolume):
            The source volume used for resampling.
        interpolation (str):
            Interpolation method used.
        rescale_slope (Optional[float]):
            RescaleSlope from the source series first dataset (if present).
        rescale_intercept (Optional[float]):
            RescaleIntercept from the source series first dataset (if present).
    """
    slices: List[np.ndarray]
    slice_stack: SliceStack
    output_spacing_mm: Tuple[float, float]
    output_thickness_mm: float
    source_volume: MprVolume
    interpolation: str
    rescale_slope: Optional[float] = None
    rescale_intercept: Optional[float] = None
    combine_mode: str = "none"
    slab_thickness_mm: float = 0.0

    @property
    def n_slices(self) -> int:
        """Number of output slices."""
        return len(self.slices)

    def apply_rescale(self, array: np.ndarray) -> np.ndarray:
        """
        Apply rescale slope/intercept to a pixel array if available.

        Args:
            array: Raw pixel array (float32).

        Returns:
            Rescaled array, or the original if no rescale parameters.
        """
        if self.rescale_slope is not None and self.rescale_intercept is not None:
            return array.astype(np.float32) * float(self.rescale_slope) + float(self.rescale_intercept)
        return array


# ---------------------------------------------------------------------------
# Builder worker (runs in background QThread)
# ---------------------------------------------------------------------------

class MprBuilderWorker(QThread):
    """
    Background thread that performs the SimpleITK MPR resampling.

    Signals:
        progress (int):  0–100 percent complete.
        finished (MprResult):  Emitted on success with the result.
        error (str):     Emitted on failure with a human-readable message.
    """

    progress = Signal(int)
    finished = Signal(object)   # MprResult (using object to avoid import cycle issues)
    error = Signal(str)

    # SimpleITK interpolation method map
    _INTERP_MAP = {
        "linear":  "sitkLinear",
        "nearest": "sitkNearestNeighbor",
        "cubic":   "sitkBSpline",
    }

    def __init__(
        self,
        source_volume: MprVolume,
        output_plane: SlicePlane,
        output_spacing_mm: float,
        output_thickness_mm: float,
        interpolation: str = "linear",
        combine_mode: str = "none",
        slab_thickness_mm: float = 0.0,
    ) -> None:
        """
        Args:
            source_volume:       Volume to resample.
            output_plane:        Defines the output orientation (origin is
                                 ignored; the full bounding box is covered).
            output_spacing_mm:   In-plane pixel spacing (mm) for output.
            output_thickness_mm: Inter-slice spacing (mm) for output.
            interpolation:       "linear" | "nearest" | "cubic".
            combine_mode:       "none" | "mip" | "minip" | "aip".
            slab_thickness_mm: Slab thickness in mm used for combine modes.
        """
        super().__init__()
        self._volume = source_volume
        self._output_plane = output_plane
        self._output_spacing = output_spacing_mm
        self._output_thickness = output_thickness_mm
        self._interpolation = interpolation.lower()
        self._combine_mode = (combine_mode or "none").lower().strip()
        self._slab_thickness_mm = float(slab_thickness_mm or 0.0)
        self._cancelled = False

        source_spacing = self._volume.sitk_image.GetSpacing()
        _mpr_log(
            "MprBuilderWorker init: "
            f"source_spacing={(round(source_spacing[0], 4), round(source_spacing[1], 4), round(source_spacing[2], 4))} "
            f"request_spacing={self._output_spacing:.4f} mm "
            f"request_thickness={self._output_thickness:.4f} mm "
            f"interpolation={self._interpolation}"
        )
        if self._output_spacing < min(source_spacing[0], source_spacing[1]):
            _mpr_log(
                "Requested in-plane spacing is finer than the source in-plane voxel size; "
                "this is an upsample and will rely on interpolation."
            )
        if self._output_thickness < source_spacing[2]:
            _mpr_log(
                "Requested output slice thickness is finer than the source slice spacing; "
                "this is an upsample through the slice direction and will rely on interpolation."
            )

    def cancel(self) -> None:
        """Request cancellation; the thread will stop at the next check."""
        self._cancelled = True

    def run(self) -> None:
        """Entry point for the background thread."""
        try:
            result = self._build()
            if not self._cancelled:
                self.finished.emit(result)
        except MprVolumeError as exc:
            if not self._cancelled:
                self.error.emit(str(exc))
        except Exception as exc:
            if not self._cancelled:
                self.error.emit(
                    f"Unexpected error during MPR build: {exc}\n"
                    + traceback.format_exc()
                )

    # ------------------------------------------------------------------
    # Core resampling logic
    # ------------------------------------------------------------------

    def _build(self) -> MprResult:
        """
        Perform the full MPR build synchronously (called from run()).

        Returns:
            MprResult on success.

        Raises:
            MprVolumeError on validation or resampling failure.
        """
        if not sitk_available:
            raise MprVolumeError(
                "SimpleITK is not installed. MPR requires SimpleITK."
            )

        self.progress.emit(5)

        # Determine output grid from the volume's bounding box projected onto
        # the output plane's coordinate system.
        sitk_img = self._volume.sitk_image
        grid = compute_mpr_output_grid(
            np.array(sitk_img.GetOrigin()),
            np.array(sitk_img.GetDirection()).reshape(3, 3),
            sitk_img.GetSize(),
            sitk_img.GetSpacing(),
            self._output_plane.row_cosine,
            self._output_plane.col_cosine,
            self._output_plane.normal,
            self._output_spacing,
            self._output_thickness,
        )
        out_origin = grid.origin
        out_size = (grid.rows_px, grid.cols_px)
        n_slices = grid.n_slices

        _mpr_log(
            "Projected source bounding box: "
            f"row_axis=({grid.row_axis_min:.4f},{grid.row_axis_max:.4f}) "
            f"col_axis=({grid.col_axis_min:.4f},{grid.col_axis_max:.4f}) "
            f"normal=({grid.normal_min:.4f},{grid.normal_max:.4f})"
        )
        _mpr_log(
            "Output grid: "
            f"origin={tuple(round(v, 4) for v in out_origin)} "
            f"rows={out_size[0]} cols={out_size[1]} slices={n_slices} "
            f"plane_normal={np.round(self._output_plane.normal, 4).tolist()} "
            f"row_cosine={np.round(self._output_plane.row_cosine, 4).tolist()} "
            f"col_cosine={np.round(self._output_plane.col_cosine, 4).tolist()}"
        )

        self.progress.emit(15)
        if self._cancelled:
            raise MprVolumeError("Build cancelled.")

        # Collect rescale parameters from source.
        rescale_slope, rescale_intercept = self._get_rescale_params()

        # Run per-slice resampling.
        slices: List[np.ndarray] = []
        mpr_planes: List[SlicePlane] = []

        out_row_cosine = self._output_plane.row_cosine
        out_col_cosine = self._output_plane.col_cosine
        out_normal = self._output_plane.normal

        # In-plane size in pixels.
        out_rows_px, out_cols_px = out_size

        for i in range(n_slices):
            if self._cancelled:
                raise MprVolumeError("Build cancelled.")

            # Origin of this output slice along the output normal.
            slice_origin = out_origin + out_normal * (i * self._output_thickness)

            # Build a reference SimpleITK image representing one output slice.
            ref_img = self._make_reference_image(
                slice_origin, out_rows_px, out_cols_px
            )

            # Resample the source volume onto this reference grid.
            resampled = self._resample_to_reference(ref_img)
            if resampled is None:
                # Append a blank slice on failure — don't abort the whole build.
                arr = np.zeros((out_rows_px, out_cols_px), dtype=np.float32)
            else:
                raw = sitk.GetArrayFromImage(resampled)
                arr = raw.squeeze().astype(np.float32)
                if arr.ndim == 3 and arr.shape[0] == 1:
                    arr = arr[0]

            if DEBUG_MPR and (
                i < 3 or i == n_slices - 1 or (n_slices > 8 and i == n_slices // 2)
            ):
                non_zero = int(np.count_nonzero(arr))
                _mpr_log(
                    f"Output slice {i + 1}/{n_slices}: "
                    f"shape={arr.shape} min={float(np.min(arr)):.4f} "
                    f"max={float(np.max(arr)):.4f} mean={float(np.mean(arr)):.4f} "
                    f"nonzero={non_zero}/{arr.size}"
                )

            slices.append(arr)
            mpr_planes.append(
                SlicePlane(
                    origin=slice_origin,
                    row_cosine=out_row_cosine,
                    col_cosine=out_col_cosine,
                    row_spacing=self._output_spacing,
                    col_spacing=self._output_spacing,
                )
            )

            pct = 15 + int(80 * (i + 1) / max(n_slices, 1))
            self.progress.emit(pct)

        # Slab combine (MIP / MinIP / AIP) is applied at display time from the
        # full uncombined stack, driven by subwindow_data and the right-pane
        # Combine Slices widget (see mpr_controller.display_mpr_slice).

        # Build output SliceStack from the MPR planes.
        out_normal_arr = out_normal
        positions = stack_positions_along_normal(mpr_planes, out_normal_arr)
        out_stack = SliceStack(
            planes=mpr_planes,
            original_indices=list(range(len(mpr_planes))),
            stack_normal=out_normal_arr,
            positions=positions,
            slice_thickness=self._output_thickness,
        )

        self.progress.emit(100)

        if DEBUG_MPR and slices:
            mins = [float(np.min(arr)) for arr in slices]
            maxs = [float(np.max(arr)) for arr in slices]
            non_zero_slices = sum(1 for arr in slices if np.count_nonzero(arr) > 0)
            _mpr_log(
                "Build complete: "
                f"slice_count={len(slices)} "
                f"nonzero_slices={non_zero_slices}/{len(slices)} "
                f"global_min={min(mins):.4f} global_max={max(maxs):.4f}"
            )

        return MprResult(
            slices=slices,
            slice_stack=out_stack,
            output_spacing_mm=(self._output_spacing, self._output_spacing),
            output_thickness_mm=self._output_thickness,
            source_volume=self._volume,
            interpolation=self._interpolation,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
            combine_mode="none",
            slab_thickness_mm=0.0,
        )

    def _make_reference_image(
        self,
        slice_origin: np.ndarray,
        rows_px: int,
        cols_px: int,
    ) -> Any:
        """
        Build a 2-D SimpleITK reference image for one output MPR slice.

        The image has 1 pixel in the slice direction (z) so it acts as a
        target grid for sitk.Resample.

        Args:
            slice_origin: Patient-space origin of this slice (mm).
            rows_px:      Number of output rows.
            cols_px:      Number of output columns.

        Returns:
            A sitk.Image with correct size / spacing / origin / direction.
        """
        ref = sitk.Image([cols_px, rows_px, 1], sitk.sitkFloat32)

        sp = self._output_spacing
        ref.SetSpacing([sp, sp, self._output_thickness])

        origin = [float(slice_origin[0]), float(slice_origin[1]), float(slice_origin[2])]
        ref.SetOrigin(origin)

        rc = self._output_plane.row_cosine
        cc = self._output_plane.col_cosine
        sn = self._output_plane.normal
        direction = [
            rc[0], cc[0], sn[0],
            rc[1], cc[1], sn[1],
            rc[2], cc[2], sn[2],
        ]
        ref.SetDirection(direction)

        return ref

    def _resample_to_reference(self, reference: Any) -> Optional[Any]:
        """
        Resample the source volume onto a reference grid using identity transform.

        Args:
            reference: Target grid (output slice definition).

        Returns:
            Resampled sitk.Image, or None on failure.
        """
        interp_name = self._INTERP_MAP.get(self._interpolation, "sitkLinear")
        try:
            interp_method = getattr(sitk, interp_name)
        except AttributeError:
            interp_method = sitk.sitkLinear

        try:
            transform = sitk.Transform(3, sitk.sitkIdentity)
            resampled = sitk.Resample(
                self._volume.sitk_image,
                reference,
                transform,
                interp_method,
                0.0,
                self._volume.sitk_image.GetPixelID(),
            )
            return resampled
        except Exception as exc:
            _mpr_log(f"Resample failed: {exc}")
            return None

    def _get_rescale_params(
        self,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract RescaleSlope and RescaleIntercept from the source series.

        Returns:
            (slope, intercept) as (float, float) or (None, None) if absent.
        """
        if not self._volume.source_datasets:
            return None, None
        ds = self._volume.source_datasets[0]
        try:
            slope = float(ds.RescaleSlope) if hasattr(ds, "RescaleSlope") else None
            intercept = float(ds.RescaleIntercept) if hasattr(ds, "RescaleIntercept") else None
        except (TypeError, ValueError):
            slope, intercept = None, None
        if DEBUG_MPR and (slope is None) != (intercept is None):
            _mpr_log(
                "Unexpected partial rescale metadata on source dataset "
                f"(RescaleSlope={slope!r}, RescaleIntercept={intercept!r}); "
                "apply_rescale will be skipped unless both are present."
            )
        return slope, intercept


# ---------------------------------------------------------------------------
# Public convenience class (thin facade over MprBuilderWorker)
# ---------------------------------------------------------------------------

class MprBuilder:
    """
    Public API for creating an MPR build job.

    Creates an ``MprBuilderWorker`` (QThread subclass) for the given
    parameters and returns it.  The caller is responsible for:
      - Connecting signals: ``worker.progress``, ``worker.finished``, ``worker.error``.
      - Starting the thread: ``worker.start()``.
      - Cancelling if needed: ``worker.cancel()``.

    Example::

        worker = MprBuilder.create_worker(volume, plane, spacing, thickness)
        worker.progress.connect(progress_dialog.setValue)
        worker.finished.connect(on_mpr_done)
        worker.error.connect(on_mpr_error)
        worker.start()
    """

    @staticmethod
    def create_worker(
        source_volume: MprVolume,
        output_plane: SlicePlane,
        output_spacing_mm: float,
        output_thickness_mm: float,
        interpolation: str = "linear",
        combine_mode: str = "none",
        slab_thickness_mm: float = 0.0,
    ) -> MprBuilderWorker:
        """
        Create (but do not start) an MprBuilderWorker.

        Args:
            source_volume:       The MprVolume to resample.
            output_plane:        Defines output orientation.
            output_spacing_mm:   In-plane pixel spacing (mm).
            output_thickness_mm: Inter-slice spacing (mm).
            interpolation:       "linear" | "nearest" | "cubic".
            combine_mode:       "none" | "mip" | "minip" | "aip".
            slab_thickness_mm: Slab thickness in mm for combine modes.

        Returns:
            MprBuilderWorker ready to be started.
        """
        return MprBuilderWorker(
            source_volume=source_volume,
            output_plane=output_plane,
            output_spacing_mm=output_spacing_mm,
            output_thickness_mm=output_thickness_mm,
            interpolation=interpolation,
            combine_mode=combine_mode,
            slab_thickness_mm=slab_thickness_mm,
        )

    @staticmethod
    def standard_planes() -> Dict[str, SlicePlane]:
        """
        Return standard anatomical output planes as a {name: SlicePlane} dict.

        These are expressed in LPS (Left-Posterior-Superior) patient coordinates
        which is the DICOM standard.

        Returns:
            {"axial": SlicePlane, "coronal": SlicePlane, "sagittal": SlicePlane}
        """
        return standard_slice_planes_lps()
