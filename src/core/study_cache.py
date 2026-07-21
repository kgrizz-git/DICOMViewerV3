"""
LRU study cache with memory monitoring.

Tracks loaded DICOM studies by access order, enforces a configurable maximum
study count, and provides process memory monitoring (Windows-native via
ctypes, Unix fallback via ``resource``).

Inputs:
    - Study UIDs, studies dict, app reference for eviction.

Outputs:
    - LRU ordering, eviction candidates, memory usage estimates.

Requirements:
    - PySide6 (QMessageBox for confirmation dialog)
    - ctypes (Windows process memory)
    - sys (object size estimation)
"""

from __future__ import annotations

# ``main`` imports this module and it back-references ``DICOMViewerApp`` only under
# TYPE_CHECKING; the runtime import graph has no cycle (same pattern as the gui
# action modules).
# pyright: reportImportCycles=false
import ctypes
import ctypes.wintypes
import logging
import os
import platform
from collections import OrderedDict
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

    from main import DICOMViewerApp

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Process memory helpers
# ---------------------------------------------------------------------------

def get_process_memory_mb() -> float:
    """Get current process RSS in MB. Returns 0.0 if unavailable."""
    try:
        if os.name == "nt":
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):  # noqa: N801 - mirrors the Win32 struct name
                _fields_ = [
                    ("cb", ctypes.wintypes.DWORD),
                    ("PageFaultCount", ctypes.wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()  # type: ignore[attr-defined]
            if ctypes.windll.kernel32.K32GetProcessMemoryInfo(  # type: ignore[attr-defined]
                handle, ctypes.byref(pmc), ctypes.sizeof(pmc)
            ):
                return pmc.WorkingSetSize / (1024 * 1024)
        else:
            import resource as _resource

            usage = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
            if platform.system() == "Darwin":
                return usage / (1024 * 1024)
            else:
                return usage / 1024
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Study size estimation
# ---------------------------------------------------------------------------

def estimate_study_size_mb(
    study_uid: str,
    studies_dict: dict[str, dict[str, list[Dataset]]],
) -> float:
    """Rough estimate of a study's memory footprint in MB.

    Iterates datasets and, for each, prefers the true byte size of a cached
    decompressed NumPy pixel array (``array.nbytes``) when present; otherwise
    falls back to the raw ``PixelData`` element's byte length as a proxy for
    uncompressed data. The two terms are never summed together (that would
    double-count the same pixel data once decompressed).
    """
    study_series = studies_dict.get(study_uid)
    if not study_series:
        return 0.0

    total_bytes = 0
    for _series_key, datasets in study_series.items():
        for ds in datasets:
            # Cached pixel array (numpy) — the real decompressed footprint.
            # ``sys.getsizeof`` on a numpy array only returns the small
            # object-header overhead (~112 bytes), not the buffer it wraps,
            # so it must not be used here.
            cached = getattr(ds, "_cached_pixel_array", None)
            nbytes = getattr(cached, "nbytes", None) if cached is not None else None
            if isinstance(nbytes, int) and nbytes > 0:
                total_bytes += nbytes
            else:
                # No cached array yet (or it lacks .nbytes) — fall back to
                # the raw (possibly compressed) PixelData element length.
                elem = ds.get((0x7FE0, 0x0010))  # PixelData
                if elem is not None and hasattr(elem, "value") and elem.value is not None:
                    total_bytes += len(elem.value)
            # Minimal per-dataset overhead
            total_bytes += 1024  # ~1 KB metadata overhead estimate

    return total_bytes / (1024 * 1024)


# ---------------------------------------------------------------------------
# Total system memory detection
# ---------------------------------------------------------------------------

def get_total_system_memory_mb() -> float:
    """Get total installed system RAM in MB. Returns 0.0 if unavailable.

    Cross-platform, dependency-free (no psutil):
      - Windows: ``GlobalMemoryStatusEx`` (``MEMORYSTATUSEX.ullTotalPhys``)
        via ctypes.
      - Linux/macOS: ``os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')``.
      - macOS fallback (if the sysconf name is missing): ``sysctl -n hw.memsize``.
    """
    try:
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):  # mirrors the Win32 struct name
                _fields_ = [
                    ("dwLength", ctypes.wintypes.DWORD),
                    ("dwMemoryLoad", ctypes.wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
                return stat.ullTotalPhys / (1024 * 1024)
        else:
            try:
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                if pages > 0 and page_size > 0:
                    return (pages * page_size) / (1024 * 1024)
            except (ValueError, OSError, AttributeError):
                pass
            if platform.system() == "Darwin":
                import subprocess

                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return int(result.stdout.strip()) / (1024 * 1024)
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Confirmation dialog
# ---------------------------------------------------------------------------

def show_eviction_confirmation(
    parent: QWidget | None,
    reason: str,
    study_descriptions: list[str],
) -> bool:
    """Show a confirmation dialog before evicting studies.

    Args:
        parent: Parent widget for the dialog (e.g. ``app.main_window``).
        reason: Human-readable reason (e.g. "study limit reached" or
                "memory limit").
        study_descriptions: List of study descriptions that will be unloaded.

    Returns:
        ``True`` if the user clicks OK to proceed, ``False`` to cancel.
    """
    desc_list = "\n".join(f"  - {d}" for d in study_descriptions)
    msg = (
        f"Loading this study would exceed the {reason}.\n\n"
        f"The following studies will be unloaded to make room:\n"
        f"{desc_list}\n\n"
        f"Do you want to continue?"
    )
    result = QMessageBox.question(
        parent,
        "Study Cache Limit",
        msg,
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Ok,
    )
    return result == QMessageBox.StandardButton.Ok


# ---------------------------------------------------------------------------
# StudyCache
# ---------------------------------------------------------------------------

class StudyCache:
    """LRU cache wrapper for loaded DICOM studies.

    Tracks access order by study_uid and provides helpers for eviction
    decisions, memory monitoring, and cache cleanup.

    Args:
        max_studies: Safety-net cap on the number of studies to keep in
            memory (default 5; callers typically raise this — e.g. to 20 —
            once the memory budget below is the primary limit).
        memory_threshold_mb: RSS threshold in MB that triggers memory-based
            eviction (default 3000). Also used as the ``get_memory_budget_mb``
            fallback when total system RAM cannot be determined.
        memory_fraction: Fraction of total system RAM to use as the primary
            memory budget (default 0.40).
        memory_floor_mb: Minimum memory budget in MB regardless of *memory_fraction*
            (default 1024).
    """

    def __init__(
        self,
        max_studies: int = 5,
        memory_threshold_mb: float = 3000.0,
        memory_fraction: float = 0.40,
        memory_floor_mb: float = 1024.0,
    ) -> None:
        self.max_studies = max_studies
        self.memory_threshold_mb = memory_threshold_mb
        self.memory_fraction = memory_fraction
        self.memory_floor_mb = memory_floor_mb
        # OrderedDict keyed by study_uid; values are unused (True).
        # Most-recently-accessed study is at the *end*.
        self._access_order: OrderedDict[str, bool] = OrderedDict()

    # -- LRU tracking -------------------------------------------------------

    def mark_accessed(self, study_uid: str) -> None:
        """Record *study_uid* as the most recently accessed study."""
        if study_uid in self._access_order:
            self._access_order.move_to_end(study_uid)
        else:
            self._access_order[study_uid] = True

    def remove(self, study_uid: str) -> None:
        """Remove *study_uid* from the LRU tracker."""
        self._access_order.pop(study_uid, None)

    def get_studies_by_lru_order(self) -> list[str]:
        """Return study UIDs ordered oldest-first (least recently used first)."""
        return list(self._access_order.keys())

    def study_count(self) -> int:
        """Number of studies currently tracked."""
        return len(self._access_order)

    def clear(self) -> None:
        """Clear the LRU tracker."""
        self._access_order.clear()

    # -- Memory helpers ------------------------------------------------------

    def get_memory_usage_mb(self) -> float:
        """Return current process RSS in MB (delegated to module function)."""
        return get_process_memory_mb()

    def would_exceed_memory(self, threshold_mb: float | None = None) -> bool:
        """Return ``True`` if current RSS exceeds *threshold_mb*."""
        limit = threshold_mb if threshold_mb is not None else self.memory_threshold_mb
        usage = self.get_memory_usage_mb()
        if usage <= 0.0:
            return False  # cannot measure; assume OK
        return usage > limit

    def get_memory_budget_mb(self) -> float:
        """Return the primary memory budget in MB.

        Computed as ``memory_fraction`` of total system RAM, clamped to a
        minimum of ``memory_floor_mb``. If total system RAM cannot be
        determined (``get_total_system_memory_mb`` returns 0.0), falls back
        to the absolute ``memory_threshold_mb`` so behavior degrades
        gracefully instead of producing an unbounded or zero budget.
        """
        total_ram_mb = get_total_system_memory_mb()
        if total_ram_mb <= 0.0:
            return self.memory_threshold_mb
        return max(self.memory_fraction * total_ram_mb, self.memory_floor_mb)

    def estimate_total_loaded_mb(
        self,
        studies_dict: dict[str, dict[str, list[Dataset]]],
    ) -> float:
        """Return the estimated in-memory footprint of all loaded studies, in MB."""
        return sum(
            estimate_study_size_mb(uid, studies_dict) for uid in studies_dict
        )

    # -- Eviction logic ------------------------------------------------------

    def get_eviction_candidates(
        self,
        studies_dict: dict[str, dict[str, list[Dataset]]],
        max_studies: int | None = None,
        active_study_uid: str | None = None,
    ) -> list[str]:
        """Return study UIDs that should be evicted (oldest first).

        Evicts enough studies so that the total count does not exceed
        *max_studies*.  The *active_study_uid* (currently displayed) is
        never evicted.

        Args:
            studies_dict: The organizer's ``studies`` dict.
            max_studies: Override for ``self.max_studies``.
            active_study_uid: Study UID that must not be evicted.

        Returns:
            List of study UIDs to evict, oldest first.
        """
        limit = max_studies if max_studies is not None else self.max_studies
        total = len(studies_dict)
        if total <= limit:
            return []

        excess = total - limit
        candidates: list[str] = []
        for uid in self._access_order:
            if len(candidates) >= excess:
                break
            if uid == active_study_uid:
                continue
            if uid in studies_dict:
                candidates.append(uid)

        # If LRU tracker is missing some studies (e.g. loaded before tracker
        # existed), fall back to studies not in the tracker.
        if len(candidates) < excess:
            for uid in studies_dict:
                if len(candidates) >= excess:
                    break
                if uid == active_study_uid:
                    continue
                if uid not in self._access_order and uid not in candidates:
                    candidates.append(uid)

        return candidates

    def get_eviction_candidates_by_size(
        self,
        studies_dict: dict[str, dict[str, list[Dataset]]],
        budget_mb: float,
        active_study_uid: str | None = None,
    ) -> list[str]:
        """Return study UIDs to evict (oldest first) to fit within *budget_mb*.

        Walks studies in LRU order (oldest first; untracked studies are
        treated as oldest-of-all, same fallback order as
        :meth:`get_eviction_candidates`), accumulating
        :func:`estimate_study_size_mb` for each until the estimated total
        footprint minus what's been freed is at or below *budget_mb*. The
        *active_study_uid* is never included.

        If no size information is available at all (every study estimates to
        0.0 — e.g. datasets have no cached pixel data or PixelData yet),
        falls back to the count-based :meth:`get_eviction_candidates` so
        eviction still makes progress.

        Args:
            studies_dict: The organizer's ``studies`` dict.
            budget_mb: Target memory budget in MB.
            active_study_uid: Study UID that must not be evicted.

        Returns:
            List of study UIDs to evict, oldest first.
        """
        sizes = {uid: estimate_study_size_mb(uid, studies_dict) for uid in studies_dict}
        total_mb = sum(sizes.values())
        if total_mb <= budget_mb:
            return []

        if total_mb <= 0.0:
            # No usable size data — fall back to the count-based strategy.
            return self.get_eviction_candidates(
                studies_dict, active_study_uid=active_study_uid
            )

        # Oldest-first: tracked studies in LRU order, then any studies not
        # yet in the LRU tracker (mirrors get_eviction_candidates's fallback).
        ordered = [uid for uid in self._access_order if uid in studies_dict]
        ordered += [uid for uid in studies_dict if uid not in self._access_order]

        candidates: list[str] = []
        remaining_mb = total_mb
        for uid in ordered:
            if remaining_mb <= budget_mb:
                break
            if uid == active_study_uid:
                continue
            candidates.append(uid)
            remaining_mb -= sizes.get(uid, 0.0)

        return candidates

    def evict_study(self, study_uid: str, app: DICOMViewerApp) -> None:
        """Remove a study from the app, clearing all associated caches.

        This delegates to ``app._close_study()`` which handles:
        - Freeing pixel caches for all datasets in the study
        - Removing the study from ``dicom_organizer``
        - Clearing affected subwindow data
        - Refreshing navigators
        - Invalidating slice-sync geometry cache

        Additionally clears projection cache and resampler cache for the
        study's series.

        Args:
            study_uid: StudyInstanceUID to evict.
            app: Application instance.
        """
        from core.dicom_projections import clear_projection_cache

        _logger.info("Evicting one study from cache")

        # Clear projection cache (module-level, not per-study; full clear is
        # acceptable because projections are cheap to recompute).
        clear_projection_cache()

        # Clear resampler cache for series belonging to this study.
        study_series = app.current_studies.get(study_uid, {})
        for idx in app.subwindow_managers:
            managers = app.subwindow_managers[idx]
            fusion_handler = managers.get("fusion_handler")
            if fusion_handler and hasattr(fusion_handler, "image_resampler"):
                resampler = fusion_handler.image_resampler
                if resampler:
                    for series_key in study_series:
                        resampler.clear_cache(series_uid=series_key)

        # Delegate the heavy lifting to the existing close-study path.
        app._close_study(study_uid)

        # Remove from LRU tracker.
        self.remove(study_uid)

    # -- Convenience ---------------------------------------------------------

    def get_study_description(
        self,
        study_uid: str,
        studies_dict: dict[str, dict[str, list[Dataset]]],
    ) -> str:
        """Return a human-readable description for a study (for dialog display)."""
        study_series = studies_dict.get(study_uid, {})
        if not study_series:
            return study_uid

        # Try to get a study description from the first dataset.
        for _series_key, datasets in study_series.items():
            if datasets:
                ds = datasets[0]
                desc = getattr(ds, "StudyDescription", "") or ""
                patient = getattr(ds, "PatientName", "") or ""
                date = getattr(ds, "StudyDate", "") or ""
                parts = [p for p in [str(desc).strip(), str(patient).strip(), date] if p]
                if parts:
                    return " / ".join(parts)
                break

        return study_uid
