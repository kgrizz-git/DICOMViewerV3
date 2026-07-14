# Plan: Overlay slice / frame / instance position labels

**Last updated:** 2026-05-31  
**Status:** Supporting — not started  
**Backlog:** [`dev-docs/TO_DO.md`](../../TO_DO.md) — UX / Workflow

---

## Goal and success criteria

Improve **corner overlay** position text so users always see a coherent “where am I in what I loaded?” label, while still surfacing DICOM acquisition metadata when it differs from the loaded stack.

**Success criteria:**

- Overlay never shows an impossible fraction like **`Slice 104/11`** (numerator from DICOM `InstanceNumber`, denominator from loaded stack length).
- **Single-frame spatial stacks:** default label reflects **stack position** in the organized/loaded list (`Slice 5/11`), not raw `InstanceNumber`, unless the user opts into DICOM-instance numbering and the values are consistent with the loaded subset.
- **Multi-frame instances:** retain and extend Tier 1–2 labels (`Instance N/M · Frame A/B`, `Phase`, `b=`, etc.) from [`MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md`](../completed/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md).
- **MPR:** continue showing MPR stack index (already synthetic in `mpr_controller.py`); do not regress [`SLICE_SYNC_AND_MPR_PLAN.md`](../completed/SLICE_SYNC_AND_MPR_PLAN.md) overlay rules.
- **In-window slider**, **slice navigator**, and **cine bar** use the **same position semantics** as the corner overlay (or document intentional differences in the plan before ship).
- Unit tests cover partial load, non-contiguous `InstanceNumber`, full-series contiguous numbering, and multi-frame paths.

---

## Context and links

### Related TO_DO items

| Item | Relationship |
|------|----------------|
| **[P1] Overlay slice/frame/instance position labels** (this plan) | Primary tracker |
| **[P1] Differentiate frames, instances, and slices in the cine player** | Cine UI should reuse the same position model; overlay corner labels partially shipped |
| **[P2] Scroll by slice # vs ImagePositionPatient** | Optional navigation preference; overlay may offer a related “show spatial index” mode later |
| **[P2] Follow-up for multi-frame instance navigation** | Audit `current_slice_index` identity in ROI/cine before bounded per-instance scroll |
| **[P2] Enhanced multi-frame IOD navigation (Tier 3)** | Independent 2D axes; overlay labels for 4D (`Slice · Frame (time)`) |
| In-window slice/frame slider polish (P1–P3) | [`IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md`](IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md) — slider label must match corner overlay rules |

### Related plans and notes

- [`FUTURE_WORK_DETAIL_NOTES.md`](../../FUTURE_WORK_DETAIL_NOTES.md) — *Differentiating Frame # vs. Slice # vs. Instance #*
- [`MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md`](../completed/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md) — Tier 1–2 overlay labels (mostly shipped)
- [`SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md`](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md) — cine vocabulary and playback axes
- [`IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md`](IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md) — in-view slider `Slice` vs `Frame` mode
- [`SLICE_SYNC_AND_MPR_PLAN.md`](../completed/SLICE_SYNC_AND_MPR_PLAN.md) — MPR overlay uses stack index, excludes misleading spatial tags

### Root cause: `Slice 104/11`

In [`src/gui/overlay_text_builder.py`](../../../src/gui/overlay_text_builder.py), when `InstanceNumber` is in the corner tag list and `total_slices` is set:

```python
instance_num = int(value_str)  # DICOM InstanceNumber, e.g. 104
slice_display = f"Slice {instance_num}/{total_slices}"  # total_slices = len(loaded list), e.g. 11
```

The **numerator** is the DICOM acquisition instance index; the **denominator** is the **count of loaded slices in the viewer**. Those are different concepts. Partial folder load, skipped instances, or a series where `InstanceNumber` is not `1..N` produces **`current > total`**.

