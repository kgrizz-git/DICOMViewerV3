# Fusion Quantitative Verification Plan

**Date:** 2026-05-22
**Status:** Plan — awaiting approval before implementation
**Related:** [FUSION_ALGORITHM_AUDIT_FINDINGS.md](FUSION_ALGORITHM_AUDIT_FINDINGS.md)

---

## Goal

Quantitatively verify the correctness of the 2D and 3D fusion overlay pipelines by comparing the rescaled overlay values produced by each path against ground-truth values computed directly from the original PET DICOM pixel data and spatial metadata. Specifically:

- Confirm in-plane (X/Y) spatial accuracy of the resampled overlay
- Confirm through-plane (Z) slice matching accuracy (the direction of most suspicion)
- Measure absolute and relative pixel-value error at known high-activity locations
- Detect any systematic through-plane shift by testing what the error pattern would look like if the overlay were shifted by +/- 0.5 or 1.0 slice increments

---

## Data

From `test-DICOM-data\SomeFusion`:

| Series | Modality | Slices | Matrix | Pixel Spacing | Slice Spacing | RescaleSlope |
|--------|----------|--------|--------|--------------|--------------|-------------|
| S3 (×3 studies) | CT | 389 | 512×512 | 0.977 mm | 2.5 mm | 1.0 (constant) |
| S102 (×3 studies) | PT | 324 | 168×168 | 4.073 mm | 3.0 mm | varies by series (7.4–10.6), constant within each |
| S103 (×2), S105 (×1) | PT | 324 | 168×168 | 4.073 mm | 3.0 mm | varies by series (0.4–0.7), constant within each |

Three Frame-of-Reference groups, each with one CT + two or more PT series. All axial, all with matching FoR UIDs.

Key geometry differences that the fusion must handle:
- In-plane: CT has 512×512 at ~1 mm; PET has 168×168 at ~4 mm (~4.17:1 ratio)
- Through-plane: CT 2.5 mm spacing, PET 3.0 mm spacing — slices will rarely align exactly; interpolation is needed
- FOV: PET FOV is ~684 mm (168 × 4.073), CT FOV is ~500 mm (512 × 0.977) — PET covers a wider physical area

---

## Approach

### Step 1: Load data, identify high-activity PET slices

For each FoR-matched CT+PT pair:
1. Load all PT datasets with full pixel data
2. Sort by SliceLocation
3. Compute per-slice summary: max pixel value, mean pixel value, and 99th percentile (rescaled)
4. Pick 5 representative slices: the slice with the global max, plus 4 others spread across the volume where the 99th percentile is in the top 20% (avoiding adjacent slices so we sample different body regions)

### Step 2: Compute ground-truth overlay at CT slice positions

For each of the 5 selected PT slices and several neighboring CT slices:

**Ground-truth construction** (independent of the app fusion code):
1. For a given CT slice location `z_ct`, find the two bracketing PT slices (`z_pt_below`, `z_pt_above`) and compute the exact interpolation weight: `w = (z_ct - z_below) / (z_above - z_below)`
2. Load the raw pixel arrays for both PT slices
3. Apply the series RescaleSlope and RescaleIntercept to each
4. Linearly interpolate: `ground_truth_pt = pt_below * (1 - w) + pt_above * w`
5. Resample in-plane from PET grid (168×168 at 4.073 mm) to CT grid (512×512 at 0.977 mm) using `scipy.ndimage.map_coordinates` (or similar) with the correct IPP-based coordinate mapping:
   - For each CT pixel `(row, col)`, compute patient XY using CT IPP + CT pixel spacing
   - Convert to PET pixel coordinates using PET IPP + PET pixel spacing
   - Sample the interpolated PT array at those coordinates

This gives us the rescaled overlay value that should appear at every CT pixel if fusion is working correctly.

### Step 3: Run the app's 2D and 3D fusion overlay extraction

For the same CT slices, call the actual fusion code paths:

**3D path:**
- Instantiate `FusionHandler` with `resampling_mode='high_accuracy'`
- Call `interpolate_overlay_slice(ct_slice_idx, ct_datasets, pt_datasets)`
- The returned array is the resampled, rescaled overlay at the CT grid

**2D path:**
- Instantiate `FusionHandler` with `resampling_mode='fast'`
- Call `interpolate_overlay_slice(ct_slice_idx, ct_datasets, pt_datasets)`
- The returned array is raw PET size (168×168); to compare with ground truth, apply the same in-plane scaling and translation as `FusionProcessor.create_fusion_image` would (using pixel spacings and IPP offset)

