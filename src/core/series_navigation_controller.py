"""
Series Navigation Controller

Module-level functions extracted from FileSeriesLoadingCoordinator that handle
series navigation, series assignment to subwindows, and series navigator
selection events.  Each function takes an ``app`` (DICOMViewerApp) instance as
its first parameter instead of ``self``.
"""
import inspect
import time
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QTimer

from core.file_path_actions import update_about_this_file_dialog
from utils.debug_flags import DEBUG_MEASUREMENT_SERIES, DEBUG_NAV, DEBUG_SERIES
from utils.dicom_utils import get_composite_series_key
from utils.privacy.console import print_redacted

# Human-readable window labels for error messages (1-based).
_WINDOW_LABELS = ["Window 1", "Window 2", "Window 3", "Window 4"]


def build_flat_series_list(
    studies: dict[str, dict[str, list[Dataset]]],
) -> list[tuple[int, str, str, Dataset]]:
    """
    Build flat list of all series from all studies in navigator display order.

    Args:
        studies: Dictionary of studies {study_uid: {series_uid: [datasets]}}

    Returns:
        List of tuples: [(series_num, study_uid, series_uid, first_dataset), ...]
    """
    flat_list = []
    for study_uid, study_series in studies.items():
        series_list = []
        for series_uid, datasets in study_series.items():
            if datasets:
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, study_uid, series_uid, first_dataset))
        series_list.sort(key=lambda x: x[0])
        flat_list.extend(series_list)
    return flat_list


def assign_series_to_subwindow(
    app: Any,
    subwindow: Any,
    series_uid: str,
    slice_index: int,
    target_study_uid: str | None = None,
) -> None:
    """Assign a series/slice to a specific subwindow."""
    subwindows = app.multi_window_layout.get_all_subwindows()
    if subwindow not in subwindows:
        return
    idx = subwindows.index(subwindow)
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(idx):
        label = _WINDOW_LABELS[idx] if idx < len(_WINDOW_LABELS) else f"Window {idx + 1}"
        app.main_window.show_toast_message(
            f"Please clear MPR before assigning a new series to {label}.",
            timeout_ms=4500,
        )
        return
    if idx not in app.subwindow_managers:
        app._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers()
    if not app.current_studies:
        return
    if target_study_uid is not None:
        if target_study_uid not in app.current_studies:
            return
        if series_uid not in app.current_studies[target_study_uid]:
            return
    else:
        for study_uid, series_dict in app.current_studies.items():
            if series_uid in series_dict:
                target_study_uid = study_uid
                break
    if target_study_uid is None:
        return
    series_datasets = app.current_studies[target_study_uid][series_uid]
    if not series_datasets:
        return
    slice_index = max(0, min(slice_index, len(series_datasets) - 1))
    if idx not in app.subwindow_data:
        app.subwindow_data[idx] = {}
    app.subwindow_data[idx]['current_study_uid'] = target_study_uid
    app.subwindow_data[idx]['current_series_uid'] = series_uid
    app.subwindow_data[idx]['current_slice_index'] = slice_index
    app.subwindow_data[idx]['current_datasets'] = series_datasets
    app.subwindow_data[idx]['current_dataset'] = (
        series_datasets[slice_index] if slice_index < len(series_datasets) else series_datasets[0]
    )
    # Mark this study as recently accessed in the LRU cache
    study_cache = getattr(app, "study_cache", None)
    if study_cache is not None and target_study_uid:
        study_cache.mark_accessed(target_study_uid)
    if DEBUG_MEASUREMENT_SERIES:
        print_redacted(
            "[DEBUG-MEAS-SERIES] assign_series_to_subwindow: "
            f"idx={idx}, target_key={(target_study_uid, series_uid, slice_index)}, "
            f"focused_idx={getattr(app, 'focused_subwindow_index', -1)}"
        )
    subwindow.set_assigned_series(series_uid, slice_index)
    managers: dict[str, Any] = {}
    if idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        slice_display_manager = managers['slice_display_manager']
        is_focused = (subwindow == app.multi_window_layout.get_focused_subwindow())
        slice_display_manager.display_slice(
            app.subwindow_data[idx]['current_dataset'],
            app.current_studies,
            target_study_uid,
            series_uid,
            slice_index,
            update_controls=is_focused,
            update_metadata=is_focused
        )
    app.dialog_coordinator.update_histogram_for_subwindow(idx)
    if subwindow == app.multi_window_layout.get_focused_subwindow():
        app.slice_navigator.set_total_slices(len(series_datasets))
        app.slice_navigator.blockSignals(True)
        app.slice_navigator.current_slice_index = slice_index
        app.slice_navigator.blockSignals(False)
    if subwindow == app.multi_window_layout.get_focused_subwindow():
        app.series_navigator.set_current_series(series_uid, target_study_uid)
    if subwindow == app.multi_window_layout.get_focused_subwindow():
        app.current_series_uid = series_uid
        app.current_study_uid = target_study_uid
        app.current_slice_index = slice_index
        app.current_dataset = app.subwindow_data[idx]['current_dataset']
        app._update_series_navigator_highlighting()
        app._update_right_panel_for_focused_subwindow()
        # Ensure cine player context and frame slider are updated when series changes
        app.cine_app_facade.update_cine_player_context()

        if managers.get('crosshair_coordinator'):
            managers['crosshair_coordinator'].update_crosshairs_for_slice()

        update_about_this_file_dialog(app)

    # Update dot indicators to reflect the new subwindow assignment
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
    refresh_window_slot_map = getattr(app, "_refresh_window_slot_map_widgets", None)
    if callable(refresh_window_slot_map):
        refresh_window_slot_map()

    # Refresh slice location lines when series assignment changes.
    app._slice_sync_coordinator.invalidate_cache()
    QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)


