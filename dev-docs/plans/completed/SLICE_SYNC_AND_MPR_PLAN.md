# Slice Sync (Non-Orthogonal) and MPR / Oblique Reconstructions – Implementation Plan

This document outlines an implementation plan for two related features from `dev-docs/TO_DO.md`:

1. **Syncing slices for non-orthogonal orientations** using `ImagePositionPatient` and `ImageOrientationPatient`, so that scrolling in one view updates the "anatomically corresponding" slice in other views. Sync works for any angle between stacks — for near-parallel stacks (e.g. 90°) the mapped slice simply does not change when the source window is scrolled.
2. **Multi-planar reconstructions (MPRs) and oblique reconstructions**, allowing a user to recompute a view of any loaded series at a chosen orientation (axial, coronal, sagittal, or arbitrary oblique) and display it in any subwindow.

Both features depend on a **unified 3D geometric model** of slice stacks and planes. The plan builds that geometry layer first, then slice sync, then MPR/oblique.

---

## Overview

| Phase | Scope | Delivers |
|-------|--------|----------|
| **Phase 1** | Shared geometry module | Plane/stack representation, plane–plane intersection, "nearest slice" in patient space |
| **Phase 2** | Slice sync for user-linked groups | Cross-window slice sync for any orientation, user-configurable linked groups, tolerance based on slice thickness |
| **Phase 3** | MPR and oblique | Per-subwindow MPR via dialog; volume building, resampling, persistent cache, overlays, "MPR" label |
| **Future** | Slice location line across views | Line showing current slice plane on other views (reuses Phase 1 geometry) |

**Recommended order**: Phase 1 → Phase 2 → Phase 3. Slice location line is deferred and reuses Phase 1 unchanged.

**Implementation status (as of plan review):** Phase 1 and Phase 2 are complete. Phase 3 is substantially complete; remaining optional items: subwindow title-bar group indicator (Phase 2), "Create MPR view…" in View menu (Phase 3). Phase 2 unit tests (`test_slice_sync.py`) are not yet added; Phase 1 has `tests/test_slice_geometry.py`; Phase 3 has `tests/test_mpr_core.py`.

---

## Resolved Decisions

The following design decisions have been made and are reflected throughout this plan:

| Topic | Decision |
|-------|----------|
| Sync default | **Off by default** |
| Sync scope | **User-selectable linked group** per subwindow (not all windows, not Frame of Reference–based) |
| Angle restriction | **No angular restriction** — sync works for any angle; near-perpendicular pairs will simply produce few or no slice changes when the source is scrolled |
| Tolerance | **Based on slice thickness** of the target stack (see Phase 2 for details) |
| MPR entry point | **Per-subwindow via a dedicated MPR dialog**; user picks source series, view orientation, and optional slice thickness |
| MPR overlays | **Enabled** — use DICOM metadata from the underlying source series (e.g. modality, institution, patient info); **slice location tag is not shown**; slice number shows the MPR stack index |
| MPR label | `MPR` banner displayed across the top of the subwindow |
| MPR interactive tools | **ROIs, annotations, and measurements disabled** on MPR subwindows |
| MPR cache | **Persistent disk cache** for computed MPR stacks |
| Slice location line | **Deferred** to a later, separate task; will reuse Phase 1 geometry |

---

## Current State and Overlap

- **Fusion** (`fusion_handler`, `fusion_coordinator`, `image_resampler`): Uses **1D slice location** (e.g. `SliceLocation` or `ImagePositionPatient[2]`) for matching base and overlay slices within one subwindow. 3D fusion resampling in `image_resampler` already uses `ImagePositionPatient` / `ImageOrientationPatient` and SimpleITK. Neither touches cross-window sync.
- **Multi-window**: Each subwindow has its own `current_slice_index` and series dict (`subwindow_data`). There is **no cross-window slice synchronization** today.
- **`dicom_utils`**: Already has `get_image_position`, `get_image_orientation`, and `pixel_to_patient_coordinates` (including slice normal from row × column cosines). Solid foundation; no explicit "slice plane" or "stack geometry" abstraction yet.
- **`dicom_organizer`**: Sorts by `InstanceNumber` or `SliceLocation` (falls back to `ImagePositionPatient` Z). No notion of 3D plane.
- **`image_resampler`**: Builds SimpleITK image from DICOM stack using full direction cosines and spacing; used today for 3D fusion. Contains the resampling logic MPR will reuse/extend.

