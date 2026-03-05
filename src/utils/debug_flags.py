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