def on_series_navigator_selected(app: Any, series_uid: str) -> None:
    """Handle series selection from series navigator (assigns to focused subwindow)."""
    focused_idx = getattr(app, "focused_subwindow_index", -1)
    if DEBUG_MEASUREMENT_SERIES:
        print_redacted(
            "[DEBUG-MEAS-SERIES] on_series_navigator_selected: "
            f"requested_series_uid={series_uid}, focused_idx={focused_idx}, "
            f"current_series_uid={getattr(app, 'current_series_uid', '')}"
        )
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
        label = _WINDOW_LABELS[focused_idx] if 0 <= focused_idx < len(_WINDOW_LABELS) else f"Window {focused_idx + 1}"
        app.main_window.show_toast_message(
            f"Please clear MPR before assigning a new series to {label}.",
            timeout_ms=4500,
        )
        return
    if not app.current_studies:
        return
    target_study_uid = None
    for study_uid, series_dict in app.current_studies.items():
        if series_uid in series_dict:
            target_study_uid = study_uid
            break
    if target_study_uid is None:
        return
    study_series = app.current_studies[target_study_uid]
    if series_uid not in study_series or not study_series[series_uid]:
        return
    focused_subwindow = app.multi_window_layout.get_focused_subwindow()
    if focused_subwindow:
        assign_series_to_subwindow(app, focused_subwindow, series_uid, 0)


def on_series_navigator_instance_selected(app: Any, study_uid: str, series_uid: str, slice_index: int) -> None:
    """Handle per-instance thumbnail selection from the series navigator."""
    focused_idx = getattr(app, "focused_subwindow_index", -1)
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
        label = _WINDOW_LABELS[focused_idx] if 0 <= focused_idx < len(_WINDOW_LABELS) else f"Window {focused_idx + 1}"
        app.main_window.show_toast_message(
            f"Please clear MPR before assigning a new series to {label}.",
            timeout_ms=4500,
        )
        return
    if not app.current_studies:
        return
    if study_uid not in app.current_studies:
        return
    if series_uid not in app.current_studies[study_uid]:
        return

    focused_subwindow = app.multi_window_layout.get_focused_subwindow()
    if focused_subwindow:
        assign_series_to_subwindow(app, focused_subwindow, series_uid, slice_index, target_study_uid=study_uid)


def on_assign_series_from_context_menu(app: Any, series_uid: str) -> None:
    """Handle series assignment request from context menu (assigns to focused subwindow)."""
    on_series_navigator_selected(app, series_uid)


