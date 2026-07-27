"""
Loading Pipeline

Shared DICOM load pipeline extracted from FileOperationsHandler.

Provides pure utility helpers and ``run_load_pipeline()``, which executes the
progress-reporting → loading → organising → status-update pipeline that was
previously duplicated across ``open_files``, ``open_folder``,
``open_recent_file``, and ``open_paths``.

The threaded entry point ``run_load_pipeline_async`` is implemented in
``loading_pipeline_async`` and re-exported here for a stable import path.

Inputs:
    - ``loader_fn``: callable that accepts a progress callback and returns a
      list of loaded datasets (wraps ``DICOMLoader.load_files`` or
      ``DICOMLoader.load_directory``).
    - Service objects: DICOMLoader, DICOMOrganizer, LoadingProgressManager.
    - UI references: main_window, file_dialog.
    - Callbacks: load_first_slice_callback, update_status_callback.

Outputs:
    - ``(datasets, studies)`` tuple on success, or ``(None, None)`` on
      cancellation / fatal error.

Optional:
    - ``on_load_success`` — after a successful load, called with
      ``(datasets, studies, merge_result, source_dir, merge_paths)`` for
      features such as the local study index (errors are logged only).
"""

import gc
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer, MergeResult
from core.loading_progress_manager import LoadingProgressManager
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure utility functions
# ---------------------------------------------------------------------------
_STATUS_LOADING_CANCELLED = "Loading cancelled."
_TITLE_LOADING_WARNINGS = "Loading Warnings"
_TITLE_MEMORY_ERROR = "Memory Error"
_TITLE_ERROR = "Error"


def format_source_name(file_paths: list[str]) -> str:
    """Format a human-readable source label for the status bar."""
    if len(file_paths) == 1:
        return os.path.basename(file_paths[0])
    if len(file_paths) > 1:
        return os.path.basename(file_paths[0]) + "..."
    return ""


def format_final_status(
    num_studies: int,
    num_series: int,
    num_files: int,
    source_name: str,
    non_dicom_count: int = 0,
    duplicate_count: int = 0,
    extension_skipped_count: int = 0,
) -> str:
    """Format the final status message shown in the status bar after loading.

    Args:
        num_studies: Number of studies in the batch.
        num_series: Number of series in the batch.
        num_files: Number of files loaded in the batch.
        source_name: Human-readable label for the source.
        non_dicom_count: Files that failed to load (attempted but not DICOM or errors).
        duplicate_count: Duplicate files that were not added.
        extension_skipped_count: Files skipped by extension (not attempted).

    Returns:
        Formatted status string.
    """
    study_text = f"{num_studies} study" if num_studies == 1 else f"{num_studies} studies"
    series_text = f"{num_series} series"
    file_text = f"{num_files} file" + ("s" if num_files != 1 else "")
    main = f"{study_text}, {series_text}, {file_text} loaded from {source_name}"

    total_non_dicom = extension_skipped_count + non_dicom_count
    if total_non_dicom > 0 or duplicate_count > 0:
        parts = []
        if total_non_dicom > 0:
            parts.append(f"{total_non_dicom} non-DICOM")
        if duplicate_count > 0:
            parts.append(f"{duplicate_count} duplicate" + ("s" if duplicate_count != 1 else ""))
        main += " (" + ", ".join(parts) + " skipped)"

    return main


def format_cancelled_partial_status(num_loaded: int, total_attempted: int) -> str:
    """Status-bar text after the user cancels a load that already read some files."""
    if total_attempted > num_loaded:
        return (
            f"Loading cancelled — {num_loaded} of {total_attempted} file(s) loaded. "
            "Study index update skipped."
        )
    return (
        f"Loading cancelled — {num_loaded} file(s) loaded. "
        "Study index update skipped."
    )


def batch_counts_from_merge_result(merge_result) -> tuple[int, int, int]:
    """Return batch-only (num_studies, num_series, num_files) from a MergeResult.

    Uses only the series actually added in this batch so the status bar
    reflects the current load even after partial cancellations or deduplication.
    """
    combined = merge_result.new_series + merge_result.appended_series
    num_studies = len({s[0] for s in combined})
    num_series = len(combined)
    num_files = merge_result.added_file_count
    return (num_studies, num_series, num_files)


