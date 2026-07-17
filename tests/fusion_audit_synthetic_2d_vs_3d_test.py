"""
Fusion Audit: Compare 2D (Fast) vs 3D (High Accuracy) resampling paths
using synthetic DICOM-like data.

Tests whether the two paths produce consistent results for:
- Same-grid (no resampling needed)
- Different pixel spacing (in-plane scaling)
- Different slice spacing (through-plane interpolation)
- Different origins (translation)

This script does NOT modify any production code. It only prints diagnostic output.

Usage: python tests/fusion_audit_synthetic_2d_vs_3d_test.py
"""
import os
import sys

import numpy as np

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import SimpleITK as sitk  # noqa: F401 - availability probe
except ImportError:
    print("ERROR: SimpleITK not available.")
    raise SystemExit(1) from None

from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

from core.fusion_handler import FusionHandler


def make_synthetic_dataset(
    rows, cols, slice_location, pixel_spacing, ipp,
    iop=(1, 0, 0, 0, 1, 0), pixel_data=None,
    rescale_slope=1.0, rescale_intercept=0.0,
    series_uid="1.2.3", frame_of_ref_uid="1.2.3.4",
    modality="CT"
):
    """Create a minimal pydicom Dataset with spatial metadata."""
    ds = Dataset()
    ds.Rows = rows
    ds.Columns = cols
    ds.SliceLocation = slice_location
    ds.PixelSpacing = [pixel_spacing[0], pixel_spacing[1]]
    ds.ImagePositionPatient = list(ipp)
    ds.ImageOrientationPatient = list(iop)
    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept
    ds.SeriesInstanceUID = series_uid
    ds.FrameOfReferenceUID = frame_of_ref_uid
    ds.Modality = modality
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"

    if pixel_data is not None:
        ds.PixelData = pixel_data.astype(np.uint16).tobytes()
        ds._pixel_array = pixel_data.astype(np.float32)
    else:
        arr = np.zeros((rows, cols), dtype=np.uint16)
        ds.PixelData = arr.tobytes()
        ds._pixel_array = arr.astype(np.float32)

    # Override pixel_array property for testing
    ds._pixel_array_cache = pixel_data.astype(np.float32) if pixel_data is not None else np.zeros((rows, cols), dtype=np.float32)

    return ds


def monkey_patch_pixel_array(ds, arr):
    """Inject pixel_array data that pydicom will return without decompression."""
    ds._pixel_array_override = arr.astype(np.float32)
    original_class = type(ds)

    class PatchedDataset(original_class):
        @property
        def pixel_array(self):
            return self._pixel_array_override

    ds.__class__ = PatchedDataset
    return ds


def create_test_series(num_slices, rows, cols, pixel_spacing, origin, slice_spacing,
                       series_uid=None, frame_of_ref_uid=None, pattern="gradient",
                       rescale_slope=1.0, rescale_intercept=0.0):
    """Create a series of synthetic datasets with known pixel patterns."""
    if series_uid is None:
        series_uid = generate_uid()
    if frame_of_ref_uid is None:
        frame_of_ref_uid = generate_uid()

    datasets = []
    for i in range(num_slices):
        ipp = [origin[0], origin[1], origin[2] + i * slice_spacing]
        slice_loc = ipp[2]

        if pattern == "gradient":
            arr = np.full((rows, cols), i * 100 + 50, dtype=np.float32)
        elif pattern == "spot":
            arr = np.zeros((rows, cols), dtype=np.float32)
            cy, cx = rows // 2, cols // 2
            arr[cy - 2:cy + 2, cx - 2:cx + 2] = 1000.0
            arr = arr * (1.0 + i * 0.1)
        elif pattern == "ramp":
            arr = np.arange(rows * cols, dtype=np.float32).reshape(rows, cols)
            arr = arr + i * 1000
        else:
            arr = np.random.rand(rows, cols).astype(np.float32) * 500

        ds = make_synthetic_dataset(
            rows, cols, slice_loc, pixel_spacing, ipp,
            pixel_data=arr.astype(np.uint16),
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
            series_uid=series_uid,
            frame_of_ref_uid=frame_of_ref_uid,
        )
        ds = monkey_patch_pixel_array(ds, arr)
        datasets.append(ds)

    return datasets


