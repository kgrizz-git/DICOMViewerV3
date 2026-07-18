"""
Volume Renderer

GPU-accelerated 3D volume rendering pipeline using VTK.  Converts a
SimpleITK image (from ``MprVolume``) into a ``vtkImageData`` and renders
it with ``vtkSmartVolumeMapper`` using configurable transfer-function
presets, global opacity, and window/level.

Inputs:
    sitk.Image — from ``MprVolume.sitk_image``.

Outputs:
    vtkRenderer ready for embedding in a ``QVTKRenderWindowInteractor``.

Requirements:
    VTK >= 9.3.0 (pip install vtk)
    SimpleITK (for ``sitk.GetArrayFromImage``)
    numpy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from utils.debug_flags import DEBUG_VOLUME_3D

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy VTK import guard (mirrors mpr_volume.py pattern for SimpleITK)
# ---------------------------------------------------------------------------

vtk_mod: Any = None
vtk_available: bool = False
try:
    import vtkmodules.all as _vtk

    vtk_mod = _vtk
    vtk_available = True
except ImportError:
    pass

if vtk_available:
    # Suppress the VTK popup output window on Windows.
    # The default vtkWin32OutputWindow shows a native popup dialog;
    # replacing the singleton with the base-class instance routes messages
    # to stderr instead, keeping the application window clean.
    try:
        vtk_mod.vtkOutputWindow.SetInstance(vtk_mod.vtkOutputWindow())
    except AttributeError:
        pass  # Older VTK build without this API

# SimpleITK is also needed for array extraction.
sitk: Any = None
sitk_available: bool = False
try:
    import SimpleITK as _sitk

    sitk = _sitk
    sitk_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Transfer-function presets — defined in volume_render_presets.py, re-exported
# here for backward compatibility with existing callers.
# ---------------------------------------------------------------------------

from core.volume_render_presets import (  # noqa: F401
    BUILTIN_PRESETS,
    PRESET_CT_ANATOMY_COLORS,
    PRESET_CT_ANGIO,
    PRESET_CT_BONE,
    PRESET_CT_FAT,
    PRESET_CT_LUNG,
    PRESET_CT_MUSCLE,
    PRESET_CT_SKIN,
    PRESET_CT_SMOOTH_ANATOMY,
    PRESET_CT_SOFT_TISSUE,
    PRESET_CT_VIVID_ANGIO,
    PRESET_GENERIC_INTENSITY,
    PRESET_GROUPS,
    PRESET_MR_DEFAULT,
    PRESET_MR_MRA,
    PRESET_MR_T1_BRAIN,
    PRESET_MR_T2_BRAIN,
    PRESET_NM_DEFAULT,
    PRESET_PT_DEFAULT,
    STEEP_PRESET_THRESHOLD,
    TransferFunctionPreset,
    is_steep_preset,
    preset_steepness,
)


@dataclass
class VolumeData:
    """Thread-safe container for prepared volume data (numpy arrays + spatial metadata)."""

    array: np.ndarray  # contiguous float32, shape (depth, height, width)
    spacing: tuple[float, ...]  # (sx, sy, sz)
    origin: tuple[float, ...]  # (ox, oy, oz)
    direction: tuple[float, ...]  # 9 floats (3x3 direction cosine matrix)
    rescale_applied: bool = False  # True when DICOM rescale slope/intercept were applied
    scalar_units: str | None = None  # e.g. "HU" for calibrated CT


def _calibrate_volume_array(
    arr: np.ndarray,
    source_datasets: list[Any] | None,
) -> tuple[np.ndarray, bool, str | None]:
    """Apply per-slice DICOM rescale only when every slice has sane metadata."""
    if not source_datasets or len(source_datasets) != arr.shape[0]:
        return arr, False, None

    from core.dicom_rescale import get_rescale_parameters, infer_rescale_type

    params: list[tuple[float, float, str | None]] = []
    units: set[str] = set()
    for dataset in source_datasets:
        slope, intercept, rescale_type = get_rescale_parameters(dataset)
        if slope is None or intercept is None:
            return arr, False, None
        if not np.isfinite(slope) or not np.isfinite(intercept):
            return arr, False, None
        # RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
        if slope == 0.0:  # NOSONAR(S1244)
            return arr, False, None

        scalar_units = infer_rescale_type(dataset, slope, intercept, rescale_type)
        if scalar_units:
            units.add(str(scalar_units))
        params.append((float(slope), float(intercept), scalar_units))

    # If slices report conflicting rescale-unit semantics (e.g. one "HU",
    # another "US"), the calibrated values are numerically valid but the
    # unit label is ambiguous.  Fall back to raw so the UI doesn't claim a
    # specific unit it can't guarantee.
    if len(units) > 1:
        _log.info(
            "Mixed rescale units across slices (%s); falling back to raw values.",
            units,
        )
        return arr, False, None

    calibrated = arr.copy()
    for z_index, (slope, intercept, _scalar_units) in enumerate(params):
        calibrated[z_index] = calibrated[z_index] * slope + intercept

    # Guard against NaN/Inf that can arise from corrupted pixel data or
    # extreme slope/intercept values.  VTK volume rendering produces
    # unpredictable blank or garbage frames when the input contains
    # non-finite values.
    if not np.all(np.isfinite(calibrated)):
        _log.warning(
            "Calibrated volume contains NaN or Inf values; "
            "falling back to raw stored values."
        )
        return arr, False, None

    resolved_units = next(iter(units)) if len(units) == 1 else None
    return np.ascontiguousarray(calibrated, dtype=np.float32), True, resolved_units


# ---------------------------------------------------------------------------
# Background colour choices (name -> RGB in 0..1)
# ---------------------------------------------------------------------------

# Smallest allowed transfer-function window width (avoids divide-by-zero and
# degenerate, fully-collapsed scalar ranges when scaling control points).
_MIN_WINDOW: float = 1e-3


# Blend modes for volume rendering (composite / MIP / MinIP).
# Each entry is (display_name, vtk_method_suffix).
BLEND_MODES: list[tuple[str, str]] = [
    ("Composite", "Composite"),
    ("Max Intensity (MIP)", "MaximumIntensity"),
    ("Min Intensity (MinIP)", "MinimumIntensity"),
]

BACKGROUND_COLORS: list[tuple[str, tuple[float, float, float]]] = [
    ("Black", (0.0, 0.0, 0.0)),
    ("Dark Gray", (0.15, 0.15, 0.18)),
    ("Light Gray", (0.78, 0.78, 0.80)),
    ("White", (1.0, 1.0, 1.0)),
]

# Quality modes map to sample distance (lower = higher quality, slower).
# Detail / quality levels map a name to a ray sample distance (lower = finer,
# slower).  Presented in the UI as a single "Detail" slider; the names are
# retained for backward compatibility with saved user presets (which store the
# selected level by name in their ``quality`` field).
QUALITY_MODES: list[tuple[str, float]] = [
    ("Fast", 3.0),
    ("Normal", 1.0),
    ("High", 0.5),
    ("Ultra", 0.25),
]

# Render methods.  "Auto" lets vtkSmartVolumeMapper decide; GPU/CPU force a
# specific path.  We only expose GPU/CPU if the mapper supports it.
RENDER_METHODS: list[str] = ["Auto", "GPU", "CPU"]

_STANDARD_VIEW_DIRECTIONS: dict[
    str,
    tuple[tuple[float, float, float], tuple[float, float, float]],
] = {
    "anterior": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "posterior": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "superior": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "inferior": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
}


def scalar_domain_label(modality: str, *, rescale_applied: bool = False) -> str:
    """
    Describe the scalar domain the renderer is operating on, honestly.

    The 3D volume path currently feeds VTK the *raw stored pixel values*
    (see ``mpr_volume`` — ``RescaleSlope`` / ``RescaleIntercept`` are not
    applied), so CT presets parameterised in HU are positioned against raw
    values, not calibrated HU.  This helper produces a short label the UI can
    show so users are not misled into reading thresholds as true HU.

    Args:
        modality: DICOM Modality tag value (e.g. ``'CT'``, ``'MR'``, ``'PT'``).
        rescale_applied: ``True`` only if calibrated values are being fed to
            VTK.  Defaults to ``False`` to match the current pipeline.

    Returns:
        A short human-readable scalar-domain description.
    """
    mod = (modality or "").upper().strip()
    if mod in ("CT",):
        if rescale_applied:
            return "CT — calibrated HU"
        return "CT — raw pixel values (not calibrated HU)"
    if mod in ("MR", "MRI", "FMRI"):
        return "MR — arbitrary intensity (no fixed units)"
    if mod in ("PT",):
        return "PT — intensity / counts (not SUV-calibrated)"
    if mod in ("NM",):
        return "NM — counts (arbitrary intensity)"
    if mod:
        return f"{mod} — intensity (units unknown)"
    return "Intensity (units unknown)"


def get_default_preset_for_modality(modality: str) -> TransferFunctionPreset:
    """
    Return the most appropriate default transfer-function preset for a DICOM modality.

    Args:
        modality: DICOM Modality tag value (e.g. ``'CT'``, ``'MR'``, ``'PT'``).

    Returns:
        A :class:`TransferFunctionPreset` from :data:`BUILTIN_PRESETS`.
    """
    mod = (modality or "").upper().strip()
    if mod in ("MR", "MRI", "FMRI"):
        return PRESET_MR_DEFAULT
    if mod == "PT":
        return PRESET_PT_DEFAULT
    if mod == "NM":
        return PRESET_NM_DEFAULT
    if mod and mod != "CT":
        return PRESET_GENERIC_INTENSITY
    return PRESET_CT_BONE


# ---------------------------------------------------------------------------
# Volume renderer
# ---------------------------------------------------------------------------

class VolumeRenderer:
    """
    VTK volume rendering pipeline.

    Converts a SimpleITK image to ``vtkImageData`` and renders it using
    ``vtkSmartVolumeMapper`` with configurable transfer functions, global
    opacity, and window/level.

    All VTK object creation and manipulation must occur on the main thread.
    Only the data-preparation step (sitk -> numpy) may happen off-thread.
    """

    def __init__(self) -> None:
        if not vtk_available:
            raise RuntimeError(
                "VTK is not installed. 3D volume rendering requires "
                "'vtk' (pip install vtk)."
            )

        self._vtk_image: Any = None
        self._renderer: Any = vtk_mod.vtkRenderer()
        self._volume: Any = None
        # Prefer GPU-accelerated mapper; fall back to CPU ray caster on
        # systems where vtkSmartVolumeMapper is unavailable or broken
        # (e.g. Parallels virtual GPU on macOS).
        self._gpu_fallback_done = False
        try:
            self._mapper: Any = vtk_mod.vtkSmartVolumeMapper()
            self._mapper.SetRequestedRenderModeToDefault()
        except (AttributeError, TypeError):
            self._mapper = vtk_mod.vtkFixedPointVolumeRayCastMapper()
        self._mapper.SetSampleDistance(1.0)
        # Disable VTK's automatic sample distance adjustment so our explicit
        # interactive/static toggle in set_interactive_quality() takes effect
        # reliably.  With auto-adjust on, the mapper may keep a coarser
        # distance even after EndInteractionEvent.
        if hasattr(self._mapper, "SetAutoAdjustSampleDistances"):
            self._mapper.SetAutoAdjustSampleDistances(False)
        self._volume_property: Any = vtk_mod.vtkVolumeProperty()
        self._scalar_opacity: Any = vtk_mod.vtkPiecewiseFunction()
        self._color_tf: Any = vtk_mod.vtkColorTransferFunction()
        self._gradient_opacity: Any = vtk_mod.vtkPiecewiseFunction()

        self._current_preset: TransferFunctionPreset | None = None
        self._global_opacity: float = 1.0
        self._opacity_gamma: float = 1.0  # opacity-response (curve shape) exponent
        self._quality_sample_distance: float = 1.0  # static-render distance
        self._render_method: str = "Auto"
        self._gradient_opacity_enabled: bool = False
        # 0.0 = no effect (equivalent to disabled), 1.0 = full preset curve.
        # Default 0.5 blends the curve with flat-1.0 so uniform regions
        # keep 50% of their base scalar opacity instead of going to zero.
        self._gradient_opacity_strength: float = 0.5
        self._vtk_image_original: Any = None  # raw image before display smoothing
        self._display_smoothing_sigma: float = 0.0
        # Window/level expressed as an explicit width + center pair.  The
        # preset's natural width/center are captured in set_preset() so that
        # leaving the controls at their defaults reproduces the preset exactly.
        self._preset_window: float = 1.0
        self._preset_center: float = 0.0
        self._window: float = 1.0
        self._center: float = 0.0
        self._threshold_shift: float = 0.0  # shifts where opacity begins

        # Configure volume property defaults.
        self._volume_property.SetInterpolationTypeToLinear()
        self._volume_property.ShadeOn()
        self._volume_property.SetAmbient(0.3)
        self._volume_property.SetDiffuse(0.7)
        self._volume_property.SetSpecular(0.2)
        self._volume_property.SetSpecularPower(10.0)

        self._renderer.SetBackground(0.0, 0.0, 0.0)

        # SSAO state (S1/T3).
        self._ssao_pass: Any = None
        self._ssao_enabled: bool = False
        self._ssao_available: bool = False
        try:
            from vtkmodules.vtkRenderingOpenGL2 import vtkRenderStepsPass as _StepsPass
            from vtkmodules.vtkRenderingOpenGL2 import vtkSSAOPass as _SSAOPass
            self._ssao_pass_class = _SSAOPass
            self._steps_pass_class = _StepsPass
            self._ssao_available = True
        except ImportError:
            self._ssao_pass_class = None
            self._steps_pass_class = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_volume_data(
        sitk_image: Any,
        *,
        source_datasets: list[Any] | None = None,
        apply_rescale: bool = False,
    ) -> VolumeData:
        """
        Extract and prepare numpy array from a SimpleITK image.

        Thread-safe -- performs only numpy operations, no VTK API calls.
        Can be called from a background thread.

        Args:
            sitk_image: SimpleITK image to convert to a renderer-ready array.
            source_datasets: DICOM datasets in the same z-order as ``sitk_image``.
            apply_rescale: When ``True``, apply DICOM rescale slope/intercept
                to the returned 3D renderer array if every source slice has
                complete, finite, non-zero rescale metadata.
        """
        if not sitk_available:
            raise RuntimeError("SimpleITK is required to convert volumes.")
        arr = sitk.GetArrayFromImage(sitk_image)  # shape: (z, y, x)
        arr = np.ascontiguousarray(arr, dtype=np.float32)
        rescale_applied = False
        scalar_units: str | None = None
        if apply_rescale:
            arr, rescale_applied, scalar_units = _calibrate_volume_array(
                arr,
                source_datasets,
            )
        spacing = sitk_image.GetSpacing()
        origin = sitk_image.GetOrigin()
        direction = sitk_image.GetDirection()
        return VolumeData(
            array=arr,
            spacing=tuple(spacing),
            origin=tuple(origin),
            direction=tuple(direction),
            rescale_applied=rescale_applied,
            scalar_units=scalar_units,
        )

    def attach_volume(self, volume_data: VolumeData) -> None:
        """
        Create VTK objects from prepared volume data and attach to the mapper.

        Must be called on the main thread (VTK API requirement).
        """
        from vtkmodules.util import numpy_support

        arr = volume_data.array
        depth, height, width = arr.shape
        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] Volume array: shape=({depth},{height},{width})"
                f"  dtype={arr.dtype}  range=[{float(arr.min()):.1f}, {float(arr.max()):.1f}]"
            )

        flat = arr.ravel()
        vtk_data_array = numpy_support.numpy_to_vtk(
            num_array=flat,
            deep=True,
            array_type=vtk_mod.VTK_FLOAT,
        )
        vtk_data_array.SetNumberOfComponents(1)
        vtk_data_array.SetNumberOfTuples(depth * height * width)

        vtk_image = vtk_mod.vtkImageData()
        vtk_image.SetDimensions(width, height, depth)

        spacing = volume_data.spacing
        vtk_image.SetSpacing(spacing[0], spacing[1], spacing[2])

        origin = volume_data.origin
        vtk_image.SetOrigin(origin[0], origin[1], origin[2])

        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] spacing=({spacing[0]:.4f}, {spacing[1]:.4f}, {spacing[2]:.4f})"
                f"  origin=({origin[0]:.2f}, {origin[1]:.2f}, {origin[2]:.2f})"
            )

        vtk_image.GetPointData().SetScalars(vtk_data_array)
        self._vtk_image = vtk_image
        self._vtk_image_original = vtk_image  # keep raw for re-smoothing
        self._mapper.SetInputData(vtk_image)

        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] vtkImageData dims={vtk_image.GetDimensions()}"
                f"  scalar_range={vtk_image.GetScalarRange()}"
            )

        # Build the volume actor if not already created.
        if self._volume is None:
            self._volume = vtk_mod.vtkVolume()
            self._volume.SetMapper(self._mapper)
            self._volume.SetProperty(self._volume_property)
            self._renderer.AddVolume(self._volume)

        # Apply direction cosines as a user transform so that the VTK world
        # space coincides with LPS patient space (X=Left, Y=Posterior,
        # Z=Superior).  We use SetMatrix() directly -- no flip -- so that the
        # camera setup in _setup_canonical_camera() can rely on the plain LPS
        # convention (camera on -Y = anterior view, Z-up = Superior up).
        direction = volume_data.direction
        if len(direction) == 9:
            mat = vtk_mod.vtkMatrix4x4()
            mat.Identity()
            for row in range(3):
                for col in range(3):
                    mat.SetElement(row, col, direction[row * 3 + col])
            mat.SetElement(0, 3, origin[0])
            mat.SetElement(1, 3, origin[1])
            mat.SetElement(2, 3, origin[2])
            # Reset origin on the image so it is not double-applied.
            vtk_image.SetOrigin(0.0, 0.0, 0.0)

            user_transform = vtk_mod.vtkTransform()
            user_transform.SetMatrix(mat)
            self._volume.SetUserTransform(user_transform)

        if DEBUG_VOLUME_3D:
            print(f"[DEBUG-VOLUME-3D] direction cosines: {direction}")
            print(f"[DEBUG-VOLUME-3D] vtkImageData bounds: {vtk_image.GetBounds()}")

        self._renderer.ResetCamera()
        self._setup_canonical_camera()
        if DEBUG_VOLUME_3D:
            print("[DEBUG-VOLUME-3D] attach_volume complete -- volume actor attached.")
            print(f"[DEBUG-VOLUME-3D] mapper class: {self._mapper.GetClassName()}")
            print(f"[DEBUG-VOLUME-3D] mapper input: {self._mapper.GetInput()}")
            if hasattr(self._mapper, 'GetLastUsedRenderMode'):
                print(f"[DEBUG-VOLUME-3D] mapper last render mode: {self._mapper.GetLastUsedRenderMode()}")

    def set_volume(self, sitk_image: Any) -> None:
        """
        Convert a SimpleITK image to vtkImageData and set it on the mapper.

        Convenience wrapper that calls prepare_volume_data() then attach_volume().
        For better performance, call prepare_volume_data() on a background thread
        and attach_volume() on the main thread.
        """
        volume_data = self.prepare_volume_data(sitk_image)
        self.attach_volume(volume_data)

    def set_preset(self, preset: TransferFunctionPreset) -> None:
        """
        Apply a transfer-function preset (opacity + colour).

        Args:
            preset: ``TransferFunctionPreset`` to apply.
        """
        self._current_preset = preset
        # Capture the preset's natural width/center so the W/L controls have a
        # neutral identity position (window == preset_window, center ==
        # preset_center reproduces the preset unchanged).
        pts = preset.scalar_opacity
        if pts:
            preset_min = pts[0][0]
            preset_max = pts[-1][0]
            self._preset_window = max(_MIN_WINDOW, preset_max - preset_min)
            self._preset_center = (preset_min + preset_max) / 2.0
        else:
            self._preset_window = 1.0
            self._preset_center = 0.0
        self._window = self._preset_window
        self._center = self._preset_center
        self._threshold_shift = 0.0
        self._rebuild_transfer_functions()
        if DEBUG_VOLUME_3D:
            print(f"[DEBUG-VOLUME-3D] Preset applied: {preset.name}")

    def set_global_opacity(self, opacity: float) -> None:
        """
        Set a global opacity multiplier (0.0 fully transparent, 1.0 opaque).

        Args:
            opacity: Value in [0.0, 1.0].
        """
        self._global_opacity = max(0.0, min(1.0, opacity))
        self._rebuild_transfer_functions()

    def set_opacity_response(self, gamma: float) -> None:
        """
        Set the opacity-response (contrast-depth) exponent.

        This reshapes the preset's scalar-opacity *curve* independently of the
        global opacity multiplier.  Each preset opacity value ``a`` (in
        ``[0, 1]``) is raised to ``gamma`` before the global multiplier is
        applied:

            ``gamma > 1`` deepens contrast — low-opacity material fades faster,
            making dense/internal structure stand out.
            ``gamma < 1`` flattens contrast — faint material becomes more
            visible.
            ``gamma == 1`` leaves the preset curve unchanged.

        Args:
            gamma: Exponent ``> 0`` (clamped to a small positive minimum).
        """
        self._opacity_gamma = max(0.05, float(gamma))
        self._rebuild_transfer_functions()

    def set_window_level(self, window: float, center: float) -> None:
        """
        Scale and recenter the transfer-function scalar range (true W/L).

        The preset control points are linearly remapped so that the preset's
        natural width maps to *window* and the preset's natural center maps to
        *center*::

            new_val = center + (val - preset_center) * (window / preset_window)

        A *window* smaller than the preset's natural width compresses the
        transfer function (sharper contrast over a narrower range); a larger
        *window* spreads it out.  Setting ``window == preset_window`` and
        ``center == preset_center`` reproduces the preset unchanged.

        Args:
            window: Transfer-function width in scalar units (clamped > 0).
            center: Scalar value the preset center maps to.
        """
        if self._current_preset is None:
            return
        self._window = max(_MIN_WINDOW, float(window))
        self._center = float(center)
        self._rebuild_transfer_functions()

    def reset_window_level(self) -> tuple[float, float]:
        """
        Restore Window/Level to the current preset's natural range.

        Threshold, opacity response, global opacity, background, quality, and
        render method are intentionally preserved.

        Returns:
            ``(window, center)`` values after the reset.
        """
        if self._current_preset is None:
            return self._window, self._center
        self._window = self._preset_window
        self._center = self._preset_center
        self._rebuild_transfer_functions()
        return self._window, self._center

    def set_threshold(self, shift: float) -> None:
        """
        Shift the opacity threshold of the current preset.

        A positive value moves the opacity onset to higher scalar values
        (hides more low-density material).  A negative value moves it
        lower (reveals more).

        Args:
            shift: HU / intensity shift applied to all TF control points.
        """
        self._threshold_shift = shift
        self._rebuild_transfer_functions()

    def set_background(self, r: float, g: float, b: float) -> None:
        """
        Set the renderer background colour (RGB components in ``[0, 1]``).

        Disables any gradient background so the chosen flat colour is exact.
        """
        cr = max(0.0, min(1.0, float(r)))
        cg = max(0.0, min(1.0, float(g)))
        cb = max(0.0, min(1.0, float(b)))
        if hasattr(self._renderer, "GradientBackgroundOff"):
            self._renderer.GradientBackgroundOff()
        self._renderer.SetBackground(cr, cg, cb)

    def get_background(self) -> tuple[float, float, float]:
        """Return the current renderer background colour as an ``(r, g, b)`` tuple."""
        return tuple(self._renderer.GetBackground())  # type: ignore[return-value]

    def get_renderer(self) -> Any:
        """Return the ``vtkRenderer`` for embedding in a render window."""
        return self._renderer

    def reset_camera(self) -> None:
        """Reset the camera to the canonical anterior view with Superior up."""
        self._setup_canonical_camera()

    def set_view(self, view_name: str) -> None:
        """
        Set the camera to one of the standard anatomical LPS views.

        Supported names are ``Anterior``, ``Posterior``, ``Left``, ``Right``,
        ``Superior``, and ``Inferior``. Unknown names are ignored.
        """
        key = (view_name or "").strip().lower()
        view = _STANDARD_VIEW_DIRECTIONS.get(key)
        if view is None:
            _log.warning("Unknown 3D view name %r; keeping current camera.", view_name)
            return
        direction, view_up = view
        self._set_camera_direction(direction, view_up)

    def set_quality_mode(self, mode_name: str) -> None:
        """
        Set the rendering quality mode.

        Updates the static-render sample distance.  See :data:`QUALITY_MODES`.

        Args:
            mode_name: One of ``"Fast"``, ``"Normal"``, ``"High"``.
        """
        for name, dist in QUALITY_MODES:
            if name == mode_name:
                self._quality_sample_distance = dist
                self._mapper.SetSampleDistance(dist)
                self._mapper.Modified()
                return
        _log.warning("Unknown quality mode %r; keeping current.", mode_name)

    def set_render_method(self, method: str) -> None:
        """
        Request a render method: ``"Auto"``, ``"GPU"``, or ``"CPU"``.

        Only applies to ``vtkSmartVolumeMapper``; ignored for CPU-only mappers.
        """
        self._render_method = method
        mapper_class = self._mapper.GetClassName()
        if "Smart" not in mapper_class:
            return
        if method == "GPU":
            self._mapper.SetRequestedRenderModeToGPU()
        elif method == "CPU":
            self._mapper.SetRequestedRenderModeToRayCast()
        else:
            self._mapper.SetRequestedRenderModeToDefault()
        self._mapper.Modified()

    def set_custom_opacity_points(
        self, points: list[tuple[float, float]]
    ) -> None:
        """
        Replace the current preset's scalar-opacity control points with
        user-edited values and rebuild.

        The colour ramp is **not** changed — only opacity.  The internal
        preset record is mutated so that subsequent W/L / threshold /
        global-opacity changes operate on the custom points.

        Args:
            points: ``(scalar_value, opacity)`` pairs, sorted by scalar value.
        """
        if self._current_preset is None:
            return
        self._current_preset = TransferFunctionPreset(
            name=self._current_preset.name,
            scalar_opacity=list(points),
            color=self._current_preset.color,
            gradient_opacity=self._current_preset.gradient_opacity,
        )
        # Recapture natural width/center for the edited points.
        pts = self._current_preset.scalar_opacity
        if pts:
            self._preset_window = max(_MIN_WINDOW, pts[-1][0] - pts[0][0])
            self._preset_center = (pts[0][0] + pts[-1][0]) / 2.0
            self._window = self._preset_window
            self._center = self._preset_center
        self._rebuild_transfer_functions()

    def set_gradient_opacity_enabled(self, enabled: bool) -> None:
        """Enable or disable gradient opacity from the current preset.

        When enabled, the preset's gradient-opacity control points are blended
        with a flat 1.0 curve according to ``set_gradient_opacity_strength()``.
        This means uniform regions always retain at least ``(1 - strength)``
        of their scalar opacity rather than going to zero, preventing the
        all-black result that occurs on smooth/low-noise volumes.
        When disabled, gradient opacity is flat 1.0 (no effect).
        """
        self._gradient_opacity_enabled = bool(enabled)
        self._rebuild_transfer_functions()

    def set_gradient_opacity_strength(self, strength: float) -> None:
        """Set the gradient opacity effect strength.

        Blends the preset's gradient-opacity curve with a flat 1.0:
            effective(mag) = strength × curve(mag) + (1 − strength) × 1.0

        Args:
            strength: 0.0 = no effect (flat 1.0 throughout);
                      1.0 = full preset curve. Default is 0.5.
        """
        self._gradient_opacity_strength = max(0.0, min(1.0, float(strength)))
        self._rebuild_transfer_functions()

    def set_display_smoothing(self, sigma: float) -> None:
        """Apply a display-only Gaussian blur to the volume before rendering.

        Runs ``vtkImageGaussianSmooth`` on the original raw vtkImageData and
        feeds the smoothed copy to the mapper.  Sigma 0 disables smoothing
        and reverts to the original data.  Does **not** modify source DICOM
        data or the cached numpy array.

        Args:
            sigma: Standard deviation in voxel units (0 = off; 0.5–1.5 typical).
        """
        if self._vtk_image_original is None:
            return
        sigma = max(0.0, float(sigma))
        self._display_smoothing_sigma = sigma
        if sigma <= 0.0:
            self._vtk_image = self._vtk_image_original
        else:
            smoother = vtk_mod.vtkImageGaussianSmooth()
            smoother.SetInputData(self._vtk_image_original)
            smoother.SetDimensionality(3)
            # RadiusFactor controls how many sigma widths are computed.
            smoother.SetRadiusFactor(1.5)
            smoother.SetStandardDeviations(sigma, sigma, sigma)
            smoother.Update()
            self._vtk_image = smoother.GetOutput()
        self._mapper.SetInputData(self._vtk_image)
        self._mapper.Modified()

    def set_blend_mode(self, mode_name: str) -> None:
        """Set the volume rendering blend mode.

        Args:
            mode_name: One of the names from ``BLEND_MODES`` —
                ``"Composite"``, ``"Max Intensity (MIP)"``,
                or ``"Min Intensity (MinIP)"``.
        """
        for name, suffix in BLEND_MODES:
            if name == mode_name:
                method = getattr(self._mapper, f"SetBlendModeTo{suffix}", None)
                if method is not None:
                    method()
                    self._mapper.Modified()
                return
        _log.warning("Unknown blend mode %r; keeping current.", mode_name)

    def is_ssao_available(self) -> bool:
        """Return whether SSAO render passes are importable."""
        return self._ssao_available

    def set_ssao_enabled(self, enabled: bool) -> None:
        """Enable or disable Screen-Space Ambient Occlusion.

        SSAO darkens crevices and concave regions, adding depth perception.
        It requires OpenGL 3.3+; on systems where the render pass classes are
        unavailable this is a no-op.  The effect on volume rendering may vary
        by GPU and VTK build — it is offered as an experimental toggle.
        """
        if not self._ssao_available:
            return
        self._ssao_enabled = bool(enabled)
        if self._ssao_enabled:
            try:
                assert self._steps_pass_class is not None and self._ssao_pass_class is not None
                delegate = self._steps_pass_class()
                ssao = self._ssao_pass_class()
                ssao.SetDelegatePass(delegate)
                ssao.SetRadius(0.05)
                ssao.SetBias(0.005)
                ssao.SetKernelSize(64)
                self._ssao_pass = ssao
                self._renderer.SetPass(ssao)
            except Exception:
                _log.warning("SSAO pass setup failed; details withheld; disabling")
                self._ssao_enabled = False
                self._ssao_pass = None
                self._renderer.SetPass(None)
        else:
            self._ssao_pass = None
            self._renderer.SetPass(None)

    def set_lighting(
        self,
        ambient: float = 0.3,
        diffuse: float = 0.7,
        specular: float = 0.2,
        specular_power: float = 10.0,
    ) -> None:
        """Set shading parameters on the volume property."""
        self._volume_property.SetAmbient(max(0.0, min(1.0, ambient)))
        self._volume_property.SetDiffuse(max(0.0, min(1.0, diffuse)))
        self._volume_property.SetSpecular(max(0.0, min(1.0, specular)))
        self._volume_property.SetSpecularPower(max(1.0, min(128.0, specular_power)))

    def get_lighting(self) -> tuple[float, float, float, float]:
        """Return ``(ambient, diffuse, specular, specular_power)``."""
        return (
            self._volume_property.GetAmbient(),
            self._volume_property.GetDiffuse(),
            self._volume_property.GetSpecular(),
            self._volume_property.GetSpecularPower(),
        )

    def set_interpolation(self, linear: bool) -> None:
        """Switch between linear and nearest-neighbour voxel interpolation."""
        if linear:
            self._volume_property.SetInterpolationTypeToLinear()
        else:
            self._volume_property.SetInterpolationTypeToNearest()

    # ------------------------------------------------------------------
    # Crop / clipping planes (T25/T26)
    # ------------------------------------------------------------------

    def set_cropping(self, planes: list[Any] | None = None) -> None:
        """
        Apply clipping planes to the volume mapper for ROI cropping.

        Args:
            planes: A list of ``vtkPlane`` objects.  Pass ``None`` or an empty
                list to remove all clipping and show the full volume.
        """
        self._mapper.RemoveAllClippingPlanes()
        if planes:
            for plane in planes:
                self._mapper.AddClippingPlane(plane)
        self._mapper.Modified()

    def clear_cropping(self) -> None:
        """Remove all clipping planes (show the full volume)."""
        self.set_cropping(None)

    def set_interactive_quality(self, low: bool) -> None:
        """Switch sample distance for interactive (coarse) vs static (fine) rendering."""
        if low:
            self._mapper.SetSampleDistance(max(self._quality_sample_distance * 2.0, 2.0))
        else:
            self._mapper.SetSampleDistance(self._quality_sample_distance)
        self._mapper.Modified()

    def check_gpu_fallback(self, render_window: Any) -> bool:
        """Check if GPU rendering produced a blank frame and fall back to CPU.

        Call once after the first Render(). Reads back pixels from the render
        window; if the image is entirely black (GPU silently failed, common on
        Parallels / virtual GPUs), switches the mapper to CPU ray-cast mode
        and re-renders.

        Returns ``True`` if a fallback was triggered.
        """
        if self._gpu_fallback_done:
            return False
        self._gpu_fallback_done = True

        # Only applies to vtkSmartVolumeMapper.
        mapper_class = self._mapper.GetClassName()
        if "Smart" not in mapper_class:
            return False

        # Check what mode was actually used.
        if not hasattr(self._mapper, "GetLastUsedRenderMode"):
            return False
        mode = self._mapper.GetLastUsedRenderMode()
        # mode 1 = CPU ray cast — already on CPU, nothing to fix.
        if mode == 1:
            if DEBUG_VOLUME_3D:
                print("[DEBUG-VOLUME-3D] GPU fallback check: already on CPU ray cast, skipping.")
            return False

        # Read back pixels and check if the frame is all-black.
        try:
            w2i = vtk_mod.vtkWindowToImageFilter()
            w2i.SetInput(render_window)
            w2i.SetInputBufferTypeToRGB()
            w2i.Update()
            img = w2i.GetOutput()
            dims = img.GetDimensions()
            n_pixels = dims[0] * dims[1]
            if n_pixels == 0:
                return False
            scalars = img.GetPointData().GetScalars()
            if scalars is None:
                return False
            # Check a sample of pixels for any non-zero value.
            n_tuples = scalars.GetNumberOfTuples()
            step = max(1, n_tuples // 200)
            all_black = True
            for i in range(0, n_tuples, step):
                r, g, b = scalars.GetTuple3(i)
                if r > 0 or g > 0 or b > 0:
                    all_black = False
                    break
            if not all_black:
                if DEBUG_VOLUME_3D:
                    print("[DEBUG-VOLUME-3D] GPU fallback check: frame has content, GPU OK.")
                return False
        except Exception:
            # If readback itself fails, try CPU fallback anyway.
            pass

        # GPU produced a black frame — switch to CPU ray casting.
        _log.warning(
            "GPU volume rendering produced a blank frame (render mode %d). "
            "Falling back to CPU ray casting.", mode,
        )
        if DEBUG_VOLUME_3D:
            print(f"[DEBUG-VOLUME-3D] GPU FALLBACK: mode {mode} produced black frame, switching to CPU.")
        self._mapper.SetRequestedRenderModeToRayCast()
        render_window.Render()
        if DEBUG_VOLUME_3D:
            new_mode = self._mapper.GetLastUsedRenderMode()
            print(f"[DEBUG-VOLUME-3D] GPU FALLBACK: new render mode = {new_mode}")
        return True

    def cleanup(self) -> None:
        """Release VTK objects to free GPU / CPU memory."""
        if self._volume is not None:
            self._renderer.RemoveVolume(self._volume)
        self._mapper.RemoveAllInputs()
        self._vtk_image = None
        self._vtk_image_original = None
        self._volume = None
        if DEBUG_VOLUME_3D:
            print("[DEBUG-VOLUME-3D] VolumeRenderer cleanup complete.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_camera_direction(
        self,
        direction: tuple[float, float, float],
        view_up: tuple[float, float, float],
    ) -> None:
        """Position the camera on a patient-axis direction and frame the volume."""
        bounds = list(self._renderer.ComputeVisiblePropBounds())
        # Guard: empty scene returns all zeros.
        # VTK ComputeVisiblePropBounds all-zero is empty-scene sentinel
        if all(v == 0.0 for v in bounds):  # NOSONAR(S1244)
            self._renderer.ResetCamera()
            return
        cx = (bounds[0] + bounds[1]) * 0.5
        cy = (bounds[2] + bounds[3]) * 0.5
        cz = (bounds[4] + bounds[5]) * 0.5
        size = max(
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4],
            1.0,
        )
        cam = self._renderer.GetActiveCamera()
        cam.SetFocalPoint(cx, cy, cz)
        # ResetCamera refines the distance to frame all visible props while
        # preserving this view-plane normal.
        cam.SetPosition(
            cx + direction[0] * size,
            cy + direction[1] * size,
            cz + direction[2] * size,
        )
        cam.SetViewUp(*view_up)
        self._renderer.ResetCamera()
        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] _set_camera_direction: "
                f"center=({cx:.1f},{cy:.1f},{cz:.1f})  size={size:.1f}  "
                f"direction={direction}  view_up={view_up}"
            )

    def _setup_canonical_camera(self) -> None:
        """
        Position the camera for a front (anterior) view with Superior up.

        In LPS world space — which the direction transform maps our volume
        into — X is Left, Y is Posterior, Z is Superior.  Placing the
        camera on the −Y axis and setting view-up to +Z gives an anterior
        view with the patient's head at the top, matching clinical convention.

        ``ResetCamera()`` is called last so VTK adjusts the viewing distance
        to frame the volume while preserving the direction just set.
        """
        bounds = list(self._renderer.ComputeVisiblePropBounds())
        # Guard: empty scene returns all zeros.
        # VTK ComputeVisiblePropBounds all-zero is empty-scene sentinel
        if all(v == 0.0 for v in bounds):  # NOSONAR(S1244)
            self._renderer.ResetCamera()
            return
        cx = (bounds[0] + bounds[1]) * 0.5
        cy = (bounds[2] + bounds[3]) * 0.5
        cz = (bounds[4] + bounds[5]) * 0.5
        size = max(
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4],
            1.0,
        )
        cam = self._renderer.GetActiveCamera()
        cam.SetFocalPoint(cx, cy, cz)
        # Initial position: 1× size along −Y (anterior side); ResetCamera
        # will fine-tune the distance to frame the volume exactly.
        cam.SetPosition(cx, cy - size, cz)
        cam.SetViewUp(0.0, 0.0, 1.0)
        self._renderer.ResetCamera()
        if DEBUG_VOLUME_3D:
            print(
                f"[DEBUG-VOLUME-3D] _setup_canonical_camera: "
                f"center=({cx:.1f},{cy:.1f},{cz:.1f})  size={size:.1f}"
            )

    def _rebuild_transfer_functions(self) -> None:
        """Rebuild scalar opacity, colour, and gradient opacity from the current preset."""
        preset = self._current_preset
        if preset is None:
            return

        alpha = self._global_opacity
        gamma = self._opacity_gamma
        scale = self._window / self._preset_window if self._preset_window else 1.0

        def remap(val: float) -> float:
            """Map a preset scalar value through the current width/center/threshold."""
            return self._center + (val - self._preset_center) * scale + self._threshold_shift

        # Scalar opacity: remap position, reshape opacity by the response
        # exponent, then apply the global multiplier.
        self._scalar_opacity.RemoveAllPoints()
        for val, opa in preset.scalar_opacity:
            shaped = (max(0.0, min(1.0, opa)) ** gamma) * alpha
            self._scalar_opacity.AddPoint(remap(val), shaped)

        # Colour transfer function (position only — colour is not reshaped).
        self._color_tf.RemoveAllPoints()
        for val, r, g, b in preset.color:
            self._color_tf.AddRGBPoint(remap(val), r, g, b)

        # Gradient opacity — only applied when explicitly enabled.  When
        # disabled, a flat 1.0 is used so uniform regions remain visible.
        # When enabled, blend the preset curve with flat 1.0 using
        # _gradient_opacity_strength so that uniform/smooth regions keep
        # (1-strength) × 1.0 of their base opacity rather than going to zero.
        self._gradient_opacity.RemoveAllPoints()
        if self._gradient_opacity_enabled and preset.gradient_opacity:
            s = self._gradient_opacity_strength
            for gval, gopa in preset.gradient_opacity:
                blended = s * gopa + (1.0 - s) * 1.0
                self._gradient_opacity.AddPoint(gval, blended)
        else:
            self._gradient_opacity.AddPoint(0.0, 1.0)
            self._gradient_opacity.AddPoint(255.0, 1.0)

        self._volume_property.SetScalarOpacity(self._scalar_opacity)
        self._volume_property.SetColor(self._color_tf)
        self._volume_property.SetGradientOpacity(self._gradient_opacity)

        if DEBUG_VOLUME_3D:
            so_range = self._scalar_opacity.GetRange()
            ct_range = self._color_tf.GetRange()
            print(f"[DEBUG-VOLUME-3D] TF rebuilt: scalar_opacity range={so_range}  "
                  f"color_tf range={ct_range}  global_opacity={alpha}  gamma={gamma}  "
                  f"window={self._window:.3f}  center={self._center:.3f}  "
                  f"threshold={self._threshold_shift:.3f}")
            print(f"[DEBUG-VOLUME-3D] scalar_opacity num_points={self._scalar_opacity.GetSize()}")
            print(f"[DEBUG-VOLUME-3D] color_tf num_points={self._color_tf.GetSize()}")