def resolve_merge_paths(
    datasets: list[Any],
    file_paths_for_merge: list[str] | None,
) -> list[str]:
    """Paths for ``merge_batch``: explicit list, or ``dataset.filename`` in folder mode."""
    if file_paths_for_merge is not None:
        return file_paths_for_merge
    return [
        p
        for p in (getattr(ds, "filename", None) for ds in datasets)
        if isinstance(p, str)
    ]


def empty_load_error_message(
    failed: list[tuple[str, str]],
    *,
    is_folder_mode: bool,
) -> str:
    """User-facing error when a load produced zero datasets."""
    if is_folder_mode:
        if failed:
            return (
                f"No DICOM files found in folder.\n\n"
                f"{len(failed)} file(s) could not be loaded."
            )
        return "No DICOM files found in folder."
    if failed:
        error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
        for path, error in failed[:5]:
            error_msg += f"\n{os.path.basename(path)}: {error}"
        if len(failed) > 5:
            error_msg += f"\n... and {len(failed) - 5} more"
        return error_msg
    return "No DICOM files could be loaded."


def failed_files_warning_message(
    failed: list[tuple[str, str]],
    *,
    is_folder_mode: bool,
) -> str | None:
    """Warning text for partial load failures, or ``None`` when nothing failed."""
    if not failed:
        return None
    if is_folder_mode:
        return f"Warning: {len(failed)} file(s) could not be loaded."
    warning_msg = f"Warning: {len(failed)} file(s) could not be loaded:\n"
    for path, error in failed[:5]:
        warning_msg += f"\n{os.path.basename(path)}: {error}"
    if len(failed) > 5:
        warning_msg += f"\n... and {len(failed) - 5} more"
    return warning_msg


def build_post_load_status(
    *,
    merge_result: MergeResult,
    loader: DICOMLoader,
    source_name: str,
    was_cancelled: bool,
    check_compression_errors: bool,
) -> str:
    """Status-bar text after organise/display (full success or partial cancel)."""
    num_studies, num_series, num_files = batch_counts_from_merge_result(merge_result)
    if was_cancelled:
        return format_cancelled_partial_status(
            num_files, loader.get_attempted_file_count()
        )

    final_status = format_final_status(
        num_studies,
        num_series,
        num_files,
        source_name,
        non_dicom_count=len(loader.get_failed_files()),
        duplicate_count=merge_result.skipped_file_count,
        extension_skipped_count=loader.get_extension_skipped_count(),
    )
    if check_compression_errors:
        compression_errors = [
            f
            for f in loader.get_failed_files()
            if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()
        ]
        if compression_errors:
            final_status += (
                f". {len(compression_errors)} compressed file(s) require pylibjpeg:"
                " pip install pylibjpeg pyjpegls"
            )
    return final_status


def _progress_label_text(current: int, total: int, filename: str) -> str:
    """Progress-dialog label for the current load step."""
    if not filename:
        return f"Loaded {current} file(s). Organizing into studies/series..."
    if filename.startswith("Deferring"):
        return filename
    return f"Loading file {current}/{total}: {filename}..."


def update_loading_progress_dialog(
    loading_manager: LoadingProgressManager,
    current: int,
    total: int,
    filename: str,
    loading_started: list[bool],
    last_ui_update: list[float],
    *,
    ui_interval: float = 0.05,
    process_events: bool = False,
) -> None:
    """Refresh the progress dialog and honor cancel once loading has started."""
    if current > 0 and filename:
        loading_started[0] = True

    dlg = loading_manager.get_dialog()
    if not dlg:
        return

    if total > dlg.maximum():
        dlg.setMaximum(total)

    now = time.monotonic()
    if now - last_ui_update[0] >= ui_interval:
        dlg.setValue(current)
        dlg.setLabelText(_progress_label_text(current, total, filename))
        last_ui_update[0] = now
        if process_events:
            QApplication.processEvents()

    if (
        not loading_manager.is_cancelled()
        and loading_started[0]
        and loading_manager.was_dialog_cancelled()
    ):
        loading_manager.on_cancel_loading()


