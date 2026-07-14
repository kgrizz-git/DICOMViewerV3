"""
File-path actions extracted from ``FileSeriesLoadingCoordinator``.

Module-level functions that open files/folders, resolve dataset file paths,
and drive the "Show file" / "About This File" dialogs.  Each function takes
the ``app`` (``DICOMViewerApp``) instance as its first parameter instead of
operating on ``self``.
"""

from __future__ import annotations

import os
from typing import Any

# -- open helpers ------------------------------------------------------------

def open_files(app: Any) -> None:
    """Handle open files request. Results arrive asynchronously via _on_load_complete."""
    app.file_operations_handler.open_files()


def open_folder(app: Any) -> None:
    """Handle open folder request. Results arrive asynchronously via _on_load_complete."""
    app.file_operations_handler.open_folder()


def open_recent_file(app: Any, file_path: str) -> None:
    """
    Handle open recent file/folder request.

    Args:
        file_path: Path to file or folder to open
    """
    app.file_operations_handler.open_recent_file(file_path)


def open_files_from_paths(app: Any, paths: list[str]) -> None:
    """
    Handle open files/folders from drag-and-drop.

    Args:
        paths: List of file or folder paths to open
    """
    app.file_operations_handler.open_paths(paths)


# -- file-path resolution ---------------------------------------------------

def get_file_path_for_dataset(
    app: Any, dataset: Any, study_uid: str, series_uid: str, slice_index: int
) -> str | None:
    """
    Get file path for a dataset.

    Args:
        app: DICOMViewerApp instance
        dataset: DICOM dataset
        study_uid: Study Instance UID
        series_uid: Series UID (composite key)
        slice_index: Slice index

    Returns:
        File path if found, None otherwise
    """
    if not dataset or not study_uid or not series_uid:
        return None
    if hasattr(dataset, 'filename') and dataset.filename:
        return dataset.filename
    instance_num = None
    if hasattr(dataset, 'InstanceNumber'):
        try:
            instance_num = int(dataset.InstanceNumber)
        except (ValueError, TypeError):
            pass
    if instance_num is not None:
        key = (study_uid, series_uid, instance_num)
        if key in app.dicom_organizer.file_paths:
            return app.dicom_organizer.file_paths[key]
    key = (study_uid, series_uid, slice_index)
    if key in app.dicom_organizer.file_paths:
        return app.dicom_organizer.file_paths[key]
    for (s_uid, ser_uid, inst_num), path in app.dicom_organizer.file_paths.items():
        if s_uid == study_uid and ser_uid == series_uid:
            if instance_num is not None and inst_num == instance_num:
                return path
            if instance_num is None:
                return path
    return None


# -- series-context file actions ---------------------------------------------

def on_show_file_from_series(app: Any, study_uid: str, series_uid: str) -> None:
    """Handle 'Show file' request from series navigator thumbnail; reveals first slice file in explorer."""
    from utils.file_explorer import reveal_file_in_explorer

    if not app.current_studies or study_uid not in app.current_studies:
        return
    study_series = app.current_studies[study_uid]
    if series_uid not in study_series or not study_series[series_uid]:
        return
    first_dataset = study_series[series_uid][0]
    file_path = get_file_path_for_dataset(app, first_dataset, study_uid, series_uid, 0)
    if file_path and os.path.exists(file_path):
        reveal_file_in_explorer(file_path)


def on_about_this_file_from_series(app: Any, study_uid: str, series_uid: str) -> None:
    """Handle 'About This File' request from series navigator thumbnail; opens dialog with first slice."""
    if not app.current_studies or study_uid not in app.current_studies:
        return
    study_series = app.current_studies[study_uid]
    if series_uid not in study_series or not study_series[series_uid]:
        return
    first_dataset = study_series[series_uid][0]
    file_path = get_file_path_for_dataset(app, first_dataset, study_uid, series_uid, 0)
    app.dialog_coordinator.open_about_this_file(first_dataset, file_path)


# -- current-slice helpers ---------------------------------------------------

def get_current_slice_file_path(app: Any, subwindow_idx: int | None = None) -> str | None:
    """Get file path for the currently displayed slice in a subwindow."""
    if subwindow_idx is None:
        subwindow_idx = app.focused_subwindow_index
    dataset = app._get_subwindow_dataset(subwindow_idx)
    study_uid = app._get_subwindow_study_uid(subwindow_idx)
    series_uid = app._get_subwindow_series_uid(subwindow_idx)
    slice_index = app._get_subwindow_slice_index(subwindow_idx)
    if not dataset or not study_uid or not series_uid:
        return None
    return get_file_path_for_dataset(app, dataset, study_uid, series_uid, slice_index)


def update_about_this_file_dialog(app: Any) -> None:
    """Update About This File dialog with current dataset and file path for focused subwindow."""
    focused_idx = app.focused_subwindow_index
    current_dataset = None
    file_path = None
    if focused_idx in app.subwindow_data:
        current_dataset = app.subwindow_data[focused_idx].get('current_dataset')
        if current_dataset:
            file_path = get_file_path_for_dataset(
                app,
                current_dataset,
                app.subwindow_data[focused_idx].get('current_study_uid', ''),
                app.subwindow_data[focused_idx].get('current_series_uid', ''),
                app.subwindow_data[focused_idx].get('current_slice_index', 0)
            )
    app.dialog_coordinator.update_about_this_file(current_dataset, file_path)
