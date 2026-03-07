"""
Main-window panel layout helper.

This module provides a single function, setup_main_window_content, that assembles
the main-window panel layout (center, left, right panels with tabs, series
navigator, and window-slot map callbacks). It is called once from
DICOMViewerApp._setup_ui in main.py.

Inputs:
    - main_window: the MainWindow instance
    - Widgets to place: multi_window_layout, cine_controls_widget, metadata_panel,
      window_level_controls, zoom_display_widget, roi_list_panel, roi_statistics_panel,
      intensity_projection_controls_widget, fusion_controls_widget, series_navigator
    - Callbacks for window-slot map: get_slot_to_view, get_layout_mode,
      get_focused_view_index, get_thumbnail_for_view

Outputs:
    - None; the main_window's panels are populated in place.

Requirements:
    - PySide6 (QVBoxLayout, QTabWidget, QWidget)
"""

from typing import Callable


def setup_main_window_content(
    main_window,
    multi_window_layout,
    cine_controls_widget,
    metadata_panel,
    window_level_controls,
    zoom_display_widget,
    roi_list_panel,
    roi_statistics_panel,
    intensity_projection_controls_widget,
    fusion_controls_widget,
    series_navigator,
    *,
    get_slot_to_view: Callable,
    get_layout_mode: Callable,
    get_focused_view_index: Callable,
    get_thumbnail_for_view: Callable,
) -> None:
    """
    Assemble the main-window panel layout: center (multi-window), left (cine + metadata),
    right (tabbed Window/Zoom/ROI and Combine/Fuse), series navigator, and window-slot map callbacks.
    """
    from PySide6.QtWidgets import QVBoxLayout, QTabWidget, QWidget

    # Add multi-window layout to center panel
    center_layout = main_window.center_panel.layout()
    if center_layout is None:
        center_layout = QVBoxLayout(main_window.center_panel)
    center_layout.addWidget(multi_window_layout)

    # Add cine controls widget and metadata panel to left panel
    left_layout = main_window.left_panel.layout()
    if left_layout is None:
        left_layout = QVBoxLayout(main_window.left_panel)
    # Add cine controls widget first (above metadata panel) with stretch 0
    left_layout.addWidget(cine_controls_widget, 0)
    # Add metadata panel below cine controls with stretch 1 to make it ~1.5x its current height
    left_layout.addWidget(metadata_panel, 1)

    # Add controls to right panel with tabbed interface
    right_layout = main_window.right_panel.layout()
    if right_layout is None:
        right_layout = QVBoxLayout(main_window.right_panel)

    # Create tab widget
    tab_widget = QTabWidget()
    tab_widget.setObjectName("right_panel_tabs")

    # Tab 1: Window/Zoom/ROI
    tab1_widget = QWidget()
    tab1_layout = QVBoxLayout(tab1_widget)
    tab1_layout.setContentsMargins(0, 0, 0, 0)
    tab1_layout.setSpacing(0)
    tab1_layout.addWidget(window_level_controls)
    tab1_layout.addWidget(zoom_display_widget)
    tab1_layout.addStretch()  # Push ROI sections to bottom
    tab1_layout.addWidget(roi_list_panel)
    tab1_layout.addWidget(roi_statistics_panel)
    tab_widget.addTab(tab1_widget, "Window/Zoom/ROI")

    # Tab 2: Combine/Fuse
    tab2_widget = QWidget()
    tab2_layout = QVBoxLayout(tab2_widget)
    tab2_layout.setContentsMargins(0, 0, 0, 0)
    tab2_layout.setSpacing(0)
    tab2_layout.addWidget(intensity_projection_controls_widget)
    tab2_layout.addWidget(fusion_controls_widget)
    tab2_layout.addStretch()
    tab_widget.addTab(tab2_widget, "Combine/Fuse")

    right_layout.addWidget(tab_widget)

    # Add series navigator and window-slot thumbnail to main window
    main_window.set_series_navigator(series_navigator)

    # Wire callbacks for window-slot thumbnail widget (if present)
    if hasattr(main_window, "set_window_slot_map_callbacks"):
        try:
            main_window.set_window_slot_map_callbacks(
                get_slot_to_view=get_slot_to_view,
                get_layout_mode=get_layout_mode,
                get_focused_view_index=get_focused_view_index,
                get_thumbnail_for_view=get_thumbnail_for_view,
            )
        except Exception:
            pass
        # Apply initial visibility from the View menu toggle if available
        if hasattr(main_window, "show_window_slot_map_action"):
            main_window.set_window_slot_map_visible(
                main_window.show_window_slot_map_action.isChecked()
            )
