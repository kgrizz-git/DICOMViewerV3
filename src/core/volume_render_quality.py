"""Pure policy helpers for responsive 3D volume-render detail selection."""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import Enum
from typing import Any, cast

import numpy as np

MEBIBYTE = 1024 * 1024
GIBIBYTE = 1024 * MEBIBYTE
LARGE_VOLUME_BYTES = 64 * MEBIBYTE
HUGE_VOLUME_BYTES = 512 * MEBIBYTE
AUTO_REFINE_BUDGET_MS = 200.0

# ---------------------------------------------------------------------------
# Automatic integer downsample-factor policy
# ---------------------------------------------------------------------------

# Target render budget = min(MAX_BUDGET_BYTES, DEFAULT_BUDGET_FRACTION * available
# RAM), never below MIN_DOWNSAMPLE_BUDGET_BYTES. The helper itself is VTK-free;
# callers pass available_bytes explicitly so unit tests are deterministic.
MAX_BUDGET_BYTES = int(2.5 * GIBIBYTE)
DEFAULT_BUDGET_FRACTION = 0.20
MIN_DOWNSAMPLE_BUDGET_BYTES = 512 * MEBIBYTE

# Default render-peak multiplier over the raw voxel buffer. A volume render
# pipeline typically holds the input staging copy plus working buffers
# (gradient tables, partial compositing) simultaneously, so the peak is
# larger than the input alone. Callers may override per pipeline.
DEFAULT_PEAK_OVERHEAD_FACTOR = 2.0

# Opacity below this is treated as fully transparent for "visible frame" purposes.
_EPS_OPACITY = 1e-4
# Any colour channel at/above this contributes a non-black contribution.
_EPS_COLOR = 1e-4
_SCALAR_HISTOGRAM_BINS = 4096


class GpuFallbackOutcome(Enum):
    """Result of checking whether a black first frame requires CPU fallback."""

    FELL_BACK = "fell_back"
    GPU_OK_VISIBLE = "gpu_ok_visible"
    EXPECTED_BLANK = "expected_blank"


def build_full_coverage_scalar_histogram(
    values: np.ndarray,
    *,
    bins: int = _SCALAR_HISTOGRAM_BINS,
) -> list[tuple[float, float, int]] | None:
    """Summarize all finite scalar values in bounded memory.

    Each result row is ``(lower_bound, upper_bound, count)``.  The caller can
    conservatively test a transfer function against the full occupied range of
    every bin: when a bin is ambiguous it must be treated as potentially
    visible.  This avoids a full-size ``np.unique`` allocation while retaining
    the fail-safe direction required for GPU-fallback detection.

    The source is traversed in chunks and never strided, so sparse opaque
    content cannot be omitted.  ``None`` means the input was malformed or
    non-finite and callers must assume a visible frame.
    """
    if not isinstance(values, np.ndarray) or values.size <= 0 or bins <= 0:
        return None

    flat = values.reshape(-1)
    chunk_size = 1_048_576
    lower = math.inf
    upper = -math.inf
    for start in range(0, flat.size, chunk_size):
        chunk = flat[start : start + chunk_size]
        if not np.all(np.isfinite(chunk)):
            return None
        lower = min(lower, float(chunk.min()))
        upper = max(upper, float(chunk.max()))

    if not math.isfinite(lower) or not math.isfinite(upper):
        return None
    if lower == upper:
        return [(lower, upper, int(flat.size))]

    counts = np.zeros(bins, dtype=np.int64)
    for start in range(0, flat.size, chunk_size):
        chunk = flat[start : start + chunk_size]
        chunk_counts, _ = np.histogram(chunk, bins=bins, range=(lower, upper))
        counts += chunk_counts

    width = (upper - lower) / bins
    return [
        (lower + index * width, lower + (index + 1) * width, int(count))
        for index, count in enumerate(counts)
        if count > 0
    ]