Callers pass `total_slices=len(series)` from [`slice_display_manager.py`](../../../src/core/slice_display_manager.py) and [`overlay_coordinator.py`](../../../src/gui/overlay_coordinator.py) but do **not** pass `current_slice_index` (stack position).

---

## Vocabulary (product-facing)

| Term | Meaning in overlay |
|------|-------------------|
| **Image** / **Slice** (stack) | Position in the **loaded, organized** series list (1-based). Denominator = `len(series)`. |
| **Instance** | DICOM SOP Instance (`InstanceNumber`, acquisition order). May not equal stack index. |
| **Frame** | Plane inside a multi-frame instance (`NumberOfFrames` > 1). |
| **Phase**, **b=**, **(time)** | Semantic frame types (Tier 2 — already in `format_multiframe_label`). |

**Recommendation:** Default corner text uses **stack position** for the fraction. Show DICOM `InstanceNumber` as a **secondary suffix** when it differs from stack position or when the loaded set is a strict subset of the series.

Example formats:

| Situation | Default overlay |
|-----------|-----------------|
| Full series, `InstanceNumber` matches stack order 1..N | `Slice 5/104` *or* `Slice 5/104 (Inst 5)` — see open question below |
| Partial load (11 of 104), stack index 5, `InstanceNumber` 104 | `Slice 5/11 (Inst 104)` |
| Multi-instance multi-frame (CCL2) | `Instance 2/5 · Frame 4/12` (unchanged) |
| MPR | `Slice 12/40` (MPR stack index; no raw IPP) |

---

## Recommended approach (default behavior)

### Phase 1 — Fix incoherent fractions (bug)

1. Thread **`stack_index`** (0-based) or **`stack_position`** (1-based) into `get_corner_text()` / overlay creation alongside `total_slices`.
2. For **non-multiframe** single-frame stacks, when formatting `InstanceNumber`:
   - **Primary:** `Slice {stack_position}/{total_slices}`.
   - **Secondary:** if DICOM `InstanceNumber` is present and `int(InstanceNumber) != stack_position`, append ` (Inst {InstanceNumber})`.
   - **Never** use raw `InstanceNumber` as the fraction numerator unless a future user preference explicitly selects “DICOM instance number” mode *and* the series passes a consistency check (Phase 3).
3. Update tests in `tests/test_mpr_overlay_and_rescale.py`, `tests/smoke/test_refactor_regression.py`, and add **`tests/test_overlay_position_labels.py`** for partial-load and mismatch cases.

### Phase 2 — Unify labels across UI surfaces

Align terminology and indices on:

- Corner overlay (`overlay_text_builder.py`, `overlay_manager.py`)
- Slice navigator badge (already uses instance/frame counts — verify consistency)
- In-window slider (`edge_reveal_slider_overlay.py` — see [`IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md`](IN_WINDOW_SLICE_FRAME_SLIDER_POLISH_PLAN.md) T4/T18)
- Cine controls (`cine_player.py`, `cine_controls_widget`) — defer axis modes to [`SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md`](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md), but **linear position readout** should match overlay stack semantics

Extract a small shared helper (e.g. `core/overlay_position_label.py` or functions on `overlay_text_builder.py`) so corner overlay and slider do not diverge.

### Phase 3 — Optional user preference (P2)

Add **`overlay_position_label_mode`** (Settings or Overlay Settings dialog):

| Mode | Behavior |
|------|----------|
| **Stack position** (default) | Phase 1 behavior |
| **DICOM InstanceNumber** | `Inst {InstanceNumber}/{max_instance_in_loaded_set}` or `Inst {InstanceNumber}` without total if max unknown — only enabled when loaded set is verified consistent |
| **Spatial** (future / tie-in) | Show projected `SliceLocation` or IPP component; links to scroll-by-IPP TO_DO |

Start with **stack position default only**; defer Settings UI until Phase 1 is verified in manual QA.

---

## Task graph and gates

### Ordering

