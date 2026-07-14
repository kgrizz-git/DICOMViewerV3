# Fusion Algorithm Audit Findings

**Date:** 2026-05-22  
**Status:** Audit complete, awaiting review before any code changes  
**Scope:** All five core fusion files: `fusion_handler_io.py`, `fusion_processor.py`, `image_resampler.py`, `fusion_handler.py`, `fusion_coordinator.py`

---

## Executive Summary

The fusion implementation works correctly for **standard axial PET/CT** studies (the primary use case). However, this audit identified **4 confirmed bugs** and **6 lower-severity issues**. The bugs affect non-axial orientations and PET data with per-slice varying RescaleSlope. All findings were verified with reproducible test scripts.

### Quick Verdict

| Scenario | Fusion Correct? |
|----------|----------------|
| Standard axial PET/CT, same FoR | **Yes** |
| Oblique/gantry-tilted PET/CT | **No** (Issues 1, 3) |
| Sagittal/coronal fusion | **No** (Issues 1, 3) |
| PET with per-slice RescaleSlope (3D mode) | **No** (Issue 2) |
| PET with constant RescaleSlope (3D mode) | **Yes** |
| CT overlay (any mode) | **Yes** |

---

## Confirmed Bugs

### BUG 1: SimpleITK Direction Matrix is Transposed (CONFIRMED)

**Severity:** Medium-High  
**File:** `src/core/image_resampler.py`, lines 279-288  
**Affects:** 3D (High Accuracy) mode with non-axial orientations  
**Test script:** `tests/fusion_audit_direction_matrix_test.py`

**Problem:** The direction cosine matrix is constructed with direction vectors as **rows** instead of **columns**. SimpleITK's `SetDirection()` expects a row-major flat list where each **column** is an axis direction vector.

**Current code (wrong for non-axial):**
```python
direction = [
    row_cosines[0], row_cosines[1], row_cosines[2],   # Row 0
    col_cosines[0], col_cosines[1], col_cosines[2],   # Row 1
    slice_cosines[0], slice_cosines[1], slice_cosines[2]  # Row 2
]
```

**Correct code:**
```python
direction = [
    row_cosines[0], col_cosines[0], slice_cosines[0],   # Row 0
    row_cosines[1], col_cosines[1], slice_cosines[1],   # Row 1
    row_cosines[2], col_cosines[2], slice_cosines[2],   # Row 2
]
```

**Test results:**
- Axial: Both produce identity matrix → no error
- Oblique (15°): Peak location shifts 8 slices (z=14 vs z=6), max pixel diff = 421
- Sagittal: Orientation label ILA instead of PIR
- Coronal: Orientation label LSA instead of LIP
- Even when both volumes get the same wrong direction, errors do NOT cancel (max pixel diff = 421 in symmetric test)

**Impact on standard axial PET/CT:** None (identity matrix is its own transpose).

---

### BUG 2: 3D Path Applies Wrong RescaleSlope for Per-Slice Varying Data (CONFIRMED)

**Severity:** Medium  
**File:** `src/core/image_resampler.py`, lines 619-623  
**Affects:** 3D (High Accuracy) mode with PET data that has per-slice RescaleSlope  
**Test script:** `tests/fusion_audit_rescale_timing_test.py`, `tests/fusion_audit_synthetic_2d_vs_3d_test.py`

**Problem:** The 3D resampling path:
1. Resamples raw stored pixel values (before rescale)
2. Applies `RescaleSlope` and `RescaleIntercept` from `overlay_datasets[0]` to all slices

When PET has time-corrected or decay-corrected per-slice slopes (common in clinical PET), this produces wrong values. The code detects inconsistency (lines 596-617) but only logs a warning — never adapts.

**Test results (synthetic variable slope 1.0→1.9):**
```
Slice  2D (correct)  3D (wrong)  Expected  3D Error
    0       500.0       500.0     500.0       0.0
    5       750.0       500.0     750.0     250.0
    9       950.0       500.0     950.0     450.0
```

Up to **50% relative error** with realistic slope variation.

**The 2D (Fast) path handles this correctly** — it applies per-slice rescale before interpolation.

**Impact on standard PET/CT:** Depends on whether the specific PET scanner produces constant or variable RescaleSlope. CT is always safe (constant slope=1).

---

### BUG 3: 2D IPP Offset Ignores Image Orientation (CONFIRMED)

**Severity:** Medium  
**File:** `src/core/fusion_handler_io.py`, lines 173-187  
**Affects:** 2D (Fast) mode with non-axial orientations  
**Test script:** `tests/fusion_audit_offset_and_spacing_test.py`

**Problem:** The translation offset formula uses patient coordinate X/Y components directly:
```python
offset_mm_x = overlay_ipp[0] - base_ipp[0]
offset_mm_y = overlay_ipp[1] - base_ipp[1]
```

This assumes the image plane is aligned with patient X/Y axes. For oblique or non-axial scans, the offset should be **projected onto image row/col directions** using `ImageOrientationPatient`:
```python
delta = overlay_ipp - base_ipp
offset_along_col = dot(delta, row_cosines)
offset_along_row = dot(delta, col_cosines)
```

**Test results:**
- Axial: Both methods agree (pass)
- Oblique (15°): 0.14 px error (minor)
- **Sagittal: 25 px error** — completely wrong

**Impact on standard axial PET/CT:** None (patient X/Y = image plane X/Y for axial).

---

### BUG 4: `_calculate_slice_spacing` Uses Unsorted Data and Wrong Distance Metric (CONFIRMED)

