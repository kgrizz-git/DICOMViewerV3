"""
First-slice (full replace) load helpers for FileSeriesLoadingCoordinator.

Extracted from ``FileSeriesLoadingCoordinator.handle_load_first_slice`` to clear
Sonar ``python:S3776`` (cognitive complexity) while preserving fusion reset,
overlay clear, projection reset, first-slice display, PS/KO load, navigator
updates, and deferred fit-to-view / slice-location refresh.

Inputs:
    - App object (DICOMViewerApp-like) with layout, managers, navigators, UI
    - Organized studies dict and ``load_first_slice`` result from
      ``file_operations_handler``

Outputs:
    - Cleared subwindow/overlay/projection state before load
    - Updated app/subwindow state and UI after the first slice is displayed

Requirements:
    - PySide6 QTimer for deferred fit-to-view, view-state store, location lines
    - ``utils.perf_timer`` marks for first-paint instrumentation
"""

from __future__ import annotations

from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QTimer

from utils.debug_flags import DEBUG_LOADING, DEBUG_SERIES
from utils.dicom_utils import get_composite_series_key
from utils.perf_timer import perf_mark, perf_timer
from utils.privacy.console import print_redacted

# Default empty subwindow_data entry when clearing stale series references.
_STALE_SUBWINDOW_DATA_TEMPLATE: dict[str, Any] = {
    "current_dataset": None,
    "current_slice_index": 0,
    "current_series_uid": "",
    "current_study_uid": "",
    "current_datasets": [],
}


def pre_first_slice_reset(app: Any) -> None:
    """
    Clear fusion, scenes, overlays, projection controls, and tag-viewer filter.

    Called before ``file_operations_handler.load_first_slice`` when opening files
    via a full replace (not additive merge).
    """
    app._reset_fusion_for_all_subwindows()

    if app.current_dataset is not None and app.tag_edit_history:
        app.tag_edit_history.clear_edited_tags(app.current_dataset)

    _clear_all_subwindow_scenes(app)
    _clear_all_overlay_items(app)

    app.slice_display_manager.reset_projection_state()
    app.intensity_projection_controls_widget.set_enabled(False)
    app.intensity_projection_controls_widget.set_projection_type("aip")
    app.intensity_projection_controls_widget.set_slice_count(4)

    if app.dialog_coordinator:
        app.dialog_coordinator.clear_tag_viewer_filter()


def _clear_all_subwindow_scenes(app: Any) -> None:
    """Clear image viewer scenes for every subwindow before a full replace load."""
    subwindows = app.multi_window_layout.get_all_subwindows()
    for subwindow in subwindows:
        if subwindow and subwindow.image_viewer:
            subwindow.image_viewer.scene.clear()
            subwindow.image_viewer.image_item = None
            subwindow.image_viewer.viewport().update()


def _clear_all_overlay_items(app: Any) -> None:
    """Remove overlay graphics items from each subwindow scene (or internal list)."""
    for idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        overlay_manager = managers.get("overlay_manager")
        if not overlay_manager:
            continue
        subwindows = app.multi_window_layout.get_all_subwindows()
        if idx < len(subwindows) and subwindows[idx] and subwindows[idx].image_viewer:
            scene = subwindows[idx].image_viewer.scene
            overlay_manager.clear_overlay_items(scene)
        else:
            overlay_manager.overlay_items.clear()


def clear_stale_subwindow_data(
    app: Any,
    current_studies: dict[str, dict[str, list[Dataset]]],
) -> int:
    """
    Reset ``subwindow_data`` entries that reference series no longer in *current_studies*.

    Args:
        app: Application with ``subwindow_data`` dict.
        current_studies: Organized studies after ``load_first_slice`` selection.

    Returns:
        Number of subwindow slots cleared.
    """
    stale_count = 0
    for idx in list(app.subwindow_data.keys()):
        data = app.subwindow_data[idx]
        study_uid = data.get("current_study_uid", "")
        series_uid = data.get("current_series_uid", "")
        if not study_uid or not series_uid:
            continue
        if study_uid not in current_studies or series_uid not in current_studies.get(
            study_uid, {}
        ):
            app.subwindow_data[idx] = dict(_STALE_SUBWINDOW_DATA_TEMPLATE)
            stale_count += 1
    if stale_count > 0 and DEBUG_LOADING and DEBUG_SERIES:
        print(f"[DEBUG] Cleared stale data from {stale_count} subwindow(s)")
    return stale_count


