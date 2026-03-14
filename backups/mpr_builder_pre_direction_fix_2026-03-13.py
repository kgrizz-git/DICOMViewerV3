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
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from PySide6.QtCore import QThread, Signal

try:
    import SimpleITK as sitk
    _SITK_AVAILABLE = True
except ImportError:
    _SITK_AVAILABLE = False
    sitk = None  # type: ignore

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
    output_spacing_mm: tuple
    output_thickness_mm: float
    source_volume: MprVolume
    interpolation: str
    rescale_slope: Optional[float] = None
    rescale_intercept: Optional[float] = None

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
    ) -> None:
        """
        Args:
            source_volume:       Volume to resample.
            output_plane:        Defines the output orientation (origin is
                                 ignored; the full bounding box is covered).
            output_spacing_mm:   In-plane pixel spacing (mm) for output.
            output_thickness_mm: Inter-slice spacing (mm) for output.
            interpolation:       "linear" | "nearest" | "cubic".
        """
        super().__init__()
        self._volume = source_volume
        self._output_plane = output_plane
        self._output_spacing = output_spacing_mm
        self._output_thickness = output_thickness_mm
        self._interpolation = interpolation.lower()
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
        if not _SITK_AVAILABLE:
            raise MprVolumeError(
                "SimpleITK is not installed. MPR requires SimpleITK."
            )

        self.progress.emit(5)

        # Determine output grid from the volume's bounding box projected onto
        # the output plane's coordinate system.
        (
            out_origin,
            out_size,
            n_slices,
        ) = self._compute_output_grid()

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

        # Build output SliceStack from the MPR planes.
        out_normal_arr = out_normal
        positions = [
            float(np.dot(p.origin, out_normal_arr)) for p in mpr_planes
        ]
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
        )

    def _compute_output_grid(self) -> tuple:
        """
        Compute the output origin, 2-D size (rows_px, cols_px), and slice count.

        Projects the 8 corners of the source bounding box onto the output
        coordinate frame (row_cosine / col_cosine / normal) and uses the
        extents to determine the output grid.

        Returns:
            (out_origin, (rows_px, cols_px), n_slices)
        """
        vol = self._volume
        sitk_img = vol.sitk_image

        # Source bounding box in patient coordinates.
        # The 8 corners of the volume in patient space.
        size = sitk_img.GetSize()        # (x_size, y_size, z_size) in pixels
        spacing = sitk_img.GetSpacing()  # (x_sp, y_sp, z_sp) in mm
        origin = np.array(sitk_img.GetOrigin())
        direction = np.array(sitk_img.GetDirection()).reshape(3, 3)

        # Physical extent vectors along each axis.
        x_vec = direction[:, 0] * spacing[0] * size[0]
        y_vec = direction[:, 1] * spacing[1] * size[1]
        z_vec = direction[:, 2] * spacing[2] * size[2]

        corners = []
        for ix in (0, 1):
            for iy in (0, 1):
                for iz in (0, 1):
                    c = origin + ix * x_vec + iy * y_vec + iz * z_vec
                    corners.append(c)
        corners = np.array(corners)  # shape: (8, 3)

        # Project corners onto output frame.
        out_row = self._output_plane.row_cosine
        out_col = self._output_plane.col_cosine
        out_n = self._output_plane.normal

        proj_row = corners @ out_row
        proj_col = corners @ out_col
        proj_n = corners @ out_n

        row_min, row_max = float(proj_row.min()), float(proj_row.max())
        col_min, col_max = float(proj_col.min()), float(proj_col.max())
        n_min, n_max = float(proj_n.min()), float(proj_n.max())

        sp = max(self._output_spacing, 1e-6)
        th = max(self._output_thickness, 1e-6)

        rows_px = max(1, int(np.ceil((row_max - row_min) / sp)))
        cols_px = max(1, int(np.ceil((col_max - col_min) / sp)))
        n_slices = max(1, int(np.ceil((n_max - n_min) / th)))

        # Cap to a reasonable maximum to avoid memory exhaustion.
        max_dim = 2048
        max_slices = 1024
        rows_px = min(rows_px, max_dim)
        cols_px = min(cols_px, max_dim)
        n_slices = min(n_slices, max_slices)

        # Output origin: corner of the bounding rectangle in patient space.
        out_origin = (
            out_row * row_min
            + out_col * col_min
            + out_n * n_min
        )

        _mpr_log(
            "Projected source bounding box: "
            f"row=({row_min:.4f},{row_max:.4f}) "
            f"col=({col_min:.4f},{col_max:.4f}) "
            f"normal=({n_min:.4f},{n_max:.4f})"
        )

        return out_origin, (rows_px, cols_px), n_slices

    def _make_reference_image(
        self,
        slice_origin: np.ndarray,
        rows_px: int,
        cols_px: int,
    ) -> "sitk.Image":
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
            rc[0], rc[1], rc[2],
            cc[0], cc[1], cc[2],
            sn[0], sn[1], sn[2],
        ]
        ref.SetDirection(direction)

        return ref

    def _resample_to_reference(
        self, reference: "sitk.Image"
    ) -> Optional["sitk.Image"]:
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

    def _get_rescale_params(self) -> tuple:
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
    ) -> MprBuilderWorker:
        """
        Create (but do not start) an MprBuilderWorker.

        Args:
            source_volume:       The MprVolume to resample.
            output_plane:        Defines output orientation.
            output_spacing_mm:   In-plane pixel spacing (mm).
            output_thickness_mm: Inter-slice spacing (mm).
            interpolation:       "linear" | "nearest" | "cubic".

        Returns:
            MprBuilderWorker ready to be started.
        """
        return MprBuilderWorker(
            source_volume=source_volume,
            output_plane=output_plane,
            output_spacing_mm=output_spacing_mm,
            output_thickness_mm=output_thickness_mm,
            interpolation=interpolation,
        )

    @staticmethod
    def standard_planes() -> dict:
        """
        Return standard anatomical output planes as a {name: SlicePlane} dict.

        These are expressed in LPS (Left-Posterior-Superior) patient coordinates
        which is the DICOM standard.

        Returns:
            {"axial": SlicePlane, "coronal": SlicePlane, "sagittal": SlicePlane}
        """
        # Axial:    normal = S (Superior, +Z in LPS)
        axial = SlicePlane(
            origin=np.array([0.0, 0.0, 0.0]),
            row_cosine=np.array([1.0, 0.0, 0.0]),   # L → R
            col_cosine=np.array([0.0, 1.0, 0.0]),   # P → A
            row_spacing=1.0,
            col_spacing=1.0,
        )
        # Coronal:  normal = A (Anterior, +Y in LPS)
        coronal = SlicePlane(
            origin=np.array([0.0, 0.0, 0.0]),
            row_cosine=np.array([1.0, 0.0, 0.0]),   # L → R
            col_cosine=np.array([0.0, 0.0, -1.0]),  # S → I (display convention)
            row_spacing=1.0,
            col_spacing=1.0,
        )
        # Sagittal: normal = L (Left, +X in LPS)
        sagittal = SlicePlane(
            origin=np.array([0.0, 0.0, 0.0]),
            row_cosine=np.array([0.0, 1.0, 0.0]),   # P → A
            col_cosine=np.array([0.0, 0.0, -1.0]),  # S → I (display convention)
            row_spacing=1.0,
            col_spacing=1.0,
        )
        return {"axial": axial, "coronal": coronal, "sagittal": sagittal}