**Key overlap**: Slice sync "overlaps conceptually with MPR" (TO_DO). Both rely on Phase 1 geometry. Phase 2 sync can later be extended to include MPR subwindows.

---

## Phase 1: Shared Geometry Module

### Goal

Introduce a small, pure-math, well-tested module in patient space (mm) that:

- Represents a **slice plane** (from one DICOM instance).
- Represents a **slice stack** (ordered planes + spacing along normal).
- Computes the **nearest slice index** in a stack for a given reference plane.
- Computes **plane–plane intersection** (for the deferred slice location line feature).
- Is independent of any Qt, display, or fusion code.

### Prerequisites

- [x] Confirm `numpy` is available (already a dependency). `scipy` is optional; Phase 1 geometry can be pure NumPy.
- [x] Review `src/utils/dicom_utils.py` (`get_image_position`, `get_image_orientation`) to avoid duplication.

### Tasks

#### 1.1 SlicePlane and SliceStack types

**File**: `src/core/slice_geometry.py`

- [x] Define `SlicePlane` (dataclass or named tuple) holding:
  - `origin`: `np.ndarray` shape `(3,)` — `ImagePositionPatient` of this slice.
  - `row_cosine`: `np.ndarray` shape `(3,)` — first three values of `ImageOrientationPatient`.
  - `col_cosine`: `np.ndarray` shape `(3,)` — last three values of `ImageOrientationPatient`.
  - `row_spacing`: `float` — row pixel spacing (mm).
  - `col_spacing`: `float` — column pixel spacing (mm).
  - Derived property `normal`: `np.ndarray` shape `(3,)` = `row_cosine × col_cosine`, normalized.
- [x] Provide class method `SlicePlane.from_dataset(ds: Dataset) -> Optional[SlicePlane]` (uses `dicom_utils.get_image_position` / `get_image_orientation` / `get_pixel_spacing`; returns `None` if required tags are missing).
- [x] Define `SliceStack` holding:
  - `planes`: list of `SlicePlane`, **sorted** by position along stack normal (ascending).
  - `slice_thickness`: `float` — nominal slice thickness in mm (from `SliceThickness` tag if available; fallback: median consecutive distance between origins along normal).
  - `original_indices`: list of `int` — original dataset indices before sorting (to map back to `current_slice_index`).
  - Method `position_of(plane: SlicePlane) -> float` (plan named it `position_along_normal`): dot product of `plane.origin` with stack normal.
- [x] Provide class method `SliceStack.from_datasets(datasets: List[Dataset]) -> Optional[SliceStack]` (returns `None` if fewer than 2 datasets or geometry is insufficient).

#### 1.2 Nearest-slice computation

This is the core function used by Phase 2 sync.

- [x] Implement `find_nearest_slice(ref_plane: SlicePlane, stack: SliceStack, tolerance_mm: Optional[float] = None) -> Optional[int]`:
  - Project `ref_plane.origin` onto `stack` normal → signed distance along normal.
  - Find the stack plane whose position along normal is closest.
  - If `tolerance_mm` is given and the gap between the reference position and the nearest plane exceeds that tolerance, return `None` ("no match within tolerance").
  - Return the **stack-original dataset index** (via `original_indices`), not the sorted position, so the result can be used directly as `current_slice_index` in the app.
- [x] Document the "near-perpendicular" case: if the source and target stacks are ~90° apart, many reference planes will map to the same nearest target slice, so scrolling in the source may produce little or no change in the target — this is correct and expected behavior.
- [x] Add unit tests in `tests/test_slice_geometry.py`:
  - Axial source → coronal target: scrolling source updates coronal correctly.
  - Near-perpendicular stacks: multiple source positions map to the same target slice.
  - Reference outside stack extent with tolerance: returns `None`.
  - Missing metadata: `from_dataset` / `from_datasets` return `None` gracefully.

