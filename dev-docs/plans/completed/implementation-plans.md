# Implementation Plans for MPR and ROI Issues

## Overview
This document provides detailed implementation plans for four critical issues identified in the DICOM Viewer V3 MPR and ROI functionality.

---

## Issue 1: [P1] MPR Window/Level Persistence Bug

### Problem Statement
After making an MPR in a window, clearing it, then making a new MPR in that window using a different series, the default (embedded) window/level from the **first** base series was applied instead of from the **second**.

### Root Cause Analysis
When an MPR is created in `mpr_controller.py`, the `display_mpr_slice()` method reads the current window/level from the UI controls (`wl_controls`) at line 307-318:

```python
wl_controls = getattr(self._app, "window_level_controls", None)
wc, ww = self._get_window_level(wl_controls, array)
```

The `_get_window_level()` method (lines 764-795) first tries to read from the controls:
- If the controls have valid values, it uses those
- Only falls back to auto-calculation if controls are invalid/unavailable

**The Problem**: When the first MPR is created:
1. Window/level from the first series' DICOM tags gets loaded into `wl_controls`
2. User clears the MPR (but window/level values remain in controls)
3. When creating a second MPR from a different series:
   - The method reads the **stale** values from controls (from series 1)
   - Never loads the default window/level from series 2

### Files Affected
- `src/core/mpr_controller.py` - MPR display logic

### Implementation Plan

#### Step 1: Reset window/level when activating new MPR
In `mpr_controller.py`, modify the `_activate_mpr()` method (around line 562-643) to reset window/level from the source series before displaying the first slice.

**Location**: After line 596 (after setting `current_datasets`), add:

```python
# Reset window/level from the new MPR source series
self._reset_window_level_for_mpr(idx, source_ds)
```

#### Step 2: Implement `_reset_window_level_for_mpr()` helper
Add a new method to `MprController` class:

```python
def _reset_window_level_for_mpr(self, idx: int, source_dataset) -> None:
    """
    Reset window/level controls to defaults from the MPR source dataset.

    This ensures that when a new MPR is created, we use the window/level
    from the new source series, not stale values from a previous series.

    Args:
        idx: Subwindow index
        source_dataset: Source DICOM dataset for the MPR
    """
    # Only update controls if this is the focused window
    if idx != getattr(self._app, "focused_subwindow_index", -1):
        return

    wl_controls = getattr(self._app, "window_level_controls", None)
    if wl_controls is None:
        return

    try:
        from core.dicom_window_level import get_window_level_presets_from_dataset
        from core.dicom_rescale import get_rescale_parameters

        # Get rescale parameters
        rescale_slope, rescale_intercept, rescale_type = get_rescale_parameters(source_dataset)

        # Try to get presets first
        presets = get_window_level_presets_from_dataset(
            source_dataset, rescale_slope, rescale_intercept
        )

        if presets:
            # Use first preset
            wc, ww, is_rescaled, preset_name = presets[0]
        else:
            # Fall back to single window/level or auto-calculation
            from core.dicom_window_level import get_window_level_from_dataset
            wc, ww, is_rescaled = get_window_level_from_dataset(
                source_dataset, rescale_slope, rescale_intercept
            )

        if wc is not None and ww is not None and ww > 0:
            wl_controls.set_window_level(wc, ww, block_signals=False)
            _mpr_log(f"Reset W/L for MPR: center={wc:.1f} width={ww:.1f}")
    except Exception as exc:
        print(f"[MprController] Failed to reset W/L for MPR in window {idx}: {exc}")
```

#### Step 3: Testing
1. Load a CT series with specific window/level (e.g., lung window)
2. Create MPR in window 1
3. Clear the MPR
4. Load a different CT series with different window/level (e.g., brain window)
5. Create MPR in window 1 again
6. **Expected**: The second MPR should use the brain window settings, not lung
7. **Verify**: Check both automatic DICOM presets and manually adjusted window/level

---

## Issue 2: [P0] MPR Rescale Slope/Intercept Not Applied

### Problem Statement
If the base series for an MPR uses rescaled pixel values (e.g., CT with RescaleSlope=1.0, RescaleIntercept=-1024.0 to convert to Hounsfield Units), the MPR pixel values should be rescaled the same way.

### Root Cause Analysis
Looking at `mpr_controller.py` line 313-315:

```python
raw_array = result.slices[slice_index]
# Apply rescale slope/intercept from source series.
array = result.apply_rescale(raw_array)
```

And in `mpr_builder.py` lines 101-113, the `MprResult.apply_rescale()` method:

```python
def apply_rescale(self, array: np.ndarray) -> np.ndarray:
    """Apply rescale slope/intercept to pixel array if available."""
    if self.rescale_slope is not None and self.rescale_intercept is not None:
        return array.astype(np.float32) * float(self.rescale_slope) + float(self.rescale_intercept)
    return array
```