def estimate_volume_megabytes(dims: tuple[int, int, int], *, bytes_per_voxel: int = 4) -> float:
    """Return the renderer input size in MiB for valid volume dimensions."""
    return (max(0, dims[0]) * max(0, dims[1]) * max(0, dims[2]) * bytes_per_voxel) / MEBIBYTE


def auto_detail_cap_index(volume_bytes: int | None, *, mode_count: int) -> int:
    """Return the maximum Auto Detail index suitable for the input size."""
    if mode_count <= 0:
        return 0
    if volume_bytes is None:
        return mode_count - 1
    if volume_bytes >= HUGE_VOLUME_BYTES:
        return 0  # Fast
    if volume_bytes >= LARGE_VOLUME_BYTES:
        return min(1, mode_count - 1)  # Normal
    return mode_count - 1


def should_auto_refine(*, preview_elapsed_ms: float, gpu_fallback_used: bool) -> bool:
    """Allow an automatic fine render only when the preview was responsive."""
    return not gpu_fallback_used and preview_elapsed_ms <= AUTO_REFINE_BUDGET_MS


def default_render_budget_bytes(available_bytes: int) -> int:
    """Return the render budget for a given amount of available RAM.

    Policy: ``min(2.5 GiB, 20% of available)``, clamped to a 512 MiB floor.
    Pure and deterministic — the caller is responsible for supplying the
    platform's "available RAM" number (e.g. from ``os.sysconf``/``GlobalMemoryStatusEx``
    or ``psutil``), keeping this helper free of any OS probing.
    """
    if available_bytes <= 0:
        return MIN_DOWNSAMPLE_BUDGET_BYTES
    budget = int(available_bytes * DEFAULT_BUDGET_FRACTION)
    if budget > MAX_BUDGET_BYTES:
        budget = MAX_BUDGET_BYTES
    if budget < MIN_DOWNSAMPLE_BUDGET_BYTES:
        budget = MIN_DOWNSAMPLE_BUDGET_BYTES
    return budget


def estimate_render_peak_bytes(
    dims: tuple[int, int, int],
    *,
    bytes_per_voxel: int = 4,
    overhead_factor: float = DEFAULT_PEAK_OVERHEAD_FACTOR,
) -> int:
    """Predict peak render memory (bytes) for a volume *before* allocating.

    VTK-free: this is the raw voxel-buffer size multiplied by an overhead
    factor that accounts for staging copies and working buffers the render
    pipeline holds simultaneously. Callers with a different pipeline may
    pass their own ``overhead_factor``; ``1.0`` reduces to the input size.
    """
    voxel_bytes = (
        max(0, dims[0]) * max(0, dims[1]) * max(0, dims[2]) * max(0, bytes_per_voxel)
    )
    return int(voxel_bytes * max(0.0, overhead_factor))


def _downsampled_dims(
    dims: tuple[int, int, int], factor: int, min_dim: int,
) -> tuple[int, int, int]:
    """Return the volume dimensions after strided downsampling by ``factor``.

    A stride of ``f`` applied via ``arr[::f]`` keeps every ``f``-th voxel,
    producing ``ceil(dim / f)`` samples — *not* ``floor``. The peak must be
    estimated from the actual retained count, so we use ``ceil`` here; using
    ``floor`` would under-estimate the buffer and risk an over-commit.
    """
    return (
        max(min_dim, math.ceil(dims[0] / factor)),
        max(min_dim, math.ceil(dims[1] / factor)),
        max(min_dim, math.ceil(dims[2] / factor)),
    )


