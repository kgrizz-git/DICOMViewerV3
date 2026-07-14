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
import sys
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

    Iterates datasets and sums ``sys.getsizeof`` on any cached pixel arrays
    plus the ``PixelData`` tag size as a proxy for uncompressed data.
    """
    study_series = studies_dict.get(study_uid)
    if not study_series:
        return 0.0

    total_bytes = 0
    for _series_key, datasets in study_series.items():
        for ds in datasets:
            # Cached pixel array (numpy)
            cached = getattr(ds, "_cached_pixel_array", None)
            if cached is not None:
                total_bytes += sys.getsizeof(cached)
            # Raw PixelData tag
            elem = ds.get((0x7FE0, 0x0010))  # PixelData
            if elem is not None and hasattr(elem, "value") and elem.value is not None:
                total_bytes += len(elem.value)
            # Minimal per-dataset overhead
            total_bytes += 1024  # ~1 KB metadata overhead estimate

    return total_bytes / (1024 * 1024)


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
        max_studies: Maximum number of studies to keep in memory (default 5).
        memory_threshold_mb: RSS threshold in MB that triggers memory-based
            eviction (default 3000).
    """

    def __init__(
        self,
        max_studies: int = 5,
        memory_threshold_mb: float = 3000.0,
    ) -> None:
        self.max_studies = max_studies
        self.memory_threshold_mb = memory_threshold_mb
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

        _logger.info("Evicting study %s from cache", study_uid)

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