def _merge_batch_or_show_error(
    *,
    organizer: DICOMOrganizer,
    datasets: list[Any],
    merge_paths: list[str],
    source_dir: str,
    main_window: Any,
    file_dialog: Any,
) -> MergeResult | None:
    """Run ``merge_batch``; show an error dialog and return ``None`` on failure."""
    try:
        return organizer.merge_batch(datasets, merge_paths, source_dir)
    except MemoryError as e:
        file_dialog.show_error(
            main_window,
            _TITLE_MEMORY_ERROR,
            f"Out of memory while organizing DICOM files. "
            f"Try closing other applications or loading fewer files.\n\nError: {e}",
        )
        return None
    except Exception as e:
        file_dialog.show_error(
            main_window, _TITLE_ERROR, f"Error organizing DICOM files: {e}"
        )
        return None


def _display_first_slice_or_show_error(
    *,
    load_first_slice_callback: Callable[..., None],
    merge_result: MergeResult,
    main_window: Any,
    file_dialog: Any,
) -> bool:
    """Display first slice; return False if an error dialog was shown."""
    try:
        load_first_slice_callback(merge_result)
        return True
    except MemoryError as e:
        file_dialog.show_error(
            main_window,
            _TITLE_MEMORY_ERROR,
            f"Out of memory while displaying image. "
            f"Try closing other applications.\n\nError: {e}",
        )
        return False
    except Exception as e:
        file_dialog.show_error(
            main_window, _TITLE_ERROR, f"Error displaying first slice: {e}"
        )
        return False


# ---------------------------------------------------------------------------
# Shared pipeline
# ---------------------------------------------------------------------------

@dataclass
class LoadPipelineRequest:
    """Bundled inputs for :func:`run_load_pipeline` / :func:`run_load_pipeline_async`."""

    loader_fn: Callable[..., list[Any]]
    source_dir: str
    source_name: str
    file_paths_for_merge: list[str] | None
    loader: DICOMLoader
    organizer: DICOMOrganizer
    loading_manager: LoadingProgressManager
    progress_max: int
    main_window: Any
    file_dialog: Any
    load_first_slice_callback: Callable[..., None]
    update_status_callback: Callable[..., None]
    progress_label: str | None = None
    check_compression_errors: bool = False
    on_load_success: Callable[..., None] | None = None



def _cleanup_loading_ui(
    loading_manager: LoadingProgressManager, loader: DICOMLoader
) -> None:
    """Stop animation, close dialog, and clear loader cancel state."""
    loading_manager.stop_animated_loading()
    loading_manager.close_progress_dialog()
    loader.reset_cancellation()


