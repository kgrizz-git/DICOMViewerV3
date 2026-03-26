# MPR: Text/Arrow Annotations + Right-Pane “Combine Slices” – Implementation Plan

This plan is a **follow-on** to `dev-docs/plans/MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md`, which covered enabling ROI, distance measurement, and Window/Level ROI on MPR, plus an initial **slab-combine** path wired through the **Create MPR** dialog.

This document covers two remaining UX and parity goals:

1. **Text and arrow annotations on MPR subwindows** (same user workflows as non-MPR views, within MPR constraints).
2. **“Combine slices” for MPR using the usual right-panel control** (`IntensityProjectionControlsWidget` — “Combine Slices”), not only when first creating the MPR.

---

## Relationship to prior work

- [ ] **Baseline (existing / in progress):** ROI + measure + WL-ROI + builder/dialog slab combine are described in `MPR_MEASUREMENTS_ROI_TOOLS_AND_COMBINE_SLICES_PLAN.md`.
- [ ] **This plan:** Completes annotation parity and harmonizes intensity projection UX between standard series views and MPR.

---

## Goals

### A. Text and arrow annotations on MPR

- [ ] User can place **text annotations** and **arrow annotations** on an MPR subwindow while that subwindow is in MPR mode.
- [ ] Annotations are stored and keyed consistently with the rest of the app (study/series + **instance identifier** for the current “logical slice”).
- [ ] Changing the MPR navigator slice shows/hides the correct annotations for that slice (same behavior as non-MPR `display_slice` + coordinators).
- [ ] Copy/paste (`AnnotationPasteHandler`) and undo/redo paths behave correctly for MPR-scoped annotations (no cross-contamination with non-MPR scenes where inappropriate).

### B. Right-pane combine slices on MPR (parity with standard views)

- [ ] When the **focused** subwindow is in MPR mode, the right panel **Combine Slices** group remains meaningful:
  - [ ] **Enable Combine Slices** toggles slab-style combining along the MPR stack (same semantics as AIP/MIP/MinIP).
  - [ ] **Projection** dropdown maps to combine mode: Average (AIP), Maximum (MIP), Minimum (MinIP).
  - [ ] **Slices** count (2 / 3 / 4 / 6 / 8) selects how many **output MPR planes** participate in the slab around the current index (see **Semantics**).
- [ ] Changing any of these controls **updates the displayed MPR image** without requiring the user to re-open **Create MPR** (except when a full **rebuild** is explicitly chosen — see **Rebuild vs runtime combine**).
- [ ] Optional UX: keep the **Create MPR** dialog slab controls in sync with right-panel state when opening the dialog again, or document that the dialog is “initial defaults only” after first implementation pass.

---

## Non-goals

- [ ] **Fusion overlays on MPR** (separate item in `TO_DO.md`).
- [ ] **Crosshair / other tools** beyond text and arrow — unless already required for consistency (only text/arrow are in scope here).
- [ ] **Guarantee identical numeric results** between (1) series-stack combine in `SliceDisplayManager` and (2) MPR-stack combine — stacks and-spacing differ; document semantics per view type.

---

## Current state (starting point)

### Annotations deliberately restricted in MPR mode

- [ ] `src/gui/image_viewer.py` — under `_mpr_mode_override`, context menu / mode gating historically disabled annotation modes alongside other tools; ROI/measure may already be partially re-enabled elsewhere.
- [ ] `src/core/mpr_controller.py` — `display_mpr_slice` must mirror what `SliceDisplayManager.display_slice` does for annotations: `display_text_annotations_for_slice`, `display_arrow_annotations_for_slice` (plus ROI/measure as already added).

### Right-panel projection wired to **focused** `SliceDisplayManager` only

- [ ] `src/main.py` — `_on_projection_enabled_changed`, `_on_projection_type_changed`, `_on_projection_slice_count_changed` update `self.slice_display_manager` (focused subwindow’s manager) and call `_display_slice(self.current_dataset)`.
- [ ] In MPR mode, `current_dataset` is often the **synthetic overlay** dataset and `_display_slice` may not be the correct refresh path; MPR pixels come from `MprResult.slices` and `display_mpr_slice`.

