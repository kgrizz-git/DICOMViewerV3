"""
Loading Pipeline

Shared DICOM load pipeline extracted from FileOperationsHandler.

Provides three pure utility functions and ``run_load_pipeline()``, which
executes the progress-reporting → loading → organising → status-update
pipeline that was previously duplicated across ``open_files``,
``open_folder``, ``open_recent_file``, and ``open_paths``.

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
from typing import Any, Callable, Optional

from PySide6.QtWidgets import QApplication

from core.dicom_loader import DICOMLoader
from core.dicom_organizer import DICOMOrganizer, MergeResult
from core.loading_progress_manager import LoadingProgressManager
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure utility functions
# ---------------------------------------------------------------------------

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
    num_processed: Optional[int] = None,
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
        num_processed: Unused; kept for call-site compatibility.
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


# ---------------------------------------------------------------------------
# Shared pipeline
# ---------------------------------------------------------------------------

def run_load_pipeline(
    *,
    loader_fn: Callable[..., list[Any]],
    source_dir: str,
    source_name: str,
    file_paths_for_merge: Optional[list[str]],
    loader: DICOMLoader,
    organizer: DICOMOrganizer,
    loading_manager: LoadingProgressManager,
    progress_max: int,
    progress_label: Optional[str] = None,
    main_window,
    file_dialog,
    load_first_slice_callback: Callable[..., None],
    update_status_callback: Callable[..., None],
    check_compression_errors: bool = False,
    on_load_success: Optional[
        Callable[[list[Any], dict[str, Any], MergeResult, str, list[str]], None]
    ] = None,
) -> tuple[list[Any] | None, dict[str, Any] | None]:
    """Execute the shared DICOM load pipeline.

    Parameters
    ----------
    loader_fn:
        ``loader_fn(progress_callback) -> datasets``.  The caller builds the
        actual load call (``load_files`` or ``load_directory``) around this
        signature.
    source_dir:
        Directory used for de-dup/disambiguation in ``merge_batch``.
    source_name:
        Human-readable label shown in the progress dialog and status bar.
    file_paths_for_merge:
        File paths passed to ``merge_batch``.  Pass ``None`` for folder loads
        where paths are extracted from ``dataset.filename`` attributes.
    loader:
        :class:`DICOMLoader` instance that performs the actual I/O.
    organizer:
        :class:`DICOMOrganizer` instance for study/series organisation.
    loading_manager:
        :class:`LoadingProgressManager` that owns the progress dialog and
        cancellation state.
    progress_max:
        Initial maximum value for the progress dialog (may grow dynamically).
    progress_label:
        Custom label for the progress dialog.  Defaults to
        ``"Loading files from {source_name}..."``.
    main_window:
        Parent window used for modal dialogs.
    file_dialog:
        :class:`FileDialog` instance used to show error/warning popups.
    load_first_slice_callback:
        Called with the ``MergeResult`` to update the image viewer.
    update_status_callback:
        Called with a status string to update the main-window status bar.
    check_compression_errors:
        When *True*, detect compressed-DICOM failures in the failed-file list
        and append a ``pylibjpeg`` installation hint to the status message.
    on_load_success:
        If set, invoked after a successful load with
        ``(datasets, studies, merge_result, source_dir, merge_paths)`` where
        ``merge_paths`` is the list passed to ``merge_batch``. Errors are
        logged and do not fail the load.

    Returns
    -------
    ``(datasets, studies)`` on success, or ``(None, None)`` on cancellation or
    fatal error.
    """
    # Folder-mode: file_paths_for_merge is None
    _is_folder_mode = file_paths_for_merge is None

    label = progress_label or f"Loading files from {source_name}..."

    try:
        loader.reset_cancellation()
        loading_manager.reset()

        progress_dialog = loading_manager.create_progress_dialog(
            main_window, progress_max, label
        )
        progress_dialog.setValue(0)
        QApplication.processEvents()

        # Progress callback shared by all load variants.
        loading_started = [False]
        last_ui_update = [0.0]
        _UI_INTERVAL = 0.05  # seconds between processEvents calls

        def progress_callback(current: int, total: int, filename: str) -> None:
            if current > 0 and filename:
                loading_started[0] = True

            dlg = loading_manager.get_dialog()
            if dlg:
                if total > dlg.maximum():
                    dlg.setMaximum(total)

                now = time.monotonic()
                if now - last_ui_update[0] >= _UI_INTERVAL:
                    dlg.setValue(current)
                    if filename:
                        if filename.startswith("Deferring"):
                            dlg.setLabelText(filename)
                        else:
                            dlg.setLabelText(
                                f"Loading file {current}/{total}: {filename}..."
                            )
                    else:
                        dlg.setLabelText(
                            f"Loaded {current} file(s). Organizing into studies/series..."
                        )
                    last_ui_update[0] = now
                    QApplication.processEvents()

                if (
                    not loading_manager.is_cancelled()
                    and loading_started[0]
                    and loading_manager.was_dialog_cancelled()
                ):
                    loading_manager.on_cancel_loading()

        datasets = loader_fn(progress_callback)
        loading_manager.close_progress_dialog()

        # ── Cancellation ──────────────────────────────────────────────────
        was_cancelled = loading_manager.is_cancelled()
        if was_cancelled:
            num_loaded = len(datasets) if datasets else 0
            if num_loaded > 0:
                update_status_callback(
                    f"Loading cancelled. {num_loaded} file(s) loaded successfully."
                )
                # Continue with partial data
            else:
                update_status_callback("Loading cancelled.")
                loader.reset_cancellation()
                return None, None

        loading_manager.stop_animated_loading()

        # ── Empty result ───────────────────────────────────────────────────
        if not datasets:
            failed = loader.get_failed_files()
            if _is_folder_mode:
                if failed:
                    error_msg = (
                        f"No DICOM files found in folder.\n\n"
                        f"{len(failed)} file(s) could not be loaded."
                    )
                else:
                    error_msg = "No DICOM files found in folder."
            else:
                if failed:
                    error_msg = "No DICOM files could be loaded.\n\nErrors:\n"
                    for path, error in failed[:5]:
                        error_msg += f"\n{os.path.basename(path)}: {error}"
                    if len(failed) > 5:
                        error_msg += f"\n... and {len(failed) - 5} more"
                else:
                    error_msg = "No DICOM files could be loaded."
            file_dialog.show_error(main_window, "Error", error_msg)
            return None, None

        # ── Warnings for failed files ──────────────────────────────────────
        failed = loader.get_failed_files()
        if failed:
            if _is_folder_mode:
                warning_msg = f"Warning: {len(failed)} file(s) could not be loaded."
            else:
                warning_msg = (
                    f"Warning: {len(failed)} file(s) could not be loaded:\n"
                )
                for path, error in failed[:5]:
                    warning_msg += f"\n{os.path.basename(path)}: {error}"
                if len(failed) > 5:
                    warning_msg += f"\n... and {len(failed) - 5} more"
            file_dialog.show_warning(main_window, "Loading Warnings", warning_msg)

        # ── GC before organising large batches ─────────────────────────────
        if len(datasets) > 100:
            gc.collect()
            QApplication.processEvents()

        # ── Organise ──────────────────────────────────────────────────────
        merge_paths = (
            file_paths_for_merge
            if not _is_folder_mode
            else [
                p
                for p in (getattr(ds, "filename", None) for ds in datasets)
                if isinstance(p, str)
            ]
        )
        try:
            merge_result = organizer.merge_batch(datasets, merge_paths, source_dir)
        except MemoryError as e:
            file_dialog.show_error(
                main_window,
                "Memory Error",
                f"Out of memory while organizing DICOM files. "
                f"Try closing other applications or loading fewer files.\n\nError: {e}",
            )
            return None, None
        except Exception as e:
            file_dialog.show_error(
                main_window, "Error", f"Error organizing DICOM files: {e}"
            )
            return None, None

        # ── Display first slice ────────────────────────────────────────────
        try:
            load_first_slice_callback(merge_result)
        except MemoryError as e:
            file_dialog.show_error(
                main_window,
                "Memory Error",
                f"Out of memory while displaying image. "
                f"Try closing other applications.\n\nError: {e}",
            )
            return None, None
        except Exception as e:
            file_dialog.show_error(
                main_window, "Error", f"Error displaying first slice: {e}"
            )
            return None, None

        # ── Status bar update ──────────────────────────────────────────────
        num_studies, num_series, num_files = batch_counts_from_merge_result(merge_result)
        extension_skipped = loader.get_extension_skipped_count()
        num_processed = loader.get_attempted_file_count() + extension_skipped
        non_dicom_count = len(loader.get_failed_files())
        duplicate_count = merge_result.skipped_file_count
        final_status = format_final_status(
            num_studies,
            num_series,
            num_files,
            source_name,
            num_processed=num_processed,
            non_dicom_count=non_dicom_count,
            duplicate_count=duplicate_count,
            extension_skipped_count=extension_skipped,
        )

        if check_compression_errors:
            failed_files = loader.get_failed_files()
            compression_errors = [
                f
                for f in failed_files
                if "Compressed DICOM" in f[1] or "pylibjpeg" in f[1].lower()
            ]
            if compression_errors:
                final_status += (
                    f". {len(compression_errors)} compressed file(s) require pylibjpeg:"
                    " pip install pylibjpeg pyjpegls"
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
                )
            except Exception:
                _logger.debug("%s", sanitized_format_exc())
        return datasets, organizer.studies

    except (SystemExit, KeyboardInterrupt):
        loading_manager.stop_animated_loading()
        loading_manager.close_progress_dialog()
        loader.reset_cancellation()
        raise

    except MemoryError as e:
        loading_manager.stop_animated_loading()
        loading_manager.close_progress_dialog()
        loader.reset_cancellation()
        file_dialog.show_error(
            main_window,
            "Memory Error",
            f"Out of memory while loading. "
            f"Try closing other applications or use a system with more memory.\n\nError: {e}",
        )
        return None, None

    except BaseException as e:
        loading_manager.stop_animated_loading()
        loading_manager.close_progress_dialog()
        loader.reset_cancellation()
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