def compute_auto_downsample_factor(
    dims: tuple[int, int, int],
    *,
    available_bytes: int,
    bytes_per_voxel: int = 4,
    overhead_factor: float = DEFAULT_PEAK_OVERHEAD_FACTOR,
    fixed_bytes: int = 0,
    min_dim: int = 1,
) -> int:
    """Return the smallest integer downsample factor ≥ 1 whose peak fits.

    Chooses an automatic integer downsample factor so the *predicted render
    peak* (input + pipeline overhead + any fixed live buffers) stays within
    the render budget derived from ``available_bytes``. Returns ``1`` (no
    downsample) whenever the native volume already fits.

    The comparison performed for every candidate ``f`` is::

        estimate_render_peak_bytes(downsampled_dims(dims, f), ...)
        + fixed_bytes  <=  budget

    ``fixed_bytes`` lets the renderer add a conservative, *unchanging* cost
    that does not shrink with downsampling — e.g. the live source buffer the
    pipeline holds alongside the renderer/smoothing buffers. It is added to
    every candidate (including the native ``f = 1`` check) so the policy
    accounts for it uniformly.

    Pure and deterministic: callers pass ``available_bytes`` explicitly so
    unit tests need no OS-memory probing. The budget itself is computed via
    :func:`default_render_budget_bytes`.

    Args:
        dims: ``(x, y, z)`` voxel dimensions of the source volume.
        available_bytes: currently available RAM supplied by the caller.
        bytes_per_voxel: scalar size of the renderer input (default 4, float32).
        overhead_factor: peak-over-input multiplier forwarded to
            :func:`estimate_render_peak_bytes`.
        fixed_bytes: constant bytes added to *every* candidate peak
            (default 0). Use this for live buffers whose size is independent
            of the downsample factor.
        min_dim: no dimension is allowed to drop below this after downsampling.

    Returns:
        Integer downsample factor ``>= 1``. A factor of ``f`` reduces each
        dimension to ``ceil(dim / f)`` (the count a ``arr[::f]`` stride
        retains).
    """
    if min_dim < 1:
        min_dim = 1
    # A zero- or negative-sized volume needs no downsampling.
    if dims[0] <= 0 or dims[1] <= 0 or dims[2] <= 0:
        return 1
    if fixed_bytes < 0:
        fixed_bytes = 0

    budget = default_render_budget_bytes(available_bytes)

    # Native (factor 1) already fits → no downsampling required.
    native_peak = estimate_render_peak_bytes(
        dims,
        bytes_per_voxel=bytes_per_voxel,
        overhead_factor=overhead_factor,
    )
    if native_peak + fixed_bytes <= budget:
        return 1

    # Native does not fit. Walk upward and return on the *first* factor whose
    # peak fits — that is the smallest factor that fits. Track the deepest
    # reachable factor so that, if nothing fits even at min_dim, we return a
    # best-effort maximum rather than the non-fitting 1.
    factor = 1
    best = 1
    while True:
        next_factor = factor + 1
        candidate = _downsampled_dims(dims, next_factor, min_dim)
        current = _downsampled_dims(dims, factor, min_dim)
        if candidate == current:
            # All dimensions clamped at min_dim — no further reduction.
            break
        candidate_peak = estimate_render_peak_bytes(
            candidate,
            bytes_per_voxel=bytes_per_voxel,
            overhead_factor=overhead_factor,
        )
        if candidate_peak + fixed_bytes <= budget:
            return next_factor
        factor = next_factor
        best = next_factor
    return best


# ---------------------------------------------------------------------------
# Transfer-function evaluation
# ---------------------------------------------------------------------------

def _is_finite_number(x: object) -> bool:
    """Return True iff ``x`` is a finite float/int (not NaN/inf)."""
    try:
        fx = float(cast(Any, x))
    except (TypeError, ValueError):
        return False
    return math.isfinite(fx)


def _validate_tf(points: object, min_channels: int) -> bool | None:
    """Validate a transfer-function control-point list.

    Returns:
        ``True`` if the list is well-formed (each row is a tuple/list of at
        least ``min_channels + 1`` finite numbers, domain values sorted and
        unique). ``False`` if it is empty (unknown → caller fails safe).
        ``None`` if it is malformed (wrong row shape, non-finite values,
        unsorted domain) — also a fail-safe "assume visible" signal.
    """
    if not isinstance(points, list):
        return None
    if not points:
        return False
    prev_x = None
    for row in points:
        if not isinstance(row, (tuple, list)) or len(row) < min_channels + 1:
            return None
        # Every coordinate we will read must be a finite number.
        for coord in row[: min_channels + 1]:
            if not _is_finite_number(coord):
                return None
        x = float(cast(Any, row[0]))
        if prev_x is not None and x <= prev_x:
            return None
        prev_x = x
    return True


