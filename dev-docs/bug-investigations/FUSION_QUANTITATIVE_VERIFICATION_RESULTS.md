# Fusion Quantitative Verification Results

**Date:** 2026-05-22  
**Status:** Complete  
**Dataset:** `test-DICOM-data/SomeFusion` (3 PET/CT exam pairs, all axial, constant RescaleSlope per series)  
**Audit findings:** [FUSION_ALGORITHM_AUDIT_FINDINGS.md](FUSION_ALGORITHM_AUDIT_FINDINGS.md)  
**Verification plan:** [FUSION_QUANTITATIVE_VERIFICATION_PLAN.md](FUSION_QUANTITATIVE_VERIFICATION_PLAN.md)

---

## Summary

The fusion algorithm produces **correct, well-registered results** on all tested axial PET/CT data. Three independent lines of evidence confirm this:

1. **Blind implementation** (built from DICOM spec only, never reading `src/`) agrees with both 2D and 3D app outputs to float32 precision.
2. **scipy vs SimpleITK** (two independent C/C++ interpolation libraries) agree for all three interpolation methods (linear, nearest, cubic).
3. **Through-plane shift analysis** confirms zero Z-misregistration across all 33 slices in 3 datasets.

The four confirmed bugs from the audit ([FUSION_ALGORITHM_AUDIT_FINDINGS.md](FUSION_ALGORITHM_AUDIT_FINDINGS.md)) are real code issues but are **latent** for standard axial data with constant per-series RescaleSlope — which matches all datasets tested.

---

## Test 1: Quantitative Verification (v2)

**Script:** `tests/fusion_audit_quantitative_verification.py`  
**Output:** `test-DICOM-data/SomeFusion/fusion_audit_results_v2/`

### Method

- Identified 5 high-activity PET slices per pair (15 total across 3 exams)
- Selected 11 CT slices per pair: 10 near PET positions (0-2.5mm away) + 1 between PET positions (requiring Z-interpolation)
- **33 total CT slices tested**
- For each CT slice:
  - **2D path:** Compared `FusionHandler.interpolate_overlay_slice(mode="fast")` output (168×168 PET native dims) against independently computed Z-interpolated ground truth
  - **3D path:** Compared `FusionHandler.interpolate_overlay_slice(mode="high_accuracy")` output (512×512 CT grid) against scipy `map_coordinates` ground truth
  - **Shift analysis:** Tested Z-shifts of ±1.5mm (half-slice) and ±3.0mm (full slice) to detect systematic misregistration

### Results

| Pair | CT Slices | 2D Mean Error | 3D Mean Error | Best Shift (all slices) |
|------|-----------|---------------|---------------|------------------------|
| FoR54113664_CT3_PT102 | 11 (10 near, 1 between) | 0.0000% | 0.0000% | +0.0mm |
| FoR13397883_CT3_PT102 | 11 (10 near, 1 between) | 0.0000% | 0.0000% | +0.0mm |
| FoR68279911_CT3_PT102 | 11 (10 near, 1 between) | 0.0000% | 0.0000% | +0.0mm |

**Data integrity check:** Outputs contain real PET activity values (max 238,163 rescaled counts, 50-97% non-zero pixels). The 0% error is not from comparing zeros.

**Shift sensitivity:** At a half-slice shift (1.5mm), error jumps to ~14,000 absolute (vs ~0.005 at zero shift), confirming the shift analysis is a strong discriminator and no misregistration exists.

### Saved data

Per pair subdirectory (3 directories, 336 files, 112 MB total):

| File pattern | Contents |
|-------------|----------|
| `ct{N}_{type}_2d.npy` | App 2D overlay output (168×168 float32) |
| `ct{N}_{type}_2d_gt.npy` | Independent ground truth for 2D (168×168) |
| `ct{N}_{type}_2d_error.npy` | Absolute error map |
| `ct{N}_{type}_3d.npy` | App 3D overlay output (512×512 float32) |
| `ct{N}_{type}_3d_gt.npy` | Independent ground truth for 3D (512×512) |
| `ct{N}_{type}_3d_error.npy` | Absolute error map |
| `ct{N}_{type}_shift_curve.png` | Through-plane shift vs error plot |
| `ct{N}_{type}_*.png` | Grayscale and error heatmap images |
| `summary.json` | Full per-slice error statistics |