### Create MPR dialog vs right pane

- [ ] Slab parameters may exist on `MprRequest` / `MprResult` from dialog creation; **right pane does not yet drive** those parameters for MPR.

---

## Semantics

### MPR slab window vs right-panel “Slices” count

- [ ] Treat the right-panel **Slices** value `N` as: “combine **N** consecutive **MPR output planes** centered (or clamped at ends) on the current `mpr_slice_index`,” using the selected **AIP/MIP/MinIP** mode.
- [ ] This aligns mentally with multi-slice projection along the direction **normal to the displayed plane** (the same axis the MPR navigator traverses).
- [ ] **Optional refinement (later):** offer mm-based thickness in addition to discrete `N`, or map `N` to mm via `output_thickness_mm` from `MprResult` for a tooltip (“≈ X mm”).

### Keying annotations on MPR

- [ ] Reuse existing `(study_uid, series_uid, instance_identifier)` pattern with `instance_identifier = mpr_slice_index` (already used for ROIs on MPR when overlay dataset carries study/series from source).
- [ ] Ensure **synthetic overlay dataset** used in MPR keeps stable **StudyInstanceUID** / composite **series key** so annotations collate with the same series as ROIs.

---

## Rebuild vs runtime combine

Pick one primary strategy (the other can remain a future optimization):

- [ ] **Option 1 — Runtime combine (recommended for responsiveness):** Keep the full `MprResult.slices` list as today; when combine is enabled, compute displayed slice = `f(stack[i-k..i+k])` in memory when rendering `display_mpr_slice`. **No cache invalidation** for projection toggle. *Requires* that `MprResult` always retains uncombined slices OR that builder stores both raw and combined (memory tradeoff — document choice).
- [ ] **Option 2 — Rebuild on parameter change:** Any right-panel change triggers `MprBuilder` (or slab-only pass) + cache key update. Simpler mentally, heavier on CPU and cache churn.

**Decision placeholder:** implement Option 1 unless profiling shows memory pressure on large stacks; then gate Option 2 behind user preference or size limits.

---

## Implementation phases (checklist)

### Phase 0 — Inventory and single source of truth for “MPR combine state”

- [ ] Add per-subwindow fields (e.g. in `subwindow_data` or a small dataclass) mirroring projection UI:
  - [ ] `mpr_combine_enabled: bool`
  - [ ] `mpr_combine_mode: str` (`"aip"|"mip"|"minip"`)
  - [ ] `mpr_combine_slice_count: int` (2–8)
- [ ] On MPR activation (`_activate_mpr`), initialize from **dialog** request if present, else from right-panel defaults.
- [ ] When focus changes to an MPR subwindow, **reflect** that subwindow’s combine state in `IntensityProjectionControlsWidget` (pattern already exists for non-MPR in `subwindow_lifecycle_controller`).

### Phase 1 — Route right-panel signals to MPR when focused window is MPR

- [ ] In `src/main.py` projection handlers (or a small delegate helper), branch:
  - [ ] If `_mpr_controller.is_mpr(focused_idx)`: update **that** subwindow’s MPR combine state, then `display_mpr_slice(focused_idx, current_slice_index)`.
  - [ ] Else: existing `slice_display_manager.set_projection_*` + `_display_slice` path.
- [ ] Ensure `IntensityProjectionControlsWidget` is **enabled** when viewing MPR (if it is currently disabled for MPR focus — verify and fix).

### Phase 2 — Implement MPR combine in `display_mpr_slice` (or helper)

- [ ] Given `combine_enabled` and mode + count, compute pixel array from `MprResult.slices` before window/level / PIL conversion.
- [ ] Ensure ROI / measurement / WL statistics use the **same** combined array as on-screen (extend `get_mpr_pixel_array` callback if it currently returns raw slice only).