def _try_navigate_multiframe_instance(
    app: Any,
    study_uid: str,
    series_uid: str,
    slice_index: int,
    direction: int,
) -> bool:
    """
    When Show Instances Separately is on and the series is multi-instance multiframe,
    jump to the previous/next instance start slice. Return False so caller runs
    series-level navigation (at first/last instance).
    """
    if not app.config_manager.get_show_instances_separately():
        return False
    if not study_uid or not series_uid:
        return False
    studies = app.current_studies
    if study_uid not in studies or series_uid not in studies[study_uid]:
        return False
    series_datasets = studies[study_uid][series_uid]
    if not series_datasets:
        return False
    info = app.dicom_organizer.get_series_multiframe_info(study_uid, series_uid)
    if info is None or info.instance_count <= 1 or info.max_frame_count <= 1:
        return False
    entries = app.series_navigator.build_instance_entries(series_datasets)
    if len(entries) <= 1:
        return False
    starts = [e[0] for e in entries]
    inst_i = 0
    for j in range(len(starts) - 1, -1, -1):
        if slice_index >= starts[j]:
            inst_i = j
            break
    focused_subwindow = app.multi_window_layout.get_focused_subwindow()
    if focused_subwindow is None:
        return False
    if direction < 0:
        if inst_i <= 0:
            return False
        target_slice = starts[inst_i - 1]
    else:
        if inst_i >= len(starts) - 1:
            return False
        target_slice = starts[inst_i + 1]
    assign_series_to_subwindow(
        app,
        focused_subwindow,
        series_uid,
        target_slice,
        target_study_uid=study_uid,
    )
    return True


