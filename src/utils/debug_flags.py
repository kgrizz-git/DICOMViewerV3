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
DEBUG_MPR: bool = True

# Enables verbose tracing of handle drag: handle/group positions, end_relative, and line p1/p2
# at each step of MeasurementHandle.itemChange so you can see exactly what moves and why.
# Affects: measurement_items.py (MeasurementHandle.itemChange).
DEBUG_MEASUREMENT_DRAG: bool = False
