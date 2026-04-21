"""
Background tag-export union across all loaded studies (Export DICOM Tags).

Owns generation counter, merged result cache, and ``TagExportUnionWorker``
lifecycle. ``DICOMViewerApp`` keeps ``tag_export_union_ready`` and delegates
``get_tag_export_union_snapshot`` / ``_drain_tag_export_union_worker`` /
``_schedule_tag_export_union_rebuild`` here so ``main.py`` stays smaller.

Inputs:
    ``app``: ``DICOMViewerApp`` (``current_studies``, ``tag_export_union_ready``).

Outputs:
    Emits ``app.tag_export_union_ready`` when union completes or is cleared.

Requirements:
    PySide6 ``QThread`` / ``QApplication`` cooperative drain on rebuild and quit.
"""

from __future__ import annotations

# pyright: reportImportCycles=false

import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication
from pydicom.dataset import Dataset

from gui.dialogs.tag_export_union_worker import TagExportUnionWorker

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp

StudiesNestedDict = Dict[str, Dict[str, List[Dataset]]]


def flatten_studies_for_tag_export_union(studies: StudiesNestedDict) -> List[Dataset]:
    """Stable study → series → instance order for tag-export union."""
    out: List[Dataset] = []
    for _, series_dict in studies.items():
        for _, datasets in series_dict.items():
            out.extend(datasets)
    return out


class TagExportUnionHost:
    """State and worker orchestration for the tag-export union background merge."""

    def __init__(self, app: "DICOMViewerApp") -> None:
        self._app = app
        self._generation = 0
        self._merged: Optional[Dict[str, Any]] = None
        self._worker: Optional[TagExportUnionWorker] = None

    def get_snapshot(self) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Current load generation and merged tag map, if background union has finished."""
        return (self._generation, self._merged)

    def drain_worker(self, timeout_sec: float = 180.0) -> None:
        """
        Stop and join the tag-export union QThread before replacing it.

        Without this, assigning a new ``TagExportUnionWorker`` drops the last
        reference to a still-running ``QThread``, which triggers Qt's
        "Destroyed while thread is still running" warning and can crash.

        Uses short ``wait`` slices plus ``processEvents`` so the UI stays
        responsive while a large multi-frame union unwinds cooperatively.
        """
        w = self._worker
        if w is None:
            return
        try:
            w.finished_ok.disconnect(self._on_worker_finished)
        except TypeError:
            pass
        try:
            w.failed.disconnect(self._on_worker_failed)
        except TypeError:
            pass
        if w.isRunning():
            w.requestInterruption()
            app_inst = QApplication.instance()
            deadline = time.time() + timeout_sec
            while w.isRunning() and time.time() < deadline:
                w.wait(50)
                if app_inst is not None:
                    app_inst.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
            if w.isRunning():
                print(
                    "[DICOMViewerApp] TagExportUnionWorker did not finish within "
                    f"{timeout_sec:.0f}s after interruption; shutdown may still warn.",
                    file=sys.stderr,
                )
        self._worker = None

    def schedule_rebuild(self) -> None:
        """Rebuild in-memory tag union off the GUI thread (no disk cache)."""
        self.drain_worker()
        self._generation += 1
        gen = self._generation
        self._merged = None
        if not self._app.current_studies:
            self._app.tag_export_union_ready.emit(gen, {})
            return
        datasets = flatten_studies_for_tag_export_union(self._app.current_studies)
        worker = TagExportUnionWorker(
            gen,
            datasets,
            include_private=True,
            supplement_standard_tags=True,
        )
        worker.finished_ok.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self, gen: int, merged: object) -> None:
        if gen != self._generation:
            return
        self._merged = cast(Dict[str, Any], merged)
        self._app.tag_export_union_ready.emit(gen, self._merged)

    def _on_worker_failed(self, gen: int, _message: str) -> None:
        if gen != self._generation:
            return
        self._merged = None
        self._app.tag_export_union_ready.emit(gen, {})
