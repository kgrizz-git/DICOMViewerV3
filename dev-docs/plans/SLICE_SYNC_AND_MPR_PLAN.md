# Slice Sync (Non-Orthogonal) and MPR / Oblique Reconstructions – Implementation Plan

This document outlines an implementation plan for two related features from `dev-docs/TO_DO.md`:

1. **Syncing slices for non-orthogonal orientations** using `ImagePositionPatient` and `ImageOrientationPatient`, so that scrolling in one view updates the “anatomically corresponding” slice in other views (e.g. axial ↔ coronal ↔ sagittal, or angled stacks).
2. **Multi-planar reconstructions (MPRs) and oblique reconstructions**, allowing resampled views on arbitrary planes (orthogonal or oblique) from a 3D volume in patient space.

Both features depend on a **unified 3D geometric model** of slice stacks and planes. The plan recommends implementing that geometry layer first, then slice sync, then MPR/oblique, with clear decision points and risk areas called out.

---

## Overview

| Phase | Scope | Delivers |
|-------|--------|----------|
| **Phase 1** | Shared geometry module | Plane/stack representation, plane–plane intersection, “nearest slice” in patient space |
| **Phase 2** | Slice sync for non-orthogonal | Cross-window slice sync when orientations differ, optional sync mode, tolerance handling |
| **Phase 3** | MPR and oblique | Orthogonal MPR (axial/coronal/sagittal), then arbitrary oblique planes; resampling, caching, UI |
| **Future** | Slice location line across views | Line showing current slice plane on other views (reuses Phase 1 geometry) |

**Recommended order**: Phase 1 → Phase 2 → Phase 3. The “Slice Location Line Across Views” item from TO_DO naturally reuses the same geometry and can be planned after Phase 2.

---

## Current State and Overlap

- **Fusion** (`fusion_handler`, `fusion_coordinator`, `image_resampler`): Uses **1D slice location** (e.g. `SliceLocation` or `ImagePositionPatient[2]`) for matching base and overlay slices. Works for same-orientation stacks; does not model full 3D plane or non-orthogonal sync. 3D fusion resampling already uses `ImagePositionPatient` / `ImageOrientationPatient` in `image_resampler`.
- **Multi-window**: Each subwindow has its own `current_slice_index` and series; there is **no cross-window slice synchronization** today.
- **`dicom_utils`**: Already has `get_image_position`, `get_image_orientation`, and `pixel_to_patient_coordinates` (including slice normal from row×column cosines). Good foundation; no explicit “slice plane” or “stack geometry” abstraction yet.
- **`dicom_organizer`**: Sorts by `InstanceNumber` or `SliceLocation` (and falls back to `ImagePositionPatient` Z). No notion of orientation or 3D plane.

**Key overlap (TO_DO)**: Slice sync “overlaps conceptually with MPR”; long term, a single geometric model should support both slice sync and full MPR views.

---

## Phase 1: Shared Geometry Module

### Goal

Introduce a small, testable core that:

- Represents a **slice plane** in patient coordinates (from one instance: `ImagePositionPatient`, `ImageOrientationPatient`, optional `PixelSpacing` for in-plane axes).
- Represents a **slice stack** (ordered list of planes with spacing / ordering along the stack normal).
- Computes **intersection** of one plane with another (line in 3D) and projects that line into a view’s 2D coordinates.
- Given a plane A and a stack B, computes the **nearest slice index** in B to plane A (distance along B’s normal), with configurable tolerance.

All in **patient space (mm)**, so it is independent of window/level, overlays, and fusion blending.

### Prerequisites

- [ ] Confirm `numpy` (and optionally `scipy`) are acceptable for geometry (no new heavy deps).
- [ ] Review `src/utils/dicom_utils.py` (`get_image_position`, `get_image_orientation`, `pixel_to_patient_coordinates`) to avoid duplication and to reuse parsing.

### Tasks

#### 1.1 Slice plane and stack representation

**Location**: New module, e.g. `src/core/slice_geometry.py` (or under `src/utils/` if preferred).

- [ ] Define a **slice plane** type (e.g. `SlicePlane` or dataclass) holding:
  - Origin in patient coords (from `ImagePositionPatient`).
  - Row and column direction cosines (from `ImageOrientationPatient`).
  - Optional in-plane spacing (`PixelSpacing`) for 2D↔patient mapping.
  - Derived: normal vector (row × column), normalized.
- [ ] Provide a constructor from a single pydicom `Dataset` (using existing `dicom_utils` where possible).
- [ ] Define a **slice stack** type (e.g. `SliceStack`) holding:
  - List of `SlicePlane` (or origin + shared orientation and spacing).
  - Ordering along the stack normal (slice index → position along normal).
  - Optional: spacing between slices (from `SliceThickness` / `SpacingBetweenSlices` or from consecutive `ImagePositionPatient`).