- T1 → T2 → T3 (audit + API + fix) before T4 (tests).
- T5 (shared helper) ∥ T6 (call-site threading) after T3 design is fixed.
- T7 (slider/cine alignment) after T5, coordinates with in-window slider plan T4/T18.
- T8 (optional preference) after Phase 1 gate.

### Verification gates

- **Gate 1:** Reviewer approves default label format (`Slice N/M (Inst X)` rule) before coding.
- **Gate 2:** Unit tests green for partial load + multiframe regression.
- **Gate 3:** Manual smoke on partial folder load, full CT stack, CCL2 multi-frame, MPR pane.

### File ownership

| Area | Modules |
|------|---------|
| Label logic | `src/gui/overlay_text_builder.py`, new helper if split |
| Call sites | `src/core/slice_display_manager.py`, `src/gui/overlay_coordinator.py`, `src/core/privacy_controller.py`, `src/core/export_rendering.py` |
| Multiframe | `src/core/dicom_organizer.py` (`get_multiframe_display_context`) |
| Slider sync | `src/core/subwindow_image_viewer_sync.py`, `src/gui/edge_reveal_slider_overlay.py` |
| Tests | `tests/test_overlay_position_labels.py`, extend existing overlay tests |

---

## Phases (checklist)

### Phase 1 — Coherent stack position labels

- [x] (T1) Scenarios documented inline in completion notes / tests: full stack (matching InstanceNumber), partial load (5/11 with Inst 104), CCL2 multi-frame, MPR (synthetic 1-based InstanceNumber), projection range.
- [x] (T2) Added `stack_position: Optional[int]` (1-based) to `get_corner_text()`, `OverlayManager.create_overlay_items()`, and `_create_widget_overlays()`.
- [x] (T3) Implemented Phase 1 formatting rules for `InstanceNumber`; `format_multiframe_label()` path preserved when `multiframe_context` is set (verified by `test_multiframe_context_unchanged_by_stack_position`).
- [x] (T4) Unit tests added in `tests/test_overlay_position_labels.py` (partial-load suffix, matching omits suffix, multiframe unchanged, legacy + guard, projection).

### Phase 2 — Cross-surface consistency

- [x] (T5) Not extracted as a separate module — logic kept inline in `get_corner_text()` (single source of `Slice X/Y`); no divergence risk since no other surface builds the fraction.
- [x] (T6) Stack position passed from `display_slice` (`_render_scene_overlays_annotations`), the overlay_coordinator refresh paths, MPR, and the export screenshot overlay path. (Privacy refresh routes through `display_slice` and inherits it; its rare exception-fallback passes no `total_slices` so the branch is not reached.)
- [x] (T7) In-window slider already consistent: it renders no embedded slice text and uses 1-based stack positions (`edge_reveal_slider_overlay.py`). No change needed.
- [ ] (T8) Align cine position readout with stack semantics; leave playback **axis** modes to [SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md) (owner: coder, parallel-safe: no, stream: none, after: T5). **Deferred.**

### Phase 3 — Preferences and spatial display (optional)

- [ ] (T9) Product decision: when full series loaded and `InstanceNumber` runs 1..N in stack order, show suffix `(Inst N)` or omit redundant suffix (owner: ux, parallel-safe: no, stream: none, after: Gate 1).
- [ ] (T10) Optional `overlay_position_label_mode` in overlay/display config + Settings (owner: coder/ux, parallel-safe: no, stream: none, after: T9).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Users expect PACS `InstanceNumber` as primary | Secondary `(Inst …)` suffix; optional preference in Phase 3 |
| Breaking tests that assert `Slice 2/10` from InstanceNumber | Update tests to pass `stack_position`; add explicit “legacy InstanceNumber mode” test if preference added |
| ROI/measurements use `current_slice_index` not InstanceNumber | Do not change storage identity in Phase 1; overlay-only |
| Export/screenshot overlay out of sync | Include `export_rendering.py` in T6 call-site audit |

