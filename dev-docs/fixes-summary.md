# MPR and ROI Fixes Summary

## Overview
This document summarizes the fixes implemented for 4 critical issues in the DICOM Viewer V3 MPR and ROI functionality.

## Issues Fixed

### 1. [P1] MPR Window/Level Persistence Bug

**Problem**: After creating an MPR, clearing it, and creating a new MPR from a different series, the window/level from the first series was incorrectly applied to the second MPR.

**Root Cause**: The window/level controls retained stale values from the previous series, and the MPR display code read from these controls without resetting them.

**Solution**:
- Added `_reset_window_level_for_mpr()` method in `mpr_controller.py`
- Method extracts window/level defaults from the new source dataset using DICOM tags
- Tries presets first, falls back to single window/level or auto-calculation
- Called from `_activate_mpr()` before displaying the first MPR slice
- Ensures each new MPR uses correct window/level from its source series

**Files Modified**: `src/core/mpr_controller.py`

**Testing**: Load two different series with different window/level presets, create MPR from each in sequence, verify each uses correct window/level.

---

### 2. [P0] MPR Rescale Slope/Intercept Not Applied

**Problem**: When the base series for an MPR uses rescaled pixel values (e.g., CT with RescaleSlope/RescaleIntercept to convert to Hounsfield Units), the window/level and pixel values didn't match.

**Root Cause**: The view_state_manager wasn't aware that MPR values were rescaled, so window/level values didn't align with the rescaled pixel array.

**Solution**:
- Enhanced `_reset_window_level_for_mpr()` to set rescale parameters in view_state_manager
- Calls `view_state_manager.set_rescale_parameters(slope, intercept, rescale_type)`
- Sets `use_rescaled_values = True` when rescale parameters exist
- Ensures window/level values from DICOM tags (which are in rescaled units) match the rescaled MPR pixel array

**Files Modified**: `src/core/mpr_controller.py`

**Testing**: Load CT series with rescale parameters, create MPR, verify pixel values are in HU and window/level adjustment works correctly.

---

### 3. [P0] ROI Focus Bug

**Problem**: When changing subwindows or slices, the selected ROI remained selected even when the new view didn't contain that ROI, and the statistics panel wasn't cleared.

**Root Cause**: The ROI selection logic checked if the ROI belonged to ANY slice in the manager, not specifically to the current slice/series being displayed.

**Solution**:
- Modified ROI selection logic in `on_focused_subwindow_changed()` in `subwindow_lifecycle_controller.py`
- Changed from checking if ROI exists in any slice to checking if it exists in the specific current slice
- Constructs ROI key `(study_uid, series_uid, slice_index)` and checks if selected ROI is in that specific slice's ROI list
- Deselects ROI when it doesn't belong to the current slice
- Calls `roi_statistics_panel.clear_statistics()` when deselecting

**Files Modified**: `src/core/subwindow_lifecycle_controller.py`

**Testing**:
1. Create ROI on slice 1, navigate to slice 2 - verify ROI deselects and statistics clear
2. Create ROI in one subwindow, switch to another subwindow - verify ROI deselects and statistics clear
3. Test with multiple subwindows in 2x2 layout

---

### 4. [P0] MPR Creation Failure After Clearing and Reloading

**Problem**: After creating MPRs, clearing them, closing all files, and loading new files, attempting to create a new MPR failed or didn't display.

**Root Cause**: Stale MPR state in `subwindow_data` after file operations, or missing image viewer when trying to activate MPR.

**Solution**:
- Added state validation at the beginning of `open_mpr_dialog()`:
  - Ensures `subwindow_data[idx]` exists (creates if missing)
  - Detects inconsistent state (is_mpr=True but mpr_result=None)
  - Calls `clear_mpr()` to reset stale state
- Added image viewer verification in `on_finished()` callback before calling `_activate_mpr()`:
  - Checks if image viewer exists
  - Shows error dialog if viewer is not ready
  - Prevents crash from trying to activate MPR without a viewer
- Added debug logging in `_activate_mpr()` to track state:
  - Logs whether image viewer exists
  - Logs whether subwindow_data exists
  - Logs result slice count
  - Helps troubleshoot issues in the field

**Files Modified**: `src/core/mpr_controller.py`

**Testing**:
1. Load series, create MPR, clear MPR, close files
2. Load new series
3. Create MPR - should work correctly
4. Repeat with different subwindow indices (0, 1, 2, 3)
5. Test in 2x2 layout with MPRs in multiple windows

---

## Implementation Details

### Code Architecture

**MPR Controller** (`src/core/mpr_controller.py`):
- Orchestrates MPR lifecycle for all subwindows
- Owns per-subwindow dict of active MprResult instances
- Methods: `open_mpr_dialog()`, `clear_mpr()`, `display_mpr_slice()`, `_activate_mpr()`
- New helper: `_reset_window_level_for_mpr()` for window/level initialization

