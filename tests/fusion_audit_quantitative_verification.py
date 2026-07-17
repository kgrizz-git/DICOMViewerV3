"""
Fusion Quantitative Verification (v2)

Compares the 2D and 3D fusion overlay pipelines against independently computed
ground-truth PET overlays for CT+PT pairs sharing a Frame of Reference.

Key improvements over v1:
- 2D path comparison in *native PET dimensions* (no circular resizing)
- Explicit testing of CT positions that fall *between* PET slices
- 3D volume caching to avoid re-building volume per slice
- Runs all dataset pairs

For each pair the script:
1.  Identifies 5 high-activity PET slices.
2.  Tests CT slices both near AND midway between PET positions.
3.  Builds ground truth independently using scipy map_coordinates.
4.  Runs the app's FusionHandler.interpolate_overlay_slice in both modes.
5.  Computes per-pixel error maps and aggregate statistics.
6.  Tests through-plane shifts to detect systematic Z misregistration.
7.  Saves numpy arrays, heatmap PNGs, and a shift-vs-error curve.

Usage:
    python tests/fusion_audit_quantitative_verification.py <dicom_folder> <private_output_root>

Inputs:  Folder containing PET/CT DICOM files.
Outputs: Results below an explicit private output root outside the source checkout.

Requirements: numpy, scipy, pydicom, SimpleITK, matplotlib, PIL (Pillow)
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from scripts.privacy_console import print_structural_event
except ModuleNotFoundError:
    import privacy_console  # pyright: ignore[reportImplicitRelativeImport]

    print_structural_event = privacy_console.print_structural_event

try:
    import pydicom
except ImportError:
    sys.exit("ERROR: pydicom not available.")

try:
    from scipy.ndimage import map_coordinates
except ImportError:
    sys.exit("ERROR: scipy not available (pip install scipy).")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("ERROR: matplotlib not available.")

# ---------------------------------------------------------------------------
# Add src/ to path so we can import the app's fusion code
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from core.dicom_processor import DICOMProcessor
from core.fusion_handler import FusionHandler
from utils.privacy.safe_storage import (
    assert_safe_internal_path,
    ensure_private_directory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Scan and group
# ---------------------------------------------------------------------------

def scan_folder(folder: str) -> dict[str, dict[str, list]]:
    """Return {frame_of_ref_uid: {series_uid: [datasets sorted by location]}}."""
    series_map: dict[str, list] = defaultdict(list)
    n = 0
    for root, _, files in os.walk(folder):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                ds = pydicom.dcmread(fpath)
                uid = getattr(ds, "SeriesInstanceUID", None)
                if uid and hasattr(ds, "pixel_array"):
                    series_map[uid].append(ds)
                    n += 1
            except Exception:
                pass
    print_structural_event(
        "fusion.load_summary",
        metrics={"instance_count": n, "series_count": len(series_map)},
    )

    for uid in series_map:
        series_map[uid].sort(key=lambda d: _slice_location(d) or 0.0)

    for_groups: dict[str, dict[str, list]] = defaultdict(dict)
    for uid, datasets in series_map.items():
        for_uid = getattr(datasets[0], "FrameOfReferenceUID", "unknown")
        for_groups[for_uid][uid] = datasets

    return dict(for_groups)

# ---------------------------------------------------------------------------
# Ground-truth: Z-interpolated rescaled PET slice in PET native dimensions
# ---------------------------------------------------------------------------

def build_ground_truth_pet_native(
    pt_datasets_sorted: list,
    ct_z: float,
    z_shift_mm: float = 0.0,
) -> np.ndarray | None:
    """Build ground-truth rescaled PET at a given Z in PET native pixel grid.

    Z-interpolates between bracketing PET slices. Returns array in PET
    dimensions (rows x cols), NOT CT dimensions.
    """
    target_z = ct_z + z_shift_mm

    pt_locs = []
    for ds in pt_datasets_sorted:
        loc = _slice_location(ds)
        if loc is not None:
            pt_locs.append(loc)

    if len(pt_locs) < 2:
        return None

    if target_z <= pt_locs[0] or target_z >= pt_locs[-1]:
        return None

    idx_above = None
    for i, loc in enumerate(pt_locs):
        if loc >= target_z:
            idx_above = i
            break
    if idx_above is None or idx_above == 0:
        return None

    idx_below = idx_above - 1
    z_below = pt_locs[idx_below]
    z_above = pt_locs[idx_above]

    dz = z_above - z_below
    if abs(dz) < 1e-6:
        w = 0.0
    else:
        w = (target_z - z_below) / dz
    w = float(np.clip(w, 0.0, 1.0))

    pt_arr_below = _rescaled_array(pt_datasets_sorted[idx_below])
    pt_arr_above = _rescaled_array(pt_datasets_sorted[idx_above])

    if pt_arr_below.shape != pt_arr_above.shape:
        return None

    return (pt_arr_below * (1.0 - w) + pt_arr_above * w).astype(np.float32)


def build_ground_truth_on_ct_grid(
    pt_datasets_sorted: list,
    ct_ds,
    z_shift_mm: float = 0.0,
) -> np.ndarray | None:
    """Build ground-truth rescaled PET resampled onto the CT pixel grid.

    Uses scipy map_coordinates for in-plane resampling (independent of app code).
    """
    ct_z = _slice_location(ct_ds)
    if ct_z is None:
        return None
    target_z = ct_z + z_shift_mm

    pt_locs = [_slice_location(ds) for ds in pt_datasets_sorted]
    if len(pt_locs) < 2 or target_z <= pt_locs[0] or target_z >= pt_locs[-1]:
        return None

    idx_above = next((i for i, loc in enumerate(pt_locs) if loc >= target_z), None)
    if idx_above is None or idx_above == 0:
        return None

    idx_below = idx_above - 1
    dz = pt_locs[idx_above] - pt_locs[idx_below]
    w = (target_z - pt_locs[idx_below]) / dz if abs(dz) > 1e-6 else 0.0
    w = float(np.clip(w, 0.0, 1.0))

    pt_arr_below = _rescaled_array(pt_datasets_sorted[idx_below])
    pt_arr_above = _rescaled_array(pt_datasets_sorted[idx_above])
    if pt_arr_below.shape != pt_arr_above.shape:
        return None
    pt_interp = pt_arr_below * (1.0 - w) + pt_arr_above * w

    ct_rows = int(getattr(ct_ds, "Rows", 512))
    ct_cols = int(getattr(ct_ds, "Columns", 512))
    ct_row_sp, ct_col_sp = _pixel_spacing(ct_ds)
    ct_ipp = _ipp(ct_ds)

    pt_ds_ref = pt_datasets_sorted[idx_below]
    pt_row_sp, pt_col_sp = _pixel_spacing(pt_ds_ref)
    pt_ipp = _ipp(pt_ds_ref)

    ct_col_grid, ct_row_grid = np.meshgrid(
        np.arange(ct_cols, dtype=np.float64),
        np.arange(ct_rows, dtype=np.float64),
    )

    patient_x = ct_ipp[0] + ct_col_grid * ct_col_sp
    patient_y = ct_ipp[1] + ct_row_grid * ct_row_sp

    pt_col_coords = (patient_x - pt_ipp[0]) / pt_col_sp
    pt_row_coords = (patient_y - pt_ipp[1]) / pt_row_sp

    coords = np.array([pt_row_coords.ravel(), pt_col_coords.ravel()])
    resampled = map_coordinates(pt_interp, coords, order=1, mode="constant", cval=0.0)
    return resampled.reshape(ct_rows, ct_cols).astype(np.float32)

# ---------------------------------------------------------------------------
# Select slices to test
# ---------------------------------------------------------------------------

def find_hot_slices(pt_datasets_sorted: list, n: int = 5) -> list[int]:
    """Return indices of n well-spaced high-activity PET slices."""
    stats = []
    for i, ds in enumerate(pt_datasets_sorted):
        arr = _rescaled_array(ds)
        p99 = float(np.percentile(arr, 99))
        stats.append((i, p99))

    stats.sort(key=lambda x: x[1], reverse=True)

    selected = []
    used = set()
    for idx, _ in stats:
        if idx in used:
            continue
        selected.append(idx)
        for j in range(max(0, idx - 10), min(len(pt_datasets_sorted), idx + 11)):
            used.add(j)
        if len(selected) >= n:
            break

    selected.sort()
    return selected


def select_ct_slices(ct_sorted, pt_sorted, hot_pt_indices, n_near=2, n_between=2):
    """Select CT slices that include positions both ON and BETWEEN PET slices.

    Returns list of (ct_idx, ct_z, position_type) where position_type is
    'near_pt' or 'between_pt'.
    """
    pt_locs = [_slice_location(ds) for ds in pt_sorted]
    ct_locs = [(i, _slice_location(ds)) for i, ds in enumerate(ct_sorted)]

    results = []
    seen_ct_idx = set()

    for pt_idx in hot_pt_indices:
        pt_z = pt_locs[pt_idx]
        if pt_z is None:
            continue

        # Near: CT slices closest to this PT position
        dists = [(i, z, abs(z - pt_z)) for i, z in ct_locs if z is not None]
        dists.sort(key=lambda x: x[2])
        for i, z, d in dists[:n_near]:
            if i not in seen_ct_idx:
                results.append((i, z, "near_pt", pt_idx, d))
                seen_ct_idx.add(i)

        # Between: CT slices midway between this PT slice and its neighbors
        if pt_idx > 0 and pt_idx < len(pt_locs) - 1:
            midpoint_above = (pt_z + pt_locs[pt_idx + 1]) / 2.0
            midpoint_below = (pt_z + pt_locs[pt_idx - 1]) / 2.0
            for midpoint in [midpoint_above, midpoint_below]:
                dists_mid = [(i, z, abs(z - midpoint)) for i, z in ct_locs if z is not None]
                dists_mid.sort(key=lambda x: x[2])
                if dists_mid and dists_mid[0][0] not in seen_ct_idx:
                    i, z, d = dists_mid[0]
                    results.append((i, z, "between_pt", pt_idx, d))
                    seen_ct_idx.add(i)

    return results

# ---------------------------------------------------------------------------
# Run app fusion paths
# ---------------------------------------------------------------------------

def run_app_fusion_2d(ct_datasets, pt_datasets, ct_idx: int) -> np.ndarray | None:
    """Run the app's 2D (fast) fusion path. Returns overlay in PET native dims."""
    handler = FusionHandler()
    handler.base_series_uid = getattr(ct_datasets[0], "SeriesInstanceUID", "ct")
    handler.overlay_series_uid = getattr(pt_datasets[0], "SeriesInstanceUID", "pt")
    handler.resampling_mode = "fast"
    handler.interpolation_method = "linear"
    return handler.interpolate_overlay_slice(ct_idx, ct_datasets, pt_datasets)


