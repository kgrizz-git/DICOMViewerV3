# Privacy Mode Window Level Bug Fix

## Issue Description
**[P0] Bug:** Opening a study with privacy mode off, then toggling privacy mode on/off caused the window width and center to change to very different values, making the image appear nearly solid black. It appeared to apply the W/L values from a background/unfocused series.

## Root Cause Analysis
The issue originated in `PrivacyController.refresh_overlays`. When privacy mode is toggled, the controller iterates over all active subwindows and calls `SliceDisplayManager.display_slice` on each one to force the overlays to refresh with the new privacy state.

`SliceDisplayManager.display_slice` has several keyword arguments, including:
- `preserve_view_override`: Defines if zoom/pan/inversion should be preserved.
- `update_controls`: Defines whether the global Window/Level (W/L) controls should be synchronized to match the displayed slice's W/L. The default value is `True`.

Because `refresh_overlays` called `display_slice` without explicitly setting `update_controls=False` or `preserve_view_override=True`, the method used its defaults. For every subwindow (including unfocused, background subwindows):
1. `preserve_view` was eventually computed as `True` since it was the same series, avoiding a zoom/pan reset.
2. `update_controls` remained `True`. 

As a result, each background window would sequentially push its W/L values to the **global** `WindowLevelControls` widget. Even though `set_window_level` blocks signals, the global UI ended up reflecting the W/L of the *last* subwindow processed rather than the focused subwindow. If the user subsequently interacted with the UI, or if another interaction synchronized state from the W/L controls, the incorrect W/L was applied to the focused subwindow, often rendering it completely black or highly distorted.

## Resolution
The fix was to explicitly pass `preserve_view_override=True` and `update_controls=False` to the `display_slice` call inside `PrivacyController.refresh_overlays`. This prevents background rendering from clobbering the global shared W/L UI controls and correctly isolates the overlay refresh from W/L/zoom state changes.

**File modified:** `src/core/privacy_controller.py`

```python
# Before
slice_display_manager.display_slice(
    slice_display_manager.current_dataset,
    slice_display_manager.current_studies,
    slice_display_manager.current_study_uid,
    slice_display_manager.current_series_uid,
    slice_display_manager.current_slice_index,
    update_metadata=(idx == focused_idx),
)

# After
slice_display_manager.display_slice(
    slice_display_manager.current_dataset,
    slice_display_manager.current_studies,
    slice_display_manager.current_study_uid,
    slice_display_manager.current_series_uid,
    slice_display_manager.current_slice_index,
    preserve_view_override=True,
    update_controls=False,
    update_metadata=(idx == focused_idx),
)
```

This pattern of isolating `update_controls=False` is consistent with how background rendering is safely performed in `SubwindowLifecycleController.redisplay_subwindow_slice` and `SliceSyncCoordinator._update_target`.
