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
from utils.debug_flags import DEBUG_LOADING, DEBUG_SERIES
from utils.dicom_utils import get_composite_series_key
from utils.perf_timer import perf_mark, perf_timer
from utils.privacy.console import print_redacted

# Human-readable window labels for error messages (1-based).
_WINDOW_LABELS = ["Window 1", "Window 2", "Window 3", "Window 4"]


def _show_duplicate_skip_toast(app: Any, skipped_count: int) -> None:
    """
    Brief toast when additive load skipped files that were already loaded.

    Centered on the main window with a slightly more opaque background than
    default toasts (see NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN §2).
    """
    if skipped_count <= 0:
        return
    app.main_window.show_toast_message(
        f"{skipped_count} file(s) already loaded and skipped",
        position="center",
        bg_alpha=0.85,
    )


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
            if stale_count > 0 and DEBUG_LOADING:
                if DEBUG_SERIES:

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

            if extracted_series_uid != app.current_series_uid:
                if DEBUG_SERIES:

                    print("[DEBUG] Syncing subwindow_data after initial load: MISMATCH detected!")
            if extracted_study_uid != app.current_study_uid:
                if DEBUG_SERIES:

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

        # Always sync current_studies with the organizer (studies dict updated in-place by merge_batch)
        app.current_studies = app.dicom_organizer.studies

        # --- LRU study cache: eviction check ---
        study_cache = getattr(app, "study_cache", None)
        if study_cache is not None and merge_result.new_series:
            # Mark all newly loaded studies as accessed
            new_study_uids = {study_uid for study_uid, _ in merge_result.new_series}
            for uid in new_study_uids:
                study_cache.mark_accessed(uid)

            # Check if we exceed the study limit or memory threshold
            needs_eviction = (
                len(app.current_studies) > study_cache.max_studies
                or study_cache.would_exceed_memory()
            )
            if needs_eviction:
                from core.study_cache import (
                    show_eviction_confirmation,
                )

                active_uid = getattr(app, "current_study_uid", "")
                candidates = study_cache.get_eviction_candidates(
                    app.current_studies,
                    active_study_uid=active_uid,
                )
                if candidates:
                    reason = (
                        "memory limit"
                        if study_cache.would_exceed_memory()
                        else "study limit reached"
                    )
                    descriptions = [
                        study_cache.get_study_description(uid, app.current_studies)
                        for uid in candidates
                    ]
                    parent = getattr(app, "main_window", None)
                    if show_eviction_confirmation(parent, reason, descriptions):
                        for uid in candidates:
                            study_cache.evict_study(uid, app)
                        # Re-sync after eviction
                        app.current_studies = app.dicom_organizer.studies
                    else:
                        # User cancelled: undo the merge by removing newly added studies
                        for uid in new_study_uids:
                            if uid in app.dicom_organizer.studies:
                                app.dicom_organizer.remove_study(uid)
                            study_cache.remove(uid)
                        app.current_studies = app.dicom_organizer.studies
                        app.main_window.statusBar().showMessage(
                            "Load cancelled by user"
                        )
                        return

        # Early-exit: nothing meaningful changed
        if not merge_result.new_series and not merge_result.appended_series:
            app.series_navigator.update_series_list(
                app.current_studies,
                app.current_study_uid,
                app.current_series_uid,
            )
            app._refresh_series_navigator_state()
            app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
            total = merge_result.skipped_file_count
            app.main_window.statusBar().showMessage(
                f"No new files — all {total} already loaded" if total else "No new files loaded"
            )
            if merge_result.skipped_file_count > 0:
                _show_duplicate_skip_toast(app, merge_result.skipped_file_count)
            return

        # Load PS/KO additively for brand-new study UIDs only
        new_study_uids = {study_uid for study_uid, _ in merge_result.new_series}
        new_ps: dict[str, Any] = {}
        new_ko: dict[str, Any] = {}
        for study_uid in new_study_uids:
            ps = app.dicom_organizer.get_presentation_states(study_uid)
            ko = app.dicom_organizer.get_key_objects(study_uid)
            if ps:
                new_ps[study_uid] = ps
            if ko:
                new_ko[study_uid] = ko
        if new_ps:
            app.annotation_manager.load_presentation_states(new_ps)
        if new_ko:
            app.annotation_manager.load_key_objects(new_ko)

        # Update subwindow_data for any series that had new slices appended
        for study_uid, series_key in merge_result.appended_series:
            updated_datasets = app.current_studies.get(study_uid, {}).get(series_key, [])
            for idx, data in app.subwindow_data.items():
                if (data.get('current_study_uid') == study_uid and
                        data.get('current_series_uid') == series_key):
                    data['current_datasets'] = updated_datasets
                    # Refresh slice navigator count if this subwindow is focused
                    if idx == app.focused_subwindow_index:
                        app.slice_navigator.set_total_slices(len(updated_datasets))
                    break

        # Find first empty subwindow for auto-assignment of the first new series
        target_idx = None
        all_subwindows = app.multi_window_layout.get_all_subwindows()
        for idx in range(len(all_subwindows)):
            data = app.subwindow_data.get(idx)
            is_empty = (data is None) or (data.get('current_dataset') is None)
            if is_empty:
                target_idx = idx
                break

        # Auto-assign first new series (by DICOM: StudyDate, StudyTime, SeriesNumber) to the first empty subwindow
        first_pair = _get_first_new_series_by_dicom(merge_result.new_series, app.current_studies)
        if target_idx is not None and first_pair is not None:
            new_study_uid, new_series_key = first_pair
            new_datasets = app.current_studies.get(new_study_uid, {}).get(new_series_key, [])

            if new_datasets:
                first_dataset = new_datasets[0]

                # Ensure per-subwindow managers exist
                if target_idx not in app.subwindow_managers:
                    app._ensure_all_subwindows_have_managers()
                managers = app.subwindow_managers.get(target_idx, {})
                slice_display_manager = managers.get('slice_display_manager')
                view_state_manager = managers.get('view_state_manager')

                # Reset view/projection state for the target subwindow (it was empty)
                if view_state_manager:
                    view_state_manager.reset_window_level_state()
                    view_state_manager.reset_series_tracking()
                if slice_display_manager and hasattr(slice_display_manager, 'reset_projection_state'):
                    slice_display_manager.reset_projection_state()

                # Display the first frame in the target subwindow.
                # Only update global W/L controls and metadata when target is the focused subwindow.
                if slice_display_manager:
                    update_controls = (target_idx == app.focused_subwindow_index)
                    update_metadata = (target_idx == app.focused_subwindow_index)
                    with perf_timer("first_paint.additive.display_slice"):
                        slice_display_manager.display_slice(
                            first_dataset,
                            app.current_studies,
                            new_study_uid,
                            new_series_key,
                            0,
                            update_controls=update_controls,
                            update_metadata=update_metadata,
                        )
                    image_item_present = bool(
                        getattr(
                            getattr(slice_display_manager, "image_viewer", None),
                            "image_item",
                            None,
                        )
                    )
                    perf_mark(
                        "first_paint.additive.display_slice.returned",
                        image_item_present=image_item_present,
                        target_idx=target_idx,
                    )
                    slice_display_manager.set_current_data_context(
                        app.current_studies,
                        new_study_uid,
                        new_series_key,
                        0,
                    )
                    # Deferred fit-to-view so it runs after layout is stable (e.g. after cancel-with-partial-load).
                    target_viewer = slice_display_manager.image_viewer
                    QTimer.singleShot(100, lambda: target_viewer.fit_to_view(center_image=True))

                if view_state_manager:
                    view_state_manager.current_dataset = first_dataset

                # Record the assignment in subwindow_data
                app.subwindow_data[target_idx] = {
                    'current_dataset': first_dataset,
                    'current_slice_index': 0,
                    'current_series_uid': new_series_key,
                    'current_study_uid': new_study_uid,
                    'current_datasets': new_datasets,
                }

                # Update focused-subwindow state only if this is the focused subwindow
                if target_idx == app.focused_subwindow_index:
                    app.current_dataset = first_dataset
                    app.current_study_uid = new_study_uid
                    app.current_series_uid = new_series_key
                    app.current_slice_index = 0
                    app.current_datasets = new_datasets

                    app.view_state_manager = view_state_manager
                    app.slice_display_manager = slice_display_manager
                    if 'roi_coordinator' in managers:
                        app.roi_coordinator = managers['roi_coordinator']

                    app.slice_navigator.set_total_slices(len(new_datasets))
                    app.slice_navigator.set_current_slice(0)

                    app._disconnect_focused_subwindow_signals()
                    app._connect_focused_subwindow_signals()

                    with perf_timer("first_paint.additive.metadata_cine_refresh"):
                        app.metadata_panel.clear_filter()
                        app.cine_app_facade.update_cine_player_context()

                    if view_state_manager:
                        QTimer.singleShot(100, view_state_manager.store_initial_view_state)

        # Refresh series navigator and dot indicators
        with perf_timer("first_paint.additive.navigator.update_series_list"):
            app.series_navigator.update_series_list(
                app.current_studies,
                app.current_study_uid,
                app.current_series_uid,
            )
        with perf_timer("first_paint.additive.navigator.refresh_state"):
            app._refresh_series_navigator_state()
        with perf_timer("first_paint.additive.navigator.set_subwindow_assignments"):
            app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())

        # Show the series navigator if it was hidden and new series were added
        if merge_result.new_series and not app.main_window.series_navigator_visible:
            app.main_window.toggle_series_navigator()

        # Update fusion controls for the focused subwindow
        focused_subwindow = app.multi_window_layout.get_focused_subwindow()
        if focused_subwindow:
            focused_subwindows = app.multi_window_layout.get_all_subwindows()
            focused_idx = (
                focused_subwindows.index(focused_subwindow)
                if focused_subwindow in focused_subwindows
                else -1
            )
            if focused_idx >= 0 and focused_idx in app.subwindow_managers:
                fusion_coordinator = app.subwindow_managers[focused_idx].get('fusion_coordinator')
                if fusion_coordinator:
                    fusion_coordinator.update_fusion_controls_series_list()

        # Status bar and toast feedback
        if merge_result.new_series:
            n = len(merge_result.new_series)
            m = len({s[0] for s in merge_result.new_series})
            app.main_window.statusBar().showMessage(
                f"Loaded {n} new series across {m} studies"
            )
        elif merge_result.appended_series:
            k = merge_result.added_file_count
            app.main_window.statusBar().showMessage(
                f"Added {k} slice(s) to existing series"
            )
        if merge_result.skipped_file_count > 0:
            _show_duplicate_skip_toast(app, merge_result.skipped_file_count)

        # Apply slice location lines if enabled. Defer so display/layout has settled.
        app._slice_sync_coordinator.invalidate_cache()
        QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)
        QTimer.singleShot(0, lambda: perf_mark("first_paint.additive.event_loop_returned"))

        app._schedule_tag_export_union_rebuild()

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