#### 1.3 Plane–plane intersection (for future slice location line)

- [x] Implement `plane_plane_intersection(a: SlicePlane, b: SlicePlane) -> Optional[Tuple[np.ndarray, np.ndarray]]`:
  - Returns `(point_on_line, direction_vector)` or `None` for degenerate (parallel/coincident) planes.
  - Use `abs(dot(a.normal, b.normal)) > 1 - epsilon` to detect parallelism.
- [x] Implement `project_line_to_2d(point: np.ndarray, direction: np.ndarray, plane: SlicePlane) -> Optional[Tuple[float, float, float, float]]`:
  - Returns `(row1, col1, row2, col2)` in the plane's 2D coordinate system by parameterizing the 3D line and projecting two points.
  - Returns `None` if line is parallel to the plane normal.
- [x] Unit tests (axial + coronal planes producing a known horizontal line; parallel planes returning `None`).
- [x] **Note**: these functions are implemented now for completeness and testability but will only be wired to UI in the separate "slice location line" task.

### Potential problems

| Area | Risk | Recommendation |
|------|------|----------------|
| **Metadata quality** | Missing `ImagePositionPatient` / `ImageOrientationPatient` | `from_dataset` returns `None`; Phase 2 disables sync for that subwindow with a brief status message. |
| **Stack sort order** | Geometry sort order may differ from `dicom_organizer` / navigator order | Store `original_indices` in `SliceStack` to map geometry position back to navigator slice index; document clearly. |
| **Numerical stability** | Cross product near-zero for collinear cosines | Normalize carefully; check for very small normal magnitude and return `None` from `from_dataset`. |

---

## Phase 2: Slice Sync for User-Linked Groups

### Goal

When slice sync is enabled and the user scrolls in a subwindow that belongs to a **linked group**, all other subwindows in the same group automatically advance to the anatomically closest slice, using Phase 1 geometry. Sync works for any orientation; near-perpendicular pairs simply don't update.

### Prerequisites

- [x] Phase 1 geometry (`SlicePlane`, `SliceStack`, `find_nearest_slice`) available and tested.
- [x] Understanding of how `current_slice_index` is updated in subwindow lifecycle (`src/core/subwindow_lifecycle_controller.py`).

### Tasks

#### 2.1 Linked-group model

- [x] A **linked group** is a named set of subwindow indices (e.g. indices 0–3 for the 2×2 layout).
- [x] Support **multiple independent groups** (e.g. group A = windows 0 and 1; group B = windows 2 and 3), though a single default group is the common case.
- [x] A subwindow can belong to at most one group at a time.
- [x] Persist group assignments in config (new `slice_sync_config.py` mixin or in `display_config`): serialize as a list of lists of subwindow indices.

#### 2.2 UI for managing groups

- [x] Add a **"Slice Sync" submenu** under the **View** menu (and optionally the image viewer context menu):
  - "Enable slice sync" — master toggle (default: off).
  - "Manage sync groups..." — opens a small dialog (see below).
- [x] **Sync Groups dialog** (`src/gui/dialogs/slice_sync_dialog.py`):
  - Lists current groups (each group shown as a set of subwindow labels, e.g. "Window 1, Window 2").
  - "Create group" — user picks which subwindows to link (checkboxes).
  - "Dissolve group" — remove a group (subwindows become unlinked).
  - "Add to group / Remove from window" — quick toggle per subwindow (handled via create/dissolve; no separate add/remove UI).
  - OK/Apply/Cancel; changes take effect immediately on Apply.
- [ ] Optionally: show a small colored dot or icon on each subwindow title bar to indicate which group it belongs to (group color), so the user can see at a glance which windows are linked.

#### 2.3 Tolerance (slice thickness–based)

- [x] The tolerance for "match within range" is defined per **target stack**: `tolerance = stack.slice_thickness * 0.5` (i.e. match if the reference plane falls within half a slice thickness of the nearest stack plane). This is sensible because it means a reference plane that falls "between" two target slices will still update the target (to whichever is closer).
- [x] If `SliceStack.slice_thickness` could not be determined (returns `None`), fall back to a default tolerance of `1.0 mm`.
- [x] If the reference plane is further than one full slice thickness from the nearest target plane (i.e. outside the stack extent or in a gap), return no update (leave target slice unchanged).