**Severity:** Medium  
**File:** `src/core/image_resampler.py`, lines 702-731  
**Affects:** The `needs_resampling()` decision logic  
**Test script:** `tests/fusion_audit_offset_and_spacing_test.py`

**Problem:** Two issues in `_calculate_slice_spacing()`:

1. **Uses 3D Euclidean distance** instead of projection along slice normal. For oblique scans with in-plane drift, this overestimates spacing by ~1.4%.

2. **Iterates over unsorted datasets** — the method receives `datasets` directly and does not sort them. With typical DICOM loading (unsorted file order), consecutive pair distances are meaningless.

**Test results (unsorted datasets):**
- Sorted Z [0, 3, 6, 9, 12]: avg spacing = **3.00 mm** (correct)
- Unsorted Z [6, 0, 12, 3, 9]: avg spacing = **8.25 mm** (175% error)

This could cause `needs_resampling()` to incorrectly trigger or skip 3D mode.

**Impact on standard axial PET/CT:** Low risk unless datasets happen to be loaded in very random order.

---

## Lower-Severity Issues

### ISSUE 5 (Low-Medium): Spatial Alignment Computed from Slice 0 Only

**File:** `src/gui/fusion_coordinator.py`, lines 825-827

The calculated offset uses `base_datasets[0]` and `overlay_datasets[0]`, which may be arbitrary slices if the list is unsorted. For gantry-tilted CT where IPP X/Y varies per slice, the offset from slice 0 may not represent the correct alignment for all slices.

### ISSUE 6 (Low): Unreachable Code

**File:** `src/core/image_resampler.py`, line 627

Dead `return None` after `return slice_array` on line 625. Harmless but should be cleaned up.

### ISSUE 7 (Low): PIL Float32 Resize

**File:** `src/core/fusion_processor.py`, lines 188-193

PIL's `Image.fromarray` on float32 creates "F" mode, then `resize(BILINEAR)` is called. This works for non-negative PET data but may clip or behave unexpectedly for negative values (e.g., CT HU where intercept shifts values negative). Low risk for typical use.

### ISSUE 8 (Low): Base Image Double-Normalization

**File:** `src/core/fusion_processor.py`, lines 239-251

The base image arrives already windowed to 0-255. The fusion processor then auto-normalizes it to [0,1] from its own min/max. If the windowed image doesn't use the full 0-255 range (narrow window), the re-normalization slightly changes the visual appearance of the base in the fused output vs unfused.

### ISSUE 9 (Info): No SUV Calculation

PET overlay values are raw + rescale, not SUV. This is by design for a viewer but means overlay W/L values don't correspond to clinical SUV units.

### ISSUE 10 (Info): No Fusion Unit Tests

No automated tests exist for any fusion algorithm. All verification was manual or via this audit's test scripts. The following areas need test coverage:
- Direction matrix construction
- Slice matching and Z-interpolation
- IPP offset calculation
- Rescale timing
- 2D vs 3D consistency

---

## Audit Test Scripts

All test scripts are in `tests/` and are non-destructive (read-only, no code modifications):

| Script | What It Tests |
|--------|--------------|
| `fusion_audit_direction_matrix_test.py` | Issue 1: Direction matrix convention with SimpleITK |
| `fusion_audit_rescale_timing_test.py` | Issue 2: Rescale-before vs rescale-after resampling |
| `fusion_audit_offset_and_spacing_test.py` | Issues 3 & 4: IPP offset formula and slice spacing |
| `fusion_audit_synthetic_2d_vs_3d_test.py` | 2D vs 3D path comparison with synthetic data |
| `fusion_audit_dicom_dataset_checker.py` | Real DICOM dataset analysis tool (run with path argument) |

---

## Recommended Fixes (Priority Order)

### Priority 1: Fix Direction Matrix (Bug 1)
- Transpose the direction vector layout in `dicom_series_to_sitk()`
- This is a one-line fix (swap rows/columns in the flat list)
- Fixes 3D resampling for all non-axial orientations

### Priority 2: Fix Rescale Timing (Bug 2)
- Option A: Apply per-slice rescale BEFORE stacking into 3D volume
- Option B: Check for per-slice variation and warn/fall back to 2D
- Option A is more correct; Option B is simpler

### Priority 3: Fix IPP Offset Formula (Bug 3)
- Add IOP projection to `translation_offset_pixels_from_ipps()`
- Requires passing `ImageOrientationPatient` to the function
- Only affects 2D mode (3D handles this via resampling grid)

### Priority 4: Fix Slice Spacing Calculation (Bug 4)
- Sort datasets before calculating consecutive spacings
- Use along-normal projection instead of 3D Euclidean distance
- Consistent with the method used in `dicom_series_to_sitk()`

### Priority 5: Clean Up Dead Code (Issue 6)
- Remove unreachable `return None` at line 627

### Priority 6: Add Unit Tests (Issue 10)
- Adapt the audit test scripts into proper `pytest` unit tests
- Cover direction matrix, rescale timing, offset formula, slice matching

---

## Data-Dependent Verification

The script `tests/fusion_audit_dicom_dataset_checker.py` is ready to analyze real PET/CT datasets. Run it with:

```bash
python tests/fusion_audit_dicom_dataset_checker.py <path_to_dicom_folder>
```

It will report:
- Whether PET has per-slice varying RescaleSlope (Bug 2 trigger)
- Orientation of each series (Bug 1 & 3 trigger)
- Frame of Reference consistency
- Spatial metadata quality

This allows targeted verification: if a user's datasets are standard axial with constant rescale, the confirmed bugs don't affect them.