def run_app_fusion_3d(ct_datasets, pt_datasets, ct_idx: int,
                      handler_cache: dict) -> np.ndarray | None:
    """Run the app's 3D fusion path. Reuses handler to leverage volume cache."""
    cache_key = (
        getattr(ct_datasets[0], "SeriesInstanceUID", "ct"),
        getattr(pt_datasets[0], "SeriesInstanceUID", "pt"),
    )
    if cache_key not in handler_cache:
        handler = FusionHandler()
        handler.base_series_uid = cache_key[0]
        handler.overlay_series_uid = cache_key[1]
        handler.resampling_mode = "high_accuracy"
        handler.interpolation_method = "linear"
        handler_cache[cache_key] = handler
    handler = handler_cache[cache_key]
    return handler.interpolate_overlay_slice(ct_idx, ct_datasets, pt_datasets)

# ---------------------------------------------------------------------------
# Error analysis
# ---------------------------------------------------------------------------

def compute_errors(
    fusion_arr: np.ndarray,
    ground_truth: np.ndarray,
    activity_threshold_frac: float = 0.10,
) -> dict:
    if fusion_arr.shape != ground_truth.shape:
        return {"error": f"shape mismatch: fusion {fusion_arr.shape} vs gt {ground_truth.shape}"}

    gt_max = float(np.max(np.abs(ground_truth)))
    if gt_max < 1e-6:
        return {"error": "ground truth is all zeros"}

    mask = np.abs(ground_truth) > activity_threshold_frac * gt_max
    n_active = int(np.sum(mask))
    if n_active < 10:
        return {"error": f"too few active pixels ({n_active})"}

    abs_err = np.abs(fusion_arr - ground_truth)
    rel_err = abs_err / (np.abs(ground_truth) + 1e-10)
    active_abs = abs_err[mask]
    active_rel = rel_err[mask]

    return {
        "n_active_pixels": n_active,
        "gt_max": float(gt_max),
        "fusion_shape": list(fusion_arr.shape),
        "gt_shape": list(ground_truth.shape),
        "abs_mean": float(np.mean(active_abs)),
        "abs_max": float(np.max(active_abs)),
        "abs_p95": float(np.percentile(active_abs, 95)),
        "rel_mean_pct": float(np.mean(active_rel) * 100),
        "rel_max_pct": float(np.max(active_rel) * 100),
        "rel_p95_pct": float(np.percentile(active_rel, 95) * 100),
        "abs_mean_pct_of_max": float(np.mean(active_abs) / gt_max * 100),
        "abs_max_pct_of_max": float(np.max(active_abs) / gt_max * 100),
    }