#### 2.4 SliceSyncCoordinator

**File**: `src/core/slice_sync_coordinator.py`

- [x] `SliceSyncCoordinator` class holding:
  - Reference to app's `subwindow_data` and lifecycle controller.
  - A geometry cache: `Dict[(study_uid, series_uid), Optional[SliceStack]]`.
  - Current group assignments.
- [x] Method `on_slice_changed(source_subwindow_idx: int)`:
  - If sync is disabled or no group contains `source_subwindow_idx`, return immediately.
  - Get source subwindow's current slice index and datasets; build or retrieve `SliceStack` for source.
  - Get current `SlicePlane` for the source's current slice.
  - For each other subwindow in the same group: build/retrieve `SliceStack` for its series; call `find_nearest_slice`; if a valid index is returned, update that subwindow's slice (programmatically, without triggering another sync event — use a `_syncing: bool` guard).
- [x] Cache `SliceStack` per `(study_uid, series_uid)` in the coordinator; invalidate when a series is closed or reassigned.
- [x] Gracefully handle subwindows with no series loaded (skip silently).

#### 2.5 Wiring into app

- [x] In `src/main.py` (or `_post_init_subwindows_and_handlers`): instantiate `SliceSyncCoordinator` and call `on_slice_changed(idx)` from the slice-changed signal / callback. The "source" is always the focused subwindow (or the subwindow that fired the slice change signal).
- [x] Wire master toggle to `SliceSyncCoordinator.enabled` flag and persist in config.
- [x] Add `_connect_slice_sync_signals()` to `_connect_signals` family (following existing pattern in `src/main.py`; slice sync is wired via `app_signal_wiring.py` and subwindow lifecycle).

#### 2.6 Edge cases and UX

- [x] **Sync unavailable (missing geometry)**: if either the source or a target stack has no geometry (returns `None` from `from_datasets`), silently skip that target; optionally show a small tooltip or status bar message ("Sync unavailable for Window N: missing DICOM geometry").
- [x] **Near-perpendicular stacks**: correct behavior is no change in target; no message needed.
- [x] **Feedback loop guard**: set `_syncing = True` before programmatic slice updates and check it at the top of `on_slice_changed`; reset to `False` after all updates.
- [x] **Subwindow reassigned to different series**: clear its `SliceStack` from cache and, if it was the only member of a group, dissolve the group automatically or leave it "pending" until a series is loaded.

### Potential problems and conflicts

| Area | Risk / conflict | Recommendation |
|------|------------------|----------------|
| **Fusion** | Fusion matches overlay to base within one subwindow using 1D `SliceLocation`. Cross-window sync only changes `current_slice_index` in each subwindow; fusion re-matches overlay on each display update — no conflict. | No change to fusion logic. |
| **Cine playback** | Cine advances slice index in a controlled loop; sync would also try to update linked windows. | Disable sync-triggered updates while cine is playing (check cine state in coordinator), or allow it (simpler) and let the linked windows scroll freely — needs UX review. |
| **MPR subwindows** | Once MPR is implemented (Phase 3), MPR subwindows have their own slice stack. | MPR stack can participate in sync using the same `SliceStack`/`find_nearest_slice` — Phase 3 wires this. |
| **Performance** | Recomputing geometry on every scroll. | Geometry cache per `(study, series)` makes repeated lookups O(n log n) once, then O(log n) per scroll. |

---

## Phase 3: Multi-Planar Reconstructions (MPR) and Oblique Reconstructions

### Goal

Allow a user to designate any subwindow as an **MPR view**: they choose the source series, the viewing plane orientation (standard axial / coronal / sagittal preset, or custom angles), and optional output slice thickness. The app resamples the 3D volume of that series onto the chosen plane family, produces an ordered MPR slice stack, and displays it in the subwindow like a regular series — but with clear UI indicators and restricted interactive tools.

### Prerequisites

