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
    open_file_action.setShortcut(QKeySequence.Open)
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

    close_action = QAction("&Close", main_window)
    close_action.setShortcut(QKeySequence("Ctrl+W"))
    close_action.triggered.connect(main_window.close_requested.emit)
    file_menu.addAction(close_action)

    file_menu.addSeparator()

    exit_action = QAction("E&xit", main_window)
    exit_action.setShortcut(QKeySequence.Quit)
    exit_action.triggered.connect(main_window.close)
    file_menu.addAction(exit_action)

    # --- Edit menu ---
    edit_menu = menubar.addMenu("&Edit")

    main_window.copy_annotation_action = QAction("&Copy", main_window)
    main_window.copy_annotation_action.setShortcut(QKeySequence.Copy)
    main_window.copy_annotation_action.triggered.connect(main_window.copy_annotation_requested.emit)
    edit_menu.addAction(main_window.copy_annotation_action)

    main_window.paste_annotation_action = QAction("&Paste", main_window)
    main_window.paste_annotation_action.setShortcut(QKeySequence.Paste)
    main_window.paste_annotation_action.triggered.connect(main_window.paste_annotation_requested.emit)
    edit_menu.addAction(main_window.paste_annotation_action)

    edit_menu.addSeparator()

    main_window.undo_tag_edit_action = QAction("&Undo", main_window)
    main_window.undo_tag_edit_action.setShortcut(QKeySequence.Undo)
    main_window.undo_tag_edit_action.setEnabled(False)
    main_window.undo_tag_edit_action.triggered.connect(main_window.undo_tag_edit_requested.emit)
    edit_menu.addAction(main_window.undo_tag_edit_action)

    main_window.redo_tag_edit_action = QAction("&Redo", main_window)
    main_window.redo_tag_edit_action.setShortcut(QKeySequence.Redo)
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

    main_window.privacy_view_action = QAction("&Privacy View", main_window)
    main_window.privacy_view_action.setCheckable(True)
    main_window.privacy_view_action.setChecked(main_window.config_manager.get_privacy_view())
    main_window.privacy_view_action.setShortcut(QKeySequence("Ctrl+P"))
    main_window.privacy_view_action.triggered.connect(main_window._on_privacy_view_toggled)
    view_menu.addAction(main_window.privacy_view_action)

    view_menu.addSeparator()

    settings_action = QAction("&Settings...", main_window)
    settings_action.triggered.connect(main_window.settings_requested.emit)
    view_menu.addAction(settings_action)

    overlay_config_action = QAction("Overlay &Configuration...", main_window)
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

    # --- Help menu ---
    help_menu = menubar.addMenu("&Help")

    quick_start_action = QAction("&Quick Start Guide", main_window)
    quick_start_action.triggered.connect(main_window.quick_start_guide_requested.emit)
    help_menu.addAction(quick_start_action)

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