- [ ] Build stack from list of datasets (reusing or delegating to `dicom_organizer` for sort order if needed; document that geometry assumes already-sorted-by-position along normal).

#### 1.2 Plane–plane intersection and projection

- [ ] Implement **plane–plane intersection**: given two planes, return the 3D line (or “nearly parallel” / degenerate handling).
- [ ] Implement **project line into view**: given a 3D line and a target slice plane (view), compute the 2D line segment in that view’s row/column coordinates (for drawing “slice location line” in a future phase).
- [ ] Add unit tests (synthetic planes: e.g. axial at Z=0, coronal at Y=0) to avoid regressions and document expected behavior for edge cases (parallel, coincident).

#### 1.3 Nearest-slice in patient space

- [ ] Implement **nearest slice index**: given a reference plane (e.g. “current slice in window A”) and a slice stack (e.g. “series in window B”), compute the slice index in B whose plane is closest to the reference plane (distance along B’s normal), and the signed distance in mm.
- [ ] Support a **tolerance** (mm): if the reference plane is outside the stack extent by more than tolerance, return a sentinel or clamp and document behavior.
- [ ] Handle **oblique stacks**: “nearest” is defined along the stack’s normal; document that for very oblique or helical acquisitions the mapping may not be one-to-one and the UI may need a “best effort” or “sync disabled” state.

#### 1.4 Integration points (no UI yet)

- [ ] Provide a thin facade that takes “current dataset (or slice index + list of datasets) for view A” and “list of datasets for view B” and returns “suggested slice index for view B” and optional “distance in mm”. This will be used by Phase 2.
- [ ] Document when the module returns `None` or invalid (e.g. missing `ImagePositionPatient` / `ImageOrientationPatient`, empty list, inconsistent orientations).

### Potential problems and decisions

| Area | Risk / conflict | Recommendation |
|------|------------------|----------------|
| **Metadata quality** | Noisy or missing `ImagePositionPatient` / `ImageOrientationPatient` in older or vendor-specific data | Use tolerances and fallbacks; allow “sync disabled” when geometry is unreliable; log warnings. |
| **Definition of “slice index”** | Stack ordering may differ from current navigator (e.g. InstanceNumber vs position along normal) | Define stack order explicitly (e.g. by position along stack normal) and map to/from navigator index in one place (e.g. in Phase 2 coordinator). |
| **Numerical stability** | Near-parallel planes, very small angles | Use epsilon in dot products; document and test degenerate cases; avoid division by very small numbers. |

---

## Phase 2: Syncing Slices for Non-Orthogonal Orientations

### Goal

When the user scrolls slices in one subwindow, optionally update the slice index in other subwindows so that the displayed slices correspond to the same anatomic location, using the Phase 1 geometry (plane + nearest slice).

### Prerequisites

- [ ] Phase 1 geometry module available and tested.
- [ ] Clear definition of “sync scope”: which subwindows participate (e.g. all 2×2, or only “linked” ones), and whether sync is per-study or global.

### Tasks

#### 2.1 Sync mode and scope (decisions)

- [ ] **Decision**: Sync on by default or off? Suggestion: **off by default**, with a View menu or toolbar option “Sync slices across views” (or “Anatomic slice sync”) so users can enable when they have multiple orientations.
- [ ] **Decision**: When sync is on, which windows sync? Options: (a) all subwindows that have a series loaded, (b) only windows that share the same Frame of Reference UID, (c) user-selectable “linked” group. Recommendation: start with (a) or (b); document and optionally add (c) later.
- [ ] **Decision**: Strict orthogonal only vs “angled within 45°”? TO_DO suggests optional/mode-based. Recommendation: support both “strict orthogonal only” and “angled within N°” (e.g. 45°) with a small tolerance (mm) for slice selection; if orientation difference exceeds threshold, show a message or disable sync for that pair.

#### 2.2 Slice sync coordinator

**Location**: New or existing coordinator (e.g. `SliceSyncCoordinator` in `src/core/` or under a dedicated `slice_sync` module).

- [ ] On “current slice changed” in subwindow A: get A’s current dataset (or slice index + stack).
- [ ] For each other subwindow B that participates in sync: get B’s stack (same study/Frame of Reference or per policy). Use Phase 1 to compute suggested slice index for B.
- [ ] If suggested index is valid and within bounds, set B’s slice index (via existing subwindow/lifecycle APIs) and trigger display update.
- [ ] Avoid feedback loops: when B’s slice is set programmatically, do not trigger “slice changed” that would again update A (e.g. “source” of the change is the user scroll in A only).

#### 2.3 Wiring to existing app