- [x] Phase 1 geometry available.
- [x] `image_resampler.py` reviewed for reusability (especially `_build_sitk_image_from_datasets` and spacing/direction logic).
- [x] Decision: MPR per-subwindow (confirmed — not a global layout mode).

### Tasks

#### 3.1 MPR Dialog

**File**: `src/gui/dialogs/mpr_dialog.py`

This dialog appears when the user selects "Create MPR view…" from the subwindow context menu or View menu.

- [x] **Source series selection**: dropdown list of all currently loaded series (grouped by study; show series description, modality, slice count). Pre-fills to the focused subwindow's series.
- [x] **View orientation**: radio buttons or dropdown:
  - Axial (standard, normal = S-I / LPS Z)
  - Coronal (standard, normal = A-P / LPS Y)
  - Sagittal (standard, normal = L-R / LPS X)
  - Custom (enables angle inputs: two rotation angles, e.g. yaw and pitch in degrees; or normal vector as three text fields)
- [x] **Output slice thickness**: numeric input in mm, defaulting to `SliceThickness` of the source series (or computed inter-slice spacing).
- [x] **Output pixel spacing**: numeric input in mm, defaulting to in-plane pixel spacing of the source series (or isotropic 1 mm for oblique; user can override).
- [x] **Interpolation**: dropdown: nearest, linear (default), cubic.
- [x] **Estimated slices / extent**: read-only, computed from volume bounding box and chosen orientation (updated live as user changes orientation/thickness).
- [x] Warn if source series lacks full `ImagePositionPatient` / `ImageOrientationPatient` geometry ("MPR requires complete DICOM spatial metadata").
- [x] OK / Cancel. On OK, trigger `MprBuilder.build()` asynchronously and display progress.

#### 3.2 Volume representation (MprVolume)

**File**: `src/core/mpr_volume.py`

- [x] `MprVolume` class wrapping a SimpleITK image (reusing `image_resampler._build_sitk_image_from_datasets` where possible):
  - Constructor from `List[Dataset]`: sort slices by position along normal (using `SliceStack`), build SimpleITK image with correct origin, spacing, and direction cosines.
  - Handle **anisotropic voxels** and **non-axis-aligned** acquisitions using full direction cosines.
  - Raise `MprVolumeError` (custom exception) on failure: inconsistent orientations, < 2 slices, missing geometry tags, all-duplicate positions.
- [x] Provide `MprVolume.available(datasets: List[Dataset]) -> bool` (quick pre-check before opening dialog).

#### 3.3 MprBuilder / resampler

**File**: `src/core/mpr_builder.py`

- [x] `MprBuilder` class: takes `MprVolume`, `SlicePlane` (output plane definition), output spacing, slice thickness, interpolation method.
- [x] `MprBuilder.build() -> List[np.ndarray]`: resamples the volume onto the entire family of parallel planes separated by `slice_thickness` along the output normal, spanning the bounding box of the volume. Returns ordered list of 2D NumPy arrays (one per output slice) via `MprResult`.
- [x] Use SimpleITK `Resample` for both orthogonal and oblique planes (avoids implementing a custom resampling loop; leverages existing `image_resampler` investment).
- [x] Return output pixel spacing (mm), extent, and a `SliceStack` representing the MPR planes (for Phase 2 sync integration).
- [x] Run in a background thread (or `QThread`) to avoid blocking the UI; emit progress signals.

#### 3.4 Persistent MPR cache

**File**: New cache module, e.g. `src/core/mpr_cache.py`, or extend an existing cache if present.

