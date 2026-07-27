"""
Async (threaded) DICOM load pipeline.

Extracted from ``loading_pipeline`` so ``run_load_pipeline_async`` and its
signal handlers stay under Sonar cognitive-complexity limits while preserving
the same public behaviour (progress dialog, organise-on-worker, UI handoff).

Public entry point is re-exported from ``core.loading_pipeline``.
"""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.dicom_organizer import MergeResult
from core.loader_worker import LoaderWorker
from core.loading_pipeline import (
    LoadPipelineRequest,
    build_post_load_status,
    empty_load_error_message,
    failed_files_warning_message,
    resolve_merge_paths,
    update_loading_progress_dialog,
)
from utils.log_sanitizer import sanitized_format_exc
from utils.perf_timer import perf_mark, perf_timer

# UI string constants mirrored from loading_pipeline (avoid private cross-imports).
_STATUS_LOADING_CANCELLED = "Loading cancelled."
_TITLE_LOADING_WARNINGS = "Loading Warnings"
_TITLE_MEMORY_ERROR = "Memory Error"
_TITLE_ERROR = "Error"

_logger = logging.getLogger(__name__)


@dataclass
class _AsyncLoadContext:
    """Mutable wiring shared by async progress / finished / organized / error slots."""

    request: LoadPipelineRequest
    is_folder_mode: bool
    on_pipeline_complete: (
        Callable[[list[Any] | None, dict[str, Any] | None], None] | None
    )
    loading_started: list[bool]
    last_ui_update: list[float]


def run_load_pipeline_async(
    request: LoadPipelineRequest,
    *,
    on_pipeline_complete: Callable[[list[Any] | None, dict[str, Any] | None], None]
    | None = None,
) -> LoaderWorker:
    """Async version of ``run_load_pipeline`` that uses a background worker thread.

    Instead of blocking the UI thread during file I/O, this function:
    1. Creates the progress dialog.
    2. Starts a LoaderWorker QThread for the actual loading.
    3. Connects signals so post-load steps run on the main thread.
    4. Returns the worker immediately (caller must hold a reference).
    """
    is_folder_mode = request.file_paths_for_merge is None
    perf_mark(
        "first_paint.prehandoff.pipeline_async.start",
        source_len=len(request.source_name),
        folder_mode=request.file_paths_for_merge is None,
        progress_max=request.progress_max,
    )

    label = (
        request.progress_label
        or f"Loading files from {request.source_name}..."
    )

    request.loader.reset_cancellation()
    request.loading_manager.reset()

    progress_dialog = request.loading_manager.create_progress_dialog(
        request.main_window, request.progress_max, label
    )
    progress_dialog.setValue(0)
    QApplication.processEvents()

    ctx = _AsyncLoadContext(
        request=request,
        is_folder_mode=is_folder_mode,
        on_pipeline_complete=on_pipeline_complete,
        loading_started=[False],
        last_ui_update=[0.0],
    )

    worker = LoaderWorker(
        request.loader_fn,
        organize_fn=partial(_organize_on_worker, ctx),
    )
    worker.progress.connect(partial(_handle_progress, ctx))
    worker.finished.connect(partial(_handle_finished, ctx))
    worker.organized.connect(partial(_handle_organized, ctx))
    worker.error.connect(partial(_handle_error, ctx))
    worker.start()
    return worker


def _organize_on_worker(ctx: _AsyncLoadContext, datasets: list[Any]) -> MergeResult:
    """``merge_batch`` on the worker thread (no Qt UI)."""
    merge_paths = resolve_merge_paths(datasets, ctx.request.file_paths_for_merge)
    return ctx.request.organizer.merge_batch(
        datasets, merge_paths, ctx.request.source_dir
    )


def _handle_progress(
    ctx: _AsyncLoadContext, current: int, total: int, filename: str
) -> None:
    """Queued progress slot: refresh dialog and honor cancel."""
    update_loading_progress_dialog(
        ctx.request.loading_manager,
        current,
        total,
        filename,
        ctx.loading_started,
        ctx.last_ui_update,
    )


def _complete_pipeline(
    ctx: _AsyncLoadContext,
    datasets: list[Any] | None,
    studies: dict[str, Any] | None,
) -> None:
    if ctx.on_pipeline_complete:
        ctx.on_pipeline_complete(datasets, studies)


def _abort_empty_cancel(ctx: _AsyncLoadContext) -> bool:
    """If cancelled with no datasets, update status and return True (caller should stop)."""
    request = ctx.request
    if not request.loading_manager.is_cancelled():
        return False
    request.update_status_callback(_STATUS_LOADING_CANCELLED)
    request.loader.reset_cancellation()
    request.loading_manager.stop_animated_loading()
    _complete_pipeline(ctx, None, None)
    return True


