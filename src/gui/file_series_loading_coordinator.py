"""
File/Series Loading Coordinator

This module owns file and series loading behavior and first-slice display for the
DICOM viewer. It is called from the main application when the user opens files,
folders, or recent items, and when series navigation or file-path actions occur.

Purpose:
    - Own _handle_load_first_slice logic (clear state, load first slice, update UI).
    - Own open_files, open_folder, open_recent_file, open_files_from_paths.
    - Own series navigation and series navigator selection.
    - Own file-path helpers (get_file_path_for_dataset, show file, about this file).

Inputs:
    - App reference (DICOMViewerApp instance) providing layout, managers, dialogs,
      config, and callbacks. The coordinator does not import main; it receives
      the app and calls app.xxx for state and UI.

Outputs:
    - Loading behavior: opening files/folders/recent/paths and displaying first slice.
    - Series navigation and assignment to subwindows.
    - File path resolution and "Show file" / "About this file" actions.

Callback interface (what the app must provide):
    The coordinator uses the app object for all state and UI. The app is expected
    to have at least: file_operations_handler, dicom_organizer, multi_window_layout,
    subwindow_managers, subwindow_data, slice_navigator, series_navigator,
    metadata_panel, dialog_coordinator, tag_edit_history, annotation_manager,
    intensity_projection_controls_widget, main_window, image_viewer (focused),
    view_state_manager, slice_display_manager, roi_coordinator; and methods
    _reset_fusion_for_all_subwindows, _ensure_all_subwindows_have_managers,
    _disconnect_focused_subwindow_signals, _connect_focused_subwindow_signals,
    cine_app_facade (``update_cine_player_context``), _update_undo_redo_state; and attributes
    current_dataset, current_studies, current_study_uid, current_series_uid,
    current_slice_index, current_datasets, focused_subwindow_index.
"""
from typing import Any

from pydicom.dataset import Dataset

from core.file_path_actions import (
    get_current_slice_file_path as _fpa_get_current_slice_file_path,
)
from core.file_path_actions import (
    get_file_path_for_dataset as _fpa_get_file_path_for_dataset,
)
from core.file_path_actions import (
    on_about_this_file_from_series as _fpa_on_about_this_file_from_series,
)
from core.file_path_actions import (
    on_show_file_from_series as _fpa_on_show_file_from_series,
)
from core.file_path_actions import (
    open_files as _fpa_open_files,
)
from core.file_path_actions import (
    open_files_from_paths as _fpa_open_files_from_paths,
)
from core.file_path_actions import (
    open_folder as _fpa_open_folder,
)
from core.file_path_actions import (
    open_recent_file as _fpa_open_recent_file,
)
from core.file_path_actions import (
    update_about_this_file_dialog as _fpa_update_about_this_file_dialog,
)
from core.series_navigation_controller import (
    assign_series_to_subwindow as _snc_assign_series_to_subwindow,
)
from core.series_navigation_controller import (
    build_flat_series_list as _snc_build_flat_series_list,
)
from core.series_navigation_controller import (
    on_assign_series_from_context_menu as _snc_on_assign_series_from_context_menu,
)
from core.series_navigation_controller import (
    on_series_navigation_requested as _snc_on_series_navigation_requested,
)
from core.series_navigation_controller import (
    on_series_navigator_instance_selected as _snc_on_series_navigator_instance_selected,
)
from core.series_navigation_controller import (
    on_series_navigator_selected as _snc_on_series_navigator_selected,
)
from gui.file_series_additive_load import (
    auto_assign_first_new_series,
    find_first_empty_subwindow_index,
    finish_additive_load_side_effects,
    handle_additive_noop_refresh,
    load_ps_ko_for_new_studies,
    maybe_evict_after_additive_load,
    maybe_show_navigator_for_new_series,
    refresh_appended_series_subwindows,
    refresh_focused_fusion_series_list,
    refresh_navigator_after_additive,
    show_additive_load_status,
    show_duplicate_skip_toast,
)
from gui.file_series_first_slice_load import (
    apply_first_slice_load,
    pre_first_slice_reset,
)
from utils.perf_timer import perf_mark, perf_timer

# Human-readable window labels for error messages (1-based).
_WINDOW_LABELS = ["Window 1", "Window 2", "Window 3", "Window 4"]


