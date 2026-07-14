"""
Blind, independent PET/CT fusion verification script.

Built from scratch using ONLY DICOM standard knowledge and medical imaging
principles — NO reading of src/ application code. Compares independently
computed fusion overlays against the application's saved .npy outputs.

Inputs:
    - DICOM PET and CT series under test-DICOM-data/SomeFusion/
    - Saved app fusion outputs (.npy) under fusion_audit_results_v2/

Outputs:
    - Per-slice pass/fail comparison with error magnitudes
    - Summary table printed to stdout

Requirements:
    pydicom, numpy, SimpleITK, scipy (all in project requirements.txt)
"""

import os
import sys

import numpy as np
import pydicom
import SimpleITK as sitk

# ---------------------------------------------------------------------------
# 1. DICOM loading helpers — built from DICOM spec knowledge
# ---------------------------------------------------------------------------

def load_dicom_series(folder: str) -> list[pydicom.Dataset]:
    """Load all DICOM files from *folder*, return list of datasets."""
    datasets = []
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            ds = pydicom.dcmread(fpath)
            datasets.append(ds)
        except Exception:
            continue
    return datasets


def sort_by_z(datasets: list[pydicom.Dataset]) -> list[pydicom.Dataset]:
    """Sort DICOM datasets by ImagePositionPatient[2] (axial Z), ascending."""
    return sorted(datasets, key=lambda ds: float(ds.ImagePositionPatient[2]))


def group_by_series(datasets: list[pydicom.Dataset]) -> dict[str, list[pydicom.Dataset]]:
    """Group datasets by SeriesInstanceUID."""
    groups: dict[str, list[pydicom.Dataset]] = {}
    for ds in datasets:
        uid = str(ds.SeriesInstanceUID)
        groups.setdefault(uid, []).append(ds)
    return groups


def group_by_for(datasets: list[pydicom.Dataset]) -> dict[str, list[pydicom.Dataset]]:
    """Group datasets by FrameOfReferenceUID."""
    groups: dict[str, list[pydicom.Dataset]] = {}
    for ds in datasets:
        uid = str(ds.FrameOfReferenceUID)
        groups.setdefault(uid, []).append(ds)
    return groups


def get_rescaled_pixels(ds: pydicom.Dataset) -> np.ndarray:
    """Apply RescaleSlope and RescaleIntercept to raw pixel_array.

    DICOM standard: stored_value = raw * RescaleSlope + RescaleIntercept
    For PET, this converts raw counts to activity concentration (Bq/ml).
    """
    raw = ds.pixel_array.astype(np.float64)
    slope = float(getattr(ds, "RescaleSlope", 1.0))
    intercept = float(getattr(ds, "RescaleIntercept", 0.0))
    return raw * slope + intercept


# ---------------------------------------------------------------------------
# 2. 2D fusion overlay — Z-interpolation between bracketing PET slices
# ---------------------------------------------------------------------------

def fusion_2d(ct_sorted: list[pydicom.Dataset],
              pt_sorted: list[pydicom.Dataset],
              ct_idx: int) -> np.ndarray:
    """Compute 2D PET overlay for a given CT slice index.

    Finds the two PET slices that bracket the CT slice's Z position and
    linearly interpolates between their rescaled pixel arrays.

    Returns array in PET native dimensions (e.g. 168x168).
    """
    ct_z = float(ct_sorted[ct_idx].ImagePositionPatient[2])

    pt_z_positions = [float(ds.ImagePositionPatient[2]) for ds in pt_sorted]

    idx_below: int | None = None
    idx_above: int | None = None

    for i, pz in enumerate(pt_z_positions):
        if pz <= ct_z:
            if idx_below is None or pz > pt_z_positions[idx_below]:
                idx_below = i
        if pz >= ct_z:
            if idx_above is None or pz < pt_z_positions[idx_above]:
                idx_above = i

    if idx_below is None:
        idx_below = 0
    if idx_above is None:
        idx_above = len(pt_sorted) - 1

    if idx_below == idx_above:
        return get_rescaled_pixels(pt_sorted[idx_below]).astype(np.float32)

    z_below = pt_z_positions[idx_below]
    z_above = pt_z_positions[idx_above]
    weight = (ct_z - z_below) / (z_above - z_below)

    pet_below = get_rescaled_pixels(pt_sorted[idx_below])
    pet_above = get_rescaled_pixels(pt_sorted[idx_above])

    result = pet_below * (1.0 - weight) + pet_above * weight
    return result.astype(np.float32)


# ---------------------------------------------------------------------------
# 3. 3D fusion overlay — SimpleITK resampling of PET volume to CT grid
# ---------------------------------------------------------------------------

