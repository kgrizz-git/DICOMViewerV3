"""
Fusion Audit: Verify IPP-to-pixel offset formula and slice spacing calculation.

Tests:
- Issue 3: Whether the 2D translation offset formula correctly handles
  non-axial orientations (it should project onto row/col directions using IOP).
- Issue 4: Whether _calculate_slice_spacing using 3D Euclidean distance
  matches the along-normal projection used in dicom_series_to_sitk.

This script does NOT modify any production code. It only prints diagnostic output.

Usage: python tests/fusion_audit_offset_and_spacing_test.py
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.fusion_handler_io import translation_offset_pixels_from_ipps


def correct_offset_with_iop(base_ipp, overlay_ipp, base_pixel_spacing, iop_row, iop_col):
    """Correct offset calculation that projects the physical offset onto image plane directions.

    The physical offset should be projected onto the row and column direction
    vectors defined by ImageOrientationPatient, not assumed to be along the
    patient coordinate X/Y axes.
    """
    delta = np.array(overlay_ipp) - np.array(base_ipp)
    # Project onto column direction (x in image) and row direction (y in image)
    offset_along_col = np.dot(delta, np.array(iop_row))  # row cosines = direction of increasing column
    offset_along_row = np.dot(delta, np.array(iop_col))  # col cosines = direction of increasing row
    offset_px_x = offset_along_col / base_pixel_spacing[1]  # col spacing
    offset_px_y = offset_along_row / base_pixel_spacing[0]  # row spacing
    return (offset_px_x, offset_px_y)


def test_axial_offset():
    """Standard axial: IOP = [1,0,0, 0,1,0]. X/Y projection == direct subtraction."""
    print("=" * 70)
    print("TEST 1: IPP offset - standard axial orientation")
    print("=" * 70)

    base_ipp = (-250.0, -250.0, -100.0)
    overlay_ipp = (-170.0, -170.0, -100.0)
    base_spacing = (1.0, 1.0)  # (row, col)

    iop_row = [1.0, 0.0, 0.0]
    iop_col = [0.0, 1.0, 0.0]

    current = translation_offset_pixels_from_ipps(base_ipp, overlay_ipp, base_spacing)
    correct = correct_offset_with_iop(base_ipp, overlay_ipp, base_spacing, iop_row, iop_col)

    print(f"  Base IPP:    {base_ipp}")
    print(f"  Overlay IPP: {overlay_ipp}")
    print(f"  Spacing:     {base_spacing}")
    print(f"  IOP:         row={iop_row}, col={iop_col}")
    print(f"  Current code offset: ({current[0]:.2f}, {current[1]:.2f}) px")
    print(f"  Correct offset:      ({correct[0]:.2f}, {correct[1]:.2f}) px")
    print(f"  Match: {np.allclose(current, correct)}")
    if np.allclose(current, correct):
        print("  PASS: For standard axial, both methods agree\n")
    else:
        print("  FAIL: Methods disagree even for axial!\n")


def test_oblique_offset():
    """Oblique: 15-degree gantry tilt. Current code ignores the tilt."""
    print("=" * 70)
    print("TEST 2: IPP offset - oblique orientation (15 deg gantry tilt)")
    print("=" * 70)

    angle = np.radians(15)
    iop_row = [np.cos(angle), 0.0, np.sin(angle)]
    iop_col = [0.0, 1.0, 0.0]

    base_ipp = (-250.0, -250.0, -100.0)
    overlay_ipp = (-170.0, -170.0, -90.0)  # z differs too
    base_spacing = (1.0, 1.0)

    current = translation_offset_pixels_from_ipps(base_ipp, overlay_ipp, base_spacing)
    correct = correct_offset_with_iop(base_ipp, overlay_ipp, base_spacing, iop_row, iop_col)

    print(f"  Base IPP:    {base_ipp}")
    print(f"  Overlay IPP: {overlay_ipp}")
    print(f"  Spacing:     {base_spacing}")
    print(f"  IOP row:     [{iop_row[0]:.4f}, {iop_row[1]:.4f}, {iop_row[2]:.4f}]")
    print(f"  IOP col:     {iop_col}")
    print()
    print(f"  Current code offset: ({current[0]:.2f}, {current[1]:.2f}) px")
    print(f"  Correct offset:      ({correct[0]:.2f}, {correct[1]:.2f}) px")
    diff_x = abs(current[0] - correct[0])
    diff_y = abs(current[1] - correct[1])
    print(f"  X difference: {diff_x:.2f} px")
    print(f"  Y difference: {diff_y:.2f} px")
    print(f"  Match: {np.allclose(current, correct)}")

    if not np.allclose(current, correct):
        print("\n  CONFIRMED: Current code produces wrong offset for oblique orientations")
        print("  The offset ignores the Z-component of the IPP difference and doesn't")
        print("  project onto the image plane row/col directions.\n")


def test_sagittal_offset():
    """Sagittal plane: major axes are swapped. Current code would be completely wrong."""
    print("=" * 70)
    print("TEST 3: IPP offset - sagittal orientation")
    print("=" * 70)

    iop_row = [0.0, 1.0, 0.0]  # Columns increase in Y direction
    iop_col = [0.0, 0.0, -1.0]  # Rows increase in -Z direction

    base_ipp = (-100.0, -200.0, 300.0)
    overlay_ipp = (-100.0, -150.0, 250.0)
    base_spacing = (2.0, 2.0)

    current = translation_offset_pixels_from_ipps(base_ipp, overlay_ipp, base_spacing)
    correct = correct_offset_with_iop(base_ipp, overlay_ipp, base_spacing, iop_row, iop_col)

    print(f"  Base IPP:    {base_ipp}")
    print(f"  Overlay IPP: {overlay_ipp}")
    print(f"  Spacing:     {base_spacing}")
    print(f"  IOP:         row={iop_row}, col={iop_col}")
    print()
    print(f"  Current code offset: ({current[0]:.2f}, {current[1]:.2f}) px")
    print(f"  Correct offset:      ({correct[0]:.2f}, {correct[1]:.2f}) px")
    print(f"  X difference: {abs(current[0] - correct[0]):.2f} px")
    print(f"  Y difference: {abs(current[1] - correct[1]):.2f} px")

    if not np.allclose(current, correct):
        print("\n  CONFIRMED: Completely wrong for sagittal - current code uses")
        print("  patient X/Y directly instead of projecting onto image plane.\n")


def test_slice_spacing_methods():
    """Compare _calculate_slice_spacing (3D distance) vs along-normal projection."""
    print("=" * 70)
    print("TEST 4: Slice spacing - 3D distance vs along-normal projection")
    print("=" * 70)

    # Standard axial: IPP Z changes, X/Y constant
    print("\n  Case A: Standard axial (Z changes only)")
    ipp_axial = [
        np.array([-250.0, -250.0, 0.0]),
        np.array([-250.0, -250.0, 3.0]),
        np.array([-250.0, -250.0, 6.0]),
    ]
    iop_row = np.array([1.0, 0.0, 0.0])
    iop_col = np.array([0.0, 1.0, 0.0])
    slice_normal = np.cross(iop_row, iop_col)

    for i in range(len(ipp_axial) - 1):
        diff = ipp_axial[i + 1] - ipp_axial[i]
        dist_3d = np.linalg.norm(diff)
        dist_normal = abs(np.dot(diff, slice_normal))
        print(f"    Slice {i}->{i+1}: 3D dist={dist_3d:.3f}mm, along-normal={dist_normal:.3f}mm, "
              f"diff={abs(dist_3d - dist_normal):.6f}mm")

    # Oblique: IPP changes in X and Z
    print("\n  Case B: 15-degree gantry tilt (X and Z change)")
    angle = np.radians(15)
    iop_row = np.array([np.cos(angle), 0.0, np.sin(angle)])
    iop_col = np.array([0.0, 1.0, 0.0])
    slice_normal = np.cross(iop_row, iop_col)
    slice_normal = slice_normal / np.linalg.norm(slice_normal)

    # Slices are 3mm apart along the slice normal
    true_spacing = 3.0
    ipp_oblique = []
    for i in range(5):
        pos = np.array([-250.0, -250.0, 0.0]) + i * true_spacing * slice_normal
        ipp_oblique.append(pos)

    for i in range(len(ipp_oblique) - 1):
        diff = ipp_oblique[i + 1] - ipp_oblique[i]
        dist_3d = np.linalg.norm(diff)
        dist_normal = abs(np.dot(diff, slice_normal))
        print(f"    Slice {i}->{i+1}: 3D dist={dist_3d:.3f}mm, along-normal={dist_normal:.3f}mm, "
              f"diff={abs(dist_3d - dist_normal):.6f}mm")
        print(f"      IPP: {ipp_oblique[i]} -> {ipp_oblique[i+1]}")

    print("\n    For slices along the normal, 3D distance == along-normal distance")
    print("    Both methods agree because position difference IS along the normal.\n")

    # Oblique with in-plane position variation (e.g., gantry tilt causing per-slice X shift)
    print("  Case C: Oblique with in-plane drift (realistic gantry tilt artifact)")
    ipp_drifted = []
    for i in range(5):
        base_pos = np.array([-250.0, -250.0, 0.0]) + i * true_spacing * slice_normal
        # Add small in-plane drift
        drift = np.array([i * 0.5, 0.0, 0.0])  # 0.5mm per slice in X
        ipp_drifted.append(base_pos + drift)

    for i in range(len(ipp_drifted) - 1):
        diff = ipp_drifted[i + 1] - ipp_drifted[i]
        dist_3d = np.linalg.norm(diff)
        dist_normal = abs(np.dot(diff, slice_normal))
        error_pct = abs(dist_3d - dist_normal) / dist_normal * 100
        print(f"    Slice {i}->{i+1}: 3D dist={dist_3d:.3f}mm, along-normal={dist_normal:.3f}mm, "
              f"error={error_pct:.2f}%")

    print("\n    With in-plane drift, 3D distance overestimates actual slice spacing.")
    print("    This could cause needs_resampling() to incorrectly flag 3D requirement.\n")


def test_unsorted_datasets_spacing():
    """Demonstrate that _calculate_slice_spacing on unsorted data gives wrong results."""
    print("=" * 70)
    print("TEST 5: Slice spacing calculation on unsorted vs sorted data")
    print("=" * 70)

    # Simulate unsorted IPP Z values
    z_values_sorted = [0.0, 3.0, 6.0, 9.0, 12.0]
    z_values_unsorted = [6.0, 0.0, 12.0, 3.0, 9.0]

    print("\n  Sorted Z values:", z_values_sorted)
    spacings_sorted = []
    for i in range(len(z_values_sorted) - 1):
        s = abs(z_values_sorted[i + 1] - z_values_sorted[i])
        spacings_sorted.append(s)
    avg_sorted = np.mean(spacings_sorted)
    print(f"  Consecutive spacings: {spacings_sorted}")
    print(f"  Average spacing: {avg_sorted:.2f}mm")

    print(f"\n  Unsorted Z values: {z_values_unsorted}")
    spacings_unsorted = []
    for i in range(len(z_values_unsorted) - 1):
        s = abs(z_values_unsorted[i + 1] - z_values_unsorted[i])
        spacings_unsorted.append(s)
    avg_unsorted = np.mean(spacings_unsorted)
    print(f"  Consecutive spacings: {spacings_unsorted}")
    print(f"  Average spacing: {avg_unsorted:.2f}mm")

    print(f"\n  Sorted avg: {avg_sorted:.2f}mm vs Unsorted avg: {avg_unsorted:.2f}mm")
    if abs(avg_sorted - avg_unsorted) > 0.01:
        print("  CONFIRMED: Unsorted datasets produce wrong average slice spacing")
        print("  _calculate_slice_spacing iterates over datasets as-received,")
        print("  which may be unsorted.\n")
    else:
        print("  Both produce same result (coincidence with these values)\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FUSION AUDIT: IPP Offset & Slice Spacing Verification")
    print("=" * 70 + "\n")

    test_axial_offset()
    test_oblique_offset()
    test_sagittal_offset()
    test_slice_spacing_methods()
    test_unsorted_datasets_spacing()

    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)