# ---------------------------------------------------------------------------
# Visualization helpers
# ---------------------------------------------------------------------------

def save_grayscale_png(arr: np.ndarray, path: str):
    vmin, vmax = float(np.min(arr)), float(np.max(arr))
    if vmax > vmin:
        normed = ((arr - vmin) / (vmax - vmin) * 255).astype(np.uint8)
    else:
        normed = np.zeros_like(arr, dtype=np.uint8)
    from PIL import Image
    Image.fromarray(normed, "L").save(path)


def save_error_heatmap(arr: np.ndarray, path: str, vmax: float | None = None):
    fig, ax = plt.subplots(1, 1, figsize=(6, 6))
    im = ax.imshow(arr, cmap="hot", vmin=0, vmax=vmax)
    plt.colorbar(im, ax=ax, label="Absolute Error")
    ax.set_title("Error Heatmap")
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)


def save_shift_curve(shifts_mm, errors, path: str, label: str):
    fig, ax = plt.subplots(1, 1, figsize=(7, 4))
    ax.plot(shifts_mm, errors, "o-", linewidth=2, markersize=8)
    ax.set_xlabel("Through-plane shift (mm)")
    ax.set_ylabel("Mean abs error (high-activity region)")
    ax.set_title(f"Shift Analysis: {label}")
    ax.axvline(0, color="gray", linestyle="--", alpha=0.5, label="Nominal (0 shift)")
    min_idx = int(np.argmin(errors))
    ax.axvline(shifts_mm[min_idx], color="red", linestyle="--", alpha=0.7,
               label=f"Min error at {shifts_mm[min_idx]:+.1f} mm")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)