### Step 4: Compute error maps

For each CT test slice:

1. **Absolute error** = `|fusion_result - ground_truth|` (per pixel, in rescaled PT units)
2. **Relative error** = `absolute_error / (|ground_truth| + epsilon)` where epsilon avoids division by zero
3. Aggregate statistics: max, mean, 95th and 99th percentile of absolute and relative error across the high-activity region (pixels where ground truth > 10% of the ground truth max on that slice)
4. Save as numpy arrays: `ground_truth.npy`, `fusion_3d.npy`, `fusion_2d.npy`, `error_3d.npy`, `error_2d.npy`

### Step 5: Through-plane shift analysis

The key question: is the overlay shifted by a fraction of a slice?

For each test CT slice:
1. Also compute ground-truth using a CT location shifted by **−1, −0.5, +0.5, +1 PET slice increments** (±3.0 mm and ±1.5 mm in Z)
2. Compute the same error statistics against the actual fusion result
3. If the error is *lower* at a shifted position than at the nominal position, this indicates a systematic through-plane misregistration
4. Report which shift (if any) minimizes error, and by how much

Rationale: if the 3D resampling has an off-by-one in the sorted-vs-unsorted slice index mapping, the overlay will be displaced by exactly 1 CT slice spacing (2.5 mm) or 1 PET slice spacing (3.0 mm).

### Step 6: Generate visual outputs

For each test slice, save:
1. **Ground truth overlay** (grayscale PNG, rescaled to 0–255)
2. **3D fusion overlay** (grayscale PNG)
3. **2D fusion overlay** (grayscale PNG after resize to CT grid)
4. **Absolute error heatmap** (colormap PNG, same scale for 2D and 3D)
5. **Through-plane shift error curve** (matplotlib plot: x = shift in mm, y = mean error in high-activity region)

All saved to `test-DICOM-data/SomeFusion/fusion_audit_results/`.

---

## Test matrix

For each of the 3 FoR groups, pick one PT series (the S102 variant with the largest RescaleSlope for maximum dynamic range). That gives 3 CT+PT pairs × 5 slices × 2 modes (2D, 3D) = **30 comparisons**, plus the shift analysis on each.

If the first pair looks clean, the other two are a quick sanity check. If the first pair shows problems, we investigate all three carefully.

---

## What constitutes a pass

| Metric | Acceptable | Concerning |
|--------|-----------|-----------|
| Mean absolute error (high-activity region) | < 2% of rescaled max | > 5% |
| Max absolute error | < 5% of rescaled max | > 10% |
| Through-plane shift that minimizes error | 0 mm (nominal) | Non-zero shift |
| 2D vs 3D agreement | < 3% mean difference | > 5% |

---

## Implementation notes

- The test script imports `FusionHandler`, `ImageResampler`, `FusionProcessor`, and `DICOMProcessor` from `src/` but does NOT use any Qt/GUI code
- All DICOM loading uses `pydicom.dcmread` with full pixel data
- Ground-truth resampling uses `scipy.ndimage.map_coordinates` with `order=1` (bilinear) for direct comparison with the app's bilinear/linear interpolation
- The script should run in under 5 minutes for all 3 pairs (most time is the 3D SimpleITK resample, which is cached per series pair)
- Output numpy arrays allow further post-hoc analysis without re-running

---

## Script location

`tests/fusion_audit_quantitative_verification.py`

Usage:
```bash
python tests/fusion_audit_quantitative_verification.py "test-DICOM-data/SomeFusion"
```

---

## Improvements over the basic plan

1. **Ground truth is independent of app code** — uses scipy for in-plane resampling and explicit Z-interpolation, not the app's FusionHandler/ImageResampler. This means bugs in the app code cannot contaminate the reference.
2. **Shift analysis** — directly tests the through-plane hypothesis rather than just measuring error; if a shift is detected, we know immediately whether it is a half-slice or full-slice offset and in which direction.
3. **High-activity masking** — error metrics focus on regions where PET signal is meaningful, avoiding the vast low-count background from diluting the statistics.
4. **Both 2D and 3D tested** — if one path is wrong and the other is right, we can isolate the bug to the specific code path.
5. **Multiple FoR groups** — different RescaleSlope values and slightly different IPP origins test robustness across the dataset.
