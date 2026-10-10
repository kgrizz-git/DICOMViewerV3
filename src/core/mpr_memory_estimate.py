"""Approximate marginal memory used by MPR sessions (pure core, no Qt).

Shown to the user in admission and status messages so they can see roughly
what their MPR sessions cost. It is a **visibility estimate, not a RAM budget
or a limit**: nothing here refuses, evicts or asks for confirmation, and the
real process footprint (allocator slack, Qt, GPU, other studies) is larger.

What is counted, each distinct buffer once:

- the SimpleITK source volume of each session (voxels x components x bytes per
  component, read from image metadata; no pixel buffer is touched or copied);
- the result slice arrays. Shared storage is recognised: a NumPy view is
  charged through the array that owns its memory, so slices cut from one stack
  count once, and two sessions or duplicate views holding the *same* result or
  volume object count once;
- a fixed upper bound per view for its bounded navigator thumbnail copy;
- the source volume of each build that has been admitted but not finished
  (its result arrays are unknown until the build ends and are counted then).

Already-loaded dataset PixelData is deliberately not counted: it exists
whether or not an MPR does. Nothing here decodes or allocates image data.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np

#: Longest side, in pixels, of an array handed to a navigator tile.
THUMBNAIL_MAX_SIDE = 256
#: Upper bound for one view's thumbnail copy (float32, longest side bounded).
THUMBNAIL_BYTES_PER_VIEW = THUMBNAIL_MAX_SIDE * THUMBNAIL_MAX_SIDE * 4

_BITS_RE = re.compile(r"(\d+)-bit")
_FLOAT32_BYTES = 4


@dataclass(frozen=True)
class MemoryEstimate:
    """Approximate bytes, by kind. ``total_bytes`` is the figure shown to users."""

    volume_bytes: int = 0
    result_bytes: int = 0
    thumbnail_bytes: int = 0
    pending_bytes: int = 0

    @property
    def total_bytes(self) -> int:
        return self.volume_bytes + self.result_bytes + self.thumbnail_bytes + self.pending_bytes


def format_mib(num_bytes: int) -> str:
    """Concise MiB figure for status text (``0 MiB`` for under half a MiB)."""
    mib = max(0, num_bytes) / (1024 * 1024)
    return f"{int(mib + 0.5):,} MiB"


def sitk_volume_bytes(image: Any) -> int:
    """Bytes of a SimpleITK image from its metadata alone (0 when it cannot be read)."""
    try:
        voxels = int(image.GetNumberOfPixels())
        components = int(image.GetNumberOfComponentsPerPixel())
        match = _BITS_RE.search(str(image.GetPixelIDTypeAsString()))
        bytes_per_component = int(match.group(1)) // 8 if match else _FLOAT32_BYTES
    except Exception:
        return 0
    return max(0, voxels) * max(1, components) * max(1, bytes_per_component)


def _foreign_buffer(owner: Any) -> tuple[int, int] | None:
    """``(start address, bytes)`` of a non-ndarray buffer owner, or None if not a buffer.

    Two ``np.frombuffer`` arrays over the same bytes get distinct wrapper
    objects as bases, so the identity of the wrapper cannot recognise shared
    storage; the buffer's start address can.
    """
    try:
        raw = np.frombuffer(memoryview(owner), dtype=np.uint8)
    except (TypeError, ValueError):
        return None
    return int(raw.__array_interface__["data"][0]), int(raw.nbytes)


def array_owner(array: np.ndarray) -> tuple[int, int]:
    """``(identity key, bytes)`` of the memory that keeps *array* alive.

    A view is charged through the array (or foreign buffer) that owns its
    memory, at that owner's full size: a small view of a large buffer still
    keeps the whole buffer alive.
    """
    current = array
    while isinstance(current.base, np.ndarray):
        current = current.base
    owner = current.base
    if owner is None:
        return id(current), int(current.nbytes)
    foreign = _foreign_buffer(owner)
    if foreign is not None:
        return foreign
    return id(owner), int(current.nbytes)


class BufferLedger:
    """Counts each distinct volume image and array buffer once across any number of results."""

    def __init__(self) -> None:
        self._seen: set[int] = set()
        self.volume_bytes = 0
        self.result_bytes = 0

    def add_result(self, result: Any) -> None:
        """Add one MPR result's source volume and slice arrays (anything already seen is skipped)."""
        image = getattr(getattr(result, "source_volume", None), "sitk_image", None)
        if image is not None and id(image) not in self._seen:
            self._seen.add(id(image))
            self.volume_bytes += sitk_volume_bytes(image)
        for plane in getattr(result, "slices", None) or ():
            if not isinstance(plane, np.ndarray):
                continue
            key, size = array_owner(plane)
            if key not in self._seen:
                self._seen.add(key)
                self.result_bytes += size


def estimate_pending_volume_bytes(datasets: Any) -> int:
    """Source-volume bytes a build of *datasets* will allocate (float32), from tag values only.

    Pure metadata arithmetic: rows x columns x slice count x 4 bytes. It never
    reads PixelData. The result stack is not included; it is unknown until the
    build ends.
    """
    try:
        first = datasets[0]
        rows = int(getattr(first, "Rows", 0) or 0)
        cols = int(getattr(first, "Columns", 0) or 0)
        return max(0, rows) * max(0, cols) * len(datasets) * _FLOAT32_BYTES
    except (TypeError, ValueError, IndexError):
        return 0


def estimate_memory(
    results: Iterable[Any], view_count: int, pending_bytes: int = 0
) -> MemoryEstimate:
    """Estimate for *results* (one per session), *view_count* tiles and pending builds."""
    ledger = BufferLedger()
    for result in results:
        ledger.add_result(result)
    return MemoryEstimate(
        volume_bytes=ledger.volume_bytes,
        result_bytes=ledger.result_bytes,
        thumbnail_bytes=max(0, int(view_count)) * THUMBNAIL_BYTES_PER_VIEW,
        pending_bytes=max(0, int(pending_bytes)),
    )


__all__ = [
    "THUMBNAIL_BYTES_PER_VIEW",
    "THUMBNAIL_MAX_SIDE",
    "BufferLedger",
    "MemoryEstimate",
    "array_owner",
    "estimate_memory",
    "estimate_pending_volume_bytes",
    "format_mib",
    "sitk_volume_bytes",
]