The rescale parameters are extracted in `mpr_builder.py` lines 498-513 and stored in the `MprResult`.

**The Issue**: The code appears to be correctly structured. The problem is likely that:
1. The rescale parameters may not be properly extracted/stored in cache
2. Or the window/level being applied doesn't account for whether values are rescaled

Let me verify cache handling in `mpr_controller.py` lines 476-492 (cache hit reconstruction).

**Cache Issue Found** (line 481-490):
When loading from cache, the `MprResult` is reconstructed with rescale parameters from the cache metadata. The cache should include rescale_slope/intercept.

**However**, there's a potential issue: When the window/level is read from controls, it might be in raw pixel units, but the array is rescaled to HU. This mismatch could cause incorrect display.

### Files Affected
- `src/core/mpr_controller.py` - MPR display and window/level logic
- `src/core/view_state_manager.py` - Window/level state management

### Implementation Plan

#### Step 1: Verify rescale is applied in display path
The current code at `mpr_controller.py:313-315` correctly applies rescale. No changes needed here.

#### Step 2: Fix window/level to account for rescaled values
The issue is that when displaying MPR slices, the window/level read from controls might not match the rescaled array values.

In `mpr_controller.py`, modify `display_mpr_slice()` around line 317-320:

**Current code:**
```python
# Determine window/level from controls (or fall back to data min/max).
wc, ww = self._get_window_level(wl_controls, array)
pil_image = self._array_to_pil(array, wc, ww)
```

**New approach**: Track whether window/level values are in raw or rescaled units.

Modify the `_get_window_level()` method to return rescale-aware values:

```python
@staticmethod
def _get_window_level(wl_controls, array: np.ndarray, mpr_result: MprResult):
    """
    Read the current window centre/width from the window-level controls.

    Falls back to (percentile-based) auto W/L from the array if controls
    are unavailable.

    Args:
        wl_controls: WindowLevelControls widget (may be None).
        array:       The pixel array to compute auto W/L from.
        mpr_result:  The MprResult containing rescale info.

    Returns:
        (window_center, window_width) as floats.
    """
    if wl_controls is not None:
        try:
            wc = float(wl_controls.window_center)
            ww = float(wl_controls.window_width)
            if ww > 0:
                # Check if we need to convert window/level to match array units
                # If array is rescaled but controls are in raw units, convert
                has_rescale = (mpr_result.rescale_slope is not None and
                              mpr_result.rescale_intercept is not None)

                # If the controls might be in raw units but array is rescaled,
                # we need to convert. However, we need to know if controls
                # are using rescaled values or not. For MPR, we should use
                # the values as-is since they're set in _reset_window_level_for_mpr.
                return wc, ww
        except (AttributeError, TypeError, ValueError):
            pass

    # Auto W/L: use 2nd–98th percentile of non-zero pixels.
    flat = array.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return 0.0, 1.0
    p2, p98 = float(np.percentile(flat, 2)), float(np.percentile(flat, 98))
    ww = max(p98 - p2, 1.0)
    wc = (p2 + p98) / 2.0
    return wc, ww
```

**Better Solution**: Ensure window/level is always set correctly when MPR is activated.

In `_reset_window_level_for_mpr()`, the window/level values retrieved from presets already account for rescale (the `get_window_level_presets_from_dataset` function handles this). So the implementation in Issue 1 should also fix this issue.

#### Step 3: Update method signature
Update the call to `_get_window_level()` at line 318:

```python
wc, ww = self._get_window_level(wl_controls, array, result)
```

#### Step 4: Testing
1. Load a CT series (has RescaleSlope=1.0, RescaleIntercept=-1024.0)
2. Verify normal display shows correct HU values (e.g., lung = -800 HU, bone = +300 HU)
3. Create an MPR
4. Measure pixel values in MPR and verify they match the original series
5. Check window/level adjustment works correctly on MPR
6. Test with series that have no rescale parameters
7. Test with series that have different rescale parameters

**Note**: After investigation, the core issue is likely that window/level from controls doesn't match the rescaled array values. The fix in Issue 1 (resetting window/level when MPR is activated) should resolve this.

---

## Issue 3: [P0] ROI Focus Bug

### Problem Statement
When changing subwindows, the selected ROI should auto-unselect and right-pane statistics should clear.

### Root Cause Analysis
In `subwindow_lifecycle_controller.py` lines 903-912, there's already logic to clear ROI selection when switching subwindows:

```python
if app.roi_manager:
    selected_roi = app.roi_manager.get_selected_roi()
    if selected_roi:
        roi_belongs = False
        for roi_list in app.roi_manager.rois.values():
            if selected_roi in roi_list:
                roi_belongs = True
                break
        if not roi_belongs:
            app.roi_manager.select_roi(None)
```