def load_presentation_states_and_key_objects(
    app: Any,
    studies: dict[str, dict[str, list[Dataset]]],
) -> None:
    """
    Load presentation states and key objects for every study in *studies*.

    Unlike ``file_series_additive_load.load_ps_ko_for_new_studies``, this loads
    PS/KO for all study UIDs present in a full replace open.
    """
    all_presentation_states: dict[str, Any] = {}
    all_key_objects: dict[str, Any] = {}
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


def focus_subwindow_zero(app: Any) -> None:
    """Focus subwindow 0 and sync ``focused_subwindow_index``."""
    subwindow_0 = app.multi_window_layout.get_subwindow(0)
    if subwindow_0:
        app.multi_window_layout.set_focused_subwindow(subwindow_0)
        app.focused_subwindow_index = 0


def _ensure_subwindow_zero_managers(app: Any) -> dict[str, Any]:
    """Return managers for subwindow 0, creating them when missing."""
    if 0 not in app.subwindow_managers:
        app._ensure_all_subwindows_have_managers()
    return app.subwindow_managers[0]


def _reset_subwindow_zero_view_state(managers_0: dict[str, Any]) -> tuple[Any, Any]:
    """Reset W/L and series tracking on subwindow 0; return display/view managers."""
    view_state_manager_0 = managers_0.get("view_state_manager")
    if view_state_manager_0:
        view_state_manager_0.reset_window_level_state()
        view_state_manager_0.reset_series_tracking()
    return managers_0.get("slice_display_manager"), view_state_manager_0


def _display_first_slice_subwindow_zero(
    app: Any,
    *,
    slice_display_manager_0: Any,
    first_slice_info: dict[str, Any],
) -> None:
    """Render frame 0 in subwindow 0 and emit first-paint perf marks."""
    with perf_timer("first_paint.display_slice"):
        slice_display_manager_0.display_slice(
            first_slice_info["dataset"],
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
            app.current_slice_index,
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


def _resolve_series_datasets_for_subwindow(
    studies: dict[str, dict[str, list[Dataset]]],
    study_uid: str,
    series_uid: str,
) -> list[Dataset]:
    """
    Pick series datasets for subwindow 0 after app UIDs are synced to the dataset.

    Returns the matching list when both UIDs are present; otherwise an empty list
    (avoids a KeyError that the prior identical if/else fallback always raised).
    """
    if study_uid in studies and series_uid in studies[study_uid]:
        return studies[study_uid][series_uid]
    return []


def _sync_subwindow_zero_data(
    app: Any,
    studies: dict[str, dict[str, list[Dataset]]],
    *,
    first_slice_info: dict[str, Any],
    extracted_series_uid: str,
    extracted_study_uid: str,
) -> None:
    """Write subwindow 0 ``subwindow_data`` and align app-level study/series UIDs."""
    focused_idx = 0
    if focused_idx not in app.subwindow_data:
        app.subwindow_data[focused_idx] = {}

    displayed_dataset = first_slice_info["dataset"]
    if extracted_series_uid != app.current_series_uid and DEBUG_SERIES:
        print("[DEBUG] Syncing subwindow_data after initial load: MISMATCH detected!")
    if extracted_study_uid != app.current_study_uid and DEBUG_SERIES:
        print_redacted(
            f"[DEBUG]   Extracted study_uid from dataset: {extracted_study_uid}"
        )

    app.subwindow_data[focused_idx]["current_dataset"] = displayed_dataset
    app.subwindow_data[focused_idx]["current_slice_index"] = app.current_slice_index
    app.subwindow_data[focused_idx]["current_series_uid"] = extracted_series_uid
    app.subwindow_data[focused_idx]["current_study_uid"] = extracted_study_uid

    app.current_series_uid = extracted_series_uid
    app.current_study_uid = extracted_study_uid

    series_datasets = _resolve_series_datasets_for_subwindow(
        studies, extracted_study_uid, extracted_series_uid
    )
    app.subwindow_data[focused_idx]["current_datasets"] = series_datasets


def _sync_focused_managers_from_subwindow_zero(
    app: Any,
    managers_0: dict[str, Any],
    *,
    slice_display_manager_0: Any,
    view_state_manager_0: Any,
    first_slice_info: dict[str, Any],
    extracted_study_uid: str,
    extracted_series_uid: str,
) -> None:
    """Point global app managers at subwindow 0 and reconnect focused signals."""
    if slice_display_manager_0:
        slice_display_manager_0.set_current_data_context(
            app.current_studies,
            extracted_study_uid,
            extracted_series_uid,
            app.current_slice_index,
        )

    if view_state_manager_0:
        view_state_manager_0.current_dataset = first_slice_info["dataset"]

    app.view_state_manager = view_state_manager_0
    app.slice_display_manager = slice_display_manager_0
    if 0 in app.subwindow_managers:
        managers_0 = app.subwindow_managers[0]
        app.roi_coordinator = managers_0.get("roi_coordinator")

    app._disconnect_focused_subwindow_signals()
    app._connect_focused_subwindow_signals()


def refresh_metadata_cine_and_history(app: Any) -> None:
    """Clear metadata filter, refresh cine context, and reset tag-edit history."""
    with perf_timer("first_paint.metadata_cine_history_refresh"):
        app.metadata_panel.clear_filter()
        app.cine_app_facade.update_cine_player_context()

        if app.tag_edit_history:
            app.tag_edit_history.clear_history(app.current_dataset)
        app._update_undo_redo_state()


def refresh_series_navigator_after_first_slice(app: Any) -> None:
    """Update series list, navigator state, and subwindow assignment dots."""
    with perf_timer("first_paint.navigator.update_series_list"):
        app.series_navigator.update_series_list(
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
        )
    with perf_timer("first_paint.navigator.refresh_state"):
        app._refresh_series_navigator_state()
    with perf_timer("first_paint.navigator.set_subwindow_assignments"):
        app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())