---

## Testing strategy

- **Unit:** `tests/test_overlay_position_labels.py` — pure `get_corner_text()` cases.
- **Regression:** existing `test_mpr_overlay_and_rescale.py`, `test_multiframe_tier2.py`, `test_refactor_regression.py` overlay assertions.
- **Manual:** [`dev-docs/orchestration/AGENT_SMOKE.md`](../../orchestration/AGENT_SMOKE.md) — partial folder load, scroll overlay, toggle overlay mode, MPR subwindow.

---

## Questions for user (non-blocking for Phase 1)

1. **Full series, matching InstanceNumber:** prefer `Slice 5/104` only, or always append `(Inst 5)` when InstanceNumber equals stack position?
2. **Partial load:** is `Slice 5/11 (Inst 104)` acceptable, or prefer `Image 5/11` wording to avoid “slice” ambiguity?
3. **Phase 3 preference:** worth a Settings toggle in v1, or ship stack-position default and revisit only if users ask?

**Phase 1 default if unanswered:** `Slice {stack}/{total}` with `(Inst {n})` suffix **only when** `n != stack`.

---

## UX / UI

Defer visual design of Settings controls to **ux** subagent. Phase 1 is logic-only in existing corner overlay font/layout.

---

## Completion notes

**Phase 1 done 2026-06-03 (core bug fixed).**

- `get_corner_text()` (`src/gui/overlay_text_builder.py`) gained a `stack_position: Optional[int]` (1-based) parameter. When provided, the `Slice X/Y` numerator is the **stack position** and the denominator is `total_slices`; the raw DICOM `InstanceNumber` is appended as ` (Instance N)` only when it differs. This eliminates `Slice 104/11`. (Suffix wording is the full word `Instance`, not abbreviated `Inst`, to avoid confusion.)
- Back-compat fallback (no `stack_position`): existing behavior preserved when `InstanceNumber <= total_slices` (`Slice 2/10`); when `InstanceNumber > total_slices` the unknown denominator is dropped (`Slice 104`) so an impossible fraction can never render even from an un-threaded caller.
- `stack_position` threaded through `OverlayManager.create_overlay_items()` + `_create_widget_overlays()` (stored as `current_stack_position` for the deleted-item refresh path) and all call sites: `slice_display_manager._render_scene_overlays_annotations` (`current_slice_index + 1`), the four `overlay_coordinator` refresh paths, `mpr_controller` (passes `slice_index + 1`; its synthetic overlay dataset already sets `InstanceNumber` to the 1-based stack index, so no `(Inst)` suffix appears), and `export_rendering` (`slice_index + 1`).
- **Cross-surface check (Phase 2 partial):** the in-window slider (`edge_reveal_slider_overlay.py`) intentionally renders no embedded slice text (overlays own it) and operates on 1-based stack positions, so it is already consistent. A repo-wide search confirmed `overlay_text_builder` is the **only** place that builds a `Slice X/Y` fraction — no other surface reproduced the bug.

Tests: new `tests/test_overlay_position_labels.py` (7 cases: partial-load suffix, no-impossible-fraction, matching-omits-suffix, legacy path kept, legacy guard, projection, multiframe-unchanged). Regression: `test_mpr_overlay_and_rescale.py`, `test_refactor_regression.py`, plus a 120-test sweep over overlay/slice_display/mpr/privacy/export/multiframe — all green.

**Remaining (deferred / optional):**
- Phase 2 T8 — align the **cine** position readout explicitly with stack semantics (cine is still slice-index oriented; tracked with the cine-axis item in `SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md`).
- Phase 3 — optional `overlay_position_label_mode` user preference (DICOM-instance / spatial modes). Not started; ship stack-position default and revisit if users ask (open question 3).
- Manual smoke (Gate 3) on a real partial folder load / CCL2 / MPR pane not performed in this environment.