def _show_duplicate_skip_toast(app: Any, skipped_count: int) -> None:
    """Backward-compatible alias for ``show_duplicate_skip_toast``."""
    show_duplicate_skip_toast(app, skipped_count)


def show_cancelled_index_skip_toast(app: Any) -> None:
    """
    Warning toast when a partial cancel skips study-index auto-add.

    Shown at the same time as the status-bar *Study index update skipped* message
    (centered, slightly more opaque — matches duplicate-skip toast style).
    """
    app.main_window.show_toast_message(
        "Folder loading canceled — study not added to index",
        position="center",
        bg_alpha=0.85,
        severity="warning",
    )


def _get_first_new_series_by_dicom(
    new_series: list[tuple[str, str]],
    current_studies: dict[str, dict[str, list[Dataset]]],
) -> tuple[str, str] | None:
    """
    From the list of (study_uid, series_key) newly added in a batch, return the one
    that is "first" using the same logic as the series navigator: first study in
    navigator order (dict iteration of current_studies), then series with lowest
    SeriesNumber in that study. So the auto-loaded series is always from the
    first study shown in the navigator.

    Args:
        new_series: List of (study_uid, series_key) from MergeResult.new_series.
        current_studies: Organized studies dict (study_uid -> series_key -> [datasets]).

    Returns:
        (study_uid, series_key) or None if new_series is empty or no datasets.
    """
    if not new_series or not current_studies:
        return None
    new_series_by_study: dict[str, list[str]] = {}
    for study_uid, series_key in new_series:
        new_series_by_study.setdefault(study_uid, []).append(series_key)
    for study_uid in current_studies:
        if study_uid not in new_series_by_study:
            continue
        candidates = []
        for series_key in new_series_by_study[study_uid]:
            datasets = current_studies.get(study_uid, {}).get(series_key, [])
            if not datasets:
                continue
            sn = getattr(datasets[0], 'SeriesNumber', None)
            try:
                sn = int(sn) if sn is not None else 0
            except (ValueError, TypeError):
                sn = 0
            candidates.append((sn, series_key))
        if not candidates:
            continue
        candidates.sort(key=lambda x: x[0])
        return (study_uid, candidates[0][1])
    return None