def maybe_reveal_navigator_and_fit(app: Any) -> None:
    """
    Show the series navigator when hidden and defer fit-to-view on first open.

    Mirrors the original two-step check on ``navigator_was_hidden`` so a future
    toggle side effect between checks would still behave the same.
    """
    navigator_was_hidden = not app.main_window.series_navigator_visible
    if navigator_was_hidden:
        app.main_window.toggle_series_navigator()
    if navigator_was_hidden:
        QTimer.singleShot(50, lambda: app.image_viewer.fit_to_view(center_image=True))


def finish_first_slice_paint_side_effects(app: Any) -> None:
    """Invalidate slice-sync cache, defer location lines, and mark event-loop return."""
    app._slice_sync_coordinator.invalidate_cache()
    QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)
    QTimer.singleShot(0, lambda: perf_mark("first_paint.event_loop_returned"))


def apply_first_slice_load(
    app: Any,
    studies: dict[str, dict[str, list[Dataset]]],
    first_slice_info: dict[str, Any],
) -> None:
    """
    Apply app state and UI updates after ``load_first_slice`` returns slice info.

    Orchestrates stale-data cleanup, PS/KO load, subwindow-0 display, navigator
    refresh, and deferred first-paint side effects. Caller must set
    ``app.current_studies`` and core current study/series/slice indices before
    invoking focused-fusion refresh (handled here).
    """
    from gui.file_series_additive_load import refresh_focused_fusion_series_list

    app.current_studies = studies
    app._schedule_tag_export_union_rebuild()
    app.current_study_uid = first_slice_info["study_uid"]
    app.current_series_uid = first_slice_info["series_uid"]
    app.current_slice_index = first_slice_info["slice_index"]

    refresh_focused_fusion_series_list(app)
    clear_stale_subwindow_data(app, studies)
    load_presentation_states_and_key_objects(app, studies)

    focus_subwindow_zero(app)
    managers_0 = _ensure_subwindow_zero_managers(app)
    slice_display_manager_0, view_state_manager_0 = _reset_subwindow_zero_view_state(
        managers_0
    )

    app.slice_navigator.set_total_slices(first_slice_info["total_slices"])
    app.slice_navigator.set_current_slice(0)

    if slice_display_manager_0:
        _display_first_slice_subwindow_zero(
            app,
            slice_display_manager_0=slice_display_manager_0,
            first_slice_info=first_slice_info,
        )

    app.current_dataset = first_slice_info["dataset"]

    displayed_dataset = first_slice_info["dataset"]
    extracted_series_uid = get_composite_series_key(displayed_dataset)
    extracted_study_uid = getattr(displayed_dataset, "StudyInstanceUID", "")
    _sync_subwindow_zero_data(
        app,
        studies,
        first_slice_info=first_slice_info,
        extracted_series_uid=extracted_series_uid,
        extracted_study_uid=extracted_study_uid,
    )
    _sync_focused_managers_from_subwindow_zero(
        app,
        managers_0,
        slice_display_manager_0=slice_display_manager_0,
        view_state_manager_0=view_state_manager_0,
        first_slice_info=first_slice_info,
        extracted_study_uid=extracted_study_uid,
        extracted_series_uid=extracted_series_uid,
    )

    refresh_metadata_cine_and_history(app)
    if app.view_state_manager is not None:
        QTimer.singleShot(100, app.view_state_manager.store_initial_view_state)

    refresh_series_navigator_after_first_slice(app)
    maybe_reveal_navigator_and_fit(app)
    finish_first_slice_paint_side_effects(app)