def build_sitk_volume(sorted_datasets: list[pydicom.Dataset],
                      apply_rescale: bool = False) -> sitk.Image:
    """Build a SimpleITK 3D volume from sorted DICOM datasets.

    - Stacks pixel arrays (sorted ascending Z) into 3D numpy array
    - Sets Origin from first (lowest Z) slice's ImagePositionPatient
    - Sets Spacing from PixelSpacing + inter-slice spacing
    - Sets Direction to identity (axial assumption)
    """
    if apply_rescale:
        slices = [get_rescaled_pixels(ds) for ds in sorted_datasets]
    else:
        slices = [ds.pixel_array.astype(np.float64) for ds in sorted_datasets]

    volume_np = np.stack(slices, axis=0)  # shape: (Z, rows, cols)

    first = sorted_datasets[0]
    ipp = [float(v) for v in first.ImagePositionPatient]
    ps = [float(v) for v in first.PixelSpacing]

    if len(sorted_datasets) > 1:
        z0 = float(sorted_datasets[0].ImagePositionPatient[2])
        z1 = float(sorted_datasets[1].ImagePositionPatient[2])
        slice_spacing = abs(z1 - z0)
    else:
        slice_spacing = float(getattr(first, "SliceThickness", 1.0))

    sitk_vol = sitk.GetImageFromArray(volume_np)
    sitk_vol = sitk.Cast(sitk_vol, sitk.sitkFloat64)

    # SimpleITK: spacing is (x, y, z) = (col_spacing, row_spacing, slice_spacing)
    sitk_vol.SetSpacing((ps[1], ps[0], slice_spacing))
    sitk_vol.SetOrigin((ipp[0], ipp[1], ipp[2]))
    sitk_vol.SetDirection((1, 0, 0, 0, 1, 0, 0, 0, 1))

    return sitk_vol


def fusion_3d(ct_sorted: list[pydicom.Dataset],
              pt_sorted: list[pydicom.Dataset],
              ct_idx: int) -> np.ndarray:
    """Compute 3D PET overlay for a given CT slice index.

    - Builds SimpleITK volumes for PET (raw) and CT
    - Resamples PET to CT grid using linear interpolation
    - Extracts the slice at ct_idx
    - Applies PET RescaleSlope/Intercept post-resample

    Returns array in CT pixel dimensions (e.g. 512x512).
    """
    pet_vol = build_sitk_volume(pt_sorted, apply_rescale=False)
    ct_vol = build_sitk_volume(ct_sorted, apply_rescale=False)

    resampled = sitk.Resample(
        pet_vol, ct_vol,
        sitk.Transform(),
        sitk.sitkLinear,
        0.0,
        pet_vol.GetPixelID()
    )

    resampled_np = sitk.GetArrayFromImage(resampled)  # (Z, rows, cols)
    slice_raw = resampled_np[ct_idx]

    slope = float(getattr(pt_sorted[0], "RescaleSlope", 1.0))
    intercept = float(getattr(pt_sorted[0], "RescaleIntercept", 0.0))
    result = slice_raw * slope + intercept

    return result.astype(np.float32)


# ---------------------------------------------------------------------------
# 4. Comparison utilities
# ---------------------------------------------------------------------------

def compare_arrays(mine: np.ndarray, reference: np.ndarray,
                   label: str, tolerance: float = 0.1) -> dict:
    """Compare two arrays and return error metrics + pass/fail."""
    result = {
        "label": label,
        "my_shape": mine.shape,
        "ref_shape": reference.shape,
        "shape_ok": mine.shape == reference.shape,
    }

    if not result["shape_ok"]:
        result["pass"] = False
        result["reason"] = "SHAPE MISMATCH"
        return result

    diff = np.abs(mine.astype(np.float64) - reference.astype(np.float64))
    ref_max = float(np.max(np.abs(reference)))

    result["max_err"] = float(np.max(diff))
    result["mean_err"] = float(np.mean(diff))
    result["ref_max"] = ref_max

    if ref_max > 0:
        result["max_err_pct"] = result["max_err"] / ref_max * 100.0
        result["mean_err_pct"] = result["mean_err"] / ref_max * 100.0
    else:
        result["max_err_pct"] = 0.0
        result["mean_err_pct"] = 0.0

    result["pass"] = result["max_err_pct"] < tolerance
    result["reason"] = "OK" if result["pass"] else f"max_err={result['max_err']:.4f} ({result['max_err_pct']:.6f}%)"
    return result


# ---------------------------------------------------------------------------
# 5. Main verification routine
# ---------------------------------------------------------------------------

