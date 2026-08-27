"""VTK-free preparation of arrays and metadata for volume rendering.

The functions in this module run on the background build thread.  They turn a
SimpleITK volume into an owned ``float32`` NumPy array, optionally calibrate
per-slice DICOM rescale values, and record the memory/downsampling provenance
that the VTK renderer later displays.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import Any

import numpy as np

from core.volume_render_quality import (
    build_full_coverage_scalar_histogram,
    compute_auto_downsample_factor,
    default_render_budget_bytes,
    estimate_render_peak_bytes,
)

_log = logging.getLogger(__name__)


# SimpleITK is optional at import time so that pure renderer-policy modules and
# tests can load without the package.  The public preparation function raises a
# clear error if called when it is unavailable.
sitk: Any = None
sitk_available: bool = False
try:
    import SimpleITK as _sitk

    sitk = _sitk
    sitk_available = True
except ImportError:
    pass


@dataclass
class VolumeData:
    """Thread-safe prepared array plus spatial and memory metadata."""

    array: np.ndarray  # contiguous float32, shape (depth, height, width)
    spacing: tuple[float, ...]  # (sx, sy, sz)
    origin: tuple[float, ...]  # (ox, oy, oz)
    direction: tuple[float, ...]  # 9 floats (3x3 direction cosine matrix)
    rescale_applied: bool = False
    scalar_units: str | None = None
    # ``None`` is deliberately fail-safe: a black frame then remains eligible
    # for GPU fallback rather than being classified as an expected blank frame.
    scalar_occupancy: list[tuple[float, float, int]] | None = None
    source_dimensions: tuple[int, int, int] | None = None
    downsample_factor: int = 1
    memory_budget_bytes: int | None = None
    estimated_peak_bytes: int | None = None


# ``MprVolume`` retains a float32 SimpleITK image and the source DICOM objects
# can retain decoded pixels.  The renderer keeps its shallow NumPy/VTK input
# plus, once enabled, a full-size smoothing output.  Account for both groups
# before allocating the renderer array; VTK shares the NumPy data (deep=False).
_SOURCE_LIVE_BYTES_PER_VOXEL = 8
_RENDER_LIVE_BYTES_PER_VOXEL = 4
_RENDER_PEAK_OVERHEAD = 2.0  # input + optional vtkImageGaussianSmooth output


def _available_system_memory_bytes() -> int | None:
    """Return currently available physical RAM without adding a dependency.

    Failure is deliberately represented as ``None`` so the pure budget policy
    selects its documented conservative minimum.
    """
    try:
        if os.name == "nt":
            class _MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            memory_status = _MemoryStatus()
            memory_status.length = ctypes.sizeof(memory_status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):  # type: ignore[attr-defined]
                available = int(memory_status.available_physical)
                return available if available > 0 else None

        system = platform.system()
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as memory_info:
                for line in memory_info:
                    if line.startswith("MemAvailable:"):
                        fields = line.split()
                        available = int(fields[1]) * 1024
                        return available if available > 0 else None

        if system == "Darwin":
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=2, check=False
            )
            if result.returncode != 0:
                return None
            match = re.search(r"page size of (\d+) bytes", result.stdout)
            if match is None:
                return None
            page_size = int(match.group(1))
            available_pages = 0
            # ``Pages speculative`` and ``Pages purgeable`` can overlap with
            # inactive pages.  Use a conservative disjoint set instead.
            for line in result.stdout.splitlines():
                if ":" not in line:
                    continue
                label, raw_count = line.split(":", 1)
                if label in {"Pages free", "Pages inactive"}:
                    available_pages += int(raw_count.strip().rstrip("."))
            available = available_pages * page_size
            return available if available > 0 else None
    except (AttributeError, OSError, ValueError, subprocess.SubprocessError):
        return None
    return None


def _calibrate_volume_array(
    arr: np.ndarray,
    source_datasets: list[Any] | None,
) -> tuple[np.ndarray, bool, str | None]:
    """Calibrate an owned float32 array in place, or return it unmodified.

    A read-only preflight validates every slice before any mutation.  It avoids
    partial calibration and proves that each ``slope * value + intercept``
    operation remains finite in float32.  The DICOM dependency remains lazy to
    avoid a top-level dependency cycle.
    """
    if not source_datasets or len(source_datasets) != arr.shape[0]:
        return arr, False, None

    assert arr.flags.owndata, (
        "_calibrate_volume_array requires an owned array; got a view "
        f"(owndata={arr.flags.owndata}, base={arr.base!r})"
    )
    assert arr.flags.c_contiguous, (
        "_calibrate_volume_array requires a C-contiguous array; "
        f"got contiguous={arr.flags.c_contiguous}"
    )
    assert arr.dtype == np.float32, (
        f"_calibrate_volume_array requires float32; got {arr.dtype}"
    )

    from core.dicom_rescale import get_rescale_parameters, infer_rescale_type

    f32_max = float(np.finfo(np.float32).max)
    params: list[tuple[float, float, str | None]] = []
    units: set[str] = set()
    for z_index, dataset in enumerate(source_datasets):
        slope, intercept, rescale_type = get_rescale_parameters(dataset)
        if slope is None or intercept is None:
            return arr, False, None
        if not np.isfinite(slope) or not np.isfinite(intercept) or slope == 0.0:
            return arr, False, None

        scalar_units = infer_rescale_type(dataset, slope, intercept, rescale_type)
        if scalar_units:
            units.add(str(scalar_units))
        params.append((float(slope), float(intercept), scalar_units))

        lo = float(arr[z_index].min())
        hi = float(arr[z_index].max())
        worst_case = max(abs(lo), abs(hi)) * abs(float(slope)) + abs(float(intercept))
        if not np.isfinite(worst_case) or worst_case >= f32_max:
            _log.warning(
                "Slice %d calibration would overflow float32 "
                "(worst-case |%.3g| >= %.3g); falling back to raw.",
                z_index,
                worst_case,
                f32_max,
            )
            return arr, False, None

    if len(units) > 1:
        _log.info(
            "Mixed rescale units across slices (%s); falling back to raw values.", units
        )
        return arr, False, None

    for z_index, (slope, intercept, _scalar_units) in enumerate(params):
        slice_view = arr[z_index]
        slice_view *= slope
        slice_view += intercept

    resolved_units = next(iter(units)) if len(units) == 1 else None
    return arr, True, resolved_units


def prepare_volume_data(
    sitk_image: Any,
    *,
    source_datasets: list[Any] | None = None,
    apply_rescale: bool = False,
) -> VolumeData:
    """Prepare an owned, renderer-ready array on a background thread.

    The source is strided before allocating a float32 renderer buffer.  This
    prevents the memory guard from first materialising a full-size copy only to
    downsample it afterward.  The output buffer is always uniquely owned and
    C-contiguous before optional in-place DICOM calibration.
    """
    if not sitk_available:
        raise RuntimeError("SimpleITK is required to convert volumes.")
    source_size = sitk_image.GetSize()
    if len(source_size) != 3:
        raise ValueError("3D volume input must have exactly three dimensions")
    source_dimensions: tuple[int, int, int] = (
        int(source_size[0]),
        int(source_size[1]),
        int(source_size[2]),
    )
    source_voxels = source_dimensions[0] * source_dimensions[1] * source_dimensions[2]
    available_bytes = _available_system_memory_bytes()
    fixed_source_bytes = source_voxels * _SOURCE_LIVE_BYTES_PER_VOXEL
    downsample_factor = compute_auto_downsample_factor(
        source_dimensions,
        available_bytes=available_bytes or 0,
        bytes_per_voxel=_RENDER_LIVE_BYTES_PER_VOXEL,
        overhead_factor=_RENDER_PEAK_OVERHEAD,
        fixed_bytes=fixed_source_bytes,
    )

    get_array_view = getattr(sitk, "GetArrayViewFromImage", None)
    source_array = (
        sitk.GetArrayFromImage(sitk_image)
        if get_array_view is None
        else get_array_view(sitk_image)
    )
    decimated = source_array[
        ::downsample_factor,
        ::downsample_factor,
        ::downsample_factor,
    ]
    # ``np.array(..., copy=True)`` ensures calibration cannot mutate a
    # SimpleITK-owned buffer even when the source is already float32.
    arr = np.array(decimated, dtype=np.float32, order="C", copy=True)
    selected_datasets = (
        source_datasets[::downsample_factor] if source_datasets is not None else None
    )
    rescale_applied = False
    scalar_units: str | None = None
    if apply_rescale:
        arr, rescale_applied, scalar_units = _calibrate_volume_array(
            arr, selected_datasets
        )

    scalar_occupancy = build_full_coverage_scalar_histogram(arr)
    spacing = tuple(
        float(value) * downsample_factor for value in sitk_image.GetSpacing()
    )
    output_dimensions = (int(arr.shape[2]), int(arr.shape[1]), int(arr.shape[0]))
    estimated_peak_bytes = estimate_render_peak_bytes(
        output_dimensions,
        bytes_per_voxel=_RENDER_LIVE_BYTES_PER_VOXEL,
        overhead_factor=_RENDER_PEAK_OVERHEAD,
    ) + fixed_source_bytes
    return VolumeData(
        array=arr,
        spacing=spacing,
        origin=tuple(sitk_image.GetOrigin()),
        direction=tuple(sitk_image.GetDirection()),
        rescale_applied=rescale_applied,
        scalar_units=scalar_units,
        scalar_occupancy=scalar_occupancy,
        source_dimensions=source_dimensions,
        downsample_factor=downsample_factor,
        memory_budget_bytes=default_render_budget_bytes(available_bytes or 0),
        estimated_peak_bytes=estimated_peak_bytes,
    )