def _eval_piecewise(
    points: list[tuple[float, ...]], value: float, channel: int,
) -> float:
    """Linearly interpolate a single channel of a piecewise function.

    ``points`` is a list of rows where row[0] is the domain value and
    row[channel] is the channel to evaluate. Returns 0.0 for empty input and
    clamps out-of-range queries to the nearest endpoint (constant
    extrapolation), matching VTK's ``vtkPiecewiseFunction`` / color TF
    behaviour below/above the defined range.
    """
    if not points:
        return 0.0
    xs = [p[0] for p in points]
    # Below the first control point.
    if value <= xs[0]:
        return float(points[0][channel])
    # Above the last control point.
    if value >= xs[-1]:
        return float(points[-1][channel])
    # Find the bracketing segment.
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x0 <= value <= x1:
            if x1 == x0:
                return float(points[i][channel])
            t = (value - x0) / (x1 - x0)
            y0 = float(points[i][channel])
            y1 = float(points[i + 1][channel])
            return y0 + t * (y1 - y0)
    return float(points[-1][channel])


def _eval_scalar_opacity(
    scalar_opacity: list[tuple[float, float]], value: float,
) -> float:
    """Evaluate the scalar-opacity transfer function at ``value``."""
    return _eval_piecewise(scalar_opacity, value, channel=1)


def _eval_color(
    color_tf: list[tuple[float, float, float, float]], value: float,
) -> tuple[float, float, float]:
    """Evaluate the RGB colour transfer function at ``value``."""
    r = _eval_piecewise(color_tf, value, channel=1)
    g = _eval_piecewise(color_tf, value, channel=2)
    b = _eval_piecewise(color_tf, value, channel=3)
    return (r, g, b)


def _interval_may_be_nonblank(
    scalar_opacity: list[tuple[float, float]],
    color_tf: list[tuple[float, float, float, float]],
    lower: float,
    upper: float,
) -> bool:
    """Conservatively check whether any scalar in an occupied bin is visible.

    This returns ``True`` when either transfer function could be nonzero in
    the bin.  Their nonzero regions may not overlap, but treating that case as
    visible is intentional: it can produce an unnecessary CPU fallback, never
    the worse false ``EXPECTED_BLANK`` outcome.
    """
    points = [lower, upper]
    points.extend(x for x, _ in scalar_opacity if lower < x < upper)
    points.extend(x for x, *_ in color_tf if lower < x < upper)
    scalar_nonzero = any(
        _eval_scalar_opacity(scalar_opacity, value) > _EPS_OPACITY
        for value in points
    )
    color_nonblack = any(
        any(channel > _EPS_COLOR for channel in _eval_color(color_tf, value))
        for value in points
    )
    return scalar_nonzero and color_nonblack


def _parse_occupied_bin(row: object) -> tuple[float, float, int] | None:
    """Return validated ``(lower, upper, count)`` or ``None`` if malformed.

    A non-positive count is valid but unoccupied; callers retain it so they can
    distinguish that case from malformed input, which must fail safe.
    """
    if not isinstance(row, (tuple, list)):
        return None
    if len(row) == 2:
        value, count = row
        lower = upper = value
    elif len(row) == 3:
        lower, upper, count = row
    else:
        return None
    if not _is_finite_number(lower) or not _is_finite_number(upper):
        return None
    lower_float = float(cast(Any, lower))
    upper_float = float(cast(Any, upper))
    if lower_float > upper_float:
        return None
    try:
        count_float = float(cast(Any, count))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(count_float) or not count_float.is_integer():
        return None
    return lower_float, upper_float, int(count_float)