- [ ] Hook “slice changed” from the slice navigator / `SliceDisplayManager` / subwindow lifecycle so the coordinator is notified for the focused (or “source”) subwindow.
- [ ] When sync is enabled, after changing slice in the source window, call coordinator to update other windows; ensure only one “source” per user action to avoid circular updates.
- [ ] Persist “sync enabled” in config (e.g. `display_config` or new `slice_sync_config`) so the setting is restored on restart.

#### 2.4 Edge cases and UX

- [ ] If geometry is missing or invalid for A or B, do not change B’s slice; optionally show a brief status message (“Sync unavailable: missing geometry”).
- [ ] If stacks have different Frame of Reference UIDs, sync may be meaningless; either exclude such pairs or show “Sync not available (different frame of reference)”.
- [ ] Document in release notes and (if present) user guide: sync is anatomic best-effort; for oblique/helical data the “nearest slice” may not be unique.

### Potential problems and conflicts

| Area | Risk / conflict | Recommendation |
|------|------------------|----------------|
| **Fusion** | Fusion already matches slices by 1D `SliceLocation`/IPP Z within one subwindow. | Leave fusion logic as-is for base/overlay in a single view. Cross-window sync is independent: it only changes which slice index is shown in each subwindow. If a subwindow has fusion on, fusion will still match overlay to base within that window using existing logic. |
| **Multiple series per study** | Different series (e.g. axial vs coronal) may have different slice counts and ordering. | Sync by anatomic position (Phase 1 nearest-slice), not by index. Each window’s navigator shows its own slice index; the coordinator maps “plane of current slice in A” → “slice index in B.” |
| **Performance** | Recomputing geometry on every scroll could be costly for many windows. | Cache stack geometry per (study, series) and invalidate on series change; keep Phase 1 functions lightweight (no heavy resampling). |
| **ROI / annotations** | Changing slice in B programmatically may change “current slice” for ROIs/annotations in B. | Use existing “current slice” semantics: ROIs/annotations in B remain tied to slice index in B; sync only updates that index. No special ROI handling unless product decision is to “link” ROIs across views (out of scope here). |

---

## Phase 3: Multi-Planar Reconstructions (MPR) and Oblique Reconstructions

### Goal

- **Orthogonal MPR**: Resample the 3D volume onto axial, coronal, and sagittal planes (or standardize existing stacks to a single volume and resample).
- **Oblique MPR**: Allow an arbitrary plane (normal + in-plane axes); resample volume onto that plane with configurable resolution and interpolation.

All driven from a **single 3D volume in patient space** built from `ImagePositionPatient`, `ImageOrientationPatient`, and spacing, so that MPR views are consistent with Phase 1 geometry and Phase 2 sync.

### Prerequisites

- [ ] Phase 1 geometry available (plane and stack representation).
- [ ] Decision on whether MPR is a **separate mode** (e.g. “MPR layout” with 3–4 views) or integrated into existing subwindows. TO_DO suggests treating MPR as a distinct mode with its own expectations and controls.

### Tasks

#### 3.1 Volume representation

- [ ] Build a **3D volume** (e.g. `PatientVolume` or reuse/extend logic in `image_resampler`) from a list of DICOM datasets: one volume per Frame of Reference (or per series, with clear documentation). Use Phase 1 for orientation and spacing; reuse `image_resampler`’s use of SimpleITK or NumPy where it already does 3D.
- [ ] Handle **anisotropic voxels** and **non–axis-aligned** acquisitions: use full direction cosines and spacing (no naïve axis-aligned assumption).
- [ ] Document when volume building fails (e.g. inconsistent orientation, gaps, duplicate positions) and how the UI should react (e.g. “MPR not available for this series”).

#### 3.2 Orthogonal MPR

- [ ] Implement resampling of the volume onto **axial / coronal / sagittal** planes (standard LPS or RAS, consistent with DICOM). Use NumPy/scipy or SimpleITK; prefer reusing `image_resampler` if it already supports “reslice to plane.”
- [ ] Define output spacing (e.g. isotropic at 1 mm or match in-plane spacing of the volume) and extent (bounding box of the volume in patient space).
- [ ] Expose as a **view type** or **layout**: e.g. “MPR” mode with three (or four) panes showing axial, coronal, sagittal, and optionally one oblique. Each pane has its own slice index along the corresponding axis.

#### 3.3 Oblique reconstructions

- [ ] Parameterize an **arbitrary plane** by normal and in-plane axes (or two angles + offset). Use Phase 1 `SlicePlane` representation for consistency.
- [ ] Resample volume onto that plane (same interpolation options as orthogonal).
- [ ] **Performance**: Use caching and, if needed, reduced resolution during interactive drag/rotate; full resolution on mouse release or after a short idle. Consider GPU later if volumes are large and interaction is slow.
- [ ] **UI**: Draggable crosshairs or rotation handles in orthogonal views to define the oblique plane; optional numeric angle/offset inputs. Visual feedback (e.g. preview line or shaded region on other views) improves usability.