- [x] Cache MPR stacks on disk (e.g. NumPy `.npz` files in a subdirectory of the app's config/cache dir, similar to where fusion or other derived data is stored). Use a **cache key** derived from:
  - Source series UID.
  - Output orientation (normal vector, quantized to 4 decimal places).
  - Output pixel spacing and slice thickness.
  - Interpolation method.
  - A hash or count of source datasets (to invalidate if series is reloaded with different content).
- [x] On MPR request: check cache first; if hit, skip resampling and load arrays from disk. Show "Loaded from cache" in progress feedback.
- [x] Cache expiry / invalidation: invalidate on series reload or when source series changes. Provide a "Clear MPR cache" option in Settings.
- [x] Cap disk usage (e.g. configurable max size in MB; evict LRU entries on overflow). Default cap: 500 MB. Add `mpr_cache_max_mb` to config.

#### 3.5 MPR subwindow display

Once `MprBuilder.build()` completes, load the resulting stack into the target subwindow like a synthetic series:

- [x] Store the MPR arrays and `SliceStack` in `subwindow_data` for the target subwindow (use a flag, e.g. `is_mpr: True`, to distinguish from real DICOM series).
- [x] The **slice navigator** counts: MPR stack size (number of output slices), not the source DICOM series length. The navigator label and scrollbar use the MPR stack index.
- [x] **"MPR" banner**: Draw a banner reading `MPR` (and optionally the orientation, e.g. `MPR – Coronal`) across the top of the subwindow image area, inside the image viewport. Use the existing overlay rendering path for positioning; ensure it is never hidden by other overlay elements. Style: bold, semi-transparent background, color distinct from clinical overlays.
- [x] **Overlays**: enable the existing overlay system for the MPR subwindow, but using metadata from the **source series** first dataset (e.g. PatientName, Modality, StudyDate). Explicitly **exclude** any overlay fields that would show a meaningless value for the resampled plane: `SliceLocation`, `InstanceNumber` (DICOM tag), `ImagePositionPatient` raw values. The slice counter shown in overlays should be the MPR stack index, sourced from the navigator's `current_slice_index`, not from the DICOM `InstanceNumber` or `SliceLocation` tag.
- [x] **Window/level**: enable fully; use the source series' window/level presets as initial values.
- [x] **Zoom, pan**: enable fully.
- [x] **ROIs, measurements, annotations**: **disabled** on any subwindow where `is_mpr = True`. If the user tries to draw an ROI or annotation, silently ignore (no tool activation). Consider showing a brief tooltip or status bar message "ROIs and annotations are not available on MPR views." (Implemented by forcing pan mode when an MPR subwindow is focused; assign-series is blocked with a toast message.)
- [x] **Right-click context menu**: show "Convert MPR to…" options later (out of scope); for now, show "Clear MPR" to reset the subwindow to its previous series (or empty).

#### 3.6 Sync integration for MPR subwindows

- [x] When the target subwindow is an MPR view, its `SliceStack` (from `MprBuilder.build`) is already in Phase 1 format. Register it in `SliceSyncCoordinator`'s geometry cache under a synthetic key (e.g. `("__mpr__", subwindow_idx)`).
- [x] MPR subwindows can participate in linked groups like any other subwindow. Scrolling an MPR subwindow can update linked original subwindows (and vice versa).

#### 3.7 Entry point (UI wiring)

- [x] Add **"Create MPR view…"** to the subwindow context menu (right-click on image → "Create MPR view…").
- [ ] Optionally add **"Create MPR view…"** to the **Tools** or **View** menu as well.
- [x] Show **"Clear MPR view"** in the same menu when the subwindow already contains an MPR (with confirmation dialog).
- [x] While MPR is building, show a `QProgressDialog` (reuse `LoadingProgressManager` pattern if applicable) with a Cancel button that aborts the background thread.

### Potential problems and conflicts

| Area | Risk / conflict | Recommendation |
|------|------------------|----------------|
| **Accuracy** | Resampling distortion with anisotropic or oblique data | Use full direction cosines in SimpleITK; document "for viewing only" until measurements are validated. |
| **Performance** | Large volumes; real-time oblique re-build on angle change | No real-time dragging in Phase 3 (angles set in dialog, not interactively). If interactive rotation is added later: cache intermediate volume, reduce resolution while dragging, full resolution on release. |
| **Memory** | Multiple MPR stacks (one per subwindow) could be memory-intensive | Store built stacks in persistent disk cache; load only the displayed slice range into RAM at a time (lazy loading for large stacks). |
| **Cache key collisions** | Series UID alone is not unique if server re-uses UIDs (rare but possible) | Include dataset count and a checksum in key; document limitation. |
| **Overlay metadata** | Source dataset metadata may not be appropriate for resampled plane (e.g. `ImagePositionPatient`) | Explicitly whitelist which overlay tags are shown (see 3.5); do not blindly pass source dataset as "current dataset" to overlay logic. |
| **Fusion on MPR** | MPR of a fused volume would require fusing in 3D | **Out of scope** for Phase 3; disable fusion controls when a subwindow is in MPR mode and show a tooltip explaining why. |
| **Slice navigator** | Navigator uses `current_datasets` list for bounds; MPR has a list of NumPy arrays, not Datasets | Add an abstraction layer or special case in the navigator so it can count MPR frames from the array list. |
| **Cine on MPR** | Cine could technically loop through MPR slices | Allow it (no harm); or disable cine on MPR (simpler initial implementation). |

---

## File and Module Sketch

```
src/
  core/
    slice_geometry.py         # Phase 1: SlicePlane, SliceStack, find_nearest_slice,
                              #          plane_plane_intersection, project_line_to_2d
    slice_sync_coordinator.py # Phase 2: SliceSyncCoordinator
    mpr_volume.py             # Phase 3: MprVolume (wraps SimpleITK volume)
    mpr_builder.py            # Phase 3: MprBuilder (resampling, threading, progress)
    mpr_cache.py              # Phase 3: MprCache (disk-based, keyed, LRU eviction)
  gui/
    dialogs/
      slice_sync_dialog.py    # Phase 2: Manage linked groups
      mpr_dialog.py           # Phase 3: Series/orientation/thickness selection
  utils/
    config/
      slice_sync_config.py    # Phase 2: Config mixin for sync enabled + group assignments
                              # (or add fields to display_config.py)

tests/
  test_slice_geometry.py      # Phase 1 unit tests (pure geometry, no Qt) — present
  test_slice_sync.py          # Phase 2 unit tests (coordinator logic, mock subwindows) — not yet added
  test_mpr_core.py            # Phase 3 unit tests (resampling / MPR core; plan referred to test_mpr_builder.py)
```

---

## Decisions Remaining

1. **Cine + sync**: Allow sync-triggered updates while cine is active (simplest) or suppress them? Needs UX input.
2. **MPR lazy loading**: Load full MPR stack into RAM on build, or lazy-load per slice? Large volumes may require lazy loading.
3. **MPR cache location**: Use existing app config/cache directory, or a user-configurable path? Add to Settings dialog.
4. **MPR measurement (future)**: When measurements on MPR are eventually enabled, pixel-to-patient mapping must account for the output plane geometry, not the source dataset. Needs a separate design.
5. **Interactive oblique rotation (future)**: Not in Phase 3. When added, will require real-time resampling or a multi-resolution strategy.

---

## Changelog and Versioning

- **Phase 1**: Small internal addition (no user-visible change); can be bundled into the next patch or minor release without a dedicated changelog entry, or noted as an internal improvement.
- **Phase 2**: New optional feature (sync off by default) — **minor version bump** (e.g. `3.x.0`). Changelog: "Added optional anatomic slice sync for user-defined linked groups."
- **Phase 3**: Significant new feature — **minor or major version bump** depending on release policy (see `dev-docs/RELEASING.md`). Changelog: "Added MPR / oblique reconstruction view; persistent cache; overlays and W/L on MPR subwindows; ROIs/annotations/measurements not available in MPR mode."

---

## References

- `dev-docs/TO_DO.md` — "Syncing Slices for Non-Orthogonal Orientations (Using ImagePositionPatient)", "Slice Location Line Across Views", "Multi-Planar Reconstructions (MPRs) and Oblique Reconstructions".
- `src/utils/dicom_utils.py` — `get_image_position`, `get_image_orientation`, `pixel_to_patient_coordinates`.
- `src/core/fusion_handler.py` — `get_slice_location`, `find_matching_slice` (current 1D matching; not changed).
- `src/core/image_resampler.py` — 3D resampling with `ImagePositionPatient`, `ImageOrientationPatient`, SimpleITK; basis for `MprBuilder`.
- `src/core/loading_progress_manager.py` — progress/cancel dialog pattern for long operations; reuse for MPR build.
- `dev-docs/plans/completed/IMAGE_FUSION_IMPLEMENTATION_PLAN.md` — phased plan structure and style.