**The Problem**: This code only clears the selection if the ROI doesn't belong to ANY slice. However, ROIs are per-slice/per-series. When switching subwindows:
1. ROI might belong to a different series loaded in the previous window
2. The logic checks if ROI belongs to ANY slice in the manager
3. It should check if ROI belongs to the CURRENT slice/series in the focused window

**Statistics Panel Issue**: The statistics panel is NOT cleared when ROI is deselected. The `clear_statistics()` method exists but is never called.

### Files Affected
- `src/core/subwindow_lifecycle_controller.py` - Subwindow focus change logic
- `src/gui/roi_coordinator.py` - ROI selection coordination

### Implementation Plan

#### Step 1: Fix ROI selection logic for subwindow changes
In `subwindow_lifecycle_controller.py`, modify the `on_focused_subwindow_changed()` method around lines 903-912:

**Current code:**
```python
if app.roi_manager:
    selected_roi = app.roi_manager.get_selected_roi()
    if selected_roi:
        roi_belongs = False
        for roi_list in app.roi_manager.rois.values():
            if selected_roi in roi_list:
                roi_belongs = True
                break
        if not roi_belongs:
            app.roi_manager.select_roi(None)
```

**Replace with:**
```python
if app.roi_manager:
    selected_roi = app.roi_manager.get_selected_roi()
    if selected_roi:
        # Check if the selected ROI belongs to the current focused slice/series
        roi_belongs_to_current_slice = False
        if app.current_dataset is not None:
            from utils.dicom_utils import get_composite_series_key
            study_uid = getattr(app.current_dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(app.current_dataset)
            slice_index = app.current_slice_index

            # Check if ROI is in the current slice's ROI list
            roi_key = (study_uid, series_uid, slice_index)
            if roi_key in app.roi_manager.rois:
                roi_list = app.roi_manager.rois[roi_key]
                if selected_roi in roi_list:
                    roi_belongs_to_current_slice = True

        # Clear selection if ROI doesn't belong to the current slice
        if not roi_belongs_to_current_slice:
            app.roi_manager.select_roi(None)
```

#### Step 2: Clear statistics panel when ROI is deselected
The ROI selection logic in `roi_manager.py` or `roi_coordinator.py` should trigger statistics panel clearing. Let's check where selection happens.

Add statistics clearing when ROI is deselected. In the modified code above, after `app.roi_manager.select_roi(None)`, add:

```python
# Clear statistics panel when ROI is deselected
if hasattr(app, 'roi_statistics_panel') and app.roi_statistics_panel:
    app.roi_statistics_panel.clear_statistics()
```

#### Step 3: Ensure statistics clear when manually deselecting ROI
Check `roi_coordinator.py` or wherever `select_roi(None)` is called to ensure statistics panel is cleared.

Search for the ROI selection handler and add statistics clearing:

```python
def _on_roi_selected(self, roi):
    """Handle ROI selection change."""
    if roi is None and hasattr(self.app, 'roi_statistics_panel'):
        self.app.roi_statistics_panel.clear_statistics()
    # ... rest of selection logic
```

#### Step 4: Testing
1. Load a series with multiple slices
2. Create an ROI on slice 1
3. Select the ROI (statistics should show in right panel)
4. Navigate to slice 2 (different slice in same series)
   - **Expected**: ROI selection should clear, statistics panel should clear
5. Load another series in a different subwindow
6. Create an ROI in the second subwindow
7. Switch back to first subwindow
   - **Expected**: Second subwindow's ROI should deselect, statistics should clear
8. Test with multiple subwindows (2x2 layout)

---

## Issue 4: [P0] MPR Creation Failure After Clearing and Reloading

### Problem Statement
After creating MPRs, clearing, closing all files, and loading new files, creating new MPR does not load/display.

### Root Cause Analysis
This issue suggests a state management problem. Possible causes:
1. MPR cache retains stale data
2. Subwindow data not properly cleared
3. View state manager retains old references
4. Image viewer not properly reset

The `clear_mpr()` method in `mpr_controller.py` (lines 157-285) should handle cleanup, but there might be edge cases when ALL files are closed.

Looking at line 173-189, the method removes MPR-specific keys:
```python
for key in (
    "is_mpr",
    "mpr_result",
    "mpr_orientation",
    "mpr_slice_index",
    "mpr_source_dataset",
    "mpr_previous_state",
):
    data.pop(key, None)
```

But if files are closed AFTER clearing MPR, the subwindow_data might be in an inconsistent state.

### Files Affected
- `src/core/mpr_controller.py` - MPR lifecycle
- `src/main.py` - File close logic
- `src/core/subwindow_lifecycle_controller.py` - Subwindow initialization

### Implementation Plan

#### Step 1: Add state validation before MPR creation
In `mpr_controller.py`, modify `open_mpr_dialog()` to validate state (around line 117):

