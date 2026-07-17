"""
Fusion 3D Interpolator Comparison

Tests the 3D fusion path with different SimpleITK interpolation methods
(linear, nearest, cubic/bspline) and compares them against each other
and against an independent scipy-based ground truth.

Usage:
    python tests/fusion_audit_interpolator_comparison.py

Inputs:  test-DICOM-data/SomeFusion
Outputs: Printed comparison table and saved numpy arrays

Requirements: numpy, scipy, pydicom, SimpleITK, matplotlib
"""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

try:
    import pydicom
except ImportError:
    sys.exit("ERROR: pydicom not available.")

try:
    from scipy.ndimage import map_coordinates
except ImportError:
    sys.exit("ERROR: scipy not available.")

_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.dicom_processor import DICOMProcessor
from core.fusion_handler import FusionHandler


def _slice_location(ds) -> float | None:
    sl = getattr(ds, "SliceLocation", None)
    if sl is not None:
        try:
            return float(sl)
        except (ValueError, TypeError):
            pass
    ipp = getattr(ds, "ImagePositionPatient", None)
    if ipp is not None and len(ipp) >= 3:
        try:
            return float(ipp[2])
        except (ValueError, TypeError, IndexError):
            pass
    return None


def _pixel_spacing(ds) -> tuple[float, float]:
    ps = getattr(ds, "PixelSpacing", None)
    if ps and len(ps) >= 2:
        return float(ps[0]), float(ps[1])
    return 1.0, 1.0


def _ipp(ds) -> tuple[float, float, float]:
    ipp = getattr(ds, "ImagePositionPatient", None)
    if ipp and len(ipp) >= 3:
        return float(ipp[0]), float(ipp[1]), float(ipp[2])
    return 0.0, 0.0, 0.0


def _rescale(ds) -> tuple[float, float]:
    slope, intercept, _ = DICOMProcessor.get_rescale_parameters(ds)
    return (float(slope) if slope is not None else 1.0,
            float(intercept) if intercept is not None else 0.0)


def _rescaled_array(ds) -> np.ndarray:
    arr = ds.pixel_array.astype(np.float32)
    slope, intercept = _rescale(ds)
    return arr * slope + intercept


def scan_folder(folder: str):
    series_map: dict[str, list] = defaultdict(list)
    for root, _, files in os.walk(folder):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                ds = pydicom.dcmread(fpath)
                uid = getattr(ds, "SeriesInstanceUID", None)
                if uid and hasattr(ds, "pixel_array"):
                    series_map[uid].append(ds)
            except Exception:
                pass
    for uid in series_map:
        series_map[uid].sort(key=lambda d: _slice_location(d) or 0.0)

    for_groups: dict[str, dict[str, list]] = defaultdict(dict)
    for uid, datasets in series_map.items():
        for_uid = getattr(datasets[0], "FrameOfReferenceUID", "unknown")
        for_groups[for_uid][uid] = datasets
    return dict(for_groups)


def build_scipy_ground_truth(pt_sorted, ct_ds, order=1):
    """Independent ground truth using scipy with configurable interpolation order."""
    ct_z = _slice_location(ct_ds)
    if ct_z is None:
        return None

    pt_locs = [_slice_location(ds) for ds in pt_sorted]
    if len(pt_locs) < 2 or ct_z <= pt_locs[0] or ct_z >= pt_locs[-1]:
        return None

    ct_rows = int(getattr(ct_ds, "Rows", 512))
    ct_cols = int(getattr(ct_ds, "Columns", 512))
    ct_row_sp, ct_col_sp = _pixel_spacing(ct_ds)
    ct_ipp = _ipp(ct_ds)

    pt_row_sp, pt_col_sp = _pixel_spacing(pt_sorted[0])
    pt_ipp_0 = _ipp(pt_sorted[0])
    pt_slice_sp = abs(pt_locs[1] - pt_locs[0])

    # Build full 3D rescaled PET volume
    pt_vol = np.stack([_rescaled_array(ds) for ds in pt_sorted], axis=0)

    # For each CT pixel, compute its 3D position in PET voxel coordinates
    ct_col_grid, ct_row_grid = np.meshgrid(
        np.arange(ct_cols, dtype=np.float64),
        np.arange(ct_rows, dtype=np.float64),
    )

    patient_x = ct_ipp[0] + ct_col_grid * ct_col_sp
    patient_y = ct_ipp[1] + ct_row_grid * ct_row_sp

    pt_col_coords = (patient_x - pt_ipp_0[0]) / pt_col_sp
    pt_row_coords = (patient_y - pt_ipp_0[1]) / pt_row_sp
    pt_z_coord = (ct_z - pt_locs[0]) / pt_slice_sp

    # 3D interpolation using scipy
    z_coords = np.full_like(pt_row_coords, pt_z_coord)
    coords = np.array([z_coords.ravel(), pt_row_coords.ravel(), pt_col_coords.ravel()])
    resampled = map_coordinates(pt_vol, coords, order=order, mode="constant", cval=0.0)
    return resampled.reshape(ct_rows, ct_cols).astype(np.float32)


