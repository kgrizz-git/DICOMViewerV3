"""
Main Window Menu Bar Builder

This module builds the application menu bar and menus for the DICOM viewer
MainWindow. It creates all menu actions and connects them to the main window's
signals and methods.

Inputs:
    - MainWindow instance (or any object with the required signals, config_manager,
      and methods: _set_theme, _on_layout_changed, _open_edit_recent_list_dialog,
      _show_disclaimer, _show_about, _on_privacy_view_toggled, _update_recent_menu,
      menuBar(), and installEventFilter).

Outputs:
    - A populated menu bar attached to the main window.
    - Action references stored on the main window (e.g. recent_menu,
      copy_annotation_action, layout_1x1_action) for use by MainWindow and callers.

Requirements:
    - PySide6 (QAction, QKeySequence, QMenu)
    - MainWindow must be fully constructed (config_manager, signals) before calling.
"""

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction, QKeySequence


def build_menu_bar(main_window) -> None:
    """
    Build and attach the application menu bar to the given main window.

    Creates File, Edit, View, Tools, and Help menus with all actions.
    Stores references to actions and the recent submenu on main_window for
    later use (e.g. update_recent_menu, update_undo_redo_state, set_layout_mode).

    Args:
        main_window: The MainWindow instance (or compatible object) that will
            receive the menu bar and hold action references.
    """
    menubar = main_window.menuBar()

    # --- File menu ---
    file_menu = menubar.addMenu("&File")

    open_file_action = QAction("&Open File(s)...", main_window)
    open_file_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Open))
    open_file_action.triggered.connect(main_window.open_file_requested.emit)
    file_menu.addAction(open_file_action)

    open_folder_action = QAction("Open &Folder...", main_window)
    open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
    open_folder_action.triggered.connect(main_window.open_folder_requested.emit)
    file_menu.addAction(open_folder_action)

    file_menu.addSeparator()

    main_window.recent_menu = file_menu.addMenu("&Recent")
    main_window.recent_menu.installEventFilter(main_window)
    main_window._update_recent_menu()

    edit_recent_list_action = QAction("Edit Recent List...", main_window)
    edit_recent_list_action.triggered.connect(main_window._open_edit_recent_list_dialog)
    file_menu.addAction(edit_recent_list_action)

    file_menu.addSeparator()

    export_action = QAction("&Export...", main_window)
    export_action.setShortcut(QKeySequence("Ctrl+E"))
    export_action.triggered.connect(main_window.export_requested.emit)
    file_menu.addAction(export_action)

    export_screenshots_action = QAction("Export Screenshots...", main_window)
    export_screenshots_action.triggered.connect(main_window.export_screenshots_requested.emit)
    file_menu.addAction(export_screenshots_action)

    file_menu.addSeparator()

    export_customizations_action = QAction("Export Customizations...", main_window)
    export_customizations_action.triggered.connect(main_window.export_customizations_requested.emit)
    file_menu.addAction(export_customizations_action)

    import_customizations_action = QAction("Import Customizations...", main_window)
    import_customizations_action.triggered.connect(main_window.import_customizations_requested.emit)
    file_menu.addAction(import_customizations_action)

    file_menu.addSeparator()

    export_tag_presets_action = QAction("Export Tag Presets...", main_window)
    export_tag_presets_action.triggered.connect(main_window.export_tag_presets_requested.emit)
    file_menu.addAction(export_tag_presets_action)

    import_tag_presets_action = QAction("Import Tag Presets...", main_window)
    import_tag_presets_action.triggered.connect(main_window.import_tag_presets_requested.emit)
    file_menu.addAction(import_tag_presets_action)

    file_menu.addSeparator()

    close_action = QAction("Close &All", main_window)
    close_action.setShortcut(QKeySequence("Ctrl+W"))
    close_action.setStatusTip("Close all loaded studies and series")
    close_action.triggered.connect(main_window.close_requested.emit)
    file_menu.addAction(close_action)

    file_menu.addSeparator()

    exit_action = QAction("E&xit", main_window)
    exit_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    # --- Edit menu ---
    edit_menu = menubar.addMenu("&Edit")

    main_window.copy_annotation_action = QAction("&Copy", main_window)
    main_window.copy_annotation_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
    main_window.copy_annotation_action.triggered.connect(main_window.copy_annotation_requested.emit)
    edit_menu.addAction(main_window.copy_annotation_action)

    main_window.paste_annotation_action = QAction("&Paste", main_window)
    main_window.paste_annotation_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Paste))
    main_window.paste_annotation_action.triggered.connect(main_window.paste_annotation_requested.emit)
    edit_menu.addAction(main_window.paste_annotation_action)

    edit_menu.addSeparator()

    main_window.undo_tag_edit_action = QAction("&Undo", main_window)
    main_window.undo_tag_edit_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Undo))
    main_window.undo_tag_edit_action.setEnabled(False)
    main_window.undo_tag_edit_action.triggered.connect(main_window.undo_tag_edit_requested.emit)
    edit_menu.addAction(main_window.undo_tag_edit_action)

    main_window.redo_tag_edit_action = QAction("&Redo", main_window)
    main_window.redo_tag_edit_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Redo))
    main_window.redo_tag_edit_action.setEnabled(False)
    main_window.redo_tag_edit_action.triggered.connect(main_window.redo_tag_edit_requested.emit)
    edit_menu.addAction(main_window.redo_tag_edit_action)

    # --- View menu ---
    view_menu = menubar.addMenu("&View")

    theme_menu = view_menu.addMenu("&Theme")
    main_window.light_theme_action = QAction("&Light", main_window)
    main_window.light_theme_action.setCheckable(True)
    main_window.light_theme_action.setChecked(main_window.config_manager.get_theme() == "light")
    main_window.light_theme_action.triggered.connect(lambda: main_window._set_theme("light"))
    theme_menu.addAction(main_window.light_theme_action)

    main_window.dark_theme_action = QAction("&Dark", main_window)
    main_window.dark_theme_action.setCheckable(True)
    main_window.dark_theme_action.setChecked(main_window.config_manager.get_theme() == "dark")
    main_window.dark_theme_action.triggered.connect(lambda: main_window._set_theme("dark"))
    theme_menu.addAction(main_window.dark_theme_action)

    view_menu.addSeparator()

    # Reset View (same action as toolbar to avoid ambiguous shortcut overload)
    view_menu.addAction(main_window.reset_view_action)

    view_menu.addSeparator()

    # Orientation submenu (flip / rotate focused viewer — non-destructive)
    orientation_menu = view_menu.addMenu("&Orientation")

    flip_h_act = QAction("Flip &Horizontal", main_window)
    flip_h_act.setShortcut(QKeySequence("Alt+H"))
    flip_h_act.triggered.connect(main_window.orientation_flip_h_requested.emit)
    orientation_menu.addAction(flip_h_act)

    flip_v_act = QAction("Flip &Vertical", main_window)
    flip_v_act.setShortcut(QKeySequence("Alt+V"))
    flip_v_act.triggered.connect(main_window.orientation_flip_v_requested.emit)
    orientation_menu.addAction(flip_v_act)

    orientation_menu.addSeparator()

    rotate_cw_act = QAction("Rotate 90° &CW", main_window)
    rotate_cw_act.setShortcut(QKeySequence("Alt+R"))
    rotate_cw_act.triggered.connect(main_window.orientation_rotate_cw_requested.emit)
    orientation_menu.addAction(rotate_cw_act)

    rotate_ccw_act = QAction("Rotate 90° CC&W", main_window)
    rotate_ccw_act.setShortcut(QKeySequence("Shift+Alt+R"))
    rotate_ccw_act.triggered.connect(main_window.orientation_rotate_ccw_requested.emit)
    orientation_menu.addAction(rotate_ccw_act)

    rotate_180_act = QAction("Rotate &180°", main_window)
    rotate_180_act.triggered.connect(main_window.orientation_rotate_180_requested.emit)
    orientation_menu.addAction(rotate_180_act)

    orientation_menu.addSeparator()

    reset_orient_act = QAction("Reset &Orientation", main_window)
    reset_orient_act.setShortcut(QKeySequence("Shift+Alt+O"))
    reset_orient_act.triggered.connect(main_window.orientation_reset_requested.emit)
    orientation_menu.addAction(reset_orient_act)

    main_window.privacy_view_action = QAction("&Privacy View", main_window)
    main_window.privacy_view_action.setCheckable(True)
    main_window.privacy_view_action.setChecked(main_window.config_manager.get_privacy_view())
    main_window.privacy_view_action.setShortcut(QKeySequence("Ctrl+P"))
    main_window.privacy_view_action.triggered.connect(main_window._on_privacy_view_toggled)
    view_menu.addAction(main_window.privacy_view_action)

    main_window.smooth_when_zoomed_action = QAction("Image Smoothing", main_window)
    main_window.smooth_when_zoomed_action.setCheckable(True)
    main_window.smooth_when_zoomed_action.setChecked(main_window.config_manager.get_smooth_image_when_zoomed())
    main_window.smooth_when_zoomed_action.triggered.connect(main_window._on_smooth_when_zoomed_toggled)
    view_menu.addAction(main_window.smooth_when_zoomed_action)

    main_window.scale_markers_action = QAction("Show Scale Markers", main_window)
    main_window.scale_markers_action.setCheckable(True)
    main_window.scale_markers_action.setChecked(main_window.config_manager.get_show_scale_markers())
    main_window.scale_markers_action.triggered.connect(main_window._on_scale_markers_toggled)
    view_menu.addAction(main_window.scale_markers_action)

    main_window.direction_labels_action = QAction("Show Direction Labels", main_window)
    main_window.direction_labels_action.setCheckable(True)
    main_window.direction_labels_action.setChecked(main_window.config_manager.get_show_direction_labels())
    main_window.direction_labels_action.triggered.connect(main_window._on_direction_labels_toggled)
    view_menu.addAction(main_window.direction_labels_action)

    scale_markers_color_action = QAction("Scale Markers Color...", main_window)
    scale_markers_color_action.triggered.connect(main_window._on_scale_markers_color_picker)
    view_menu.addAction(scale_markers_color_action)

    direction_labels_color_action = QAction("Direction Labels Color...", main_window)
    direction_labels_color_action.triggered.connect(main_window._on_direction_labels_color_picker)
    view_menu.addAction(direction_labels_color_action)

    main_window.slice_slider_action = QAction("Show In-View Slice/Frame Slider", main_window)
    main_window.slice_slider_action.setCheckable(True)
    main_window.slice_slider_action.setChecked(main_window.config_manager.get_show_slice_slider())
    main_window.slice_slider_action.triggered.connect(
        lambda checked: main_window.slice_slider_toggled.emit(checked)
    )
    view_menu.addAction(main_window.slice_slider_action)

    main_window.show_instances_separately_action = QAction("Show Instances Separately", main_window)
    main_window.show_instances_separately_action.setCheckable(True)
    main_window.show_instances_separately_action.setChecked(main_window.config_manager.get_show_instances_separately())
    main_window.show_instances_separately_action.setEnabled(False)
    main_window.show_instances_separately_action.triggered.connect(main_window._on_show_instances_separately_toggled)
    view_menu.addAction(main_window.show_instances_separately_action)

    # Show/Hide Left Pane and Right Pane (initial check state default True; MainWindow syncs from splitter after central widget is created)
    main_window.show_left_pane_action = QAction("Show/Hide Left Pane", main_window)
    main_window.show_left_pane_action.setCheckable(True)
    main_window.show_left_pane_action.setChecked(True)
    main_window.show_left_pane_action.triggered.connect(main_window._toggle_left_pane)
    view_menu.addAction(main_window.show_left_pane_action)

    main_window.show_right_pane_action = QAction("Show/Hide Right Pane", main_window)
    main_window.show_right_pane_action.setCheckable(True)
    main_window.show_right_pane_action.setChecked(True)
    main_window.show_right_pane_action.triggered.connect(main_window._toggle_right_pane)
    view_menu.addAction(main_window.show_right_pane_action)

    # Show/Hide Series Navigator (check state synced in MainWindow.toggle_series_navigator)
    main_window.show_series_navigator_action = QAction("Show/Hide Series Navigator", main_window)
    main_window.show_series_navigator_action.setCheckable(True)
    main_window.show_series_navigator_action.setChecked(False)  # Navigator starts hidden
    main_window.show_series_navigator_action.triggered.connect(main_window.toggle_series_navigator)
    view_menu.addAction(main_window.show_series_navigator_action)

    view_menu.addSeparator()

    # Window assignment thumbnail toggle
    main_window.show_window_slot_map_action = QAction("Show Window Assignment Thumbnail", main_window)
    main_window.show_window_slot_map_action.setCheckable(True)
    main_window.show_window_slot_map_action.setChecked(True)
    main_window.show_window_slot_map_action.triggered.connect(
        lambda checked: getattr(main_window, "set_window_slot_map_visible", lambda v: None)(checked)
    )
    view_menu.addAction(main_window.show_window_slot_map_action)

    settings_action = QAction("&Settings...", main_window)
    settings_action.triggered.connect(main_window.settings_requested.emit)
    view_menu.addAction(settings_action)

    overlay_config_action = QAction("Overlay &Tags Configuration...", main_window)
    overlay_config_action.setShortcut(QKeySequence("Ctrl+O"))
    overlay_config_action.triggered.connect(main_window.overlay_config_requested.emit)
    view_menu.addAction(overlay_config_action)

    overlay_settings_action = QAction("Overlay &Settings...", main_window)
    overlay_settings_action.triggered.connect(main_window.overlay_settings_requested.emit)
    view_menu.addAction(overlay_settings_action)

    annotation_options_action = QAction("Annotation &Options...", main_window)
    annotation_options_action.triggered.connect(main_window.annotation_options_requested.emit)
    view_menu.addAction(annotation_options_action)

    view_menu.addSeparator()

    layout_menu = view_menu.addMenu("&Layout")
    main_window.layout_1x1_action = QAction("&1x1  (1)", main_window)
    main_window.layout_1x1_action.setCheckable(True)
    main_window.layout_1x1_action.setChecked(True)
    main_window.layout_1x1_action.triggered.connect(lambda: main_window._on_layout_changed("1x1"))
    layout_menu.addAction(main_window.layout_1x1_action)

    main_window.layout_1x2_action = QAction("&1x2  (2)", main_window)
    main_window.layout_1x2_action.setCheckable(True)
    main_window.layout_1x2_action.triggered.connect(lambda: main_window._on_layout_changed("1x2"))
    layout_menu.addAction(main_window.layout_1x2_action)

    main_window.layout_2x1_action = QAction("&2x1  (3)", main_window)
    main_window.layout_2x1_action.setCheckable(True)
    main_window.layout_2x1_action.triggered.connect(lambda: main_window._on_layout_changed("2x1"))
    layout_menu.addAction(main_window.layout_2x1_action)

    main_window.layout_2x2_action = QAction("&2x2  (4)", main_window)
    main_window.layout_2x2_action.setCheckable(True)
    main_window.layout_2x2_action.triggered.connect(lambda: main_window._on_layout_changed("2x2"))
    layout_menu.addAction(main_window.layout_2x2_action)

    view_menu.addSeparator()

    # Slice Sync submenu
    slice_sync_menu = view_menu.addMenu("Slice &Sync")

    main_window.slice_sync_action = QAction("Enable Slice Sync", main_window)
    main_window.slice_sync_action.setCheckable(True)
    main_window.slice_sync_action.setChecked(
        main_window.config_manager.get_slice_sync_enabled()
    )
    main_window.slice_sync_action.triggered.connect(
        lambda checked: main_window.slice_sync_toggled.emit(checked)
    )
    slice_sync_menu.addAction(main_window.slice_sync_action)

    manage_sync_groups_action = QAction("Manage Sync Groups...", main_window)
    manage_sync_groups_action.triggered.connect(
        main_window.slice_sync_manage_requested.emit
    )
    slice_sync_menu.addAction(manage_sync_groups_action)

    # Show Lines submenu (slice location lines across views)
    show_lines_menu = view_menu.addMenu("Show &Slice Location Lines")

    main_window.slice_location_lines_enable_action = QAction("Enable/Disable", main_window)
    main_window.slice_location_lines_enable_action.setCheckable(True)
    main_window.slice_location_lines_enable_action.setChecked(
        main_window.config_manager.get_slice_location_lines_visible()
    )
    main_window.slice_location_lines_enable_action.setStatusTip(
        "Show the intersection of other views' slice planes on the current image"
    )
    main_window.slice_location_lines_enable_action.triggered.connect(
        lambda checked: main_window.slice_location_lines_toggled.emit(checked)
    )
    show_lines_menu.addAction(main_window.slice_location_lines_enable_action)

    main_window.slice_location_lines_same_group_only_action = QAction("Only Show For Same Group", main_window)
    main_window.slice_location_lines_same_group_only_action.setCheckable(True)
    main_window.slice_location_lines_same_group_only_action.setChecked(
        main_window.config_manager.get_slice_location_lines_same_group_only()
    )
    main_window.slice_location_lines_same_group_only_action.setStatusTip(
        "Only show slice location lines from subwindows in the same linked group"
    )
    main_window.slice_location_lines_same_group_only_action.triggered.connect(
        lambda checked: main_window.slice_location_lines_same_group_only_toggled.emit(checked)
    )
    show_lines_menu.addAction(main_window.slice_location_lines_same_group_only_action)

    main_window.slice_location_lines_focused_only_action = QAction("Show Only For Focused Window", main_window)
    main_window.slice_location_lines_focused_only_action.setCheckable(True)
    main_window.slice_location_lines_focused_only_action.setChecked(
        main_window.config_manager.get_slice_location_lines_focused_only()
    )
    main_window.slice_location_lines_focused_only_action.setStatusTip(
        "Only show slice location lines from the currently focused subwindow"
    )
    main_window.slice_location_lines_focused_only_action.triggered.connect(
        lambda checked: main_window.slice_location_lines_focused_only_toggled.emit(checked)
    )
    show_lines_menu.addAction(main_window.slice_location_lines_focused_only_action)

    show_lines_menu.addSeparator()

    # Line mode: "Middle" vs "Begin/End" (checkable action — unchecked = middle, checked = begin_end)
    main_window.slice_location_lines_show_slab_bounds_action = QAction(
        "Show Slab Boundaries (Begin/End) Instead of Centre", main_window
    )
    main_window.slice_location_lines_show_slab_bounds_action.setCheckable(True)
    main_window.slice_location_lines_show_slab_bounds_action.setChecked(
        main_window.config_manager.get_slice_location_line_mode() == "begin_end"
    )
    main_window.slice_location_lines_show_slab_bounds_action.setStatusTip(
        "Draw two lines at the slab boundaries (±½ slice thickness) instead of "
        "a single line at the centre plane"
    )
    main_window.slice_location_lines_show_slab_bounds_action.triggered.connect(
        lambda checked: main_window.slice_location_lines_mode_toggled.emit(
            "begin_end" if checked else "middle"
        )
    )
    show_lines_menu.addAction(main_window.slice_location_lines_show_slab_bounds_action)

    # --- Tools menu ---
    tools_menu = menubar.addMenu("&Tools")

    tag_viewer_action = QAction("View/Edit DICOM &Tags...", main_window)
    tag_viewer_action.setShortcut(QKeySequence("Ctrl+T"))
    tag_viewer_action.triggered.connect(main_window.tag_viewer_requested.emit)
    tools_menu.addAction(tag_viewer_action)

    tag_export_action = QAction("Export DICOM &Tags...", main_window)
    tag_export_action.setShortcut(QKeySequence("Shift+Ctrl+T"))
    tag_export_action.triggered.connect(main_window.tag_export_requested.emit)
    tools_menu.addAction(tag_export_action)

    create_mpr_action = QAction("Create MPR &View…", main_window)
    create_mpr_action.setStatusTip(
        "Build a multi-planar reconstruction in the focused image window"
    )
    create_mpr_action.triggered.connect(main_window.create_mpr_view_requested.emit)
    tools_menu.addAction(create_mpr_action)

    study_index_action = QAction("Study &index search…", main_window)
    study_index_action.setStatusTip(
        "Search the local encrypted study index or index a folder of DICOM files"
    )
    study_index_action.triggered.connect(main_window.study_index_search_requested.emit)
    tools_menu.addAction(study_index_action)

    about_this_file_action = QAction("About this File...", main_window)
    about_this_file_action.setMenuRole(QAction.MenuRole.NoRole)
    about_this_file_action.setShortcut(QKeySequence("Ctrl+A"))
    about_this_file_action.triggered.connect(main_window.about_this_file_requested.emit)
    tools_menu.addAction(about_this_file_action)

    tools_menu.addSeparator()

    histogram_action = QAction("&Histogram...", main_window)
    histogram_action.setShortcut(QKeySequence("Shift+Ctrl+H"))
    histogram_action.triggered.connect(main_window.histogram_requested.emit)
    tools_menu.addAction(histogram_action)

    export_roi_stats_action = QAction("Export &ROI Statistics...", main_window)
    export_roi_stats_action.triggered.connect(main_window.export_roi_statistics_requested.emit)
    tools_menu.addAction(export_roi_stats_action)

    tools_menu.addSeparator()

    acr_ct_phantom_action = QAction("ACR CT Phantom (pylinac)...", main_window)
    acr_ct_phantom_action.triggered.connect(main_window.acr_ct_phantom_requested.emit)
    tools_menu.addAction(acr_ct_phantom_action)

    acr_mri_phantom_action = QAction("ACR MRI Phantom (pylinac)...", main_window)
    acr_mri_phantom_action.triggered.connect(main_window.acr_mri_phantom_requested.emit)
    tools_menu.addAction(acr_mri_phantom_action)

    # --- Help menu ---
    help_menu = menubar.addMenu("&Help")

    quick_start_action = QAction("&Quick Start Guide", main_window)
    quick_start_action.triggered.connect(main_window.quick_start_guide_requested.emit)
    help_menu.addAction(quick_start_action)

    documentation_action = QAction("&Documentation (browser)...", main_window)
    documentation_action.setStatusTip("Open the user guide hub on GitHub in your web browser")
    documentation_action.triggered.connect(main_window.user_documentation_requested.emit)
    help_menu.addAction(documentation_action)

    fusion_tech_doc_action = QAction("Fusion &Technical Documentation", main_window)
    fusion_tech_doc_action.triggered.connect(main_window.fusion_technical_doc_requested.emit)
    help_menu.addAction(fusion_tech_doc_action)

    disclaimer_action = QAction("&Disclaimer", main_window)
    disclaimer_action.triggered.connect(main_window._show_disclaimer)
    help_menu.addAction(disclaimer_action)

    help_menu.addSeparator()

    about_action = QAction("&About", main_window)
    about_action.triggered.connect(main_window._show_about)
    help_menu.addAction(about_action)