**Subwindow Lifecycle Controller** (`src/core/subwindow_lifecycle_controller.py`):
- Handles subwindow focus changes
- Updates references to current dataset, managers, panels
- Manages ROI selection state across subwindow changes

**View State Manager** (`src/core/view_state_manager.py`):
- Tracks window/level state, rescale parameters, zoom/pan
- Has `use_rescaled_values` flag to indicate if values are in raw or rescaled units
- Method: `set_rescale_parameters(slope, intercept, rescale_type)`

### Key Functions Used

**DICOM Window/Level** (`src/core/dicom_window_level.py`):
- `get_window_level_presets_from_dataset()` - Extracts all presets from DICOM tags
- `get_window_level_from_dataset()` - Extracts single window/level or calculates from pixel range

**DICOM Rescale** (`src/core/dicom_rescale.py`):
- `get_rescale_parameters()` - Extracts RescaleSlope, RescaleIntercept, RescaleType
- Returns tuple: `(slope, intercept, rescale_type)`

**ROI Statistics Panel** (`src/gui/roi_statistics_panel.py`):
- `update_statistics()` - Updates displayed statistics for selected ROI
- `clear_statistics()` - Clears all statistics (called when ROI deselected)

---

## Testing Recommendations

### Automated Testing
1. Add unit tests for `_reset_window_level_for_mpr()`
2. Add tests for ROI selection state changes
3. Add tests for MPR state cleanup

### Manual Testing Scenarios

**Scenario 1: MPR Window/Level Persistence**
1. Load CT lung series (window: center=-600, width=1500)
2. Create MPR in window 1
3. Verify window/level is correct (-600/1500)
4. Clear MPR
5. Load CT brain series (window: center=40, width=80)
6. Create MPR in window 1 again
7. **Verify**: Window/level is 40/80, not -600/1500 ✓

**Scenario 2: MPR Rescale**
1. Load CT series with RescaleSlope=1.0, RescaleIntercept=-1024
2. Verify normal display shows HU values (lung=-800, bone=+300)
3. Create MPR
4. Measure pixel values in MPR
5. **Verify**: MPR shows same HU values as original series ✓
6. Adjust window/level on MPR
7. **Verify**: Adjustment works correctly ✓

**Scenario 3: ROI Focus**
1. Load multi-slice series
2. Create ROI on slice 1
3. Select ROI (statistics appear in right panel)
4. Navigate to slice 2
5. **Verify**: ROI deselected, statistics cleared ✓
6. Load another series in window 2
7. Create ROI in window 2
8. Switch back to window 1
9. **Verify**: Window 2 ROI deselected, statistics cleared ✓

**Scenario 4: MPR After Reload**
1. Load series
2. Create MPR in window 1
3. Verify MPR displays correctly
4. Clear MPR
5. Close all files
6. Load NEW series (different from step 1)
7. Try to create MPR in window 1
8. **Verify**: Dialog opens, MPR builds, MPR displays correctly ✓
9. Repeat with window 2, 3, 4
10. **Verify**: All windows can create MPR ✓

---

## Risk Assessment

### Low Risk Changes
- Issue 1 (Window/level reset): Localized change, only affects MPR initialization
- Issue 3 (ROI selection): Well-isolated logic, only affects selection state

### Medium Risk Changes
- Issue 2 (Rescale handling): Affects display pipeline, but change is conservative
- Issue 4 (State management): Crosses multiple modules, but includes safety checks

### Mitigation Strategies
1. Extensive testing with real DICOM data (CT, MR, etc.)
2. Debug logging added for troubleshooting issues in production
3. Error handling added (e.g., QMessageBox for missing image viewer)
4. Backward compatible (doesn't break existing functionality)
5. Incremental implementation with validation at each step

---

## Performance Impact

**Minimal**: All changes are in code paths that are only executed:
1. When creating/activating MPR (infrequent operation)
2. When changing subwindow focus (infrequent operation)
3. When selecting/deselecting ROI (infrequent operation)

No impact on:
- Normal image display
- Scrolling through slices
- Window/level adjustment during normal viewing

---

## Future Improvements

### Potential Enhancements
1. **Cache management**: Add method to clear cache entries for specific series when closed
2. **Unit tests**: Add comprehensive test suite for MPR and ROI logic
3. **State persistence**: Save MPR settings (orientation, spacing, interpolation) per series
4. **User preferences**: Allow user to set default MPR parameters

### Known Limitations
1. MPR window/level reset only happens for focused window (by design)
2. Cache doesn't track series UIDs for selective clearing (uses natural eviction)
3. Debug logging requires `DEBUG_MPR` flag to be enabled

---

## Conclusion

All 4 issues have been successfully addressed with targeted, minimal changes to the codebase. The fixes are well-documented, include error handling, and maintain backward compatibility. The implementation follows the existing code patterns and architecture of the DICOM Viewer V3 project.
