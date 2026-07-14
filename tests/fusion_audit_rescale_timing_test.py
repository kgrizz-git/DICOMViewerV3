"""
Fusion Audit: Verify rescale-before vs rescale-after resampling behavior.

Tests whether applying RescaleSlope/Intercept before vs after 3D interpolation
produces different results, especially when rescale parameters vary per slice.

This script does NOT modify any production code. It only prints diagnostic output.

Usage: python tests/fusion_audit_rescale_timing_test.py
"""

import numpy as np

try:
    import SimpleITK as sitk
except ImportError:
    print("ERROR: SimpleITK not available. Cannot run this test.")
    raise SystemExit(1) from None


def test_constant_rescale():
    """When rescale is constant across slices, order doesn't matter (linear operation)."""
    print("=" * 70)
    print("TEST 1: Constant rescale parameters (slope=2, intercept=100)")
    print("=" * 70)

    slope = 2.0
    intercept = 100.0
    num_slices = 10

    # Create raw pixel data volume
    raw_data = np.random.rand(num_slices, 32, 32).astype(np.float32) * 1000

    # Method A: Rescale AFTER resampling (current 3D code path)
    volume_raw = sitk.GetImageFromArray(raw_data)
    volume_raw.SetSpacing([2.0, 2.0, 3.0])
    volume_raw.SetOrigin([0.0, 0.0, 0.0])

    ref = sitk.Image(32, 32, num_slices, sitk.sitkFloat32)
    ref.SetSpacing([2.0, 2.0, 3.0])
    ref.SetOrigin([0.0, 0.0, 0.0])

    resampled_raw = sitk.Resample(volume_raw, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_after = sitk.GetArrayFromImage(resampled_raw) * slope + intercept

    # Method B: Rescale BEFORE resampling (correct for variable slope)
    calibrated_data = raw_data * slope + intercept
    volume_cal = sitk.GetImageFromArray(calibrated_data)
    volume_cal.SetSpacing([2.0, 2.0, 3.0])
    volume_cal.SetOrigin([0.0, 0.0, 0.0])

    resampled_cal = sitk.Resample(volume_cal, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_before = sitk.GetArrayFromImage(resampled_cal)

    diff = np.abs(result_after - result_before)
    print(f"  Max difference: {np.max(diff):.6f}")
    print(f"  Mean difference: {np.mean(diff):.6f}")
    if np.max(diff) < 0.01:
        print("  PASS: Constant rescale -> rescale order doesn't matter\n")
    else:
        print("  INFO: Small numerical differences exist\n")


def test_variable_rescale_slope():
    """When RescaleSlope varies per slice (e.g., PET decay correction),
    rescale-after produces different results than rescale-before."""
    print("=" * 70)
    print("TEST 2: Variable rescale slope per slice (PET-like scenario)")
    print("=" * 70)

    num_slices = 10
    intercept = 0.0

    # Simulate varying slope (e.g., PET decay correction changes per slice)
    slopes = np.linspace(1.0, 2.0, num_slices).astype(np.float32)
    print(f"  Slopes per slice: {[f'{s:.2f}' for s in slopes]}")

    # Create raw pixel data
    raw_data = np.random.rand(num_slices, 32, 32).astype(np.float32) * 1000

    # Reference grid with different spacing to force interpolation
    ref_spacing = [2.0, 2.0, 2.0]  # Different z-spacing forces z-interpolation
    src_spacing = [2.0, 2.0, 3.0]

    num_ref_slices = int(num_slices * 3.0 / 2.0)

    # Method A: Rescale AFTER with slope from slice 0 only (current 3D code behavior)
    volume_raw = sitk.GetImageFromArray(raw_data)
    volume_raw.SetSpacing(src_spacing)
    volume_raw.SetOrigin([0.0, 0.0, 0.0])

    ref = sitk.Image(32, 32, num_ref_slices, sitk.sitkFloat32)
    ref.SetSpacing(ref_spacing)
    ref.SetOrigin([0.0, 0.0, 0.0])

    resampled_raw = sitk.Resample(volume_raw, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_after = sitk.GetArrayFromImage(resampled_raw) * slopes[0] + intercept

    # Method B: Rescale BEFORE resampling (correct per-slice application)
    calibrated_data = np.zeros_like(raw_data)
    for i in range(num_slices):
        calibrated_data[i] = raw_data[i] * slopes[i] + intercept

    volume_cal = sitk.GetImageFromArray(calibrated_data)
    volume_cal.SetSpacing(src_spacing)
    volume_cal.SetOrigin([0.0, 0.0, 0.0])

    resampled_cal = sitk.Resample(volume_cal, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_before = sitk.GetArrayFromImage(resampled_cal)

    diff = np.abs(result_after - result_before)
    rel_diff = diff / (np.abs(result_before) + 1e-10) * 100

    print(f"\n  Result shapes: after={result_after.shape}, before={result_before.shape}")
    print(f"  Max absolute difference: {np.max(diff):.2f}")
    print(f"  Mean absolute difference: {np.mean(diff):.2f}")
    print(f"  Max relative difference: {np.max(rel_diff[result_before > 1]):.1f}%")
    print(f"  Mean relative difference: {np.mean(rel_diff[result_before > 1]):.1f}%")

    # Check specific slices to show the pattern
    print("\n  Per-slice comparison (center pixel):")
    for z in range(min(num_ref_slices, 12)):
        val_after = result_after[z, 16, 16]
        val_before = result_before[z, 16, 16]
        slice_diff = abs(val_after - val_before)
        pct = (slice_diff / (abs(val_before) + 1e-10)) * 100
        print(f"    z={z:2d}: after={val_after:8.1f}, before={val_before:8.1f}, "
              f"diff={slice_diff:7.1f} ({pct:5.1f}%)")

    if np.max(diff) > 1.0:
        print("\n  CONFIRMED: Variable rescale slope causes significant differences")
        print("  when applying rescale after resampling vs before.")
        print("  Current code uses slope from overlay_datasets[0] for all slices.\n")
    else:
        print("\n  Differences are negligible.\n")


def test_ct_typical_rescale():
    """CT typically has constant slope=1, intercept=-1024. Should be equivalent."""
    print("=" * 70)
    print("TEST 3: Typical CT rescale (slope=1, intercept=-1024)")
    print("=" * 70)

    slope = 1.0
    intercept = -1024.0
    num_slices = 10

    raw_data = (np.random.rand(num_slices, 32, 32) * 4000).astype(np.float32)

    src_spacing = [0.5, 0.5, 2.0]
    ref_spacing = [1.0, 1.0, 3.0]
    num_ref_slices = int(num_slices * 2.0 / 3.0) + 1

    # Method A: Rescale after
    vol_raw = sitk.GetImageFromArray(raw_data)
    vol_raw.SetSpacing(src_spacing)
    vol_raw.SetOrigin([0.0, 0.0, 0.0])

    ref = sitk.Image(16, 16, num_ref_slices, sitk.sitkFloat32)
    ref.SetSpacing(ref_spacing)
    ref.SetOrigin([0.0, 0.0, 0.0])

    resampled_raw = sitk.Resample(vol_raw, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_after = sitk.GetArrayFromImage(resampled_raw) * slope + intercept

    # Method B: Rescale before
    cal_data = raw_data * slope + intercept
    vol_cal = sitk.GetImageFromArray(cal_data)
    vol_cal.SetSpacing(src_spacing)
    vol_cal.SetOrigin([0.0, 0.0, 0.0])

    resampled_cal = sitk.Resample(vol_cal, ref, sitk.Transform(3, sitk.sitkIdentity),
                                   sitk.sitkLinear, 0.0)
    result_before = sitk.GetArrayFromImage(resampled_cal)

    diff = np.abs(result_after - result_before)
    print(f"  Max difference: {np.max(diff):.6f}")
    print(f"  Mean difference: {np.mean(diff):.6f}")
    if np.max(diff) < 0.01:
        print("  PASS: CT rescale (slope=1, intercept=-1024) -> order doesn't matter")
        print("  (Linear transform with constant params commutes with interpolation)\n")
    else:
        print(f"  INFO: Differences exist (max={np.max(diff):.4f})\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FUSION AUDIT: Rescale Timing Verification")
    print("=" * 70 + "\n")

    test_constant_rescale()
    test_variable_rescale_slope()
    test_ct_typical_rescale()

    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)