def discover_exam_for_FoR(base_dicom_dir: str, for_suffix: str
                          ) -> tuple[str, str, str]:
    """Find which exam folder contains the FoR ending with for_suffix.

    Returns (exam_folder, ct_series_folder, pt102_series_folder).
    """
    for exam_name in os.listdir(base_dicom_dir):
        exam_path = os.path.join(base_dicom_dir, exam_name)
        if not os.path.isdir(exam_path) or "audit" in exam_name:
            continue
        for series_name in os.listdir(exam_path):
            series_path = os.path.join(exam_path, series_name)
            if not os.path.isdir(series_path):
                continue
            dcm_files = [f for f in os.listdir(series_path)
                         if os.path.isfile(os.path.join(series_path, f))]
            if not dcm_files:
                continue
            ds = pydicom.dcmread(
                os.path.join(series_path, dcm_files[0]),
                stop_before_pixels=True
            )
            if str(ds.FrameOfReferenceUID).endswith(for_suffix):
                ct_folder = None
                pt_folder = None
                for sn in os.listdir(exam_path):
                    sp = os.path.join(exam_path, sn)
                    if not os.path.isdir(sp):
                        continue
                    sample = pydicom.dcmread(
                        os.path.join(sp, os.listdir(sp)[0]),
                        stop_before_pixels=True
                    )
                    if sample.Modality == "CT" and sn.startswith("3."):
                        ct_folder = sp
                    elif sample.Modality == "PT" and sn.startswith("102."):
                        pt_folder = sp
                return exam_path, ct_folder, pt_folder
    raise FileNotFoundError(f"No exam found with FoR ending {for_suffix}")


