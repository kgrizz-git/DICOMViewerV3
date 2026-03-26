"""
MPR Cache

Persistent disk-based LRU cache for MPR resampled stacks.

Each cached entry stores:
  - The NumPy pixel arrays for every MPR slice (.npz compressed).
  - A JSON metadata sidecar with the cache key, creation time, size,
    and all parameters used to build the MPR (for validation on re-load).

The LRU eviction policy is applied on writes when the total cache size
exceeds the configured maximum (default: 500 MB).  The oldest-accessed
entries are evicted first.

Inputs:
    MprResult   — result of a completed MPR build.
    cache_dir   — Path (or str) of the directory used for storage.
    max_size_mb — Maximum total disk usage in MB; 0 = unlimited.

Outputs:
    Cached MprResult on a cache hit (pixel arrays loaded from disk).
    None on a cache miss.

Requirements:
    numpy (already a project dependency)
    Standard library: json, hashlib, pathlib, os, time, threading
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from core.mpr_builder import MprResult
from core.mpr_volume import MprVolume
from core.slice_geometry import SlicePlane, SliceStack


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------

_MPR_CACHE_FORMAT_VERSION = "4"

def _quantise_float(value: float, decimals: int = 4) -> str:
    """Round a float and return its string representation for stable keys."""
    return str(round(float(value), decimals))


def _make_cache_key(
    series_uid: str,
    normal: np.ndarray,
    output_spacing_mm: float,
    output_thickness_mm: float,
    interpolation: str,
    source_dataset_count: int,
) -> str:
    """
    Build a stable SHA-256 hex digest cache key.

    The key is derived from series UID + output orientation + spacing
    + interpolation + dataset count.  A changed dataset count is used
    as a lightweight proxy for series content change.

    Slab combine parameters are intentionally excluded: the cached stack
    is always uncombined; combine is applied at display time.

    Args:
        series_uid:          DICOM SeriesInstanceUID of the source.
        normal:              Output plane normal (3-element float array).
        output_spacing_mm:   In-plane pixel spacing of the output (mm).
        output_thickness_mm: Inter-slice spacing of the output (mm).
        interpolation:       Interpolation method string.
        source_dataset_count: Number of slices in the source series.

    Returns:
        32-character hex digest string.
    """
    parts = [
        _MPR_CACHE_FORMAT_VERSION,
        series_uid.strip(),
        _quantise_float(float(normal[0])),
        _quantise_float(float(normal[1])),
        _quantise_float(float(normal[2])),
        _quantise_float(output_spacing_mm),
        _quantise_float(output_thickness_mm),
        interpolation.lower().strip(),
        str(int(source_dataset_count)),
    ]
    key_str = "|".join(parts)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def make_result_key(result: MprResult) -> str:
    """
    Derive a cache key from an MprResult.

    Extracts the SeriesInstanceUID from the first source dataset.

    Args:
        result: Completed MPR result.

    Returns:
        Cache key string.
    """
    ds_list = result.source_volume.source_datasets
    try:
        series_uid = str(ds_list[0].SeriesInstanceUID)
    except (AttributeError, IndexError):
        series_uid = "__unknown__"

    normal = result.slice_stack.stack_normal
    sp = result.output_spacing_mm[0]  # isotropic
    th = result.output_thickness_mm
    return _make_cache_key(
        series_uid=series_uid,
        normal=normal,
        output_spacing_mm=sp,
        output_thickness_mm=th,
        interpolation=result.interpolation,
        source_dataset_count=len(ds_list),
    )


# ---------------------------------------------------------------------------
# Cache entry metadata
# ---------------------------------------------------------------------------

class _CacheEntry:
    """Lightweight descriptor for a single cache entry (metadata only)."""

    __slots__ = ("key", "path_npz", "path_meta", "size_bytes", "last_access")

    def __init__(
        self,
        key: str,
        path_npz: Path,
        path_meta: Path,
        size_bytes: int,
        last_access: float,
    ) -> None:
        self.key = key
        self.path_npz = path_npz
        self.path_meta = path_meta
        self.size_bytes = size_bytes
        self.last_access = last_access


# ---------------------------------------------------------------------------
# MprCache
# ---------------------------------------------------------------------------

class MprCache:
    """
    Persistent disk-based LRU cache for MPR stacks.

    Thread-safe (uses an internal lock for all mutating operations).

    Usage::

        cache = MprCache(cache_dir=Path("..."), max_size_mb=500)

        key = make_result_key(result)
        if cache.has(key):
            slices, stack = cache.load(key)
        else:
            # ... build result ...
            cache.save(result)
    """

    # File name components.
    _NPZ_SUFFIX = ".npz"
    _META_SUFFIX = "_meta.json"

    def __init__(
        self,
        cache_dir: Path,
        max_size_mb: int = 500,
    ) -> None:
        """
        Args:
            cache_dir:    Directory where cache files are stored.
                          Created if it does not exist.
            max_size_mb:  Maximum total cache size in MB (0 = unlimited).
        """
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_size_bytes = int(max_size_mb) * 1024 * 1024
        self._lock = threading.Lock()
        # In-memory index of all cache entries: key → _CacheEntry.
        self._index: Dict[str, _CacheEntry] = {}
        self._scan_disk()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def has(self, key: str) -> bool:
        """Return True if a valid cache entry exists for *key*."""
        with self._lock:
            entry = self._index.get(key)
            if entry is None:
                return False
            return entry.path_npz.exists() and entry.path_meta.exists()

    def load(
        self, key: str
    ) -> Optional[Tuple[List[np.ndarray], SliceStack, Dict[str, Any]]]:
        """
        Load cached MPR data for *key*.

        Args:
            key: Cache key (from ``make_result_key`` or ``_make_cache_key``).

        Returns:
            ``(slices, slice_stack, metadata_dict)`` on a cache hit where:
              - ``slices`` is a list of 2-D float32 NumPy arrays.
              - ``slice_stack`` is a reconstructed SliceStack.
              - ``metadata_dict`` is the raw JSON metadata (contains
                rescale slope/intercept, spacings, etc.).
            ``None`` on a cache miss or I/O error.
        """
        with self._lock:
            entry = self._index.get(key)
            if entry is None:
                return None
            if not entry.path_npz.exists() or not entry.path_meta.exists():
                # Entry is stale; remove from index.
                self._index.pop(key, None)
                return None

        try:
            npz = np.load(str(entry.path_npz))
            n_slices = int(npz["n_slices"])
            slices: List[np.ndarray] = [
                npz[f"slice_{i}"].astype(np.float32) for i in range(n_slices)
            ]

            with open(entry.path_meta, "r", encoding="utf-8") as f:
                meta: Dict[str, Any] = json.load(f)

            slice_stack = self._reconstruct_stack(meta, slices)
        except Exception as exc:
            print(f"[MprCache] Load failed for key {key[:12]}…: {exc}")
            return None

        # Update last-access time.
        with self._lock:
            if key in self._index:
                self._index[key].last_access = time.time()
                self._update_meta_access(entry.path_meta)

        return slices, slice_stack, meta

    def save(self, result: MprResult) -> bool:
        """
        Persist an MprResult to disk.

        If the operation would exceed the maximum cache size, LRU entries are
        evicted first.

        Args:
            result: Completed MPR result to cache.

        Returns:
            True on success, False on failure.
        """
        key = make_result_key(result)

        # Build metadata dict.
        ds_list = result.source_volume.source_datasets
        try:
            series_uid = str(ds_list[0].SeriesInstanceUID)
        except (AttributeError, IndexError):
            series_uid = "__unknown__"

        normal = result.slice_stack.stack_normal
        meta = {
            "key": key,
            "cache_format_version": _MPR_CACHE_FORMAT_VERSION,
            "created": time.time(),
            "last_access": time.time(),
            "series_uid": series_uid,
            "source_dataset_count": len(ds_list),
            "n_slices": result.n_slices,
            "output_spacing_mm": list(result.output_spacing_mm),
            "output_thickness_mm": result.output_thickness_mm,
            "interpolation": result.interpolation,
            "combine_mode": "none",
            "slab_thickness_mm": 0.0,
            "stack_normal": [float(normal[0]), float(normal[1]), float(normal[2])],
            "stack_positions": list(result.slice_stack.positions),
            "slice_origins": [
                [float(p.origin[0]), float(p.origin[1]), float(p.origin[2])]
                for p in result.slice_stack.planes
            ],
            "row_cosine": [
                float(result.slice_stack.planes[0].row_cosine[0]),
                float(result.slice_stack.planes[0].row_cosine[1]),
                float(result.slice_stack.planes[0].row_cosine[2]),
            ],
            "col_cosine": [
                float(result.slice_stack.planes[0].col_cosine[0]),
                float(result.slice_stack.planes[0].col_cosine[1]),
                float(result.slice_stack.planes[0].col_cosine[2]),
            ],
            "rescale_slope": result.rescale_slope,
            "rescale_intercept": result.rescale_intercept,
        }

        path_npz = self._cache_dir / (key + self._NPZ_SUFFIX)
        path_meta = self._cache_dir / (key + self._META_SUFFIX)

        try:
            npz_payload: Dict[str, Any] = {"n_slices": np.array(result.n_slices)}
            for i, arr in enumerate(result.slices):
                npz_payload[f"slice_{i}"] = arr.astype(np.float32)
            np.savez_compressed(str(path_npz), **npz_payload)

            with open(path_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as exc:
            print(f"[MprCache] Save failed for key {key[:12]}…: {exc}")
            return False

        size_bytes = self._file_size(path_npz) + self._file_size(path_meta)

        with self._lock:
            self._index[key] = _CacheEntry(
                key=key,
                path_npz=path_npz,
                path_meta=path_meta,
                size_bytes=size_bytes,
                last_access=time.time(),
            )
            if self._max_size_bytes > 0:
                self._evict_lru()

        return True

    def invalidate(self, series_uid: Optional[str] = None) -> int:
        """
        Remove cache entries matching a series UID, or the entire cache.

        Args:
            series_uid: If provided, remove only entries whose metadata
                        contains this series UID.  If None, clear all entries.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            if series_uid is None:
                keys_to_remove = list(self._index.keys())
            else:
                keys_to_remove = [
                    k for k, e in self._index.items()
                    if self._meta_has_series(e.path_meta, series_uid)
                ]
            count = 0
            for k in keys_to_remove:
                self._remove_entry(k)
                count += 1
            return count

    def total_size_bytes(self) -> int:
        """Return total disk usage of all cache entries (bytes)."""
        with self._lock:
            return sum(e.size_bytes for e in self._index.values())

    def entry_count(self) -> int:
        """Return number of cached entries."""
        with self._lock:
            return len(self._index)

    # ------------------------------------------------------------------
    # Disk scanning and indexing
    # ------------------------------------------------------------------

    def _scan_disk(self) -> None:
        """Rebuild the in-memory index by scanning the cache directory."""
        for meta_path in self._cache_dir.glob(f"*{self._META_SUFFIX}"):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                key = meta.get("key", "")
                if not key:
                    continue
                path_npz = self._cache_dir / (key + self._NPZ_SUFFIX)
                if not path_npz.exists():
                    continue
                size_bytes = self._file_size(path_npz) + self._file_size(meta_path)
                last_access = float(meta.get("last_access", 0.0))
                self._index[key] = _CacheEntry(
                    key=key,
                    path_npz=path_npz,
                    path_meta=meta_path,
                    size_bytes=size_bytes,
                    last_access=last_access,
                )
            except Exception:
                # Ignore corrupted metadata files.
                pass

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def _evict_lru(self) -> None:
        """Remove oldest-accessed entries until total size ≤ max_size_bytes."""
        total = sum(e.size_bytes for e in self._index.values())
        if total <= self._max_size_bytes:
            return
        sorted_entries = sorted(self._index.values(), key=lambda e: e.last_access)
        for entry in sorted_entries:
            if total <= self._max_size_bytes:
                break
            total -= entry.size_bytes
            self._remove_entry(entry.key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_entry(self, key: str) -> None:
        """Remove entry files and index record (must hold _lock)."""
        entry = self._index.pop(key, None)
        if entry is None:
            return
        for p in (entry.path_npz, entry.path_meta):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass

    @staticmethod
    def _file_size(path: Path) -> int:
        """Return file size in bytes, 0 if missing."""
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    @staticmethod
    def _update_meta_access(path_meta: Path) -> None:
        """Silently update last_access in a metadata JSON file."""
        try:
            with open(path_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["last_access"] = time.time()
            with open(path_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _meta_has_series(path_meta: Path, series_uid: str) -> bool:
        """Return True if a metadata file references *series_uid*."""
        try:
            with open(path_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return meta.get("series_uid", "") == series_uid
        except Exception:
            return False

    @staticmethod
    def _reconstruct_stack(
        meta: Dict[str, Any], slices: List[np.ndarray]
    ) -> SliceStack:
        """
        Rebuild a SliceStack from cached metadata.

        Args:
            meta:   Metadata dict as stored in the JSON sidecar.
            slices: Loaded pixel arrays (used only for length).

        Returns:
            SliceStack with correct geometry.
        """
        row_cosine = np.array(meta["row_cosine"], dtype=float)
        col_cosine = np.array(meta["col_cosine"], dtype=float)
        stack_normal = np.array(meta["stack_normal"], dtype=float)
        positions = meta["stack_positions"]
        slice_origins = meta["slice_origins"]
        sp = float(meta["output_spacing_mm"][0])
        th = float(meta["output_thickness_mm"])

        planes = [
            SlicePlane(
                origin=np.array(orig, dtype=float),
                row_cosine=row_cosine,
                col_cosine=col_cosine,
                row_spacing=sp,
                col_spacing=sp,
            )
            for orig in slice_origins
        ]

        return SliceStack(
            planes=planes,
            original_indices=list(range(len(planes))),
            stack_normal=stack_normal,
            positions=positions,
            slice_thickness=th,
        )