def _run_load_pipeline_body(
    request: LoadPipelineRequest,
) -> tuple[list[Any] | None, dict[str, Any] | None]:
    """Core sync load path (progress → load → organise → display → status)."""
    loader_fn = request.loader_fn
    source_dir = request.source_dir
    source_name = request.source_name
    file_paths_for_merge = request.file_paths_for_merge
    loader = request.loader
    organizer = request.organizer
    loading_manager = request.loading_manager
    progress_max = request.progress_max
    progress_label = request.progress_label
    main_window = request.main_window
    file_dialog = request.file_dialog
    load_first_slice_callback = request.load_first_slice_callback
    update_status_callback = request.update_status_callback
    check_compression_errors = request.check_compression_errors
    on_load_success = request.on_load_success
    is_folder_mode = file_paths_for_merge is None
    label = progress_label or f"Loading files from {source_name}..."

    loader.reset_cancellation()
    loading_manager.reset()

    progress_dialog = loading_manager.create_progress_dialog(
        main_window, progress_max, label
    )
    progress_dialog.setValue(0)
    QApplication.processEvents()

    loading_started = [False]
    last_ui_update = [0.0]

    def progress_callback(current: int, total: int, filename: str) -> None:
        update_loading_progress_dialog(
            loading_manager,
            current,
            total,
            filename,
            loading_started,
            last_ui_update,
            process_events=True,
        )

    datasets = loader_fn(progress_callback)
    loading_manager.close_progress_dialog()

    was_cancelled = loading_manager.is_cancelled()
    if was_cancelled:
        num_loaded = len(datasets) if datasets else 0
        if num_loaded <= 0:
            update_status_callback(_STATUS_LOADING_CANCELLED)
            loader.reset_cancellation()
            loading_manager.stop_animated_loading()
            return None, None

    loading_manager.stop_animated_loading()

    if not datasets:
        file_dialog.show_error(
            main_window,
            _TITLE_ERROR,
            empty_load_error_message(
                loader.get_failed_files(), is_folder_mode=is_folder_mode
            ),
        )
        return None, None

    warning_msg = failed_files_warning_message(
        loader.get_failed_files(), is_folder_mode=is_folder_mode
    )
    if warning_msg is not None:
        file_dialog.show_warning(main_window, _TITLE_LOADING_WARNINGS, warning_msg)

    merge_paths = resolve_merge_paths(datasets, file_paths_for_merge)
    merge_result = _merge_batch_or_show_error(
        organizer=organizer,
        datasets=datasets,
        merge_paths=merge_paths,
        source_dir=source_dir,
        main_window=main_window,
        file_dialog=file_dialog,
    )
    if merge_result is None:
        return None, None

    if not _display_first_slice_or_show_error(
        load_first_slice_callback=load_first_slice_callback,
        merge_result=merge_result,
        main_window=main_window,
        file_dialog=file_dialog,
    ):
        return None, None

    final_status = build_post_load_status(
        merge_result=merge_result,
        loader=loader,
        source_name=source_name,
        was_cancelled=was_cancelled,
        check_compression_errors=check_compression_errors,
    )
    update_status_callback(final_status)
    QApplication.processEvents()
    loader.reset_cancellation()
    if on_load_success is not None:
        try:
            on_load_success(
                datasets,
                organizer.studies,
                merge_result,
                source_dir,
                merge_paths,
                was_cancelled=was_cancelled,
            )
        except Exception:
            _logger.debug("%s", sanitized_format_exc())
    if len(datasets) > 100:
        QTimer.singleShot(2000, gc.collect)
    return datasets, organizer.studies


def run_load_pipeline(
    request: LoadPipelineRequest,
) -> tuple[list[Any] | None, dict[str, Any] | None]:
    """Execute the shared DICOM load pipeline.

    See ``LoadPipelineRequest`` for parameter semantics. Returns
    ``(datasets, studies)`` on success, or ``(None, None)`` on cancellation or
    fatal error.
    """
    loader = request.loader
    loading_manager = request.loading_manager
    main_window = request.main_window
    file_dialog = request.file_dialog

    try:
        return _run_load_pipeline_body(request)

    except (SystemExit, KeyboardInterrupt):
        _cleanup_loading_ui(loading_manager, loader)
        raise

    except MemoryError as e:
        _cleanup_loading_ui(loading_manager, loader)
        file_dialog.show_error(
            main_window,
            _TITLE_MEMORY_ERROR,
            f"Out of memory while loading. "
            f"Try closing other applications or use a system with more memory.\n\nError: {e}",
        )
        return None, None

    except BaseException as e:
        _cleanup_loading_ui(loading_manager, loader)
        error_type = type(e).__name__
        _logger.debug("%s", sanitized_format_exc())
        file_dialog.show_error(
            main_window,
            "Critical Error",
            f"A critical error occurred during loading.\n\n"
            f"Error: {error_type}: {e}\n\n"
            "This may be due to corrupted or unsupported DICOM files.",
        )
        return None, None



# ---------------------------------------------------------------------------
# Async (threaded) pipeline — see loading_pipeline_async.py
# ---------------------------------------------------------------------------


def run_load_pipeline_async(
    request: LoadPipelineRequest,
    *,
    on_pipeline_complete: Callable[[list[Any] | None, dict[str, Any] | None], None]
    | None = None,
):
    """Async load pipeline; implementation lives in ``loading_pipeline_async``.

    Uses ``importlib`` so basedpyright does not treat this as an import cycle
    with ``loading_pipeline_async`` (which imports shared types from here).
    """
    import importlib

    async_mod = importlib.import_module("core.loading_pipeline_async")
    return async_mod.run_load_pipeline_async(
        request, on_pipeline_complete=on_pipeline_complete
    )