def run_verification():
    """Main entry point: loads data, computes fusion, compares, prints results."""

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_dicom = os.path.join(project_root, "test-DICOM-data", "SomeFusion")
    results_dir = os.path.join(
        base_dicom, "fusion_audit_results_v2", "FoR13397883_CT3_PT102"
    )

    print("=" * 70)
    print("BLIND PET/CT FUSION VERIFICATION")
    print("Built independently from DICOM spec — no src/ code read")
    print("=" * 70)

    # --- Discover and load DICOM data ---
    print("\n[1] Discovering exam for FoR ...13397883 ...")
    _, ct_folder, pt_folder = discover_exam_for_FoR(base_dicom, "13397883")
    print(f"    CT folder: {os.path.basename(ct_folder)}")
    print(f"    PT folder: {os.path.basename(pt_folder)}")

    print("[2] Loading CT DICOM files ...")
    ct_datasets = load_dicom_series(ct_folder)
    ct_sorted = sort_by_z(ct_datasets)
    print(f"    Loaded {len(ct_sorted)} CT slices, "
          f"Z range: {float(ct_sorted[0].ImagePositionPatient[2]):.1f} "
          f"to {float(ct_sorted[-1].ImagePositionPatient[2]):.1f} mm")

    print("[3] Loading PT DICOM files ...")
    pt_datasets = load_dicom_series(pt_folder)
    pt_sorted = sort_by_z(pt_datasets)
    print(f"    Loaded {len(pt_sorted)} PT slices, "
          f"Z range: {float(pt_sorted[0].ImagePositionPatient[2]):.1f} "
          f"to {float(pt_sorted[-1].ImagePositionPatient[2]):.1f} mm")

    pt0 = pt_sorted[0]
    print(f"    PET dims: {pt0.Rows}x{pt0.Columns}, "
          f"RescaleSlope={getattr(pt0, 'RescaleSlope', 1)}, "
          f"RescaleIntercept={getattr(pt0, 'RescaleIntercept', 0)}")

    # --- CT slice indices to test ---
    # Determined from the saved results folder filenames
    test_indices = [72, 73, 173, 174, 186, 201, 203, 215]

    # Map indices to the label used in filenames
    def get_file_label(idx: int) -> str:
        """Determine the filename label for a CT index based on available files."""
        for suffix in ["near_pt", "between_pt"]:
            fname = f"ct{idx}_{suffix}_2d.npy"
            if os.path.exists(os.path.join(results_dir, fname)):
                return f"ct{idx}_{suffix}"
        return f"ct{idx}_near_pt"

    # --- Run fusion and compare ---
    print(f"\n[4] Computing fusion for {len(test_indices)} CT slice indices ...")
    print("    (2D = PET-native Z-interpolation, 3D = SimpleITK resample)\n")

    all_results = []

    for ct_idx in test_indices:
        ct_z = float(ct_sorted[ct_idx].ImagePositionPatient[2])
        label = get_file_label(ct_idx)
        print(f"  --- CT[{ct_idx}] z={ct_z:.1f} mm ({label}) ---")

        # 2D fusion
        my_2d = fusion_2d(ct_sorted, pt_sorted, ct_idx)
        ref_2d_path = os.path.join(results_dir, f"{label}_2d.npy")
        if os.path.exists(ref_2d_path):
            ref_2d = np.load(ref_2d_path)
            cmp_2d = compare_arrays(my_2d, ref_2d, f"CT[{ct_idx}] 2D vs app")
            all_results.append(cmp_2d)
            status = "PASS" if cmp_2d["pass"] else "FAIL"
            print(f"    2D: shape {my_2d.shape} vs {ref_2d.shape}, "
                  f"max_err={cmp_2d['max_err']:.4f} "
                  f"({cmp_2d['max_err_pct']:.6f}%), "
                  f"mean_err={cmp_2d['mean_err']:.6f} -> {status}")
        else:
            print(f"    2D: no reference file found at {ref_2d_path}")

        # Also compare against _gt if available
        gt_2d_path = os.path.join(results_dir, f"{label}_2d_gt.npy")
        if os.path.exists(gt_2d_path):
            gt_2d = np.load(gt_2d_path)
            cmp_2d_gt = compare_arrays(my_2d, gt_2d, f"CT[{ct_idx}] 2D vs gt")
            all_results.append(cmp_2d_gt)
            status = "PASS" if cmp_2d_gt["pass"] else "FAIL"
            print(f"    2D vs gt: max_err={cmp_2d_gt['max_err']:.4f} "
                  f"({cmp_2d_gt['max_err_pct']:.6f}%), "
                  f"mean_err={cmp_2d_gt['mean_err']:.6f} -> {status}")

        # 3D fusion
        my_3d = fusion_3d(ct_sorted, pt_sorted, ct_idx)
        ref_3d_path = os.path.join(results_dir, f"{label}_3d.npy")
        if os.path.exists(ref_3d_path):
            ref_3d = np.load(ref_3d_path)
            cmp_3d = compare_arrays(my_3d, ref_3d, f"CT[{ct_idx}] 3D vs app")
            all_results.append(cmp_3d)
            status = "PASS" if cmp_3d["pass"] else "FAIL"
            print(f"    3D: shape {my_3d.shape} vs {ref_3d.shape}, "
                  f"max_err={cmp_3d['max_err']:.4f} "
                  f"({cmp_3d['max_err_pct']:.6f}%), "
                  f"mean_err={cmp_3d['mean_err']:.6f} -> {status}")
        else:
            print(f"    3D: no reference file found at {ref_3d_path}")

        gt_3d_path = os.path.join(results_dir, f"{label}_3d_gt.npy")
        if os.path.exists(gt_3d_path):
            gt_3d = np.load(gt_3d_path)
            cmp_3d_gt = compare_arrays(my_3d, gt_3d, f"CT[{ct_idx}] 3D vs gt")
            all_results.append(cmp_3d_gt)
            status = "PASS" if cmp_3d_gt["pass"] else "FAIL"
            print(f"    3D vs gt: max_err={cmp_3d_gt['max_err']:.4f} "
                  f"({cmp_3d_gt['max_err_pct']:.6f}%), "
                  f"mean_err={cmp_3d_gt['mean_err']:.6f} -> {status}")

        print()

    # --- Summary table ---
    print("\n" + "=" * 70)
    print("BLIND VERIFICATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'Label':<35} {'Shape':>12} {'MaxErr':>12} {'MeanErr':>12} {'MaxErr%':>10} {'Result':>8}")
    print("-" * 70)

    passes = 0
    fails = 0
    for r in all_results:
        shape_str = f"{r['my_shape']}" if r["shape_ok"] else "MISMATCH"
        if r["pass"]:
            passes += 1
            result_str = "PASS"
        else:
            fails += 1
            result_str = "FAIL"
        print(f"{r['label']:<35} {shape_str:>12} "
              f"{r.get('max_err', -1):>12.4f} "
              f"{r.get('mean_err', -1):>12.6f} "
              f"{r.get('max_err_pct', -1):>9.6f}% "
              f"{result_str:>8}")

    print("-" * 70)
    print(f"Total: {passes} PASS, {fails} FAIL out of {len(all_results)} comparisons")

    if fails == 0:
        print("\n*** ALL COMPARISONS PASSED — App fusion matches blind implementation ***")
    else:
        print(f"\n*** {fails} COMPARISON(S) FAILED — see details above ***")

    print("=" * 70)
    return fails == 0


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