### Phase 3 — Deprecate or sync dialog-only slab (product decision)

- [ ] Either:
  - [ ] **Keep dialog** as “defaults at create time” only and document; or
  - [ ] **Remove** duplicate slab UI from dialog and always use right panel; or
  - [ ] **Bidirectional sync:** dialog pre-fills from current right-panel state when opening **Create MPR** for a series.

### Phase 4 — Text and arrow annotations on MPR

- [ ] `src/gui/image_viewer.py`: allow `text_annotation` and `arrow_annotation` mouse modes under MPR restriction policy (remove from disabled set if still blocked).
- [ ] `src/core/mpr_controller.py`: after setting image for an MPR slice, call the same annotation display helpers used by `SliceDisplayManager` for the current overlay dataset (or factor shared helper to avoid drift).
- [ ] `src/gui/text_annotation_coordinator.py` / `src/gui/arrow_annotation_coordinator.py`: confirm `get_current_dataset` / slice index callbacks resolve to MPR overlay + `mpr_slice_index`; fix if they read wrong manager when focused MPR window is not slot 0.
- [ ] `src/core/annotation_paste_handler.py`: verify paste targets the correct subwindow ROI/annotation managers for MPR.
- [ ] Toolbar / menu actions that set mouse mode: ensure they are not blocked for MPR for text/arrow.

### Phase 5 — Testing & QA

- [ ] Manual: MPR with combine off — place text + arrow on slice 0 and slice 5; verify visibility when stepping navigator.
- [ ] Manual: enable right-panel combine, switch AIP/MIP/MinIP and slice counts; verify image updates and ROI stats (if any) match display.
- [ ] Automated (where feasible): unit tests for slab combine function given a toy `slices` stack (max/min/mean over window with edge clamping).

---

## Files likely to be touched (tracked)

- [ ] `src/main.py` — projection signal handlers; MPR branch; possibly `_display_slice` guard
- [ ] `src/core/mpr_controller.py` — combine state; `display_mpr_slice` pixel path; annotation refresh calls
- [ ] `src/core/subwindow_lifecycle_controller.py` — sync intensity projection widget when focusing MPR subwindow
- [ ] `src/gui/intensity_projection_controls_widget.py` — optional: tooltips / enablement rules for MPR
- [ ] `src/gui/image_viewer.py` — MPR mode gating for text/arrow
- [ ] `src/gui/text_annotation_coordinator.py` — MPR-safe dataset/slice resolution
- [ ] `src/gui/arrow_annotation_coordinator.py` — MPR-safe dataset/slice resolution
- [ ] `src/core/slice_display_manager.py` — optional: shared helper for “display annotations for dataset + slice index” to avoid duplication with MPR path
- [ ] `src/core/annotation_paste_handler.py` — paste selection / typing imports (already uses deferred annotations)
- [ ] `src/gui/dialogs/mpr_dialog.py` — optional: sync or simplify slab UI vs right panel
- [ ] `dev-docs/TO_DO.md` — link to this plan

---

## Risks

- **Memory:** Retaining full-resolution **uncombined** MPR stacks for runtime slab may duplicate memory if combined slices are also stored — decide one source of truth.
- **Stale cache:** If combine parameters are folded into `MprCache` keys, right-panel tweaks must update keys or bypass cache for runtime combine.
- **Focus bugs:** Global `slice_display_manager` vs per-subwindow managers — projection callbacks must always target the **focused** subwindow’s MPR state.

---

## Completion criteria

- [ ] Text and arrow annotations work on MPR subwindows, slice-scoped, with navigator and focus behaving consistently with non-MPR views.
- [ ] Right-panel **Combine Slices** drives MPR slab preview without reopening the MPR dialog.
- [ ] `CHANGELOG.md` updated under `[Unreleased]` when the feature ships.
- [ ] Relevant `TO_DO.md` items checked off or downgraded once verified.
