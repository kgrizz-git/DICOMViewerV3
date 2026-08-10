"""Pure policy helpers for responsive 3D volume-render detail selection."""

from __future__ import annotations

MEBIBYTE = 1024 * 1024
LARGE_VOLUME_BYTES = 64 * MEBIBYTE
HUGE_VOLUME_BYTES = 512 * MEBIBYTE
AUTO_REFINE_BUDGET_MS = 200.0


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
