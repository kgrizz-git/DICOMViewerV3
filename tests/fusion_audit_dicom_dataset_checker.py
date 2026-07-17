"""
Fusion Audit: DICOM Dataset Checker for PET/CT Fusion Verification.

Run this on a folder containing PET/CT DICOM files to check:
1. Whether PET has per-slice varying RescaleSlope (triggers Issue 2)
2. Orientation of both series (axial/oblique/sagittal -- triggers Issues 1, 3)
3. Spatial alignment metadata quality
4. Frame of Reference UID consistency

Usage:
    python tests/fusion_audit_dicom_dataset_checker.py <path_to_dicom_folder>

The script recursively scans the folder for DICOM files and groups them by series.
"""
import os
import sys
from collections import defaultdict

import numpy as np

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

try:
    import pydicom
except ImportError:
    print("ERROR: pydicom not available.")
    raise SystemExit(1) from None


def scan_dicom_folder(folder_path):
    """Recursively find and load all DICOM files, group by SeriesInstanceUID."""
    series_dict = defaultdict(list)
    file_count = 0
    error_count = 0

    for root, _dirs, files in os.walk(folder_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                ds = pydicom.dcmread(fpath, stop_before_pixels=True)
                series_uid = getattr(ds, 'SeriesInstanceUID', None)
                if series_uid:
                    series_dict[series_uid].append(ds)
                    file_count += 1
            except Exception:
                error_count += 1

    print(f"Scanned: {file_count} DICOM files in {len(series_dict)} series ({error_count} non-DICOM files skipped)")
    return dict(series_dict)


def analyze_series(series_uid, datasets):
    """Analyze a single series for fusion-relevant properties."""
    if not datasets:
        return

    ds0 = datasets[0]
    modality = getattr(ds0, 'Modality', 'Unknown')
    series_desc = getattr(ds0, 'SeriesDescription', 'No description')
    series_num = getattr(ds0, 'SeriesNumber', '?')
    num_slices = len(datasets)

    print(f"\n{'-' * 60}")
    print(f"Series {series_num}: {modality} - {series_desc}")
    print_redacted(f"  UID: {series_uid[:40]}...")
    print(f"  Slices: {num_slices}")

    # Frame of Reference
    for_uid = getattr(ds0, 'FrameOfReferenceUID', None)
    if for_uid:
        print_redacted(f"  FrameOfReferenceUID: {for_uid[:40]}...")
    else:
        print_redacted("  FrameOfReferenceUID: MISSING")

    # Orientation
    iop = getattr(ds0, 'ImageOrientationPatient', None)
    if iop and len(iop) >= 6:
        row_cos = np.array([float(iop[0]), float(iop[1]), float(iop[2])])
        col_cos = np.array([float(iop[3]), float(iop[4]), float(iop[5])])
        # Determine orientation type
        is_axial = (abs(row_cos[0]) > 0.9 and abs(col_cos[1]) > 0.9)
        is_sagittal = (abs(row_cos[1]) > 0.9 and abs(col_cos[2]) > 0.9)
        is_coronal = (abs(row_cos[0]) > 0.9 and abs(col_cos[2]) > 0.9)

        if is_axial:
            orient_label = "AXIAL"
        elif is_sagittal:
            orient_label = "SAGITTAL"
        elif is_coronal:
            orient_label = "CORONAL"
        else:
            orient_label = "OBLIQUE"

        print(f"  Orientation: {orient_label}")
        print(f"    Row cosines: [{row_cos[0]:.4f}, {row_cos[1]:.4f}, {row_cos[2]:.4f}]")
        print(f"    Col cosines: [{col_cos[0]:.4f}, {col_cos[1]:.4f}, {col_cos[2]:.4f}]")

        if orient_label == "OBLIQUE":
            print("    *** OBLIQUE ORIENTATION DETECTED - Issues 1, 3 are relevant ***")
        if orient_label in ("SAGITTAL", "CORONAL"):
            print("    *** NON-AXIAL ORIENTATION - Issues 1, 3 will cause errors in fusion ***")
    else:
        print("  Orientation: MISSING (ImageOrientationPatient not present)")

    # Pixel spacing
    ps = getattr(ds0, 'PixelSpacing', None)
    if ps and len(ps) >= 2:
        print(f"  Pixel spacing: {float(ps[0]):.4f} x {float(ps[1]):.4f} mm")
    else:
        print("  Pixel spacing: MISSING")

    # Matrix size
    rows = getattr(ds0, 'Rows', None)
    cols = getattr(ds0, 'Columns', None)
    if rows and cols:
        print(f"  Matrix: {int(rows)} x {int(cols)}")

    # Slice spacing and IPP
    ipp0 = getattr(ds0, 'ImagePositionPatient', None)
    if ipp0:
        print(f"  First IPP: [{float(ipp0[0]):.2f}, {float(ipp0[1]):.2f}, {float(ipp0[2]):.2f}]")

    # Rescale parameters -- check all slices for consistency
    slopes = []
    intercepts = []
    for ds in datasets:
        slope = getattr(ds, 'RescaleSlope', None)
        intercept = getattr(ds, 'RescaleIntercept', None)
        if slope is not None:
            slopes.append(float(slope))
        if intercept is not None:
            intercepts.append(float(intercept))

    if slopes:
        unique_slopes = len({round(s, 6) for s in slopes})
        if unique_slopes == 1:
            print(f"  RescaleSlope: {slopes[0]:.6f} (constant across all slices)")
        else:
            print("  RescaleSlope: VARIES across slices!")
            print(f"    Range: [{min(slopes):.6f}, {max(slopes):.6f}]")
            print(f"    Unique values: {unique_slopes}")
            print("    *** ISSUE 2 IS RELEVANT: Per-slice RescaleSlope detected ***")
            print(f"    *** 3D path will use slope from slice 0 ({slopes[0]:.6f}) for ALL slices ***")
    else:
        print("  RescaleSlope: Not present")

    if intercepts:
        unique_intercepts = len({round(i, 6) for i in intercepts})
        if unique_intercepts == 1:
            print(f"  RescaleIntercept: {intercepts[0]:.6f} (constant)")
        else:
            print(f"  RescaleIntercept: VARIES ({min(intercepts):.6f} to {max(intercepts):.6f})")

    # Slice location analysis
    locations = []
    for ds in datasets:
        sl = getattr(ds, 'SliceLocation', None)
        if sl is not None:
            locations.append(float(sl))
        else:
            ipp = getattr(ds, 'ImagePositionPatient', None)
            if ipp and len(ipp) >= 3:
                locations.append(float(ipp[2]))

    if len(locations) >= 2:
        locations_sorted = sorted(locations)
        spacings = [locations_sorted[i+1] - locations_sorted[i] for i in range(len(locations_sorted)-1)]
        avg_spacing = np.mean(spacings)
        std_spacing = np.std(spacings)
        print(f"  Slice spacing: {avg_spacing:.3f} +/- {std_spacing:.4f} mm ({len(locations)} slices)")

        duplicates = sum(1 for s in spacings if abs(s) < 0.01)
        if duplicates > 0:
            print(f"    *** {duplicates} duplicate locations found ***")

    return {
        'modality': modality,
        'for_uid': for_uid,
        'orientation': orient_label if iop else 'UNKNOWN',
        'has_variable_slope': (unique_slopes > 1) if slopes else False,
        'num_slices': num_slices,
    }


def check_fusion_compatibility(series_analyses, series_dict):
    """Check fusion compatibility between series pairs."""
    print(f"\n{'=' * 60}")
    print("FUSION COMPATIBILITY ANALYSIS")
    print('=' * 60)

    # Group by FrameOfReferenceUID
    for_groups = defaultdict(list)
    for uid, info in series_analyses.items():
        if info and info.get('for_uid'):
            for_groups[info['for_uid']].append((uid, info))

    for for_uid, members in for_groups.items():
        if len(members) < 2:
            continue

        print_redacted(f"\nFrame of Reference: {for_uid[:40]}...")
        pet_series = [(uid, info) for uid, info in members if info['modality'] in ('PT', 'NM')]
        anat_series = [(uid, info) for uid, info in members if info['modality'] in ('CT', 'MR')]

        for _pet_uid, pet_info in pet_series:
            for _anat_uid, anat_info in anat_series:
                print(f"\n  Pair: {anat_info['modality']} + {pet_info['modality']}")
                print(f"  Orientations: {anat_info['orientation']} / {pet_info['orientation']}")

                issues = []
                if pet_info.get('has_variable_slope'):
                    issues.append("Issue 2: PET has variable RescaleSlope - 3D path will be inaccurate")
                if pet_info['orientation'] != 'AXIAL' or anat_info['orientation'] != 'AXIAL':
                    issues.append("Issues 1,3: Non-axial orientation - direction matrix and offset formula have bugs")

                if issues:
                    print("  WARNINGS:")
                    for issue in issues:
                        print(f"    - {issue}")
                else:
                    print("  OK: Standard axial pair - known issues do not affect this configuration")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/fusion_audit_dicom_dataset_checker.py <path_to_dicom_folder>")
        print("\nThis script checks DICOM datasets for fusion-relevant properties.")
        print("Provide a folder containing PET/CT DICOM files to analyze.")
        return

    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path):
        print_redacted(f"ERROR: '{folder_path}' is not a valid directory.")
        return

    print(f"\n{'=' * 60}")
    print("FUSION AUDIT: DICOM Dataset Checker")
    print(f"{'=' * 60}")
    print_redacted(f"Scanning: {folder_path}\n")

    series_dict = scan_dicom_folder(folder_path)

    if not series_dict:
        print("No DICOM series found.")
        return

    series_analyses = {}
    for uid, datasets in sorted(series_dict.items(), key=lambda x: getattr(x[1][0], 'SeriesNumber', 999)):
        info = analyze_series(uid, datasets)
        series_analyses[uid] = info

    check_fusion_compatibility(series_analyses, series_dict)

    print(f"\n{'=' * 60}")
    print("ANALYSIS COMPLETE")
    print(f"{'=' * 60}")
    print("\nTo use with real PET/CT data, run:")
    print("  python tests/fusion_audit_dicom_dataset_checker.py <path_to_PET_CT_folder>")


if __name__ == "__main__":
    main()