# ---------------------------------------------------------------------------
# Main per-pair processing
# ---------------------------------------------------------------------------

def _setup_pair(ct_datasets, pt_datasets, pair_label, out_dir):
    pair_dir = out_dir / pair_label
    pair_dir.mkdir(parents=True, exist_ok=True)
    ct_sorted = sorted(ct_datasets, key=lambda d: _slice_location(d) or 0.0)
    pt_sorted = sorted(pt_datasets, key=lambda d: _slice_location(d) or 0.0)
    return pair_dir, ct_sorted, pt_sorted

def _get_dataset_info(ds, default_shape):
    slope, intercept = _rescale(ds)
    spacing = _pixel_spacing(ds)
    rows = int(getattr(ds, "Rows", default_shape[0]))
    cols = int(getattr(ds, "Columns", default_shape[1]))
    return {"slope": slope, "intercept": intercept, "spacing": spacing, "rows": rows, "cols": cols}

def process_pair(
    ct_datasets: list,
    pt_datasets: list,
    pair_label: str,
    out_dir: Path,
):
    """Run full verification for one CT+PT pair."""
    pair_dir, ct_sorted, pt_sorted = _setup_pair(ct_datasets, pt_datasets, pair_label, out_dir)
    pt_info = _get_dataset_info(pt_sorted[0], (128, 128))
    ct_info = _get_dataset_info(ct_sorted[0], (512, 512))

    pt_slope, _pt_intercept = pt_info["slope"], pt_info["intercept"]
    pt_sp, ct_sp = pt_info["spacing"], ct_info["spacing"]
    pt_rows, pt_cols = pt_info["rows"], pt_info["cols"]
    ct_rows, ct_cols = ct_info["rows"], ct_info["cols"]

    pt_locs = [_slice_location(ds) for ds in pt_sorted]
    pt_slice_spacing = abs(pt_locs[1] - pt_locs[0]) if len(pt_locs) >= 2 else 3.0

    print(f"\n{'='*70}")
    print(f"Pair: {pair_label}")
    print_structural_event(
        "fusion.series_summary",
        category="ct",
        metrics={
            "slice_count": len(ct_sorted),
            "rows": ct_rows,
            "columns": ct_cols,
            "pixel_spacing_mm": ct_sp[0],
        },
    )
    print_structural_event(
        "fusion.series_summary",
        category="pt",
        metrics={
            "slice_count": len(pt_sorted),
            "rows": pt_rows,
            "columns": pt_cols,
            "pixel_spacing_mm": pt_sp[0],
            "slope": pt_slope,
            "slice_spacing_mm": pt_slice_spacing,
        },
    )

    # Step 1: find hot slices
    hot_indices = find_hot_slices(pt_sorted, n=5)
    print(f"  Hot PT slices (sorted idx): {hot_indices}")
    for hi in hot_indices:
        loc = _slice_location(pt_sorted[hi])
        arr = _rescaled_array(pt_sorted[hi])
        print(f"    PT[{hi}]: z={loc:.1f}mm, max={np.max(arr):.1f}, p99={np.percentile(arr, 99):.1f}")

    # Step 2: select CT slices (near AND between PET positions)
    ct_slices = select_ct_slices(ct_sorted, pt_sorted, hot_indices, n_near=2, n_between=2)
    near_count = sum(1 for s in ct_slices if s[2] == "near_pt")
    between_count = sum(1 for s in ct_slices if s[2] == "between_pt")
    print(f"  Selected {len(ct_slices)} CT slices: {near_count} near PT, {between_count} between PT")

    # Shift values for shift analysis
    shifts_mm = [-pt_slice_spacing, -pt_slice_spacing / 2, 0.0,
                 pt_slice_spacing / 2, pt_slice_spacing]

    handler_cache_3d: dict = {}
    all_results = []

    for si, (ct_idx, ct_z, pos_type, ref_pt_idx, dist_to_pt) in enumerate(ct_slices):
        slice_label = f"ct{ct_idx}_{pos_type}"
        print(f"\n    [{si+1}/{len(ct_slices)}] CT[{ct_idx}] z={ct_z:.1f}mm "
              f"({pos_type}, {dist_to_pt:.1f}mm from PT[{ref_pt_idx}]): ", end="", flush=True)

        result = {
            "pair": pair_label,
            "ct_idx": ct_idx,
            "ct_z": ct_z,
            "position_type": pos_type,
            "ref_pt_idx": ref_pt_idx,
            "dist_to_nearest_pt_mm": round(dist_to_pt, 2),
            "slice_label": slice_label,
        }

        # -- 2D path --
        # App returns overlay in PET native dimensions
        fusion_2d = run_app_fusion_2d(ct_sorted, pt_sorted, ct_idx)
        # Ground truth in PET native dimensions
        gt_pet_native = build_ground_truth_pet_native(pt_sorted, ct_z)

        if fusion_2d is not None and gt_pet_native is not None:
            errs_2d = compute_errors(fusion_2d, gt_pet_native)
            result["2d_errors"] = errs_2d
            status = errs_2d.get("error", f"mean={errs_2d.get('abs_mean_pct_of_max', '?'):.4f}%")
            print(f"2d({fusion_2d.shape}):{status}  ", end="")

            np.save(str(pair_dir / f"{slice_label}_2d.npy"), fusion_2d)
            np.save(str(pair_dir / f"{slice_label}_2d_gt.npy"), gt_pet_native)
            if "error" not in errs_2d:
                abs_err = np.abs(fusion_2d - gt_pet_native)
                np.save(str(pair_dir / f"{slice_label}_2d_error.npy"), abs_err)
                save_error_heatmap(abs_err, str(pair_dir / f"{slice_label}_2d_error.png"),
                                   vmax=errs_2d["gt_max"] * 0.05)
        else:
            result["2d_errors"] = {"error": "None returned or outside coverage"}
            print("2d:None  ", end="")

        # -- 3D path --
        # App returns overlay in CT dimensions (resampled to reference grid)
        fusion_3d = run_app_fusion_3d(ct_sorted, pt_sorted, ct_idx, handler_cache_3d)
        # Ground truth on CT grid (independent scipy resampling)
        gt_ct_grid = build_ground_truth_on_ct_grid(pt_sorted, ct_sorted[ct_idx])

        if fusion_3d is not None and gt_ct_grid is not None:
            errs_3d = compute_errors(fusion_3d, gt_ct_grid)
            result["3d_errors"] = errs_3d
            status = errs_3d.get("error", f"mean={errs_3d.get('abs_mean_pct_of_max', '?'):.4f}%")
            print(f"3d({fusion_3d.shape}):{status}  ", end="")

            np.save(str(pair_dir / f"{slice_label}_3d.npy"), fusion_3d)
            np.save(str(pair_dir / f"{slice_label}_3d_gt.npy"), gt_ct_grid)
            if "error" not in errs_3d:
                abs_err = np.abs(fusion_3d - gt_ct_grid)
                np.save(str(pair_dir / f"{slice_label}_3d_error.npy"), abs_err)
                save_error_heatmap(abs_err, str(pair_dir / f"{slice_label}_3d_error.png"),
                                   vmax=errs_3d["gt_max"] * 0.05)
        else:
            result["3d_errors"] = {"error": "None returned or outside coverage"}
            print("3d:None  ", end="")

        # -- Shift analysis (3D, compared to CT-grid ground truth) --
        shift_errors = []
        for shift in shifts_mm:
            gt_shifted = build_ground_truth_on_ct_grid(pt_sorted, ct_sorted[ct_idx], z_shift_mm=shift)
            if gt_shifted is not None and fusion_3d is not None:
                errs_shifted = compute_errors(fusion_3d, gt_shifted)
                shift_errors.append(errs_shifted.get("abs_mean", float("inf")))
            else:
                shift_errors.append(float("inf"))

        result["shift_analysis"] = {
            "shifts_mm": shifts_mm,
            "mean_abs_errors": shift_errors,
            "best_shift_mm": shifts_mm[int(np.argmin(shift_errors))] if shift_errors else None,
        }

        finite_mask = [e < float("inf") for e in shift_errors]
        if sum(finite_mask) >= 3:
            s_mm = [s for s, f in zip(shifts_mm, finite_mask, strict=False) if f]
            s_err = [e for e, f in zip(shift_errors, finite_mask, strict=False) if f]
            save_shift_curve(s_mm, s_err,
                             str(pair_dir / f"{slice_label}_shift_curve.png"),
                             f"CT[{ct_idx}] z={ct_z:.1f}mm ({pos_type})")

        best_shift = result["shift_analysis"]["best_shift_mm"]
        print(f"best_shift={best_shift:+.1f}mm" if best_shift is not None else "")
        all_results.append(result)

    # Save grayscale images for a few representative slices
    for r in all_results[:3]:
        sl = r["slice_label"]
        for suffix in ["2d", "2d_gt", "3d", "3d_gt"]:
            npy_path = pair_dir / f"{sl}_{suffix}.npy"
            if npy_path.exists():
                arr = np.load(str(npy_path))
                save_grayscale_png(arr, str(pair_dir / f"{sl}_{suffix}.png"))

    summary_path = pair_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print("\n  Results saved to the protected pair directory")

    return all_results