def _warn_failed_files(ctx: _AsyncLoadContext) -> None:
    warning_msg = failed_files_warning_message(
        ctx.request.loader.get_failed_files(),
        is_folder_mode=ctx.is_folder_mode,
    )
    if warning_msg is not None:
        ctx.request.file_dialog.show_warning(
            ctx.request.main_window, _TITLE_LOADING_WARNINGS, warning_msg
        )


def _handle_finished(
    ctx: _AsyncLoadContext, datasets: list[Any], _failed: list[Any]
) -> None:
    """Fallback when organise did not run (empty / cancelled / no organize_fn)."""
    request = ctx.request
    request.loading_manager.close_progress_dialog()

    if request.loading_manager.is_cancelled():
        num_loaded = len(datasets) if datasets else 0
        if num_loaded <= 0 and _abort_empty_cancel(ctx):
            return

    request.loading_manager.stop_animated_loading()

    if not datasets:
        request.file_dialog.show_error(
            request.main_window,
            _TITLE_ERROR,
            empty_load_error_message(
                request.loader.get_failed_files(),
                is_folder_mode=ctx.is_folder_mode,
            ),
        )
        _complete_pipeline(ctx, None, None)
        return

    _warn_failed_files(ctx)
    request.loader.reset_cancellation()
    _complete_pipeline(ctx, None, None)


def _try_display_first_slice(ctx: _AsyncLoadContext, merge_result: MergeResult) -> bool:
    """Run UI handoff; return False if display failed (error dialogs already shown)."""
    request = ctx.request
    try:
        with perf_timer("first_paint.prehandoff.pipeline_async.ui_handoff"):
            request.load_first_slice_callback(merge_result)
        return True
    except MemoryError as e:
        request.file_dialog.show_error(
            request.main_window,
            _TITLE_MEMORY_ERROR,
            f"Out of memory while displaying image. "
            f"Try closing other applications.\n\nError: {e}",
        )
        _complete_pipeline(ctx, None, None)
        return False
    except Exception as e:
        request.file_dialog.show_error(
            request.main_window, _TITLE_ERROR, f"Error displaying first slice: {e}"
        )
        _complete_pipeline(ctx, None, None)
        return False


def _finish_organized_success(
    ctx: _AsyncLoadContext,
    datasets: list[Any],
    merge_result: MergeResult,
    was_cancelled: bool,
) -> None:
    """Status bar, optional index callback, deferred GC, pipeline-complete."""
    request = ctx.request
    merge_paths = resolve_merge_paths(datasets, request.file_paths_for_merge)
    final_status = build_post_load_status(
        merge_result=merge_result,
        loader=request.loader,
        source_name=request.source_name,
        was_cancelled=was_cancelled,
        check_compression_errors=request.check_compression_errors,
    )
    request.update_status_callback(final_status)
    QApplication.processEvents()
    request.loader.reset_cancellation()

    if request.on_load_success is not None:
        try:
            request.on_load_success(
                datasets,
                request.organizer.studies,
                merge_result,
                request.source_dir,
                merge_paths,
                was_cancelled=was_cancelled,
            )
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

    if len(datasets) > 100:
        QTimer.singleShot(2000, gc.collect)

    _complete_pipeline(ctx, datasets, request.organizer.studies)


def _handle_organized(
    ctx: _AsyncLoadContext, datasets: list[Any], merge_result: MergeResult
) -> None:
    """Main-thread slot after worker-thread ``merge_batch``."""
    request = ctx.request
    perf_mark(
        "first_paint.prehandoff.pipeline_async.organized_signal",
        datasets=len(datasets),
        new_series=len(getattr(merge_result, "new_series", [])),
        appended_series=len(getattr(merge_result, "appended_series", [])),
        added_files=getattr(merge_result, "added_file_count", 0),
    )
    request.loading_manager.close_progress_dialog()

    was_cancelled = request.loading_manager.is_cancelled()
    if was_cancelled:
        num_loaded = len(datasets) if datasets else 0
        if num_loaded <= 0 and _abort_empty_cancel(ctx):
            return

    request.loading_manager.stop_animated_loading()
    _warn_failed_files(ctx)

    if not _try_display_first_slice(ctx, merge_result):
        return

    _finish_organized_success(ctx, datasets, merge_result, was_cancelled)


def _handle_error(ctx: _AsyncLoadContext, _error_msg: str) -> None:
    """Fatal worker error: redact details in the UI dialog."""
    request = ctx.request
    request.loading_manager.stop_animated_loading()
    request.loading_manager.close_progress_dialog()
    request.loader.reset_cancellation()
    _logger.debug("Loader worker reported a redacted error")
    request.file_dialog.show_error(
        request.main_window,
        "Critical Error",
        "A critical error occurred during loading. Details were withheld "
        "to protect private data.\n\n"
        "This may be due to corrupted or unsupported DICOM files.",
    )
    _complete_pipeline(ctx, None, None)
