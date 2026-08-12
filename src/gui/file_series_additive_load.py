"""
Additive (non-destructive) load helpers for FileSeriesLoadingCoordinator.

Extracted from ``FileSeriesLoadingCoordinator.handle_additive_load`` to clear
Sonar ``python:S3776`` (cognitive complexity) while preserving study-cache
eviction, empty-subwindow auto-assign, navigator refresh, and status feedback.

Inputs:
    - App object (DICOMViewerApp-like) with organizer, layout, managers, UI
    - MergeResult from ``DICOMOrganizer.merge_batch``

Outputs:
    - Updated app/subwindow state and UI side effects for an additive load

Requirements:
    - PySide6 QTimer for deferred fit-to-view / slice-location refresh
    - Optional ``app.study_cache`` for LRU eviction prompts
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QTimer

from utils.perf_timer import perf_mark, perf_timer


def show_duplicate_skip_toast(app: Any, skipped_count: int) -> None:
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


def _top_up_count_cap_candidates(
    study_cache: Any,
    studies: Any,
    candidates: list[str],
    active_uid: str,
) -> list[str]:
    """Append count-based eviction UIDs when size-based picks leave us over the cap."""
    remaining_after = len(studies) - len(candidates)
    if remaining_after <= study_cache.max_studies:
        return candidates
    for uid in study_cache.get_eviction_candidates(studies, active_study_uid=active_uid):
        if uid not in candidates:
            candidates.append(uid)
    return candidates


def _undo_additive_merge_studies(
    app: Any, study_cache: Any, new_study_uids: set[str]
) -> None:
    """Remove newly added studies after the user cancels an eviction prompt."""
    for uid in new_study_uids:
        if uid in app.dicom_organizer.studies:
            app.dicom_organizer.remove_study(uid)
        study_cache.remove(uid)
    app.current_studies = app.dicom_organizer.studies
    app.main_window.statusBar().showMessage("Load cancelled by user")


def maybe_evict_after_additive_load(app: Any, merge_result: Any) -> bool:
    """
    Run study-cache eviction when memory/count limits are exceeded.

    Returns:
        False when the user cancels eviction (merge undone; caller must abort).
        True when eviction is not needed, confirmed, or no candidates exist.
    """
    study_cache = getattr(app, "study_cache", None)
    if study_cache is None or not merge_result.new_series:
        return True

    new_study_uids = {study_uid for study_uid, _ in merge_result.new_series}
    for uid in new_study_uids:
        study_cache.mark_accessed(uid)

    budget_mb = study_cache.get_memory_budget_mb()
    estimated_loaded_mb = study_cache.estimate_total_loaded_mb(app.current_studies)
    memory_exceeded = (
        estimated_loaded_mb > budget_mb or study_cache.would_exceed_memory(budget_mb)
    )
    count_exceeded = len(app.current_studies) > study_cache.max_studies
    if not (memory_exceeded or count_exceeded):
        return True

    from core.study_cache import show_eviction_confirmation

    active_uid = getattr(app, "current_study_uid", "")
    candidates = study_cache.get_eviction_candidates_by_size(
        app.current_studies,
        budget_mb,
        active_study_uid=active_uid,
    )
    if count_exceeded:
        candidates = _top_up_count_cap_candidates(
            study_cache, app.current_studies, candidates, active_uid
        )

    if not candidates:
        return True

    reason = "memory budget" if memory_exceeded else "study count cap"
    descriptions = [
        study_cache.get_study_description(uid, app.current_studies) for uid in candidates
    ]
    parent = getattr(app, "main_window", None)
    if show_eviction_confirmation(parent, reason, descriptions):
        for uid in candidates:
            study_cache.evict_study(uid, app)
        app.current_studies = app.dicom_organizer.studies
        return True

    _undo_additive_merge_studies(app, study_cache, new_study_uids)
    return False


def handle_additive_noop_refresh(app: Any, merge_result: Any) -> None:
    """Refresh navigator/status when merge added neither new nor appended series."""
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
        show_duplicate_skip_toast(app, merge_result.skipped_file_count)


def load_ps_ko_for_new_studies(app: Any, new_study_uids: set[str]) -> None:
    """Load presentation states / key objects for brand-new study UIDs only."""
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


def invalidate_fusion_resampler_caches_for_series(
    app: Any,
    series_uids: set[str],
) -> None:
    """Clear fusion resampler caches that reference any of the given series UIDs.

    Additive loads grow series in-place; cached resampled volumes and sorted
    reference grids are keyed by series UID and become stale when slice count
    changes without invalidation.
    """
    if not series_uids:
        return
    for managers in app.subwindow_managers.values():
        fusion_handler = managers.get("fusion_handler")
        if not fusion_handler:
            continue
        resampler = getattr(fusion_handler, "image_resampler", None)
        for series_uid in series_uids:
            if hasattr(fusion_handler, "_slice_location_cache"):
                fusion_handler._slice_location_cache.pop(series_uid, None)
            if resampler:
                resampler.clear_cache(series_uid=series_uid)


def refresh_appended_series_subwindows(app: Any, appended_series: list[tuple[str, str]]) -> None:
    """Update ``subwindow_data`` datasets when slices were appended to open series."""
    appended_series_uids: set[str] = set()
    for study_uid, series_key in appended_series:
        updated_datasets = app.current_studies.get(study_uid, {}).get(series_key, [])
        appended_series_uids.add(series_key)
        for idx, data in app.subwindow_data.items():
            if (
                data.get("current_study_uid") == study_uid
                and data.get("current_series_uid") == series_key
            ):
                data["current_datasets"] = updated_datasets
                if idx == app.focused_subwindow_index:
                    app.slice_navigator.set_total_slices(len(updated_datasets))
    invalidate_fusion_resampler_caches_for_series(app, appended_series_uids)


def find_first_empty_subwindow_index(app: Any) -> int | None:
    """Return the first empty subwindow index, or None if all panes have content."""
    all_subwindows = app.multi_window_layout.get_all_subwindows()
    for idx in range(len(all_subwindows)):
        data = app.subwindow_data.get(idx)
        is_empty = (data is None) or (data.get("current_dataset") is None)
        if is_empty:
            return idx
    return None


def _reset_empty_target_managers(
    slice_display_manager: Any, view_state_manager: Any
) -> None:
    """Clear W/L and projection state before displaying into a previously empty pane."""
    if view_state_manager:
        view_state_manager.reset_window_level_state()
        view_state_manager.reset_series_tracking()
    if slice_display_manager and hasattr(slice_display_manager, "reset_projection_state"):
        slice_display_manager.reset_projection_state()


def _display_first_slice_in_target(
    app: Any,
    *,
    slice_display_manager: Any,
    target_idx: int,
    first_dataset: Any,
    new_study_uid: str,
    new_series_key: str,
) -> None:
    """Display frame 0 in *target_idx* and schedule a deferred fit-to-view."""
    update_controls = target_idx == app.focused_subwindow_index
    update_metadata = target_idx == app.focused_subwindow_index
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
    target_viewer = slice_display_manager.image_viewer
    QTimer.singleShot(100, lambda: target_viewer.fit_to_view(center_image=True))


def _sync_focused_app_state_after_assign(
    app: Any,
    *,
    managers: dict[str, Any],
    slice_display_manager: Any,
    view_state_manager: Any,
    first_dataset: Any,
    new_study_uid: str,
    new_series_key: str,
    new_datasets: list[Any],
) -> None:
    """Update global focused-pane pointers after assigning into the focused subwindow."""
    app.current_dataset = first_dataset
    app.current_study_uid = new_study_uid
    app.current_series_uid = new_series_key
    app.current_slice_index = 0
    app.current_datasets = new_datasets

    app.view_state_manager = view_state_manager
    app.slice_display_manager = slice_display_manager
    if "roi_coordinator" in managers:
        app.roi_coordinator = managers["roi_coordinator"]

    app.slice_navigator.set_total_slices(len(new_datasets))
    app.slice_navigator.set_current_slice(0)

    app._disconnect_focused_subwindow_signals()
    app._connect_focused_subwindow_signals()

    with perf_timer("first_paint.additive.metadata_cine_refresh"):
        app.metadata_panel.clear_filter()
        app.cine_app_facade.update_cine_player_context()

    if view_state_manager:
        QTimer.singleShot(100, view_state_manager.store_initial_view_state)


def auto_assign_first_new_series(
    app: Any,
    target_idx: int,
    first_pair: tuple[str, str],
) -> None:
    """
    Display the first new series (DICOM order) into an empty subwindow.

    When *target_idx* is the focused pane, also sync global app managers and
    slice-navigator state.
    """
    new_study_uid, new_series_key = first_pair
    new_datasets = app.current_studies.get(new_study_uid, {}).get(new_series_key, [])
    if not new_datasets:
        return

    first_dataset = new_datasets[0]

    if target_idx not in app.subwindow_managers:
        app._ensure_all_subwindows_have_managers()
    managers = app.subwindow_managers.get(target_idx, {})
    slice_display_manager = managers.get("slice_display_manager")
    view_state_manager = managers.get("view_state_manager")

    _reset_empty_target_managers(slice_display_manager, view_state_manager)

    if slice_display_manager:
        _display_first_slice_in_target(
            app,
            slice_display_manager=slice_display_manager,
            target_idx=target_idx,
            first_dataset=first_dataset,
            new_study_uid=new_study_uid,
            new_series_key=new_series_key,
        )

    if view_state_manager:
        view_state_manager.current_dataset = first_dataset

    app.subwindow_data[target_idx] = {
        "current_dataset": first_dataset,
        "current_slice_index": 0,
        "current_series_uid": new_series_key,
        "current_study_uid": new_study_uid,
        "current_datasets": new_datasets,
    }

    if target_idx == app.focused_subwindow_index:
        _sync_focused_app_state_after_assign(
            app,
            managers=managers,
            slice_display_manager=slice_display_manager,
            view_state_manager=view_state_manager,
            first_dataset=first_dataset,
            new_study_uid=new_study_uid,
            new_series_key=new_series_key,
            new_datasets=new_datasets,
        )


def refresh_navigator_after_additive(app: Any) -> None:
    """Refresh series list, navigator state, and subwindow assignment dots."""
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


def maybe_show_navigator_for_new_series(app: Any, merge_result: Any) -> None:
    """Show the series navigator when new series arrived and it was hidden."""
    if merge_result.new_series and not app.main_window.series_navigator_visible:
        app.main_window.toggle_series_navigator()


def refresh_focused_fusion_series_list(app: Any) -> None:
    """Ask the focused pane's fusion coordinator to refresh its series lists."""
    focused_subwindow = app.multi_window_layout.get_focused_subwindow()
    if not focused_subwindow:
        return
    focused_subwindows = app.multi_window_layout.get_all_subwindows()
    focused_idx = (
        focused_subwindows.index(focused_subwindow)
        if focused_subwindow in focused_subwindows
        else -1
    )
    if focused_idx < 0 or focused_idx not in app.subwindow_managers:
        return
    fusion_coordinator = app.subwindow_managers[focused_idx].get("fusion_coordinator")
    if fusion_coordinator:
        fusion_coordinator.update_fusion_controls_series_list()


def show_additive_load_status(app: Any, merge_result: Any) -> None:
    """Status-bar summary plus duplicate-skip toast for an additive load."""
    if merge_result.new_series:
        n = len(merge_result.new_series)
        m = len({s[0] for s in merge_result.new_series})
        app.main_window.statusBar().showMessage(
            f"Loaded {n} new series across {m} studies"
        )
    elif merge_result.appended_series:
        k = merge_result.added_file_count
        app.main_window.statusBar().showMessage(f"Added {k} slice(s) to existing series")
    if merge_result.skipped_file_count > 0:
        show_duplicate_skip_toast(app, merge_result.skipped_file_count)


def finish_additive_load_side_effects(app: Any) -> None:
    """Invalidate slice-sync cache, defer location lines, rebuild tag-export union."""
    app._slice_sync_coordinator.invalidate_cache()
    QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)
    QTimer.singleShot(0, lambda: perf_mark("first_paint.additive.event_loop_returned"))
    app._schedule_tag_export_union_rebuild()
