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

from collections.abc import Callable
from typing import Any


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
    get_slot_to_view: Callable[..., Any],
    get_layout_mode: Callable[..., Any],
    get_focused_view_index: Callable[..., Any],
    get_thumbnail_for_view: Callable[..., Any],
) -> None:
    """
    Assemble the main-window panel layout: center (multi-window), left (cine + metadata),
    right (tabbed Window/Zoom/ROI and Combine/Fuse), series navigator, and window-slot map callbacks.
    """
    from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

    # Add multi-window layout to center panel
    center_layout = main_window.center_panel.layout()
    if center_layout is None:
        center_layout = QVBoxLayout(main_window.center_panel)
    # No outer margins — image viewport should fill to the splitter handles
    center_layout.setContentsMargins(0, 0, 0, 0)
    center_layout.setSpacing(0)
    center_layout.addWidget(multi_window_layout)

    # Add cine controls widget and metadata panel to left panel
    left_layout = main_window.left_panel.layout()
    if left_layout is None:
        left_layout = QVBoxLayout(main_window.left_panel)
    # Remove default platform margins — individual widgets carry their own padding
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)
    # Add cine controls widget first (above metadata panel) with stretch 0
    left_layout.addWidget(cine_controls_widget, 0)
    # Add metadata panel below cine controls with stretch 1 to make it ~1.5x its current height
    left_layout.addWidget(metadata_panel, 1)

    # Add controls to right panel with tabbed interface
    right_layout = main_window.right_panel.layout()
    if right_layout is None:
        right_layout = QVBoxLayout(main_window.right_panel)
    # Remove default platform margins — tab widget fills the panel edge-to-edge
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)

    # Create tab widget
    tab_widget = QTabWidget()
    tab_widget.setObjectName("right_panel_tabs")

    # Tab 1: Window/Zoom/ROI
    from PySide6.QtWidgets import QCheckBox, QHBoxLayout

    tab1_widget = QWidget()
    tab1_layout = QVBoxLayout(tab1_widget)
    tab1_layout.setContentsMargins(3, 4, 4, 0)
    tab1_layout.setSpacing(0)

    # Rescale toggle + Presets… on one row (Presets button attached from main.py)
    rescale_cb = QCheckBox("Use rescaled values")
    rescale_cb.setChecked(False)  # Default; updated by set_rescale_toggle_state when a series loads
    rescale_cb.setToolTip(
        "When checked, pixel values are multiplied by RescaleSlope and offset by RescaleIntercept "
        "(e.g. Hounsfield Units for CT). When unchecked, raw stored pixel values are used."
    )
    rescale_cb.toggled.connect(main_window.rescale_toggle_changed.emit)
    main_window.use_rescaled_values_checkbox = rescale_cb

    rescale_presets_row = QHBoxLayout()
    rescale_presets_row.setContentsMargins(0, 0, 0, 0)
    rescale_presets_row.addWidget(rescale_cb)
    rescale_presets_row.addStretch()
    main_window.wl_presets_row_layout = rescale_presets_row
    tab1_layout.addLayout(rescale_presets_row, 0)
    tab1_layout.addWidget(window_level_controls, 0)
    tab1_layout.addWidget(zoom_display_widget, 0)
    # ROI panels share all remaining space equally; they expand when the
    # window is tall and shrink to their minimum height when short.
    tab1_layout.addWidget(roi_list_panel, 1)
    tab1_layout.addWidget(roi_statistics_panel, 1)
    tab_widget.addTab(tab1_widget, "Window/Zoom/ROI")

    # Tab 2: Combine/Fuse
    tab2_widget = QWidget()
    tab2_layout = QVBoxLayout(tab2_widget)
    tab2_layout.setContentsMargins(3, 4, 4, 0)
    tab2_layout.setSpacing(0)
    tab2_layout.addWidget(intensity_projection_controls_widget)
    tab2_layout.addWidget(fusion_controls_widget)
    tab2_layout.addStretch()

    # Contextual link to fusion algorithm documentation (moved from Help menu)
    from PySide6.QtWidgets import QPushButton
    fusion_doc_btn = QPushButton("Fusion Documentation…")
    fusion_doc_btn.setFlat(True)
    fusion_doc_btn.setToolTip("Open fusion algorithm documentation in browser")
    fusion_doc_btn.clicked.connect(main_window.fusion_technical_doc_requested.emit)
    tab2_layout.addWidget(fusion_doc_btn)

    tab_widget.addTab(tab2_widget, "Slab / Fuse")

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