---

## Test 2: Blind Independent Implementation

**Script:** `tests/fusion_blind_verification.py`  
**Method:** A separate AI agent built a complete fusion implementation from scratch using only DICOM specification knowledge, without reading any `src/` code or the verification scripts. It then compared its outputs against the app's saved `.npy` files.

### Results

- **8 CT slices tested** (indices 72, 73, 173, 174, 186, 201, 203, 215)
- **32 comparisons** (8 slices × 2 paths × 2 references each)
- **All 32 PASSED**
- Maximum absolute error: 0.0156 (<0.00002% of signal max)
- All errors consistent with float32 rounding artifacts

### Conclusion

The blind implementation confirms the app's fusion is algorithmically correct — both the 2D Z-interpolation logic and the 3D SimpleITK resampling pipeline produce the expected results when independently reimplemented.

---

## Test 3: Multi-Interpolator Cross-Validation

**Script:** `tests/fusion_audit_interpolator_comparison.py`  
**Method:** Tested the 3D path with all three supported SimpleITK interpolation methods (linear, nearest, cubic/bspline), comparing each against an independent scipy implementation using the corresponding interpolation order.

### Results — App vs scipy (same method)

| Interpolator | Max Diff | % of Max | Verdict |
|-------------|----------|----------|---------|
| Linear (sitk vs scipy order=1) | 0.001 | 0.000007% | **PASS** |
| Nearest (sitk vs scipy order=0) | 0.000 | 0.000000% | **PASS** |
| Cubic (sitk vs scipy order=3) | 0.002 | 0.000015% | **PASS** |

All three methods agree with their independent scipy counterparts to floating-point precision across 5 CT slices.

### Results — Cross-interpolator (expected differences)

| Comparison | Max Diff | % of Max | Notes |
|-----------|----------|----------|-------|
| Linear vs Nearest | ~2,500–3,100 | 18–23% | Expected: fundamentally different algorithms |
| Linear vs Cubic | ~530–730 | 4–5% | Expected: cubic adds Gibbs-like ringing |
| Nearest vs Cubic | ~2,600–2,800 | 19–20% | Expected: most different pair |

These cross-method differences are large, expected, and healthy — confirming each interpolator is producing its mathematically distinct result correctly.

---

## Confirmed bugs — deferred to next phase

The following bugs from the audit are confirmed in code but do **not** affect the tested axial data. They will be fixed next, with this verification serving as the pre-fix baseline for regression testing:

1. **Direction matrix transposed** in `image_resampler.py` `dicom_series_to_sitk()` — affects oblique/sagittal/coronal 3D fusion
2. **3D path applies RescaleSlope from slice 0** to entire volume — wrong when slope varies per slice (some PET)
3. **2D IPP-to-pixel offset ignores ImageOrientationPatient** — affects oblique 2D mode
4. **`_calculate_slice_spacing` uses unsorted data and wrong distance metric** — affects series with non-uniform or misordered slices
5. **Dead `return None`** at line 627 of `image_resampler.py`

Details and test scripts: [FUSION_ALGORITHM_AUDIT_FINDINGS.md](FUSION_ALGORITHM_AUDIT_FINDINGS.md), `tests/fusion_audit_*.py`

---

## Scripts index

| Script | Purpose |
|--------|---------|
| `tests/fusion_audit_quantitative_verification.py` | Main quantitative verification (v2): 2D+3D vs ground truth, shift analysis |
| `tests/fusion_blind_verification.py` | Blind independent implementation comparison |
| `tests/fusion_audit_interpolator_comparison.py` | Multi-interpolator cross-validation (linear, nearest, cubic) |
| `tests/fusion_audit_direction_matrix_test.py` | Bug 1: direction matrix transposition test |
| `tests/fusion_audit_rescale_timing_test.py` | Bug 2: per-slice rescale timing test |
| `tests/fusion_audit_offset_and_spacing_test.py` | Bugs 3+4: IPP offset and slice spacing tests |
| `tests/fusion_audit_synthetic_2d_vs_3d_test.py` | Synthetic 2D vs 3D path comparison |
| `tests/fusion_audit_dicom_dataset_checker.py` | DICOM dataset property scanner |