def print_summary_table(all_results: list[dict]):
    print(f"\n{'='*70}")
    print("AGGREGATE SUMMARY")
    print(f"{'='*70}")
    print(f"{'Pair':<20} {'CT':>3} {'CT_z':>8} {'PosType':<11} {'Mode':>4} "
          f"{'Shape':>10} {'MeanErr%':>9} {'MaxErr%':>8} {'BestShft':>8}")
    print("-" * 95)

    for r in all_results:
        for mode in ["2d", "3d"]:
            errs = r.get(f"{mode}_errors", {})
            if "error" in errs:
                continue
            mean_pct = errs.get("abs_mean_pct_of_max", -1)
            max_pct = errs.get("abs_max_pct_of_max", -1)
            shape = "x".join(str(s) for s in errs.get("fusion_shape", []))
            shift = r.get("shift_analysis", {}).get("best_shift_mm", None)
            shift_str = f"{shift:+.1f}mm" if shift is not None and mode == "3d" else ""
            print(f"{r['pair']:<20} {r['ct_idx']:>3} {r['ct_z']:>8.1f} "
                  f"{r.get('position_type','?'):<11} {mode:>4} "
                  f"{shape:>10} {mean_pct:>8.4f}% {max_pct:>7.4f}% {shift_str:>8}")