#### 3.4 Integration with existing features

- [ ] **Window/level**: Apply per MPR view; reuse existing W/L infrastructure where possible.
- [ ] **Overlays**: Define whether overlays are drawn on MPR views (e.g. same overlay logic, but metadata may need to be mapped to MPR slice). Likely Phase 3.2+.
- [ ] **ROIs / measurements**: ROIs are currently in 2D slice space. Decide: (a) MPR views are read-only for ROIs, (b) ROIs can be drawn on MPR and stored in patient coordinates, or (c) ROIs only on original slices. Document and implement consistently.
- [ ] **Fusion**: MPR of a fused volume (e.g. CT+PET) would require fusing in 3D then reslicing; defer or scope to a later phase.
- [ ] **Slice sync**: Once MPR views exist, Phase 2 sync can be extended so that scrolling in one MPR pane updates the corresponding slice in other MPR panes (and optionally in “original” subwindows if same Frame of Reference).

### Potential problems and conflicts

| Area | Risk / conflict | Recommendation |
|------|------------------|----------------|
| **Accuracy** | Naïve resampling can distort anatomy or distances with anisotropic or oblique data | Use full DICOM geometry in resampling; validate on known datasets; consider documenting “for viewing only” if not validated for measurement. |
| **Performance** | Large volumes, real-time oblique rotation | Cache resampled slices; reduce resolution during interaction; consider GPU (e.g. CuPy, OpenCL) in a later iteration if needed. |
| **Complexity** | MPR + W/L + overlays + ROIs + fusion is a large matrix | Implement orthogonal MPR first with basic W/L; add oblique and other integrations incrementally. Treat MPR as a distinct “mode” in UI and code to limit coupling. |
| **Slice location line** | Drawing current slice line on other views (TO_DO) | Use Phase 1 plane–plane intersection and projection; implement as a separate, smaller feature after Phase 2, reusing the same geometry. |

---

## Decisions to Be Made (Summary)

1. **Slice sync default**: On or off by default; and which subwindows participate (all vs same Frame of Reference vs user-linked).
2. **Strictness**: “Strict orthogonal only” vs “angled within N°” and tolerance (mm) for slice matching.
3. **MPR mode**: Separate “MPR layout/mode” vs integrated into current subwindows; and which features (ROIs, overlays, fusion) apply in MPR.
4. **Stack ordering**: Single definition of “slice index” for geometry (e.g. by position along stack normal) and how it maps to series navigator index.
5. **Slice location line**: Implement in same release as Phase 2 or as a follow-on; same geometry, different UI (draw line in 2D from projected intersection).

---

## File and Module Sketch

- **Phase 1**: `src/core/slice_geometry.py` (or `src/utils/slice_geometry.py`) — planes, stacks, intersection, nearest slice. Unit tests in `tests/` (e.g. `test_slice_geometry.py`).
- **Phase 2**: `src/core/slice_sync_coordinator.py` (or under `src/core/`) — responds to slice changes, uses geometry, updates other subwindows; config key in `display_config` or new mixin.
- **Phase 3**: New module(s) for volume building and MPR resampling (may extend `image_resampler`); MPR-specific UI (layout, controls) in `src/gui/`; possibly `src/core/mpr_volume.py` and `src/gui/mpr_*.py`.

---

## Changelog and Versioning

- **Changelog**: When Phase 1 or 2 is merged, add an entry (e.g. “Added slice geometry module and optional anatomic slice sync across views”). Phase 3 is a larger feature and should get its own entry.
- **Semantic versioning**: Phase 1–2 can be minor (e.g. 3.x.0) as new optional behavior; Phase 3 (MPR) is a significant feature — minor or major depending on project policy (see `dev-docs/RELEASING.md` and `dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`).

---

## References

- `dev-docs/TO_DO.md` — “Syncing Slices for Non-Orthogonal Orientations (Using ImagePositionPatient)”, “Slice Location Line Across Views”, “Multi-Planar Reconstructions (MPRs) and Oblique Reconstructions”.
- `src/utils/dicom_utils.py` — `get_image_position`, `get_image_orientation`, `pixel_to_patient_coordinates`.
- `src/core/fusion_handler.py` — `get_slice_location`, `find_matching_slice` (current 1D matching).
- `src/core/image_resampler.py` — 3D resampling with `ImagePositionPatient`, `ImageOrientationPatient`, spacing.
- `dev-docs/plans/IMAGE_FUSION_IMPLEMENTATION_PLAN.md` — structure and style for phased plans.
