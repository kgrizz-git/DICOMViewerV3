# About This File Dialog Update Bug Fix

## Issue Description
The "About this file" dialog was not updating correctly when the user changed the series or instance displayed within the currently focused window (for example, by clicking on a thumbnail in the series navigator or using the arrow keys to navigate between series). It only updated when a completely different subwindow was selected.

## Root Cause
The `_update_about_this_file_dialog` method, which pulls the `current_dataset` and `file_path` for the focused subwindow to update the dialog, was only being called in `_on_slice_changed` (for scrolling slices) and when the layout changed focus to a new window. It was missing from the code paths responsible for:
1. Assigning a new series or instance to the focused subwindow (`assign_series_to_subwindow` in `FileSeriesLoadingCoordinator`).
2. Navigating between series using keyboard shortcuts (`on_series_navigation_requested` in `FileSeriesLoadingCoordinator`).

## Implementation Details
1. **`src/core/file_series_loading_coordinator.py`**:
   - In `assign_series_to_subwindow`: Added `self.update_about_this_file_dialog()` after the crosshairs and UI elements are updated but before the navigator dots are refreshed.
   - In `on_series_navigation_requested`: Added `self.update_about_this_file_dialog()` to both return paths at the end of the navigation logic (one for standard series navigation and one for multi-frame instance navigation).

## Verification
- Click on a thumbnail in the series navigator to load a new series into the active window; the "About this file" dialog (if open) should immediately reflect the new file's information.
- Navigate to the next/previous series using keyboard shortcuts; the dialog should also update.
- Scroll through slices; the dialog should continue to update as before.