def test_same_grid():
    """When base and overlay have identical grids, both paths should produce same result."""
    print("=" * 70)
    print("TEST 1: Same grid - 2D vs 3D should be nearly identical")
    print("=" * 70)

    for_uid = generate_uid()
    base_uid = generate_uid()
    overlay_uid = generate_uid()

    base_ds = create_test_series(10, 64, 64, (1.0, 1.0), (-32.0, -32.0, 0.0), 3.0,
                                  series_uid=base_uid, frame_of_ref_uid=for_uid, pattern="gradient")
    overlay_ds = create_test_series(10, 64, 64, (1.0, 1.0), (-32.0, -32.0, 0.0), 3.0,
                                     series_uid=overlay_uid, frame_of_ref_uid=for_uid, pattern="spot")

    handler = FusionHandler()
    handler.base_series_uid = base_uid
    handler.overlay_series_uid = overlay_uid

    # Test 2D path
    handler.resampling_mode = 'fast'
    overlay_2d = handler.interpolate_overlay_slice(5, base_ds, overlay_ds)

    # Test 3D path
    handler.resampling_mode = 'high_accuracy'
    handler.image_resampler.clear_cache()
    overlay_3d = handler.interpolate_overlay_slice(5, base_ds, overlay_ds)

    if overlay_2d is not None and overlay_3d is not None:
        diff = np.abs(overlay_2d - overlay_3d)
        print(f"  2D shape: {overlay_2d.shape}, 3D shape: {overlay_3d.shape}")
        print(f"  2D range: [{np.min(overlay_2d):.1f}, {np.max(overlay_2d):.1f}]")
        print(f"  3D range: [{np.min(overlay_3d):.1f}, {np.max(overlay_3d):.1f}]")
        print(f"  Max diff: {np.max(diff):.4f}")
        print(f"  Mean diff: {np.mean(diff):.4f}")
        if np.max(diff) < 1.0:
            print("  PASS: Same grid produces consistent results\n")
        else:
            print("  INFO: Some difference exists (may be due to rescale timing)\n")
    else:
        print(f"  2D result: {'OK' if overlay_2d is not None else 'None'}")
        print(f"  3D result: {'OK' if overlay_3d is not None else 'None'}")
        print("  WARN: One path returned None\n")


def test_different_spacing():
    """PET typically has larger pixels than CT. Both paths should handle scaling."""
    print("=" * 70)
    print("TEST 2: Different pixel spacing (CT 0.5mm, PET 4mm)")
    print("=" * 70)

    for_uid = generate_uid()
    base_uid = generate_uid()
    overlay_uid = generate_uid()

    base_ds = create_test_series(20, 512, 512, (0.5, 0.5), (-128.0, -128.0, 0.0), 2.0,
                                  series_uid=base_uid, frame_of_ref_uid=for_uid, pattern="gradient")
    overlay_ds = create_test_series(20, 128, 128, (4.0, 4.0), (-256.0, -256.0, 0.0), 2.0,
                                     series_uid=overlay_uid, frame_of_ref_uid=for_uid, pattern="spot")

    handler = FusionHandler()
    handler.base_series_uid = base_uid
    handler.overlay_series_uid = overlay_uid

    # 2D path
    handler.resampling_mode = 'fast'
    overlay_2d = handler.interpolate_overlay_slice(10, base_ds, overlay_ds)

    # 3D path
    handler.resampling_mode = 'high_accuracy'
    handler.image_resampler.clear_cache()
    overlay_3d = handler.interpolate_overlay_slice(10, base_ds, overlay_ds)

    if overlay_2d is not None and overlay_3d is not None:
        print(f"  2D shape: {overlay_2d.shape} (raw overlay, pre-resize)")
        print(f"  3D shape: {overlay_3d.shape} (resampled to base grid)")
        print(f"  2D range: [{np.min(overlay_2d):.1f}, {np.max(overlay_2d):.1f}]")
        print(f"  3D range: [{np.min(overlay_3d):.1f}, {np.max(overlay_3d):.1f}]")
        print(f"  2D non-zero: {np.count_nonzero(overlay_2d)}")
        print(f"  3D non-zero: {np.count_nonzero(overlay_3d)}")
        print("  NOTE: 2D returns raw overlay (resize happens in FusionProcessor)")
        print("  NOTE: 3D returns overlay resampled to base grid dimensions\n")
    else:
        print(f"  2D result: {'OK' if overlay_2d is not None else 'None'}")
        print(f"  3D result: {'OK' if overlay_3d is not None else 'None'}\n")