class FileSeriesLoadingCoordinator:
    """
    Coordinates file/series loading and first-slice display.

    Receives the main application instance (app) and delegates all state/UI
    access through it to avoid circular imports and keep a single source of truth.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the coordinator with a reference to the main application.

        Args:
            app: The DICOMViewerApp instance (or any object providing the
                 attributes and methods documented in the module docstring).
        """
        self.app = app

    def handle_load_first_slice(
        self, studies: dict[str, dict[str, list[Dataset]]]
    ) -> None:
        """
        Handle loading first slice after file operations.

        Clears edited tags for the previous dataset, clears subwindows and
        overlays, resets projection state, loads first slice via
        file_operations_handler, updates app state and UI (navigators, panels,
        fusion, presentation states, key objects).
        """
        app = self.app

        perf_mark("first_paint.handle_load_first_slice.start", studies=len(studies))

        with perf_timer("first_paint.pre_first_slice_reset"):
            pre_first_slice_reset(app)

        with perf_timer("first_paint.load_first_slice_info"):
            first_slice_info = app.file_operations_handler.load_first_slice(studies)
        if first_slice_info:
            apply_first_slice_load(app, studies, first_slice_info)

    def handle_additive_load(self, merge_result: Any) -> None:
        """
        Handle the result of an additive (non-destructive) file load.

        Called after merge_batch() has updated dicom_organizer.studies in-place.
        Assigns the first new series to the first empty subwindow (if any), updates
        subwindow_data for appended series, and refreshes UI without disturbing
        existing subwindow content or focus.

        Args:
            merge_result: MergeResult dataclass from DICOMOrganizer.merge_batch(),
                          containing new_series, appended_series, skipped_file_count,
                          and added_file_count.
        """
        app = self.app
        perf_mark(
            "first_paint.handle_additive_load.start",
            new_series=len(getattr(merge_result, "new_series", [])),
            appended_series=len(getattr(merge_result, "appended_series", [])),
            added_files=getattr(merge_result, "added_file_count", 0),
        )

        # Always sync current_studies with the organizer (updated in-place by merge_batch)
        app.current_studies = app.dicom_organizer.studies

        if not maybe_evict_after_additive_load(app, merge_result):
            return

        if not merge_result.new_series and not merge_result.appended_series:
            handle_additive_noop_refresh(app, merge_result)
            return

        new_study_uids = {study_uid for study_uid, _ in merge_result.new_series}
        load_ps_ko_for_new_studies(app, new_study_uids)
        refresh_appended_series_subwindows(app, merge_result.appended_series)

        target_idx = find_first_empty_subwindow_index(app)
        first_pair = _get_first_new_series_by_dicom(merge_result.new_series, app.current_studies)
        if target_idx is not None and first_pair is not None:
            auto_assign_first_new_series(app, target_idx, first_pair)

        refresh_navigator_after_additive(app)
        maybe_show_navigator_for_new_series(app, merge_result)
        refresh_focused_fusion_series_list(app)
        show_additive_load_status(app, merge_result)
        finish_additive_load_side_effects(app)

    def _on_load_complete(self, datasets, studies) -> None:
        """Callback for async pipeline completion. Updates app state."""
        if datasets is not None and studies is not None:
            self.app.current_datasets = datasets
            self.app.current_studies = studies
            # Mark all loaded studies as accessed in the LRU cache
            study_cache = getattr(self.app, "study_cache", None)
            if study_cache is not None:
                for study_uid in studies:
                    study_cache.mark_accessed(study_uid)
            self.app._schedule_tag_export_union_rebuild()

    def open_files(self) -> None:
        """Body in ``file_path_actions``."""
        _fpa_open_files(self.app)

    def open_folder(self) -> None:
        """Body in ``file_path_actions``."""
        _fpa_open_folder(self.app)

    def open_recent_file(self, file_path: str) -> None:
        """Body in ``file_path_actions``."""
        _fpa_open_recent_file(self.app, file_path)

    def open_files_from_paths(self, paths: list[str]) -> None:
        """Body in ``file_path_actions``."""
        _fpa_open_files_from_paths(self.app, paths)

    def build_flat_series_list(
        self, studies: dict[str, dict[str, list[Dataset]]]
    ) -> list[tuple[int, str, str, Dataset]]:
        """Body in ``series_navigation_controller``."""
        return _snc_build_flat_series_list(studies)

    def assign_series_to_subwindow(
        self,
        subwindow: Any,
        series_uid: str,
        slice_index: int,
        target_study_uid: str | None = None,
    ) -> None:
        """Body in ``series_navigation_controller``."""
        _snc_assign_series_to_subwindow(self.app, subwindow, series_uid, slice_index, target_study_uid)

    def on_series_navigator_selected(self, series_uid: str) -> None:
        """Body in ``series_navigation_controller``."""
        _snc_on_series_navigator_selected(self.app, series_uid)

    def on_series_navigator_instance_selected(self, study_uid: str, series_uid: str, slice_index: int) -> None:
        """Body in ``series_navigation_controller``."""
        _snc_on_series_navigator_instance_selected(self.app, study_uid, series_uid, slice_index)

    def on_assign_series_from_context_menu(self, series_uid: str) -> None:
        """Body in ``series_navigation_controller``."""
        _snc_on_assign_series_from_context_menu(self.app, series_uid)

    def on_series_navigation_requested(self, direction: int) -> None:
        """Body in ``series_navigation_controller``."""
        _snc_on_series_navigation_requested(self.app, direction)

    def get_file_path_for_dataset(
        self, dataset: Any, study_uid: str, series_uid: str, slice_index: int
    ) -> str | None:
        """Body in ``file_path_actions``."""
        return _fpa_get_file_path_for_dataset(self.app, dataset, study_uid, series_uid, slice_index)

    def on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Body in ``file_path_actions``."""
        _fpa_on_show_file_from_series(self.app, study_uid, series_uid)

    def on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Body in ``file_path_actions``."""
        _fpa_on_about_this_file_from_series(self.app, study_uid, series_uid)

    def get_current_slice_file_path(self, subwindow_idx: int | None = None) -> str | None:
        """Body in ``file_path_actions``."""
        return _fpa_get_current_slice_file_path(self.app, subwindow_idx)

    def update_about_this_file_dialog(self) -> None:
        """Body in ``file_path_actions``."""
        _fpa_update_about_this_file_dialog(self.app)
