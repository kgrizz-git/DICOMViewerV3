"""
Debug Flags

Central toggle for optional diagnostic print statements.  Set a flag to True
temporarily when investigating a specific problem, then set it back to False
before committing.  All flags default to False so production builds are silent.

Usage example:
    from utils.debug_flags import DEBUG_LAYOUT
    if DEBUG_LAYOUT:
        print(f"[DEBUG-LAYOUT] ...")
"""

# Enables verbose layout / viewport-resize / view-state tracing.
# Affects: multi_window_layout, main_window, subwindow_lifecycle_controller,
# view_state_manager.
DEBUG_LAYOUT: bool = False

# Enables verbose file/series loading tracing (stale-data clearing, etc.).
# Affects: file_series_loading_coordinator.
DEBUG_LOADING: bool = False

# Enables verbose crosshair text-item / scene tracing.
# Affects: crosshair_manager.
DEBUG_CROSSHAIR: bool = False

# Enables series-navigation key/request/lock tracing.
# Affects: series_navigator, image_viewer, file_series_loading_coordinator.
DEBUG_NAV: bool = False

# Enables window/level and rescale tracing when switching series (e.g. cross-study).
# Use when investigating default WL not applied correctly when switching between series from different studies.
# Affects: slice_display_manager.
DEBUG_WL: bool = False

# Enables magnifier-related print logging (cursor magnifier and handle-drag magnifier).
# Affects: image_viewer (_extract_image_region, magnifier paths), magnifier_widget.
DEBUG_MAGNIFIER: bool = False

# Enables MPR volume/build/display/cache tracing.
# Affects: mpr_volume, mpr_builder, mpr_controller.
DEBUG_MPR: bool = False

# Enables verbose tracing of handle drag: handle/group positions, end_relative, and line p1/p2
# at each step of MeasurementHandle.itemChange so you can see exactly what moves and why.
# Affects: measurement_items.py (MeasurementHandle.itemChange).
DEBUG_MEASUREMENT_DRAG: bool = False

# Enables targeted tracing for measurement persistence across series changes.
# Affects: measurement_coordinator.py, measurement_tool.py, slice_display_manager.py,
# and file_series_loading_coordinator.py.
DEBUG_MEASUREMENT_SERIES: bool = False

# Enables intensity projection debugging (enabled/type/count changes, state management).
# Affects: main.py (_on_projection_* methods).
DEBUG_PROJECTION: bool = False

# Enables fusion/overlay offset calculation and user-modification tracing.
# Affects: fusion_controls_widget.py, fusion_handler.py.
DEBUG_OFFSET: bool = False

# Enables spatial alignment and resampling tracing for fusion/overlay.
# Affects: fusion_coordinator.py.
DEBUG_SPATIAL_ALIGNMENT: bool = False

# Enables diagnostic tracing for view state and viewport operations.
# Affects: view_state_manager.py.
DEBUG_DIAG: bool = False

# Enables widget pan/interaction tracing for overlays.
# Affects: overlay_manager.py.
DEBUG_WIDGET_PAN: bool = False

# Enables viewport resize tracing.
# Affects: multi_window_layout.py.
DEBUG_RESIZE: bool = False

# Enables annotation-related tracing.
# Affects: debug_log.py.
DEBUG_ANNOTATION: bool = False

# Enables agent-based diagnostic logging to debug-088dbc.log.
# Set to False before commits/builds; logs are written to working directory.
# Affects: image_viewer, slice_display_manager.
DEBUG_AGENT_LOG: bool = False

# Enables font variant diagnostic logging.
# Affects: debug_log.py.
DEBUG_FONT_VARIANT: bool = False

# Enables font family/variant persistence tracing in config setters and dialogs.
# Affects: overlay_config.py, overlay_settings_dialog.py.
DEBUG_FONT_VARIANT: bool = False

# Enables patient coordinate calculation tracing.
# Affects: dicom_utils.py.
DEBUG_PATIENT_COORDS: bool = False

# Enables generic series loading / navigation / state management debugging.
# Affects: file_series_loading_coordinator.py, slice_display_manager.py.
DEBUG_SERIES: bool = False

# Enables agent hypothesis log writes to debug-088dbc.log file in repo root.
# These are structured JSON logs for specific hypothesis testing (H1-H5).
# Affects: image_viewer.py, slice_display_manager.py.
DEBUG_AGENT_LOG: bool = False