def frame_expected_nonblank(
    scalar_opacity: list[tuple[float, float]] | None,
    color_tf: list[tuple[float, float, float, float]] | None,
    occupancy: object,
) -> bool:
    """Return ``True`` if the occupied scalar values can produce a visible frame.

    Pure, VTK-free helper used by ``check_gpu_fallback()`` to decide whether a
    black frame means "the GPU failed" or "nothing was supposed to be visible".

    The decision is driven from a **full-coverage histogram** (``occupancy``),
    not a strided sample, so sparse opaque content (fiducials, seeds, clips)
    cannot be missed. A strided sample that misses sparse opaque voxels would
    wrongly conclude EXPECTED_BLANK and suppress a *genuine* CPU fallback —
    the worse error.

    Fail-safe: on malformed / unknown input, returns ``True`` (expected
    visible). A false EXPECTED_BLANK suppresses a real fallback and leaves the
    user on a silently-broken GPU path; err toward "visible" whenever the
    inputs do not unambiguously prove every occupied voxel maps to a
    transparent-or-black result. This includes:
      - ``None`` / empty transfer functions
      - control-point rows of the wrong shape, non-finite values, or an
        unsorted / non-unique domain
      - an empty occupancy, or one with no positive counts
      - non-finite scalar values in the occupancy

    Args:
        scalar_opacity: Control points ``(scalar_value, opacity)`` of the
            piecewise scalar-opacity function. ``None`` / empty is treated as
            "unknown" → returns ``True``.
        color_tf: Control points ``(scalar_value, r, g, b)`` of the piecewise
            colour transfer function. ``None`` / empty is treated as "unknown"
            → returns ``True``.
        occupancy: Full-coverage histogram of the volume. Either a dict
            ``{scalar_value: count}``, exact ``(scalar_value, count)`` rows,
            or bounded-memory ``(lower_bound, upper_bound, count)`` rows.
            Only rows with a positive count are considered occupied.

    Returns:
        ``True`` if at least one occupied scalar value maps to an opacity
        above ``_EPS_OPACITY`` **and** a colour with at least one channel
        above ``_EPS_COLOR``. ``False`` only when *every* occupied value maps
        to a transparent-or-black result.
    """
    # Validate transfer functions. _validate_tf returns:
    #   False  → empty/unknown TF  → fail safe (assume visible)
    #   None   → malformed TF       → fail safe (assume visible)
    #   True   → well-formed TF     → proceed
    if _validate_tf(scalar_opacity, min_channels=1) is not True:
        return True
    if _validate_tf(color_tf, min_channels=3) is not True:
        return True
    # The validation above establishes the content contract; these explicit
    # guards narrow the optional API types for the evaluators below.
    if scalar_opacity is None or color_tf is None:
        return True

    # Normalise occupancy to an iterable of (value, count). Any unusable
    # occupancy (None, not iterable) is degenerate → fail safe.
    try:
        if isinstance(occupancy, dict):
            items = occupancy.items()
        elif isinstance(occupancy, Iterable) and not isinstance(
            occupancy, (str, bytes)
        ):
            items = occupancy
        else:
            return True
    except TypeError:
        return True

    # Inspect only occupied bins. Fail-safe: if we cannot find any well-formed
    # occupied bin (empty occupancy, all counts <= 0, or every row malformed),
    # assume visible rather than claim "expected blank" on bad data.
    found_occupied = False
    for row in items:
        occupied_bin = _parse_occupied_bin(row)
        if occupied_bin is None:
            return True
        lower_float, upper_float, count_int = occupied_bin
        if count_int <= 0:
            continue
        found_occupied = True

        if _interval_may_be_nonblank(
            scalar_opacity,
            color_tf,
            lower_float,
            upper_float,
        ):
            return True

    # No well-formed occupied bin found → degenerate input → fail safe.
    return not found_occupied
