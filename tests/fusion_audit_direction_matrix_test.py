"""
Fusion Audit: Verify SimpleITK direction matrix convention.

Tests whether the current code's direction matrix construction is correct
by comparing it against SimpleITK's expected convention (row-major, columns = axis directions).

This script does NOT modify any production code. It only prints diagnostic output.

Usage: python tests/fusion_audit_direction_matrix_test.py
"""
import numpy as np

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

try:
    import SimpleITK as sitk
except ImportError:
    print("ERROR: SimpleITK not available. Cannot run this test.")
    raise SystemExit(1) from None


def build_direction_current_code(row_cosines, col_cosines):
    """Replicates the direction matrix construction from image_resampler.py lines 279-283."""
    slice_cosines = np.cross(row_cosines, col_cosines)
    direction = [
        row_cosines[0], row_cosines[1], row_cosines[2],
        col_cosines[0], col_cosines[1], col_cosines[2],
        slice_cosines[0], slice_cosines[1], slice_cosines[2],
    ]
    return direction


def build_direction_columns(row_cosines, col_cosines):
    """Correct construction: columns of the matrix are the axis direction vectors.

    SimpleITK convention (from docs): row-major flat list where each COLUMN
    is the physical direction of the corresponding image axis.

    For GetImageFromArray(numpy[z,y,x]) -> sitk[x,y,z]:
      - axis 0 (x) = pixel columns -> direction = row_cosines (IOP first triple)
      - axis 1 (y) = pixel rows    -> direction = col_cosines (IOP second triple)
      - axis 2 (z) = slices        -> direction = slice_normal
    """
    slice_cosines = np.cross(row_cosines, col_cosines)
    direction = [
        row_cosines[0], col_cosines[0], slice_cosines[0],
        row_cosines[1], col_cosines[1], slice_cosines[1],
        row_cosines[2], col_cosines[2], slice_cosines[2],
    ]
    return direction


def test_with_sitk_reader():
    """Use SimpleITK's DICOMOrient to verify the standard LPS direction."""
    print("=" * 70)
    print("TEST 1: Verify identity direction is LPS")
    print("=" * 70)

    img = sitk.Image(10, 10, 10, sitk.sitkFloat32)
    orientation = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(
        list(img.GetDirection())
    )
    print(f"Identity direction: {list(img.GetDirection())}")
    print(f"Orientation label:  {orientation}")
    print("Expected:           LPS")
    assert orientation == "LPS", f"FAIL: expected LPS, got {orientation}"
    print("PASS: Identity direction = LPS\n")


def test_axial_case():
    """Standard axial: row=[1,0,0], col=[0,1,0]. Both methods should produce identity."""
    print("=" * 70)
    print("TEST 2: Standard axial orientation (should be identical)")
    print("=" * 70)

    row_cos = np.array([1.0, 0.0, 0.0])
    col_cos = np.array([0.0, 1.0, 0.0])

    current = build_direction_current_code(row_cos, col_cos)
    correct = build_direction_columns(row_cos, col_cos)

    print(f"Current code direction: {current}")
    print(f"Correct direction:      {correct}")

    are_equal = np.allclose(current, correct)
    print(f"Equal: {are_equal}")
    if are_equal:
        print("PASS: For standard axial, both produce the same result (identity)\n")
    else:
        print("INFO: Differ even for axial (unexpected)\n")

    img = sitk.Image(10, 10, 10, sitk.sitkFloat32)
    img.SetDirection(current)
    orient_current = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(current)
    orient_correct = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(correct)
    print(f"Current code orientation label: {orient_current}")
    print(f"Correct orientation label:      {orient_correct}")
    print()


def test_oblique_case():
    """Oblique acquisition: row and col cosines are not axis-aligned."""
    print("=" * 70)
    print("TEST 3: Oblique orientation (sagittal oblique)")
    print("=" * 70)

    # Simulate a ~15 degree gantry tilt around Y axis
    angle = np.radians(15)
    row_cos = np.array([np.cos(angle), 0.0, np.sin(angle)])
    col_cos = np.array([0.0, 1.0, 0.0])

    current = build_direction_current_code(row_cos, col_cos)
    correct = build_direction_columns(row_cos, col_cos)

    print(f"Row cosines: {row_cos}")
    print(f"Col cosines: {col_cos}")
    print()
    print(f"Current code direction: {[round(x, 6) for x in current]}")
    print(f"Correct direction:      {[round(x, 6) for x in correct]}")

    are_equal = np.allclose(current, correct)
    print(f"\nEqual: {are_equal}")

    if not are_equal:
        diff = np.array(current) - np.array(correct)
        print(f"Difference:             {[round(x, 6) for x in diff]}")
        print(f"Max absolute diff:      {np.max(np.abs(diff)):.6f}")

    orient_current = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(current)
    orient_correct = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(correct)
    print(f"\nCurrent code orientation label: {orient_current}")
    print(f"Correct orientation label:      {orient_correct}")
    print(f"Labels match: {orient_current == orient_correct}")
    print()