def run_app_3d(ct_sorted, pt_sorted, ct_idx, interp_method, handler_cache):
    """Run app's 3D path with a specific interpolation method, caching per method."""
    cache_key = (
        getattr(ct_sorted[0], "SeriesInstanceUID", "ct"),
        getattr(pt_sorted[0], "SeriesInstanceUID", "pt"),
        interp_method,
    )
    if cache_key not in handler_cache:
        handler = FusionHandler()
        handler.base_series_uid = cache_key[0]
        handler.overlay_series_uid = cache_key[1]
        handler.resampling_mode = "high_accuracy"
        handler.interpolation_method = interp_method
        handler_cache[cache_key] = handler
    handler = handler_cache[cache_key]

    # Clear volume cache when switching interpolators
    # (the cache key includes series UIDs but not interpolator,
    #  so we need separate handlers)
    return handler.interpolate_overlay_slice(ct_idx, ct_sorted, pt_sorted)


def compare_arrays(a, b, label_a, label_b):
    if a is None or b is None:
        return {"status": "SKIP (None)", "label": f"{label_a} vs {label_b}"}
    if a.shape != b.shape:
        return {"status": f"SHAPE MISMATCH {a.shape} vs {b.shape}",
                "label": f"{label_a} vs {label_b}"}
    diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
    a_max = float(np.max(np.abs(a)))
    return {
        "label": f"{label_a} vs {label_b}",
        "max_diff": float(diff.max()),
        "mean_diff": float(diff.mean()),
        "pct_of_max": float(diff.max() / a_max * 100) if a_max > 0 else 0,
        "nonzero_diffs": int(np.count_nonzero(diff)),
        "a_max": a_max,
        "a_mean": float(np.mean(a)),
        "a_nonzero": int(np.count_nonzero(a)),
        "status": "OK",
    }