def test_variable_rescale_in_3d():
    """Demonstrate the rescale-after-resample problem with synthetic per-slice slopes."""
    print("=" * 70)
    print("TEST 3: Variable RescaleSlope in 3D path (PET-like)")
    print("=" * 70)

    for_uid = generate_uid()
    base_uid = generate_uid()
    overlay_uid = generate_uid()

    num_slices = 10
    base_ds = create_test_series(num_slices, 64, 64, (1.0, 1.0), (0.0, 0.0, 0.0), 3.0,
                                  series_uid=base_uid, frame_of_ref_uid=for_uid, pattern="gradient")

    # Create overlay with varying rescale slope
    overlay_ds = []
    for i in range(num_slices):
        slope = 1.0 + i * 0.1  # Slopes: 1.0, 1.1, 1.2, ..., 1.9
        arr = np.full((64, 64), 500.0, dtype=np.float32)
        ipp = [0.0, 0.0, i * 3.0]
        ds = make_synthetic_dataset(64, 64, ipp[2], (1.0, 1.0), ipp,
                                     pixel_data=arr.astype(np.uint16),
                                     rescale_slope=slope,
                                     rescale_intercept=0.0,
                                     series_uid=overlay_uid,
                                     frame_of_ref_uid=for_uid)
        ds = monkey_patch_pixel_array(ds, arr)
        overlay_ds.append(ds)

    handler = FusionHandler()
    handler.base_series_uid = base_uid
    handler.overlay_series_uid = overlay_uid

    # Check what slopes the code detects
    from core.dicom_processor import DICOMProcessor
    slopes_found = []
    for ds in overlay_ds:
        slope, intercept, _ = DICOMProcessor.get_rescale_parameters(ds)
        slopes_found.append(slope)

    print(f"  Rescale slopes per slice: {[f'{s:.1f}' for s in slopes_found]}")
    print(f"  3D path will use slope from slice 0: {slopes_found[0]}")

    # 2D path (applies per-slice rescale correctly)
    handler.resampling_mode = 'fast'
    values_2d = []
    for i in range(num_slices):
        arr = handler.interpolate_overlay_slice(i, base_ds, overlay_ds)
        if arr is not None:
            values_2d.append(arr[32, 32])
        else:
            values_2d.append(None)

    # 3D path (applies slope from slice 0 to all)
    handler.resampling_mode = 'high_accuracy'
    handler.image_resampler.clear_cache()
    values_3d = []
    for i in range(num_slices):
        arr = handler.interpolate_overlay_slice(i, base_ds, overlay_ds)
        if arr is not None:
            values_3d.append(arr[32, 32])
        else:
            values_3d.append(None)

    print("\n  Center pixel values per slice:")
    print(f"  {'Slice':>5} {'2D (per-slice)':>15} {'3D (slope[0])':>15} {'Expected':>10} {'3D Error':>10}")
    for i in range(num_slices):
        expected = 500.0 * slopes_found[i]
        v2d = values_2d[i] if values_2d[i] is not None else float('nan')
        v3d = values_3d[i] if values_3d[i] is not None else float('nan')
        error = abs(v3d - expected) if values_3d[i] is not None else float('nan')
        print_redacted(f"  {i:5d} {v2d:15.1f} {v3d:15.1f} {expected:10.1f} {error:10.1f}")

    print()


def test_dead_return_statement():
    """Verify the unreachable return None at line 627 of image_resampler.py."""
    print("=" * 70)
    print("TEST 4: Dead code check (image_resampler.py line 627)")
    print("=" * 70)

    import inspect

    from core.image_resampler import ImageResampler

    source = inspect.getsource(ImageResampler.get_resampled_slice)
    lines = source.split('\n')

    # Find consecutive returns
    found_dead = False
    for i in range(len(lines) - 1):
        stripped = lines[i].strip()
        next_stripped = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if stripped.startswith("return ") and next_stripped == "" and i + 2 < len(lines):
            next_next = lines[i + 2].strip()
            if next_next.startswith("return "):
                found_dead = True
                print("  Found unreachable return:")
                print(f"    Line {i}: {stripped}")
                print(f"    Line {i+1}: (blank)")
                print(f"    Line {i+2}: {next_next} <-- UNREACHABLE")

    if found_dead:
        print("  CONFIRMED: Dead return statement exists (harmless but should be cleaned up)\n")
    else:
        print("  No dead return found (may have been cleaned up)\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FUSION AUDIT: 2D vs 3D Path Comparison (Synthetic Data)")
    print("=" * 70 + "\n")

    test_same_grid()
    test_different_spacing()
    test_variable_rescale_in_3d()
    test_dead_return_statement()

    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)
