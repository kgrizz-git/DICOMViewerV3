"""
Case table: ``main.py`` mixin methods that forward to a module-level handler.

The extracted handler functions (``core.*_handlers``, ``gui.actions.*``) have
their own tests, so what needs pinning here is the seam: that each mixin slot
calls the expected handler with ``(self, *args, **kwargs)``. A swapped handler or
a dropped argument is otherwise invisible until runtime.
"""

from __future__ import annotations

from main_mixin_delegation_support import HandlerCase

# The handler's first argument is always the app, so cases record only the
# caller's own arguments.
# --- module-level handler forwards (app is always the handler's first argument) ------

HANDLER_CASES: tuple[HandlerCase, ...] = (
    # InitializationMixin -> handler bootstrap / main-window assembly / layout signals
    HandlerCase("InitializationMixin", "_initialize_handlers", "bootstrap_initialize_handlers", ()),
    HandlerCase(
        "InitializationMixin",
        "_connect_all_subwindow_transform_signals",
        "layout_connect_all_subwindow_transform_signals",
        (),
    ),
    HandlerCase(
        "InitializationMixin",
        "_connect_all_subwindow_context_menu_signals",
        "layout_connect_all_subwindow_context_menu_signals",
        (),
    ),
    # DisplayProjectionMixin -> core.slice_display_handlers / overlay handlers
    HandlerCase(
        "DisplayProjectionMixin",
        "_display_slice",
        "display_slice",
        (object(),),
        {"preserve_view_override": None},
    ),
    HandlerCase(
        "DisplayProjectionMixin",
        "_display_slice",
        "display_slice",
        (object(),),
        {"preserve_view_override": True},
    ),
    HandlerCase("DisplayProjectionMixin", "_redisplay_current_slice", "redisplay_current_slice", (True,)),
    HandlerCase(
        "DisplayProjectionMixin",
        "_sync_all_overlay_managers_from_config",
        "sync_all_overlay_managers_from_config",
        (),
    ),
    HandlerCase("DisplayProjectionMixin", "_cycle_overlay_detail_mode", "cycle_overlay_detail_mode", ()),
    HandlerCase("DisplayProjectionMixin", "_on_overlay_config_applied", "on_overlay_config_applied", ()),
    HandlerCase("DisplayProjectionMixin", "_on_zoom_changed", "on_zoom_changed", (2.5,)),
    HandlerCase(
        "DisplayProjectionMixin",
        "_on_window_level_preset_selected",
        "apply_window_level_preset",
        (3,),
    ),
    HandlerCase("DisplayProjectionMixin", "_update_zoom_preset_status_bar", "update_zoom_preset_status_bar", ()),
    HandlerCase(
        "DisplayProjectionMixin",
        "_on_overlay_font_size_changed",
        "on_overlay_font_size_changed",
        (14,),
    ),
    HandlerCase(
        "DisplayProjectionMixin",
        "_on_overlay_font_color_changed",
        "on_overlay_font_color_changed",
        (10, 20, 30),
    ),
    HandlerCase("DisplayProjectionMixin", "_on_slice_changed", "on_slice_changed", (7,)),
    HandlerCase(
        "DisplayProjectionMixin",
        "_on_smooth_when_zoomed_toggled",
        "view_actions.on_smooth_when_zoomed_toggled",
        (True,),
    ),
    # SettingsLayoutMixin -> study navigation / layout controller / view actions
    HandlerCase(
        "SettingsLayoutMixin",
        "_update_series_navigator_highlighting",
        "update_series_navigator_highlighting",
        (),
    ),
    HandlerCase(
        "SettingsLayoutMixin",
        "_refresh_series_navigator_state",
        "refresh_series_navigator_state",
        (),
    ),
    HandlerCase("SettingsLayoutMixin", "_on_layout_changed", "layout_on_layout_changed", ("2x2",)),
    HandlerCase(
        "SettingsLayoutMixin",
        "_on_main_window_layout_changed",
        "layout_on_main_window_layout_changed",
        ("1x2",),
    ),
    HandlerCase(
        "SettingsLayoutMixin",
        "_on_layout_change_requested",
        "layout_on_layout_change_requested",
        ("2x1",),
    ),
    HandlerCase("SettingsLayoutMixin", "_on_expand_to_1x1_requested", "layout_on_expand_to_1x1_requested", ()),
    HandlerCase("SettingsLayoutMixin", "_on_swap_view_requested", "layout_on_swap_view_requested", (2,)),
    HandlerCase("SettingsLayoutMixin", "_refresh_window_slot_map_widgets", "layout_refresh_window_slot_map_widgets", ()),
    HandlerCase("SettingsLayoutMixin", "_on_privacy_view_toggled", "view_actions.on_privacy_view_toggled", (True,)),
    HandlerCase("SettingsLayoutMixin", "_on_slice_sync_toggled", "view_actions.on_slice_sync_toggled", (False,)),
    HandlerCase(
        "SettingsLayoutMixin",
        "_on_slice_sync_groups_changed",
        "view_actions.on_slice_sync_groups_changed",
        ([0, 1],),
    ),
    HandlerCase("SettingsLayoutMixin", "_apply_imported_customizations", "apply_imported_customizations", ()),
    HandlerCase("SettingsLayoutMixin", "_on_settings_applied", "on_settings_applied", ()),
    # UIHandlersMixin -> view-state handlers / orientation / overlay toggles
    HandlerCase("UIHandlersMixin", "_update_3d_view_action_state", "update_3d_view_action_state", ()),
    HandlerCase(
        "UIHandlersMixin",
        "_on_window_slot_map_cell_clicked",
        "layout_on_window_slot_map_cell_clicked",
        (2,),
    ),
    HandlerCase("UIHandlersMixin", "_on_window_slot_map_popup_requested", "layout_on_window_slot_map_popup_requested", ()),
    HandlerCase("UIHandlersMixin", "_on_slice_location_lines_toggled", "view_actions.on_slice_location_lines_toggled", (True,)),
    HandlerCase(
        "UIHandlersMixin",
        "_on_slice_location_lines_same_group_only_toggled",
        "view_actions.on_slice_location_lines_same_group_only_toggled",
        (True,),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_slice_location_lines_focused_only_toggled",
        "view_actions.on_slice_location_lines_focused_only_toggled",
        (False,),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_slice_location_lines_mode_toggled",
        "view_actions.on_slice_location_lines_mode_toggled",
        ("slab",),
    ),
    HandlerCase("UIHandlersMixin", "_on_orientation_flip_h", "view_actions.on_orientation_flip_h", ()),
    HandlerCase("UIHandlersMixin", "_on_orientation_flip_v", "view_actions.on_orientation_flip_v", ()),
    HandlerCase("UIHandlersMixin", "_on_orientation_rotate_cw", "view_actions.on_orientation_rotate_cw", ()),
    HandlerCase("UIHandlersMixin", "_on_orientation_rotate_ccw", "view_actions.on_orientation_rotate_ccw", ()),
    HandlerCase("UIHandlersMixin", "_on_orientation_rotate_180", "view_actions.on_orientation_rotate_180", ()),
    HandlerCase("UIHandlersMixin", "_on_orientation_reset", "view_actions.on_orientation_reset", ()),
    HandlerCase("UIHandlersMixin", "_on_scale_markers_toggled", "view_actions.on_scale_markers_toggled", (True,)),
    HandlerCase("UIHandlersMixin", "_on_direction_labels_toggled", "view_actions.on_direction_labels_toggled", (True,)),
    HandlerCase("UIHandlersMixin", "_on_slice_slider_toggled", "view_actions.on_slice_slider_toggled", (True,)),
    HandlerCase(
        "UIHandlersMixin",
        "_on_slice_slider_placement_changed",
        "view_actions.on_slice_slider_placement_changed",
        ("top",),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_slice_slider_direction_changed",
        "view_actions.on_slice_slider_direction_changed",
        ("vertical",),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_scale_markers_color_changed",
        "view_actions.on_scale_markers_color_changed",
        (1, 2, 3),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_direction_labels_color_changed",
        "view_actions.on_direction_labels_color_changed",
        (4, 5, 6),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_show_instances_separately_toggled",
        "view_actions.on_show_instances_separately_toggled",
        (True,),
    ),
    HandlerCase("UIHandlersMixin", "_on_rescale_toggle_changed", "on_rescale_toggle_changed", (True,)),
    HandlerCase("UIHandlersMixin", "_on_reset_all_views", "on_reset_all_views", ()),
    HandlerCase("UIHandlersMixin", "_on_transform_changed", "on_transform_changed", ()),
    HandlerCase("UIHandlersMixin", "_on_viewport_resizing", "on_viewport_resizing", ()),
    HandlerCase("UIHandlersMixin", "_on_viewport_resized", "on_viewport_resized", ()),
    HandlerCase("UIHandlersMixin", "_on_pixel_info_changed", "on_pixel_info_changed", ("42", 3, 4, 5)),
    HandlerCase(
        "UIHandlersMixin",
        "_on_export_customizations",
        "customization_actions.on_export_customizations",
        (),
    ),
    HandlerCase(
        "UIHandlersMixin",
        "_on_import_customizations",
        "customization_actions.on_import_customizations",
        (),
    ),
    HandlerCase("UIHandlersMixin", "_on_annotation_options_applied", "on_annotation_options_applied", ()),
    # FileOperationsMixin -> dialog_actions
    HandlerCase("FileOperationsMixin", "_open_wl_preset_manager", "dialog_actions.open_wl_preset_manager", ()),
    HandlerCase("FileOperationsMixin", "_open_files", "dialog_actions.open_files", ()),
    HandlerCase("FileOperationsMixin", "_open_folder", "dialog_actions.open_folder", ()),
    HandlerCase("FileOperationsMixin", "_open_recent_file", "dialog_actions.open_recent_file", ("/tmp/x.dcm",)),
    HandlerCase("FileOperationsMixin", "_open_files_from_paths", "dialog_actions.open_files_from_paths", (["/tmp/a"],)),
    HandlerCase("FileOperationsMixin", "_open_settings", "dialog_actions.open_settings", ()),
    HandlerCase("FileOperationsMixin", "_open_study_index_search", "dialog_actions.open_study_index_search", ()),
    HandlerCase("FileOperationsMixin", "_open_overlay_settings", "dialog_actions.open_overlay_settings", ()),
    HandlerCase("FileOperationsMixin", "_open_about_this_file", "dialog_actions.open_about_this_file", ()),
    HandlerCase("FileOperationsMixin", "_open_slice_sync_dialog", "dialog_actions.open_slice_sync_dialog", ()),
    HandlerCase("FileOperationsMixin", "_open_overlay_config", "dialog_actions.open_overlay_config", ()),
    HandlerCase("FileOperationsMixin", "_open_annotation_options", "dialog_actions.open_annotation_options", ()),
    HandlerCase("FileOperationsMixin", "_open_quick_window_level", "dialog_actions.open_quick_window_level", ()),
    HandlerCase("FileOperationsMixin", "_open_quick_start_guide", "dialog_actions.open_quick_start_guide", ()),
    HandlerCase(
        "FileOperationsMixin",
        "_open_user_documentation_in_browser",
        "dialog_actions.open_user_documentation_in_browser",
        (),
    ),
    HandlerCase(
        "FileOperationsMixin",
        "_open_fusion_technical_doc",
        "dialog_actions.open_fusion_technical_doc",
        (),
    ),
    HandlerCase(
        "FileOperationsMixin",
        "_open_structured_report_browser",
        "dialog_actions.open_structured_report_browser",
        (1,),
    ),
    HandlerCase("FileOperationsMixin", "_on_export_cine_video", "dialog_actions.open_export_cine_video", ()),
    HandlerCase(
        "FileOperationsMixin",
        "_open_acr_ct_phantom_analysis",
        "dialog_actions.open_acr_ct_phantom_analysis",
        (),
    ),
    HandlerCase(
        "FileOperationsMixin",
        "_open_acr_ct_batch_analysis",
        "dialog_actions.open_acr_ct_batch_analysis",
        (),
    ),
    HandlerCase(
        "FileOperationsMixin",
        "_open_acr_mri_phantom_analysis",
        "dialog_actions.open_acr_mri_phantom_analysis",
        (),
    ),
    HandlerCase(
        "FileOperationsMixin",
        "_open_acr_mri_batch_analysis",
        "dialog_actions.open_acr_mri_batch_analysis",
        (),
    ),
    HandlerCase("FileOperationsMixin", "_open_nuclear_qc_analysis", "dialog_actions.open_nuclear_qc_analysis", ()),
    HandlerCase(
        "FileOperationsMixin",
        "_open_path_in_system_viewer",
        "dialog_actions.open_path_in_system_viewer",
        ("/tmp/report.pdf",),
    ),
    # TagEditingMixin
    HandlerCase("TagEditingMixin", "_open_tag_viewer", "dialog_actions.open_tag_viewer", ()),
    HandlerCase("TagEditingMixin", "_open_tag_export", "dialog_actions.open_tag_export", ()),
    HandlerCase(
        "TagEditingMixin",
        "_on_export_tag_presets",
        "customization_actions.on_export_tag_presets",
        (),
    ),
    HandlerCase(
        "TagEditingMixin",
        "_on_import_tag_presets",
        "customization_actions.on_import_tag_presets",
        (),
    ),
    # ROIWorkflowMixin -> core.slice_display_handlers
    HandlerCase("ROIWorkflowMixin", "_update_roi_list", "update_roi_list", ()),
    HandlerCase("ROIWorkflowMixin", "_display_rois_for_slice", "display_rois_for_slice", (object(),)),
    HandlerCase("ROIWorkflowMixin", "_display_measurements_for_slice", "display_measurements_for_slice", (object(),)),
    # SubwindowManagementMixin -> session reset / assignment helpers
    HandlerCase("SubwindowManagementMixin", "_clear_data", "session_reset_clear_data", ()),
    HandlerCase("SubwindowManagementMixin", "_close_files", "session_reset_close_all_files", ()),
    HandlerCase("SubwindowManagementMixin", "_get_subwindow_assignments", "get_subwindow_assignments", ()),
)