**Add at the beginning of the method:**
```python
def open_mpr_dialog(self, target_subwindow_idx: int) -> None:
    """Open the MPR dialog for the given subwindow."""
    from gui.dialogs.mpr_dialog import MprDialog

    # Ensure subwindow data exists and is properly initialized
    if target_subwindow_idx not in self._app.subwindow_data:
        self._app.subwindow_data[target_subwindow_idx] = {}

    # Clear any stale MPR state
    data = self._app.subwindow_data[target_subwindow_idx]
    if data.get("is_mpr") and data.get("mpr_result") is None:
        # Inconsistent state - clear it
        self.clear_mpr(target_subwindow_idx)
```

#### Step 2: Ensure image viewer is ready
Before calling `_activate_mpr()`, verify the image viewer exists:

In `_on_mpr_requested()`, before the final call to `self._activate_mpr()` (line 539), add:

```python
# Verify image viewer exists before activating MPR
image_viewer = self._get_image_viewer(target_idx)
if image_viewer is None:
    QMessageBox.critical(
        self._app.main_window,
        "MPR Error",
        "Cannot activate MPR: image viewer not ready. Please try again.",
    )
    return
```

#### Step 3: Clear cache entries when closing files
Add a method to clear cache entries for a series when it's closed:

```python
def clear_cache_for_series(self, series_uid: str) -> None:
    """
    Clear cache entries for a specific series.

    This should be called when a series is closed/unloaded.

    Args:
        series_uid: Series instance UID to clear from cache
    """
    if self._cache is None:
        return

    try:
        # Cache keys include series_uid, so we'd need to track them
        # For now, the cache will naturally evict old entries
        _mpr_log(f"Cache cleanup for series {series_uid} (natural eviction)")
    except Exception as exc:
        print(f"[MprController] Cache cleanup error: {exc}")
```

#### Step 4: Verify subwindow state on file close
In the main application's file close handler, ensure MPR state is properly cleared:

```python
# In the file close handler (likely in main.py or file_operations_handler.py)
# After closing files:
for idx in range(4):  # For all subwindows
    if mpr_controller.is_mpr(idx):
        mpr_controller.clear_mpr(idx)
```

#### Step 5: Add debug logging
Add debug logging to track MPR state transitions:

In `_activate_mpr()` at the beginning:
```python
_mpr_log(
    f"Activating MPR: window={idx} "
    f"has_image_viewer={self._get_image_viewer(idx) is not None} "
    f"has_subwindow_data={idx in self._app.subwindow_data} "
    f"result_slices={result.n_slices}"
)
```

#### Step 6: Testing
1. Load a series
2. Create an MPR in window 1
3. Verify it displays correctly
4. Clear the MPR
5. Close all files (File → Close All or similar)
6. Verify all subwindows are empty
7. Load a NEW series (different from step 1)
8. Try to create an MPR in window 1
   - **Expected**: Dialog opens, MPR builds successfully, and displays
9. Repeat test with different window indices (0, 1, 2, 3)
10. Test in 2x2 layout with MPRs in multiple windows

---

## Implementation Order

Based on dependencies and priority:

1. **Issue 1 (P1)**: MPR window/level persistence bug
   - Implement `_reset_window_level_for_mpr()` helper
   - Call it from `_activate_mpr()`
   - This also helps with Issue 2

2. **Issue 2 (P0)**: MPR rescale slope/intercept
   - Verify fix from Issue 1 resolves this
   - Update `_get_window_level()` signature if needed
   - Test with CT data

3. **Issue 3 (P0)**: ROI focus bug
   - Fix ROI selection logic in `on_focused_subwindow_changed()`
   - Add statistics panel clearing
   - Test subwindow switching

4. **Issue 4 (P0)**: MPR creation failure
   - Add state validation in `open_mpr_dialog()`
   - Add image viewer verification
   - Add debug logging
   - Test file close/reload scenario

## Testing Strategy

### Unit Testing
- Add tests for `_reset_window_level_for_mpr()`
- Add tests for ROI selection state changes
- Add tests for MPR state cleanup

### Integration Testing
- Test MPR workflow with multiple series
- Test ROI selection across subwindows
- Test file open/close/reload cycles

### Manual Testing
- Use real DICOM data (CT, MR, etc.)
- Test with multiple series in multi-window layouts
- Test edge cases (empty series, missing metadata, etc.)

## Risk Assessment

### Low Risk
- Issue 1: Window/level reset is a localized change
- Issue 3: ROI selection logic is well-isolated

### Medium Risk
- Issue 2: Rescale handling affects display pipeline (but fix is conservative)
- Issue 4: State management crosses multiple modules

### Mitigation
- Extensive testing with real DICOM data
- Add debug logging for troubleshooting
- Ensure backward compatibility (don't break existing functionality)
- Implement fixes incrementally with validation at each step