def on_series_navigation_requested(app: Any, direction: int) -> None:
    """
    Handle series navigation request from image viewer (focused subwindow only).

    Args:
        direction: -1 for left/previous series, 1 for right/next series
    """
    timestamp = time.time()
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame else None
    caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
    caller_file = caller_frame.f_code.co_filename.split('/')[-1] if caller_frame else "unknown"
    if DEBUG_NAV:
        print_redacted(f"[DEBUG-NAV] [{timestamp:.6f}] _on_series_navigation_requested: direction={direction}, caller={caller_name} in {caller_file}, lock={app._series_navigation_in_progress}")

    if app._series_navigation_in_progress:
        if DEBUG_NAV:
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Navigation already in progress, ignoring request")
        return
    focused_idx = app.focused_subwindow_index
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
        label = _WINDOW_LABELS[focused_idx] if 0 <= focused_idx < len(_WINDOW_LABELS) else f"Window {focused_idx + 1}"
        app.main_window.show_toast_message(
            f"Please clear MPR before assigning a new series to {label}.",
            timeout_ms=4500,
        )
        return
    app._series_navigation_in_progress = True
    if DEBUG_NAV:
        print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock acquired")

    try:
        if focused_idx not in app.subwindow_data:
            if DEBUG_NAV and DEBUG_SERIES:

                print(f"[DEBUG] Series navigation: subwindow {focused_idx} not in subwindow_data")
            return
        data = app.subwindow_data[focused_idx]
        focused_study_uid = data.get('current_study_uid', '')
        focused_series_uid = data.get('current_series_uid', '')
        focused_slice_index = data.get('current_slice_index', 0)
        displayed_dataset = data.get('current_dataset')
        if displayed_dataset:
            extracted_series_uid = get_composite_series_key(displayed_dataset)
            extracted_study_uid = getattr(displayed_dataset, 'StudyInstanceUID', '')
            if extracted_series_uid and extracted_series_uid != focused_series_uid:
                if DEBUG_NAV and DEBUG_SERIES:

                    print_redacted(f"[DEBUG] Series navigation: MISMATCH at start! Stored={focused_series_uid}, Extracted={extracted_series_uid}")
                focused_series_uid = extracted_series_uid
                focused_study_uid = extracted_study_uid
                data['current_series_uid'] = extracted_series_uid
                data['current_study_uid'] = extracted_study_uid
        elif not focused_series_uid:
            if DEBUG_NAV and DEBUG_SERIES:

                print(f"[DEBUG] Series navigation: No series loaded, attempting to load {'first' if direction > 0 else 'last'} series")
            if not app.current_studies:
                if DEBUG_NAV and DEBUG_SERIES:

                    print("[DEBUG] Series navigation: No studies loaded, cannot navigate")
                return
            if not focused_study_uid:
                focused_study_uid = next(iter(app.current_studies.keys()))
                data['current_study_uid'] = focused_study_uid
            study_series = app.current_studies.get(focused_study_uid, {})
            if not study_series:
                if DEBUG_NAV and DEBUG_SERIES:

                    print("[DEBUG] Series navigation: Study has no series, cannot navigate")
                return
            series_list = []
            for series_uid, datasets in study_series.items():
                if datasets:
                    first_dataset = datasets[0]
                    series_number = getattr(first_dataset, 'SeriesNumber', None)
                    try:
                        series_num = int(series_number) if series_number is not None else 0
                    except (ValueError, TypeError):
                        series_num = 0
                    series_list.append((series_num, series_uid, datasets))
            series_list.sort(key=lambda x: x[0])
            if not series_list:
                if DEBUG_NAV and DEBUG_SERIES:

                    print("[DEBUG] Series navigation: No valid series in study, cannot navigate")
                return
            if direction > 0:
                _, target_series_uid, target_datasets = series_list[0]
            else:
                _, target_series_uid, target_datasets = series_list[-1]
            data['current_series_uid'] = target_series_uid
            data['current_study_uid'] = focused_study_uid
            data['current_dataset'] = target_datasets[0]
            data['current_slice_index'] = 0
            app.current_series_uid = target_series_uid
            app.current_slice_index = 0
            app.current_dataset = target_datasets[0]
            app.current_study_uid = focused_study_uid
            app.slice_display_manager.set_current_data_context(
                app.current_studies, focused_study_uid, target_series_uid, 0
            )
            app.slice_display_manager.display_slice(
                target_datasets[0], app.current_studies, focused_study_uid, target_series_uid, 0
            )
            extracted_series_uid = get_composite_series_key(target_datasets[0])
            extracted_study_uid = getattr(target_datasets[0], 'StudyInstanceUID', '')
            app.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
            app.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid
            app.subwindow_data[focused_idx]['current_dataset'] = target_datasets[0]
            app.subwindow_data[focused_idx]['current_slice_index'] = 0
            app.current_series_uid = extracted_series_uid
            app.current_study_uid = extracted_study_uid
            app.current_slice_index = 0
            app.current_dataset = target_datasets[0]
            app.slice_display_manager.set_current_data_context(
                app.current_studies, extracted_study_uid, extracted_series_uid, 0
            )
            app._update_undo_redo_state()
            if app.current_studies and app.current_study_uid and app.current_series_uid:
                datasets = app.current_studies[app.current_study_uid][app.current_series_uid]
                app.slice_navigator.set_total_slices(len(datasets))
                app.slice_navigator.set_current_slice(0)
            if focused_idx in app.subwindow_data:
                data = app.subwindow_data[focused_idx]
                focused_series_uid = data.get('current_series_uid', '')
                focused_study_uid = data.get('current_study_uid', '')
                if focused_series_uid and focused_study_uid:
                    app.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
                    app._refresh_series_navigator_state()
                    # Refresh colored dot indicators so the slot-to-series
                    # mapping follows the newly selected series.
                    app.series_navigator.set_subwindow_assignments(
                        app._get_subwindow_assignments()
                    )
            app.cine_app_facade.update_cine_player_context()
            update_about_this_file_dialog(app)
            return

        if DEBUG_NAV and DEBUG_SERIES:

            print_redacted(f"[DEBUG] Series navigation: subwindow {focused_idx}, study={focused_study_uid[:20] if focused_study_uid else 'None'}..., series={focused_series_uid[:20] if focused_series_uid else 'None'}..., direction={direction}")
        if not focused_study_uid or focused_study_uid not in app.current_studies:
            if DEBUG_NAV and DEBUG_SERIES:

                print("[DEBUG] Series navigation: Invalid study UID or study not in current_studies")
            return
        study_series = app.current_studies[focused_study_uid]
        if focused_series_uid and focused_series_uid not in study_series:
            if study_series:
                series_list = []
                for series_uid, datasets in study_series.items():
                    if datasets:
                        first_dataset = datasets[0]
                        series_number = getattr(first_dataset, 'SeriesNumber', None)
                        try:
                            series_num = int(series_number) if series_number is not None else 0
                        except (ValueError, TypeError):
                            series_num = 0
                        series_list.append((series_num, series_uid, datasets))
                series_list.sort(key=lambda x: x[0])
                if series_list:
                    _, first_series_uid, first_datasets = series_list[0]
                    focused_series_uid = first_series_uid
                    app.subwindow_data[focused_idx]['current_series_uid'] = first_series_uid
                    app.subwindow_data[focused_idx]['current_dataset'] = first_datasets[0]
                    app.subwindow_data[focused_idx]['current_slice_index'] = 0
                    focused_slice_index = 0
                else:
                    return
            else:
                return
        app.slice_display_manager.set_current_data_context(
            app.current_studies, focused_study_uid, focused_series_uid, focused_slice_index
        )
        if (app.slice_display_manager.current_study_uid != focused_study_uid or
            app.slice_display_manager.current_series_uid != focused_series_uid):
            app.slice_display_manager.set_current_data_context(
                app.current_studies, focused_study_uid, focused_series_uid, focused_slice_index
            )
        if _try_navigate_multiframe_instance(
            app,
            focused_study_uid,
            focused_series_uid,
            focused_slice_index,
            direction,
        ):
            return
        flat_series_list = build_flat_series_list(app.current_studies)
        if not flat_series_list:
            if DEBUG_NAV and DEBUG_SERIES:

                print("[DEBUG] Series navigation: No series found in any study")
            return
        current_index = None
        for idx, (_, study_uid, series_uid, _) in enumerate(flat_series_list):
            if study_uid == focused_study_uid and series_uid == focused_series_uid:
                current_index = idx
                break
        if current_index is None:
            return
        new_index = current_index + direction
        if new_index < 0 or new_index >= len(flat_series_list):
            return
        _, target_study_uid, target_series_uid, target_first_dataset = flat_series_list[new_index]
        if target_study_uid not in app.current_studies or target_series_uid not in app.current_studies[target_study_uid]:
            return
        target_datasets = app.current_studies[target_study_uid][target_series_uid]
        if not target_datasets:
            return
        new_series_uid = target_series_uid
        slice_index = 0
        dataset = target_datasets[0]
        app.subwindow_data[focused_idx]['current_series_uid'] = new_series_uid
        app.subwindow_data[focused_idx]['current_study_uid'] = target_study_uid
        app.subwindow_data[focused_idx]['current_slice_index'] = slice_index
        app.subwindow_data[focused_idx]['current_dataset'] = dataset
        app.current_series_uid = new_series_uid
        app.current_slice_index = slice_index
        app.current_dataset = dataset
        app.current_study_uid = target_study_uid
        app.slice_display_manager.reset_projection_state()
        app.intensity_projection_controls_widget.set_enabled(False)
        app.intensity_projection_controls_widget.set_projection_type("aip")
        app.intensity_projection_controls_widget.set_slice_count(4)
        app.slice_display_manager.display_slice(
            dataset, app.current_studies, target_study_uid, new_series_uid, slice_index
        )
        extracted_series_uid = get_composite_series_key(dataset)
        extracted_study_uid = getattr(dataset, 'StudyInstanceUID', '')
        app.subwindow_data[focused_idx]['current_series_uid'] = extracted_series_uid
        app.subwindow_data[focused_idx]['current_study_uid'] = extracted_study_uid
        app.subwindow_data[focused_idx]['current_dataset'] = dataset
        app.subwindow_data[focused_idx]['current_slice_index'] = slice_index
        app.current_series_uid = extracted_series_uid
        app.current_study_uid = extracted_study_uid
        app.current_slice_index = slice_index
        app.current_dataset = dataset
        app.slice_display_manager.set_current_data_context(
            app.current_studies, extracted_study_uid, extracted_series_uid, slice_index
        )
        app._update_undo_redo_state()
        if app.current_studies and app.current_study_uid and app.current_series_uid:
            datasets = app.current_studies[app.current_study_uid][app.current_series_uid]
            app.slice_navigator.set_total_slices(len(datasets))
            app.slice_navigator.set_current_slice(slice_index)
        if focused_idx in app.subwindow_data:
            data = app.subwindow_data[focused_idx]
            focused_series_uid = data.get('current_series_uid', '')
            focused_study_uid = data.get('current_study_uid', '')
            if focused_series_uid and focused_study_uid:
                app.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
                app._refresh_series_navigator_state()
                # Also update dot indicators to follow the new assignment
                # of series to subwindows after keyboard navigation.
                app.series_navigator.set_subwindow_assignments(
                    app._get_subwindow_assignments()
                )
        app._update_right_panel_for_focused_subwindow()
        app.cine_app_facade.update_cine_player_context()
        update_about_this_file_dialog(app)
    finally:
        if DEBUG_NAV:
            timestamp = time.time()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock released")
        app._series_navigation_in_progress = False