def parse_args(args):
    if len(args) < 3:
        print("Usage: python tests/fusion_audit_quantitative_verification.py <dicom_folder> <private_output_root>")
        sys.exit(1)
    folder = args[1]
    if not os.path.isdir(folder):
        sys.exit("ERROR: the input directory is unavailable.")
    return folder, Path(args[2])


def setup_output_dir(output_root):
    repo_root = _SCRIPT_DIR.parent
    root = assert_safe_internal_path(Path(output_root), source_root=repo_root)
    ensure_private_directory(root)
    return ensure_private_directory(root / "fusion_audit_results_v2")


def print_initial_info(folder):
    print("Fusion Quantitative Verification v2")
    _ = folder
    print_structural_event("fusion.input", category="protected")
    print("Output: protected external directory")
    print("Loading DICOM data...\n")


def load_for_groups(folder):
    t0 = time.time()
    groups = scan_folder(folder)
    print_structural_event(
        "fusion.group_summary",
        metrics={
            "duration_ms": (time.time() - t0) * 1000,
            "group_count": len(groups),
        },
    )
    return groups


def main():
    t0 = time.time()
    folder, output_root = parse_args(sys.argv)
    try:
        out_dir = setup_output_dir(output_root)
    except (OSError, ValueError):
        raise SystemExit("ERROR: choose a writable private output root outside the source checkout.") from None
    print_initial_info(folder)
    for_groups = load_for_groups(folder)
    all_results = []

    pair_index = 0
    for _for_uid, series_dict in for_groups.items():
        ct_series = {}
        pt_series = {}
        for uid, datasets in series_dict.items():
            mod = getattr(datasets[0], "Modality", "")
            if mod == "CT":
                ct_series[uid] = datasets
            elif mod in ("PT", "NM"):
                pt_series[uid] = datasets

        if not ct_series or not pt_series:
            continue

        best_pt_uid = max(pt_series.keys(),
                         key=lambda u: abs(_rescale(pt_series[u][0])[0]))

        for _ct_uid, ct_ds in ct_series.items():
            pair_index += 1
            pair_label = f"pair_{pair_index:03d}"
            results = process_pair(ct_ds, pt_series[best_pt_uid], pair_label, out_dir)
            all_results.extend(results)

    print_summary_table(all_results)

    # Overall assessment
    shift_issues = []
    error_issues = []
    for r in all_results:
        shift = r.get("shift_analysis", {}).get("best_shift_mm", 0)
        if shift is not None and abs(shift) > 0.1:
            shift_issues.append(r)
        for mode in ["3d", "2d"]:
            errs = r.get(f"{mode}_errors", {})
            mean_pct = errs.get("abs_mean_pct_of_max", 0)
            if mean_pct > 5.0:
                error_issues.append((r, mode, mean_pct))

    print(f"\n{'='*70}")
    near_count = sum(1 for r in all_results if r.get("position_type") == "near_pt")
    between_count = sum(1 for r in all_results if r.get("position_type") == "between_pt")
    print(f"Tested: {len(all_results)} CT slices ({near_count} near PT, {between_count} between PT)")

    if shift_issues:
        print(f"\nTHROUGH-PLANE SHIFT DETECTED in {len(shift_issues)} slice(s):")
        for r in shift_issues:
            shift = r["shift_analysis"]["best_shift_mm"]
            print(f"  {r['pair']} CT[{r['ct_idx']}] z={r['ct_z']:.1f}mm "
                  f"({r['position_type']}) -> best shift = {shift:+.1f}mm")
    else:
        print("\nTHROUGH-PLANE: No systematic shift detected (all best shifts = 0 mm)")

    if error_issues:
        print(f"\nHIGH ERRORS (>5% of max) in {len(error_issues)} case(s):")
        for r, mode, pct in error_issues:
            print(f"  {r['pair']} CT[{r['ct_idx']}] {mode} ({r.get('position_type','')}): "
                  f"mean error = {pct:.4f}% of max")
    else:
        print("ERRORS: All within acceptable range (<5% of max)")

    print(f"\nTotal elapsed: {time.time() - t0:.1f}s")
    print("Results: protected external directory")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
