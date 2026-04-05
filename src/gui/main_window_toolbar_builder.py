"""
Main Window Toolbar Builder

Builds the main application toolbar (mouse modes, privacy, reset view, series nav,
overlay font controls, rescale toggle, scroll-wheel mode) for MainWindow.

Inputs:
    - MainWindow instance (or compatible): config_manager, reset_view_action,
      signals and slots used by toolbar actions (_on_mouse_mode_changed,
      _on_privacy_mode_button_clicked, toggle_series_navigator, etc.).

Outputs:
    - QToolBar added to the window; action/widget references stored on main_window
      (e.g. main_toolbar, mouse_mode_pan_action, scroll_wheel_mode_combo).

Requirements:
    - PySide6 (QToolBar, QAction, QLabel, QComboBox, …)
    - reset_view_action must exist on main_window before calling (shared with menu).
"""

from PySide6.QtWidgets import QToolBar, QLabel, QSizePolicy, QWidget, QComboBox
from PySide6.QtGui import QAction, QKeySequence


def build_main_toolbar(main_window) -> None:
    """
    Create and attach the main toolbar to the given main window.

    Args:
        main_window: MainWindow instance (same contract as build_menu_bar).
    """
    toolbar = QToolBar("Main Toolbar", main_window)
    toolbar.setMovable(False)
    main_window.addToolBar(toolbar)

    # Mouse interaction mode buttons (exclusive)
    main_window.mouse_mode_ellipse_roi_action = QAction("Ellipse ROI", main_window)
    main_window.mouse_mode_ellipse_roi_action.setCheckable(True)
    main_window.mouse_mode_ellipse_roi_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("roi_ellipse")
    )
    toolbar.addAction(main_window.mouse_mode_ellipse_roi_action)

    main_window.mouse_mode_rectangle_roi_action = QAction("Rectangle ROI", main_window)
    main_window.mouse_mode_rectangle_roi_action.setCheckable(True)
    main_window.mouse_mode_rectangle_roi_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("roi_rectangle")
    )
    toolbar.addAction(main_window.mouse_mode_rectangle_roi_action)

    main_window.mouse_mode_measure_action = QAction("Measure", main_window)
    main_window.mouse_mode_measure_action.setCheckable(True)
    main_window.mouse_mode_measure_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("measure")
    )
    toolbar.addAction(main_window.mouse_mode_measure_action)

    # Text Annotation tool
    main_window.mouse_mode_text_annotation_action = QAction("Text", main_window)
    main_window.mouse_mode_text_annotation_action.setCheckable(True)
    main_window.mouse_mode_text_annotation_action.setShortcut(QKeySequence("T"))
    main_window.mouse_mode_text_annotation_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("text_annotation")
    )
    toolbar.addAction(main_window.mouse_mode_text_annotation_action)

    # Arrow Annotation tool
    main_window.mouse_mode_arrow_annotation_action = QAction("Arrow", main_window)
    main_window.mouse_mode_arrow_annotation_action.setCheckable(True)
    main_window.mouse_mode_arrow_annotation_action.setShortcut(QKeySequence("A"))
    main_window.mouse_mode_arrow_annotation_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("arrow_annotation")
    )
    toolbar.addAction(main_window.mouse_mode_arrow_annotation_action)

    main_window.mouse_mode_crosshair_action = QAction("Crosshair", main_window)
    main_window.mouse_mode_crosshair_action.setCheckable(True)
    main_window.mouse_mode_crosshair_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("crosshair")
    )
    toolbar.addAction(main_window.mouse_mode_crosshair_action)

    main_window.mouse_mode_zoom_action = QAction("Zoom", main_window)
    main_window.mouse_mode_zoom_action.setCheckable(True)
    main_window.mouse_mode_zoom_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("zoom")
    )
    toolbar.addAction(main_window.mouse_mode_zoom_action)

    main_window.mouse_mode_magnifier_action = QAction("Magnifier", main_window)
    main_window.mouse_mode_magnifier_action.setCheckable(True)
    main_window.mouse_mode_magnifier_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("magnifier")
    )
    toolbar.addAction(main_window.mouse_mode_magnifier_action)

    main_window.mouse_mode_pan_action = QAction("Pan", main_window)
    main_window.mouse_mode_pan_action.setCheckable(True)
    main_window.mouse_mode_pan_action.setChecked(True)  # Default mode
    main_window.mouse_mode_pan_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("pan")
    )
    toolbar.addAction(main_window.mouse_mode_pan_action)

    main_window.mouse_mode_select_action = QAction("Select", main_window)
    main_window.mouse_mode_select_action.setCheckable(True)
    main_window.mouse_mode_select_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("select")
    )
    toolbar.addAction(main_window.mouse_mode_select_action)

    # Window/Level ROI tool
    main_window.mouse_mode_auto_window_level_action = QAction("Window/Level ROI", main_window)
    main_window.mouse_mode_auto_window_level_action.setCheckable(True)
    main_window.mouse_mode_auto_window_level_action.triggered.connect(
        lambda: main_window._on_mouse_mode_changed("auto_window_level")
    )
    toolbar.addAction(main_window.mouse_mode_auto_window_level_action)

    toolbar.addSeparator()

    # Privacy Mode button
    main_window.privacy_mode_action = QAction("Privacy is OFF", main_window)
    main_window.privacy_mode_action.setCheckable(True)
    # Initialize from config - when privacy is OFF, button should be highlighted (checked)
    privacy_enabled = main_window.config_manager.get_privacy_view()
    main_window.privacy_mode_action.setChecked(not privacy_enabled)  # Checked when privacy is OFF
    main_window.privacy_mode_action.triggered.connect(main_window._on_privacy_mode_button_clicked)
    toolbar.addAction(main_window.privacy_mode_action)
    # Store toolbar reference for styling
    main_window.main_toolbar = toolbar
    # Update button appearance
    main_window._update_privacy_mode_button()

    toolbar.addSeparator()

    # Reset View button (shared action with View menu; V or Shift+V for focused subwindow)
    toolbar.addAction(main_window.reset_view_action)

    # Reset All Views button
    reset_all_views_action = QAction("Reset All Views", main_window)
    reset_all_views_action.setToolTip("Reset zoom, pan, window center and level for all subwindows")
    reset_all_views_action.setShortcut(QKeySequence("Shift+A"))
    reset_all_views_action.triggered.connect(main_window.reset_all_views_requested.emit)
    toolbar.addAction(reset_all_views_action)

    toolbar.addSeparator()

    # Series Navigator toggle button
    main_window.series_navigator_action = QAction("Show Series Navigator", main_window)
    main_window.series_navigator_action.setToolTip("Show/hide series navigator bar at bottom")
    main_window.series_navigator_action.triggered.connect(main_window.toggle_series_navigator)
    toolbar.addAction(main_window.series_navigator_action)

    toolbar.addSeparator()

    # Series navigation buttons
    main_window.prev_series_action = QAction("Prev Series", main_window)
    main_window.prev_series_action.setToolTip("Navigate to previous series (left arrow key)")
    main_window.prev_series_action.triggered.connect(main_window._on_prev_series)
    toolbar.addAction(main_window.prev_series_action)

    main_window.next_series_action = QAction("Next Series", main_window)
    main_window.next_series_action.setToolTip("Navigate to next series (right arrow key)")
    main_window.next_series_action.triggered.connect(main_window._on_next_series)
    toolbar.addAction(main_window.next_series_action)

    toolbar.addSeparator()

    # Overlay font size controls
    toolbar.addWidget(QLabel("Font Size:"))

    # Font size decrease button
    font_size_decrease_action = QAction("−", main_window)
    font_size_decrease_action.setToolTip("Decrease overlay font size")
    font_size_decrease_action.triggered.connect(main_window._on_font_size_decrease)
    toolbar.addAction(font_size_decrease_action)

    # Font size increase button
    font_size_increase_action = QAction("+", main_window)
    font_size_increase_action.setToolTip("Increase overlay font size")
    font_size_increase_action.triggered.connect(main_window._on_font_size_increase)
    toolbar.addAction(font_size_increase_action)

    toolbar.addSeparator()

    # Font color picker button
    font_color_action = QAction("Font Color", main_window)
    font_color_action.setToolTip("Change overlay font color")
    font_color_action.triggered.connect(main_window._on_font_color_picker)
    toolbar.addAction(font_color_action)

    toolbar.addSeparator()

    # Use Rescaled Values toggle button (non-checkable, text alternates)
    main_window.use_rescaled_values_action = QAction("Use Rescaled Values", main_window)
    main_window.use_rescaled_values_action.setCheckable(False)  # Not checkable, text shows current state
    main_window.use_rescaled_values_action.setToolTip("Toggle between rescaled and raw pixel values")
    main_window.use_rescaled_values_action.triggered.connect(main_window._on_rescale_toggle_changed)
    toolbar.addAction(main_window.use_rescaled_values_action)

    # Add stretch to push scroll wheel mode toggle to the right
    toolbar.addSeparator()

    # Create spacer widget that expands
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    toolbar.addWidget(spacer)

    toolbar.addWidget(QLabel("Scroll Wheel:"))

    # Scroll wheel mode toggle (right-aligned)
    main_window.scroll_wheel_mode_combo = QComboBox()
    main_window.scroll_wheel_mode_combo.setObjectName("scroll_wheel_mode_combo")
    main_window.scroll_wheel_mode_combo.addItems(["Slice", "Zoom"])
    # Set current mode from config
    current_mode = (
        main_window.config_manager.get_scroll_wheel_mode()
        if main_window.config_manager
        else "slice"
    )
    if current_mode == "zoom":
        main_window.scroll_wheel_mode_combo.setCurrentIndex(1)
    else:
        main_window.scroll_wheel_mode_combo.setCurrentIndex(0)
    main_window.scroll_wheel_mode_combo.currentTextChanged.connect(
        main_window._on_scroll_wheel_mode_combo_changed
    )
    toolbar.addWidget(main_window.scroll_wheel_mode_combo)