def main():
    folder = "test-DICOM-data/SomeFusion"
    print("Fusion 3D Interpolator Comparison")
    print_redacted(f"Data: {folder}\n")

    t0 = time.time()
    for_groups = scan_folder(folder)
    print(f"Loaded in {time.time() - t0:.1f}s, {len(for_groups)} FoR groups\n")

    # Pick the first FoR group with both CT and PT
    ct_sorted = None
    pt_sorted = None
    for _for_uid, series_dict in for_groups.items():
        for _uid, datasets in series_dict.items():
            mod = getattr(datasets[0], "Modality", "")
            if mod == "CT" and ct_sorted is None:
                ct_sorted = datasets
            elif mod in ("PT", "NM") and pt_sorted is None:
                pt_sorted = datasets
        if ct_sorted and pt_sorted:
            break

    if not ct_sorted or not pt_sorted:
        sys.exit("No CT+PT pair found")

    print(f"CT: {len(ct_sorted)} slices, PT: {len(pt_sorted)} slices")
    print(f"PT pixel spacing: {_pixel_spacing(pt_sorted[0])}")
    print(f"PT RescaleSlope: {_rescale(pt_sorted[0])[0]}")

    # Find a few interesting CT slices
    pt_locs = [_slice_location(ds) for ds in pt_sorted]
    hot_indices = []
    for i, ds in enumerate(pt_sorted):
        arr = _rescaled_array(ds)
        hot_indices.append((i, float(np.percentile(arr, 99))))
    hot_indices.sort(key=lambda x: x[1], reverse=True)

    test_pt_indices = [hot_indices[0][0], hot_indices[5][0], hot_indices[15][0]]
    test_ct_indices = []
    for pt_idx in test_pt_indices:
        pt_z = pt_locs[pt_idx]
        best_ct = min(range(len(ct_sorted)),
                      key=lambda i: abs((_slice_location(ct_sorted[i]) or 0) - pt_z))
        test_ct_indices.append(best_ct)
        # Also add one offset by half a PT slice spacing
        offset_z = pt_z + abs(pt_locs[1] - pt_locs[0]) * 0.5
        best_ct_offset = min(range(len(ct_sorted)),
                             key=lambda i: abs((_slice_location(ct_sorted[i]) or 0) - offset_z))
        if best_ct_offset != best_ct:
            test_ct_indices.append(best_ct_offset)

    test_ct_indices = sorted(set(test_ct_indices))
    print(f"\nTesting CT slices: {test_ct_indices}")

    interpolators = ["linear", "nearest", "cubic"]
    scipy_orders = {"linear": 1, "nearest": 0, "cubic": 3}
    handler_cache: dict = {}

    all_comparisons = []

    for ct_idx in test_ct_indices:
        ct_z = _slice_location(ct_sorted[ct_idx])
        print(f"\n--- CT[{ct_idx}] z={ct_z:.1f}mm ---")

        results = {}
        for interp in interpolators:
            print(f"  Running app 3D ({interp})...", end="", flush=True)
            arr = run_app_3d(ct_sorted, pt_sorted, ct_idx, interp, handler_cache)
            if arr is not None:
                print(f" shape={arr.shape}, max={arr.max():.1f}, mean={arr.mean():.1f}")
            else:
                print(" None!")
            results[f"app_{interp}"] = arr

            print(f"  Running scipy ({interp}, order={scipy_orders[interp]})...", end="", flush=True)
            gt = build_scipy_ground_truth(pt_sorted, ct_sorted[ct_idx], order=scipy_orders[interp])
            if gt is not None:
                print(f" shape={gt.shape}, max={gt.max():.1f}, mean={gt.mean():.1f}")
            else:
                print(" None!")
            results[f"scipy_{interp}"] = gt

        # Cross-comparisons
        comparisons = []

        # App vs scipy (same interpolator)
        for interp in interpolators:
            comp = compare_arrays(results[f"app_{interp}"], results[f"scipy_{interp}"],
                                  f"app_{interp}", f"scipy_{interp}")
            comp["ct_idx"] = ct_idx
            comp["ct_z"] = ct_z
            comp["type"] = "app_vs_scipy"
            comparisons.append(comp)

        # App interpolators vs each other
        for i, a in enumerate(interpolators):
            for b in interpolators[i+1:]:
                comp = compare_arrays(results[f"app_{a}"], results[f"app_{b}"],
                                      f"app_{a}", f"app_{b}")
                comp["ct_idx"] = ct_idx
                comp["ct_z"] = ct_z
                comp["type"] = "app_cross"
                comparisons.append(comp)

        # Print results
        for c in comparisons:
            if c["status"] == "OK":
                print(f"  {c['label']:35s} max_diff={c['max_diff']:10.4f} "
                      f"({c['pct_of_max']:.6f}% of max) "
                      f"mean_diff={c['mean_diff']:.4f}")
            else:
                print(f"  {c['label']:35s} {c['status']}")

        all_comparisons.extend(comparisons)

    # Summary
    print(f"\n{'='*80}")
    print("INTERPOLATOR COMPARISON SUMMARY")
    print(f"{'='*80}")
    print(f"{'CT':>4} {'CT_z':>8} {'Type':<14} {'Comparison':<36} "
          f"{'MaxDiff':>10} {'%ofMax':>10} {'Status':>8}")
    print("-" * 100)

    for c in all_comparisons:
        if c["status"] == "OK":
            pct = c["pct_of_max"]
            verdict = "PASS" if pct < 1.0 else ("WARN" if pct < 5.0 else "FAIL")
            print(f"{c['ct_idx']:>4} {c['ct_z']:>8.1f} {c['type']:<14} {c['label']:<36} "
                  f"{c['max_diff']:>10.4f} {pct:>9.6f}% {verdict:>8}")
        else:
            print(f"{c.get('ct_idx','?'):>4} {c.get('ct_z',0):>8.1f} {c.get('type','?'):<14} "
                  f"{c['label']:<36} {'':>10} {'':>10} {c['status']:>8}")

    print(f"\nElapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