def test_resampling_impact():
    """Create two small volumes with oblique orientation and different origins,
    then compare resampling results with current vs correct direction."""
    print("=" * 70)
    print("TEST 4: Resampling impact with oblique orientation + different origins")
    print("=" * 70)

    angle = np.radians(15)
    row_cos = np.array([np.cos(angle), 0.0, np.sin(angle)])
    col_cos = np.array([0.0, 1.0, 0.0])

    current_dir = build_direction_current_code(row_cos, col_cos)
    correct_dir = build_direction_columns(row_cos, col_cos)

    # Create reference volume (like CT)
    ref_data = np.zeros((20, 64, 64), dtype=np.float32)
    ref_origin = [-160.0, -160.0, -50.0]
    ref_spacing = [5.0, 5.0, 5.0]

    # Create moving volume (like PET) with different origin/spacing
    mov_data = np.ones((20, 32, 32), dtype=np.float32) * 100.0
    # Place a bright spot at center
    mov_data[10, 16, 16] = 1000.0
    mov_origin = [-80.0, -80.0, -50.0]
    mov_spacing = [5.0, 5.0, 5.0]

    for label, direction in [("CURRENT CODE", current_dir), ("CORRECT", correct_dir)]:
        ref_img = sitk.GetImageFromArray(ref_data)
        ref_img.SetOrigin(ref_origin)
        ref_img.SetSpacing(ref_spacing)
        ref_img.SetDirection(direction)

        mov_img = sitk.GetImageFromArray(mov_data)
        mov_img.SetOrigin(mov_origin)
        mov_img.SetSpacing(mov_spacing)
        mov_img.SetDirection(direction)

        transform = sitk.Transform(3, sitk.sitkIdentity)
        resampled = sitk.Resample(mov_img, ref_img, transform, sitk.sitkLinear, 0.0)
        result = sitk.GetArrayFromImage(resampled)

        # Find the peak location in the resampled volume
        peak_idx = np.unravel_index(np.argmax(result), result.shape)
        peak_val = result[peak_idx]

        print(f"\n  [{label}]")
        print(f"    Resampled volume shape: {result.shape}")
        print(f"    Peak value: {peak_val:.1f} at index (z,y,x) = {peak_idx}")
        print(f"    Non-zero voxels: {np.count_nonzero(result)}")
        print(f"    Sum: {np.sum(result):.1f}")

    # Now test with SAME direction for both (symmetric error cancellation)
    print("\n  [SAME WRONG DIRECTION FOR BOTH - error cancellation test]")
    ref_img = sitk.GetImageFromArray(ref_data)
    ref_img.SetOrigin(ref_origin)
    ref_img.SetSpacing(ref_spacing)
    ref_img.SetDirection(current_dir)

    mov_img = sitk.GetImageFromArray(mov_data)
    mov_img.SetOrigin(mov_origin)
    mov_img.SetSpacing(mov_spacing)
    mov_img.SetDirection(current_dir)

    transform = sitk.Transform(3, sitk.sitkIdentity)
    resampled_wrong = sitk.Resample(mov_img, ref_img, transform, sitk.sitkLinear, 0.0)
    result_wrong = sitk.GetArrayFromImage(resampled_wrong)

    ref_img2 = sitk.GetImageFromArray(ref_data)
    ref_img2.SetOrigin(ref_origin)
    ref_img2.SetSpacing(ref_spacing)
    ref_img2.SetDirection(correct_dir)

    mov_img2 = sitk.GetImageFromArray(mov_data)
    mov_img2.SetOrigin(mov_origin)
    mov_img2.SetSpacing(mov_spacing)
    mov_img2.SetDirection(correct_dir)

    resampled_correct = sitk.Resample(mov_img2, ref_img2, transform, sitk.sitkLinear, 0.0)
    result_correct = sitk.GetArrayFromImage(resampled_correct)

    peak_wrong = np.unravel_index(np.argmax(result_wrong), result_wrong.shape)
    peak_correct = np.unravel_index(np.argmax(result_correct), result_correct.shape)

    print(f"    Peak with WRONG direction (both):   (z,y,x) = {peak_wrong}, val = {result_wrong[peak_wrong]:.1f}")
    print(f"    Peak with CORRECT direction (both):  (z,y,x) = {peak_correct}, val = {result_correct[peak_correct]:.1f}")
    print(f"    Peaks match: {peak_wrong == peak_correct}")

    diff = np.abs(result_wrong.astype(float) - result_correct.astype(float))
    print(f"    Max pixel difference: {np.max(diff):.4f}")
    print(f"    Mean pixel difference: {np.mean(diff):.4f}")
    if np.max(diff) > 0.01:
        print("    RESULT: Direction transpose DOES affect resampling for oblique + different origins")
    else:
        print("    RESULT: Direction transpose does NOT affect resampling (errors cancel)")
    print()


def test_sagittal_coronal():
    """Test with pure sagittal and coronal orientations."""
    print("=" * 70)
    print("TEST 5: Pure sagittal and coronal orientations")
    print("=" * 70)

    orientations = {
        "Sagittal": (np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, -1.0])),
        "Coronal": (np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0])),
    }

    for name, (row_cos, col_cos) in orientations.items():
        current = build_direction_current_code(row_cos, col_cos)
        correct = build_direction_columns(row_cos, col_cos)
        are_equal = np.allclose(current, correct)

        orient_current = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(current)
        orient_correct = sitk.DICOMOrientImageFilter.GetOrientationFromDirectionCosines(correct)

        print_redacted(f"\n  {name}:")
        print(f"    Row cosines: {row_cos}")
        print(f"    Col cosines: {col_cos}")
        print(f"    Current code label: {orient_current}")
        print(f"    Correct label:      {orient_correct}")
        print(f"    Equal: {are_equal}")
        if not are_equal:
            print_redacted(f"    BUG: Direction matrices differ for {name}!")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("FUSION AUDIT: SimpleITK Direction Matrix Verification")
    print("=" * 70 + "\n")

    test_with_sitk_reader()
    test_axial_case()
    test_oblique_case()
    test_resampling_impact()
    test_sagittal_coronal()

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)
