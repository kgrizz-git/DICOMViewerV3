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
    _update_cine_player_context, _update_undo_redo_state; and attributes
    current_dataset, current_studies, current_study_uid, current_series_uid,
    current_slice_index, current_datasets, focused_subwindow_index.
"""

import os
import time
import inspect
from typing import Dict, List, Optional, Tuple, Any
from pydicom.dataset import Dataset

from utils.dicom_utils import get_composite_series_key


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

    def handle_load_first_slice(self, studies: dict) -> None:
        """
        Handle loading first slice after file operations.

        Clears edited tags for the previous dataset, clears subwindows and
        overlays, resets projection state, loads first slice via
        file_operations_handler, updates app state and UI (navigators, panels,
        fusion, presentation states, key objects).
        """
        app = self.app

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

        first_slice_info = app.file_operations_handler.load_first_slice(studies)
        if first_slice_info:
            app.current_studies = studies
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
            if stale_count > 0:
                print(f"[DEBUG] Cleared stale data from {stale_count} subwindow(s)")

            # Load Presentation States and Key Objects into annotation manager
            all_presentation_states = {}
            all_key_objects = {}
            for study_uid in studies.keys():
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
                slice_display_manager_0.display_slice(
                    first_slice_info['dataset'],
                    app.current_studies,
                    app.current_study_uid,
                    app.current_series_uid,
                    app.current_slice_index
                )

            app.current_dataset = first_slice_info['dataset']

            focused_idx = 0
            if focused_idx not in app.subwindow_data:
                app.subwindow_data[focused_idx] = {}

            displayed_dataset = first_slice_info['dataset']
            extracted_series_uid = get_composite_series_key(displayed_dataset)
            extracted_study_uid = getattr(displayed_dataset, 'StudyInstanceUID', '')

            if extracted_series_uid != app.current_series_uid:
                print(f"[DEBUG] Syncing subwindow_data after initial load: MISMATCH detected!")
            if extracted_study_uid != app.current_study_uid:
                print(f"[DEBUG]   Extracted study_uid from dataset: {extracted_study_uid}")

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

            app.metadata_panel.clear_filter()
            app._update_cine_player_context()

            if app.tag_edit_history:
                app.tag_edit_history.clear_history(app.current_dataset)
            app._update_undo_redo_state()

            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, app.view_state_manager.store_initial_view_state)

            app.series_navigator.update_series_list(
                app.current_studies,
                app.current_study_uid,
                app.current_series_uid
            )

            navigator_was_hidden = not app.main_window.series_navigator_visible
            if navigator_was_hidden:
                app.main_window.toggle_series_navigator()
            if navigator_was_hidden:
                QTimer.singleShot(50, lambda: app.image_viewer.fit_to_view(center_image=True))

    def open_files(self) -> None:
        """Handle open files request. Delegates to file_operations_handler and updates app state."""
        datasets, studies = self.app.file_operations_handler.open_files()
        if datasets is not None and studies is not None:
            self.app.current_datasets = datasets
            self.app.current_studies = studies

    def open_folder(self) -> None:
        """Handle open folder request. Delegates to file_operations_handler and updates app state."""
        datasets, studies = self.app.file_operations_handler.open_folder()
        if datasets is not None and studies is not None:
            self.app.current_datasets = datasets
            self.app.current_studies = studies

    def open_recent_file(self, file_path: str) -> None:
        """
        Handle open recent file/folder request.

        Args:
            file_path: Path to file or folder to open
        """
        datasets, studies = self.app.file_operations_handler.open_recent_file(file_path)
        if datasets is not None and studies is not None:
            self.app.current_datasets = datasets
            self.app.current_studies = studies

    def open_files_from_paths(self, paths: List[str]) -> None:
        """
        Handle open files/folders from drag-and-drop.

        Args:
            paths: List of file or folder paths to open
        """
        datasets, studies = self.app.file_operations_handler.open_paths(paths)
        if datasets is not None and studies is not None:
            self.app.current_datasets = datasets
            self.app.current_studies = studies

    def build_flat_series_list(self, studies: Dict) -> List[Tuple[int, str, str, Dataset]]:
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

    def assign_series_to_subwindow(self, subwindow: Any, series_uid: str, slice_index: int) -> None:
        """Assign a series/slice to a specific subwindow."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        if subwindow not in subwindows:
            return
        idx = subwindows.index(subwindow)
        if idx not in app.subwindow_managers:
            app._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers()
        if not app.current_studies:
            return
        target_study_uid = None
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
        subwindow.set_assigned_series(series_uid, slice_index)
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

    def on_series_navigator_selected(self, series_uid: str) -> None:
        """Handle series selection from series navigator (assigns to focused subwindow)."""
        app = self.app
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
            self.assign_series_to_subwindow(focused_subwindow, series_uid, 0)

    def on_assign_series_from_context_menu(self, series_uid: str) -> None:
        """Handle series assignment request from context menu (assigns to focused subwindow)."""
        self.on_series_navigator_selected(series_uid)

    def on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer (focused subwindow only).

        Args:
            direction: -1 for left/previous series, 1 for right/next series
        """
        app = self.app
        timestamp = time.time()
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        caller_file = caller_frame.f_code.co_filename.split('/')[-1] if caller_frame else "unknown"
        print(f"[DEBUG-NAV] [{timestamp:.6f}] _on_series_navigation_requested: direction={direction}, caller={caller_name} in {caller_file}, lock={app._series_navigation_in_progress}")

        if app._series_navigation_in_progress:
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Navigation already in progress, ignoring request")
            return
        app._series_navigation_in_progress = True
        print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock acquired")

        try:
            focused_idx = app.focused_subwindow_index
            if focused_idx not in app.subwindow_data:
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
                    print(f"[DEBUG] Series navigation: MISMATCH at start! Stored={focused_series_uid}, Extracted={extracted_series_uid}")
                    focused_series_uid = extracted_series_uid
                    focused_study_uid = extracted_study_uid
                    data['current_series_uid'] = extracted_series_uid
                    data['current_study_uid'] = extracted_study_uid
            elif not focused_series_uid:
                print(f"[DEBUG] Series navigation: No series loaded, attempting to load {'first' if direction > 0 else 'last'} series")
                if not app.current_studies:
                    print(f"[DEBUG] Series navigation: No studies loaded, cannot navigate")
                    return
                if not focused_study_uid:
                    focused_study_uid = list(app.current_studies.keys())[0]
                    data['current_study_uid'] = focused_study_uid
                study_series = app.current_studies.get(focused_study_uid, {})
                if not study_series:
                    print(f"[DEBUG] Series navigation: Study has no series, cannot navigate")
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
                    print(f"[DEBUG] Series navigation: No valid series in study, cannot navigate")
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
                app._update_cine_player_context()
                return

            print(f"[DEBUG] Series navigation: subwindow {focused_idx}, study={focused_study_uid[:20] if focused_study_uid else 'None'}..., series={focused_series_uid[:20] if focused_series_uid else 'None'}..., direction={direction}")
            if not focused_study_uid or focused_study_uid not in app.current_studies:
                print(f"[DEBUG] Series navigation: Invalid study UID or study not in current_studies")
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
            flat_series_list = self.build_flat_series_list(app.current_studies)
            if not flat_series_list:
                print(f"[DEBUG] Series navigation: No series found in any study")
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
            app._update_right_panel_for_focused_subwindow()
            app._update_cine_player_context()
        finally:
            timestamp = time.time()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] Series navigation: Lock released")
            app._series_navigation_in_progress = False

    def get_file_path_for_dataset(
        self, dataset: Any, study_uid: str, series_uid: str, slice_index: int
    ) -> Optional[str]:
        """
        Get file path for a dataset.

        Args:
            dataset: DICOM dataset
            study_uid: Study Instance UID
            series_uid: Series UID (composite key)
            slice_index: Slice index

        Returns:
            File path if found, None otherwise
        """
        app = self.app
        if not dataset or not study_uid or not series_uid:
            return None
        if hasattr(dataset, 'filename') and dataset.filename:
            return dataset.filename
        instance_num = None
        if hasattr(dataset, 'InstanceNumber'):
            try:
                instance_num = int(getattr(dataset, 'InstanceNumber'))
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

    def on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'Show file' request from series navigator thumbnail; reveals first slice file in explorer."""
        from utils.file_explorer import reveal_file_in_explorer
        app = self.app
        if not app.current_studies or study_uid not in app.current_studies:
            return
        study_series = app.current_studies[study_uid]
        if series_uid not in study_series or not study_series[series_uid]:
            return
        first_dataset = study_series[series_uid][0]
        file_path = self.get_file_path_for_dataset(first_dataset, study_uid, series_uid, 0)
        if file_path and os.path.exists(file_path):
            reveal_file_in_explorer(file_path)

    def on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'About This File' request from series navigator thumbnail; opens dialog with first slice."""
        app = self.app
        if not app.current_studies or study_uid not in app.current_studies:
            return
        study_series = app.current_studies[study_uid]
        if series_uid not in study_series or not study_series[series_uid]:
            return
        first_dataset = study_series[series_uid][0]
        file_path = self.get_file_path_for_dataset(first_dataset, study_uid, series_uid, 0)
        app.dialog_coordinator.open_about_this_file(first_dataset, file_path)

    def get_current_slice_file_path(self, subwindow_idx: Optional[int] = None) -> Optional[str]:
        """Get file path for the currently displayed slice in a subwindow."""
        app = self.app
        if subwindow_idx is None:
            subwindow_idx = app.focused_subwindow_index
        dataset = app._get_subwindow_dataset(subwindow_idx)
        study_uid = app._get_subwindow_study_uid(subwindow_idx)
        series_uid = app._get_subwindow_series_uid(subwindow_idx)
        slice_index = app._get_subwindow_slice_index(subwindow_idx)
        if not dataset or not study_uid or not series_uid:
            return None
        return self.get_file_path_for_dataset(dataset, study_uid, series_uid, slice_index)

    def update_about_this_file_dialog(self) -> None:
        """Update About This File dialog with current dataset and file path for focused subwindow."""
        app = self.app
        focused_idx = app.focused_subwindow_index
        current_dataset = None
        file_path = None
        if focused_idx in app.subwindow_data:
            current_dataset = app.subwindow_data[focused_idx].get('current_dataset')
            if current_dataset:
                file_path = self.get_file_path_for_dataset(
                    current_dataset,
                    app.subwindow_data[focused_idx].get('current_study_uid', ''),
                    app.subwindow_data[focused_idx].get('current_series_uid', ''),
                    app.subwindow_data[focused_idx].get('current_slice_index', 0)
                )
        app.dialog_coordinator.update_about_this_file(current_dataset, file_path)
