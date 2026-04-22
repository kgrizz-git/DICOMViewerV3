"""
Bootstrap construction of runtime handlers on ``DICOMViewerApp`` after subwindows exist.

This module holds the body formerly in ``DICOMViewerApp._initialize_handlers``:
``FileSeriesLoadingCoordinator``, ``FileOperationsHandler``, ``DialogCoordinator``,
``PrivacyController``, ``CustomizationHandlers``, ``MouseModeHandler``, ``CinePlayer``,
``CineAppFacade``, and ``KeyboardEventHandler``.

Inputs:
    ``app``: fully constructed ``DICOMViewerApp`` through ``_post_init`` steps that
    create ``subwindow_managers``, focused manager aliases, ``image_viewer``, etc.

Outputs:
    Mutates ``app`` by assigning handler attributes and connecting context-menu signals.

Requirements:
    PySide6; must not ``import main`` at runtime (``TYPE_CHECKING`` only).
"""

from __future__ import annotations

# pyright: reportImportCycles=false

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QApplication

from core.cine_app_facade import CineAppFacade
from core.customization_handlers import CustomizationHandlers
from core.file_operations_handler import FileOperationsHandler
from core.file_series_loading_coordinator import FileSeriesLoadingCoordinator
from core.main_app_key_event_filter import is_widget_allowed_for_layout_shortcuts
from core.privacy_controller import PrivacyController
from core.study_index import LocalStudyIndexService
from gui.cine_player import CinePlayer
from gui.dialog_coordinator import DialogCoordinator
from gui.keyboard_event_handler import KeyboardEventHandler
from gui.mouse_mode_handler import MouseModeHandler

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def initialize_handlers(app: "DICOMViewerApp") -> None:
    """Initialize all handler classes on ``app`` (moved from ``DICOMViewerApp._initialize_handlers``)."""
    # Note: Per-subwindow managers are created in _initialize_subwindow_managers
    # References to focused subwindow's managers should already be set in __init__
    # before this method is called. If not, we'll use the first subwindow's managers.

    # Ensure managers are set (should already be set in __init__, but double-check)
    if not hasattr(app, "roi_coordinator") or app.roi_coordinator is None:
        # Fallback: use first subwindow's managers
        subwindows = app.multi_window_layout.get_all_subwindows()
        if subwindows and 0 in app.subwindow_managers:
            managers = app.subwindow_managers[0]
            app.view_state_manager = managers["view_state_manager"]
            app.slice_display_manager = managers["slice_display_manager"]
            app.roi_coordinator = managers["roi_coordinator"]
            app.measurement_coordinator = managers["measurement_coordinator"]
            app.text_annotation_coordinator = managers.get("text_annotation_coordinator")
            app.arrow_annotation_coordinator = managers.get("arrow_annotation_coordinator")
            app.crosshair_coordinator = managers.get("crosshair_coordinator")
            app.overlay_coordinator = managers["overlay_coordinator"]
            app.roi_manager = managers["roi_manager"]
            app.measurement_tool = managers["measurement_tool"]
            app.text_annotation_tool = managers.get("text_annotation_tool")
            app.arrow_annotation_tool = managers.get("arrow_annotation_tool")
            app.crosshair_manager = managers.get("crosshair_manager")
            app.overlay_manager = managers["overlay_manager"]
            if subwindows[0]:
                app.image_viewer = subwindows[0].image_viewer
                app.main_window.image_viewer = app.image_viewer
        else:
            raise RuntimeError("No subwindow managers available. Cannot initialize handlers.")

    if app.image_viewer is None:
        raise RuntimeError(
            "image_viewer must be set before initializing handlers that require a focused viewer."
        )
    focused_image_viewer = app.image_viewer

    # Initialize file/series loading coordinator (owns load-first-slice and open entry points)
    app._file_series_coordinator = FileSeriesLoadingCoordinator(app)
    # Local encrypted study index (SQLCipher + keyring; optional auto-add on open)
    app.study_index_service = LocalStudyIndexService(
        app.config_manager, parent_widget=app.main_window
    )
    # Initialize FileOperationsHandler (shared, not per-subwindow)
    app.file_operations_handler = FileOperationsHandler(
        app.dicom_loader,
        app.dicom_organizer,
        app.file_dialog,
        app.config_manager,
        app.main_window,
        clear_data_callback=app._clear_data,
        load_first_slice_callback=app._file_series_coordinator.handle_additive_load,
        update_status_callback=app.main_window.update_status,
        on_load_success_callback=app._on_study_index_after_load,
    )

    # Initialize DialogCoordinator
    app.dialog_coordinator = DialogCoordinator(
        app.config_manager,
        app.main_window,
        get_current_studies=lambda: app.current_studies,
        settings_applied_callback=app._on_settings_applied,
        overlay_config_applied_callback=app._on_overlay_config_applied,
        tag_edit_history=app.tag_edit_history,
        get_histogram_callbacks_for_subwindow=app.get_histogram_callbacks_for_subwindow,
        get_focused_subwindow_index=app.get_focused_subwindow_index,
        undo_redo_manager=app.undo_redo_manager,
        ui_refresh_callback=app._refresh_tag_ui,
        tag_export_union_host=app,
    )
    # Set annotation options callback
    app.dialog_coordinator.annotation_options_applied_callback = app._on_annotation_options_applied
    # Set tag edited callback
    app.dialog_coordinator.tag_edited_callback = app._on_tag_edited
    # Set undo/redo callbacks for tag viewer dialog
    app.dialog_coordinator.undo_redo_callbacks = (
        lambda: app._on_undo_requested(),
        lambda: app._on_redo_requested(),
        lambda: app.undo_redo_manager.can_undo() if app.undo_redo_manager else False,
        lambda: app.undo_redo_manager.can_redo() if app.undo_redo_manager else False,
    )

    # Privacy controller (propagates privacy mode and refreshes overlays)
    app._privacy_controller = PrivacyController(
        config_manager=app.config_manager,
        metadata_controller=app.metadata_controller,
        overlay_manager=app.overlay_manager,
        dialog_coordinator=app.dialog_coordinator,
        get_subwindow_managers=lambda: app.subwindow_managers,
        get_all_subwindows=app.multi_window_layout.get_all_subwindows,
        get_focused_subwindow_index=app.get_focused_subwindow_index,
        get_subwindow_data=lambda: app.subwindow_data,
    )

    # Customization and tag-preset export/import (callbacks run after import; need app state)
    app._customization_handlers = CustomizationHandlers(
        app.config_manager,
        app.main_window,
        after_import_customizations=app._apply_imported_customizations,
    )

    # Initialize MouseModeHandler
    app.mouse_mode_handler = MouseModeHandler(
        focused_image_viewer,
        app.main_window,
        app.slice_navigator,
        app.config_manager,
    )

    # Connect context menu signals for all subwindows (now that mouse_mode_handler exists)
    app._connect_all_subwindow_context_menu_signals()

    # Initialize CinePlayer
    app.cine_player = CinePlayer(
        slice_navigator=app.slice_navigator,
        get_total_slices_callback=lambda: app.slice_navigator.total_slices,
        get_current_slice_callback=lambda: app.slice_navigator.get_current_slice(),
    )

    # Set default cine settings from config
    default_speed = app.config_manager.get_cine_default_speed()
    default_loop = app.config_manager.get_cine_default_loop()
    app.cine_player.set_speed(default_speed)
    app.cine_player.set_loop(default_loop)
    # Update UI to match defaults
    app.cine_controls_widget.set_speed(default_speed)
    app.cine_controls_widget.set_loop(default_loop)

    app.cine_app_facade = CineAppFacade(app)

    # Initialize KeyboardEventHandler
    # Ensure all required managers exist before initializing
    if not all(
        [
            hasattr(app, attr) and getattr(app, attr) is not None
            for attr in [
                "roi_manager",
                "measurement_tool",
                "overlay_manager",
                "image_viewer",
                "roi_coordinator",
                "measurement_coordinator",
                "overlay_coordinator",
                "view_state_manager",
            ]
        ]
    ):
        raise RuntimeError("Required managers not initialized. Cannot create KeyboardEventHandler.")

    app.keyboard_event_handler = KeyboardEventHandler(
        app.roi_manager,
        app.measurement_tool,
        app.slice_navigator,
        app.overlay_manager,
        focused_image_viewer,
        set_mouse_mode=app.mouse_mode_handler.set_mouse_mode,
        delete_all_rois_callback=app.roi_coordinator.delete_all_rois_current_slice,
        clear_measurements_callback=app.measurement_coordinator.handle_clear_measurements,
        toggle_overlay_callback=app.overlay_coordinator.handle_toggle_overlay,
        cycle_overlay_detail_callback=app._cycle_overlay_detail_mode,
        toggle_overlay_visibility_legacy_callback=app.overlay_coordinator.handle_toggle_overlay,
        get_selected_roi=lambda: app.roi_manager.get_selected_roi(),
        delete_roi_callback=app._keyboard_delete_roi,
        delete_measurement_callback=app.measurement_coordinator.handle_measurement_delete_requested,
        update_roi_list_callback=app._update_roi_list,
        clear_roi_statistics_callback=app.roi_statistics_panel.clear_statistics,
        reset_view_callback=app.view_state_manager.reset_view,
        toggle_series_navigator_callback=app.main_window.toggle_series_navigator,
        invert_image_callback=focused_image_viewer.invert_image,
        open_histogram_callback=app.dialog_coordinator.open_histogram,
        reset_all_views_callback=app._on_reset_all_views,
        toggle_privacy_view_callback=lambda enabled: app._on_privacy_view_toggled(enabled),
        get_privacy_view_state_callback=lambda: app.privacy_view_enabled,
        delete_text_annotation_callback=None,  # Will be set when coordinators are available
        delete_arrow_annotation_callback=None,  # Will be set when coordinators are available
        change_layout_callback=app.main_window.set_layout_mode,
        is_focus_ok_for_reset_view=lambda: is_widget_allowed_for_layout_shortcuts(
            app, QApplication.focusWidget()
        ),
        open_quick_window_level_callback=app._open_quick_window_level,
        cancel_angle_draw_callback=app.measurement_coordinator.handle_angle_draw_cancel_requested,
    )
