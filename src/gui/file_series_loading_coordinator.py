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
from PySide6.QtCore import QTimer

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
from utils.debug_flags import DEBUG_LOADING, DEBUG_SERIES
from utils.dicom_utils import get_composite_series_key
from utils.perf_timer import perf_mark, perf_timer
from utils.privacy.console import print_redacted

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
            # Disable fusion and clear status for all subwindows when opening new files
            app._reset_fusion_for_all_subwindows()

            # Clear edited tags for previous dataset if it exists
            if app.current_dataset is not None and app.tag_edit_history:
                app.tag_edit_history.clear_edited_tags(app.current_dataset)
            # Clear all subwindows before loading new files
            subwindows = app.multi_window_layout.get_all_subwindows()
            for subwindow in subwindows:
                if subwindow and subwindow.image_viewer:
                    subwindow.image_viewer.scene.clear()
                    subwindow.image_viewer.image_item = None
                    subwindow.image_viewer.viewport().update()

            # Clear overlay items for all subwindows
            for idx in app.subwindow_managers:
                managers = app.subwindow_managers[idx]
                overlay_manager = managers.get('overlay_manager')
                if overlay_manager:
                    subwindows = app.multi_window_layout.get_all_subwindows()
                    if idx < len(subwindows) and subwindows[idx] and subwindows[idx].image_viewer:
                        scene = subwindows[idx].image_viewer.scene
                        overlay_manager.clear_overlay_items(scene)
                    else:
                        overlay_manager.overlay_items.clear()

            # Reset projection state when new files are opened
            app.slice_display_manager.reset_projection_state()
            app.intensity_projection_controls_widget.set_enabled(False)
            app.intensity_projection_controls_widget.set_projection_type("aip")
            app.intensity_projection_controls_widget.set_slice_count(4)

            if app.dialog_coordinator:
                app.dialog_coordinator.clear_tag_viewer_filter()

        with perf_timer("first_paint.load_first_slice_info"):
            first_slice_info = app.file_operations_handler.load_first_slice(studies)
        if first_slice_info:
            app.current_studies = studies
            app._schedule_tag_export_union_rebuild()
            app.current_study_uid = first_slice_info['study_uid']
            app.current_series_uid = first_slice_info['series_uid']
            app.current_slice_index = first_slice_info['slice_index']

            focused_subwindow = app.multi_window_layout.get_focused_subwindow()
            if focused_subwindow:
                subwindows = app.multi_window_layout.get_all_subwindows()
                focused_idx = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
                if focused_idx >= 0 and focused_idx in app.subwindow_managers:
                    fusion_coordinator = app.subwindow_managers[focused_idx].get('fusion_coordinator')
                    if fusion_coordinator:
                        fusion_coordinator.update_fusion_controls_series_list()

            # Clear stale subwindow data that references series not in current_studies
            stale_count = 0
            for idx in list(app.subwindow_data.keys()):
                data = app.subwindow_data[idx]
                study_uid = data.get('current_study_uid', '')
                series_uid = data.get('current_series_uid', '')
                if study_uid and series_uid:
                    if (study_uid not in app.current_studies or
                        series_uid not in app.current_studies.get(study_uid, {})):
                        app.subwindow_data[idx] = {
                            'current_dataset': None,
                            'current_slice_index': 0,
                            'current_series_uid': '',
                            'current_study_uid': '',
                            'current_datasets': []
                        }
                        stale_count += 1
            if stale_count > 0 and DEBUG_LOADING and DEBUG_SERIES:

                print(f"[DEBUG] Cleared stale data from {stale_count} subwindow(s)")

            # Load Presentation States and Key Objects into annotation manager
            all_presentation_states = {}
            all_key_objects = {}
            for study_uid in studies:
                presentation_states = app.dicom_organizer.get_presentation_states(study_uid)
                key_objects = app.dicom_organizer.get_key_objects(study_uid)
                if presentation_states:
                    all_presentation_states[study_uid] = presentation_states
                if key_objects:
                    all_key_objects[study_uid] = key_objects
            if all_presentation_states:
                app.annotation_manager.load_presentation_states(all_presentation_states)
            if all_key_objects:
                app.annotation_manager.load_key_objects(all_key_objects)

            # Always load first series to subwindow 0 and make it focused
            subwindow_0 = app.multi_window_layout.get_subwindow(0)
            if subwindow_0:
                app.multi_window_layout.set_focused_subwindow(subwindow_0)
                app.focused_subwindow_index = 0

            if 0 not in app.subwindow_managers:
                app._ensure_all_subwindows_have_managers()

            managers_0 = app.subwindow_managers[0]
            slice_display_manager_0 = managers_0.get('slice_display_manager')
            view_state_manager_0 = managers_0.get('view_state_manager')

            if view_state_manager_0:
                view_state_manager_0.reset_window_level_state()
                view_state_manager_0.reset_series_tracking()

            app.slice_navigator.set_total_slices(first_slice_info['total_slices'])
            app.slice_navigator.set_current_slice(0)

            if slice_display_manager_0:
                with perf_timer("first_paint.display_slice"):
                    slice_display_manager_0.display_slice(
                        first_slice_info['dataset'],
                        app.current_studies,
                        app.current_study_uid,
                        app.current_series_uid,
                        app.current_slice_index
                    )
                image_item_present = bool(
                    getattr(
                        getattr(slice_display_manager_0, "image_viewer", None),
                        "image_item",
                        None,
                    )
                )
                perf_mark(
                    "first_paint.display_slice.returned",
                    image_item_present=image_item_present,
                )

            app.current_dataset = first_slice_info['dataset']

            focused_idx = 0
            if focused_idx not in app.subwindow_data:
                app.subwindow_data[focused_idx] = {}

            displayed_dataset = first_slice_info['dataset']
            extracted_series_uid = get_composite_series_key(displayed_dataset)
            extracted_study_uid = getattr(displayed_dataset, 'StudyInstanceUID', '')

            if extracted_series_uid != app.current_series_uid and DEBUG_SERIES:

                print("[DEBUG] Syncing subwindow_data after initial load: MISMATCH detected!")
            if extracted_study_uid != app.current_study_uid and DEBUG_SERIES:

                print_redacted(f"[DEBUG]   Extracted study_uid from dataset: {extracted_study_uid}")

            app.subwindow_data[focused_idx]['current_dataset'] = displayed_dataset
            app.subwindow_data[focused_idx]['current_slice_index'] = app.current_slice_index
            app.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
            app.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid

            app.current_series_uid = extracted_series_uid
            app.current_study_uid = extracted_study_uid

            if extracted_study_uid in studies and extracted_series_uid in studies[extracted_study_uid]:
                series_datasets = studies[extracted_study_uid][extracted_series_uid]
                app.subwindow_data[focused_idx]['current_datasets'] = series_datasets
            else:
                series_datasets = studies[app.current_study_uid][app.current_series_uid]
                app.subwindow_data[focused_idx]['current_datasets'] = series_datasets

            if slice_display_manager_0:
                slice_display_manager_0.set_current_data_context(
                    app.current_studies,
                    extracted_study_uid,
                    extracted_series_uid,
                    app.current_slice_index
                )

            if view_state_manager_0:
                view_state_manager_0.current_dataset = first_slice_info['dataset']

            app.view_state_manager = view_state_manager_0
            app.slice_display_manager = slice_display_manager_0
            if 0 in app.subwindow_managers:
                managers_0 = app.subwindow_managers[0]
                app.roi_coordinator = managers_0.get('roi_coordinator')

            app._disconnect_focused_subwindow_signals()
            app._connect_focused_subwindow_signals()

            with perf_timer("first_paint.metadata_cine_history_refresh"):
                app.metadata_panel.clear_filter()
                app.cine_app_facade.update_cine_player_context()

                if app.tag_edit_history:
                    app.tag_edit_history.clear_history(app.current_dataset)
                app._update_undo_redo_state()

            QTimer.singleShot(100, app.view_state_manager.store_initial_view_state)

            with perf_timer("first_paint.navigator.update_series_list"):
                app.series_navigator.update_series_list(
                    app.current_studies,
                    app.current_study_uid,
                    app.current_series_uid
                )
            with perf_timer("first_paint.navigator.refresh_state"):
                app._refresh_series_navigator_state()
            with perf_timer("first_paint.navigator.set_subwindow_assignments"):
                app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())

            navigator_was_hidden = not app.main_window.series_navigator_visible
            if navigator_was_hidden:
                app.main_window.toggle_series_navigator()
            if navigator_was_hidden:
                QTimer.singleShot(50, lambda: app.image_viewer.fit_to_view(center_image=True))

            # Apply slice location lines if enabled. Defer so display/layout has settled.
            app._slice_sync_coordinator.invalidate_cache()
            QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)
            QTimer.singleShot(0, lambda: perf_mark("first_paint.event_loop_returned"))

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
