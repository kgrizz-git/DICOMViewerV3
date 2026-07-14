"""
Background worker thread for DICOM file loading.

Wraps a loader function (DICOMLoader.load_files or load_directory) in a
QThread so the UI thread stays responsive during I/O-heavy loading.

An optional *organize_fn* can be supplied to run data-only organisation
(e.g. ``DICOMOrganizer.merge_batch``) on the worker thread instead of
blocking the UI thread after loading completes.
"""

import gc
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

from utils.perf_timer import perf_mark, perf_timer


class LoaderWorker(QThread):
    """QThread that runs a loader function and reports progress via signals.

    When *organize_fn* is provided the worker will:
    1. Run ``loader_fn`` (I/O phase).
    2. Optionally ``gc.collect()`` for large batches (>100 datasets).
    3. Run ``organize_fn(datasets)`` (pure-data organisation phase).
    4. Emit ``organized(datasets, merge_result)`` instead of ``finished``.

    If *organize_fn* is ``None`` (default), behaviour is unchanged: only
    ``finished(datasets, failed_files)`` is emitted.
    """

    progress = Signal(int, int, str)       # (current, total, filename)
    finished = Signal(list, list)          # (datasets, failed_files)
    organized = Signal(list, object)       # (datasets, merge_result)
    error = Signal(str)                    # fatal error message

    def __init__(
        self,
        loader_fn: Callable[..., list[Any]],
        organize_fn: Callable[[list[Any]], Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._loader_fn = loader_fn
        self._organize_fn = organize_fn

    def run(self) -> None:
        """Execute the loader function on this background thread."""
        try:
            def _progress_callback(current: int, total: int, filename: str) -> None:
                self.progress.emit(current, total, filename)

            with perf_timer("first_paint.prehandoff.loader_worker.load"):
                datasets = self._loader_fn(_progress_callback)
            perf_mark(
                "first_paint.prehandoff.loader_worker.load_complete",
                datasets=len(datasets) if datasets else 0,
            )

            if self._organize_fn is not None and datasets:
                # GC before organising large batches — on the worker thread,
                # not the UI thread, so the main event loop stays responsive.
                if len(datasets) > 100:
                    gc.collect()
                with perf_timer("first_paint.prehandoff.loader_worker.merge"):
                    merge_result = self._organize_fn(datasets)
                perf_mark(
                    "first_paint.prehandoff.loader_worker.merge_complete",
                    datasets=len(datasets),
                    new_series=len(getattr(merge_result, "new_series", [])),
                    appended_series=len(getattr(merge_result, "appended_series", [])),
                    added_files=getattr(merge_result, "added_file_count", 0),
                )
                self.organized.emit(datasets, merge_result)
            else:
                self.finished.emit(datasets if datasets else [], [])
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")
