# Plan: Top refactor extractions — 4 streams (tag-export controller, volume-viewer helpers, main-window status, MPR reslice)

> Filename keeps the `top3` slug for the existing TO_DO link; scope expanded to **4 streams** (added MPR reslice) per user decision 2026-06-14.

**Status:** Ready for review → implementation
**Priority:** P2 (maintainability; not release-gating)
**Source:** [refactor-assessment-2026-06-14](../../refactor-assessments/refactor-assessment-2026-06-14-160124.md) High-priority items #1–#4 (all four in scope per user decision 2026-06-14)
**Branch recommendation:** `feature/refactor-top3-extractions` (orchestrator-approved). Streams may use separate worktrees since file sets are disjoint.

## Goal and success criteria

Extract pure / focused units from three oversized GUI files **without behavior change**:

1. **`tag_export_dialog.py`** (1195) → pure `core/tag_export_controller.py` (selection model + export orchestration); dialog becomes presentation + signal wiring.
2. **`gui/volume_viewer_widget.py`** (1726) → `gui/volume/` helpers (preset catalog, render pipeline, transfer-function); widget stays a thin view.
3. **`gui/main_window.py`** (1749) → `gui/main_window_status_controller.py` (status-bar build + readouts); window keeps layout + signal surface.
4. **`gui/mpr_controller.py`** (1650) → Qt-free `core/mpr_reslice.py` (per-plane reslice math); controller keeps Qt + state + cine/scroll.

**Success criteria**
- [ ] No user-visible behavior change (verified by existing suites + manual smoke).
- [ ] Each touched file drops below or meaningfully toward the 600-line Python threshold; no new file > ~600 lines.
- [ ] New pure modules are **Qt/VTK-free where claimed** (esp. `core/tag_export_controller.py`) and unit-tested without a Qt app.
- [ ] `pytest` green; `scripts/check_repo_harness.py`, `scripts/check_architecture_boundaries.py`, agent smoke all green.
- [ ] No new architecture-boundary violations (core must not import `gui`/`PySide6`/`vtk`).

## Context and links

- Already-extracted collaborators to build on (avoid duplicating):
  - `core/tag_export_writer.py` (CSV/TXT/XLSX writers), `core/tag_export_analysis_service.py` (`analyze_tag_variations`), `core/tag_export_catalog.py`, `core/spreadsheet_safety.py`.
  - `gui/main_window_menu_builder.py` / `gui/main_window_toolbar_builder.py` (menu/toolbar already out); `core/wl_preset_catalog.format_status_bar_wl`.
  - `core/volume_opacity_model.py` (opacity mapping already partly extracted); `core/volume_renderer.py` (VTK).
- Guardrail scripts: `scripts/check_architecture_boundaries.py` (+ baseline), `scripts/check_repo_harness.py`, `scripts/agent_smoke_harness.py`.

## Task graph and gates

### Ordering (execution mode: **parallel** — user-approved 2026-06-14)
- Streams **A ∥ B ∥ C ∥ D** are parallel-safe: each touches a disjoint file set, shares no lockfile/mutable state, and adds its own new module + tests.
- **Recommendation:** land **Stream A first as the reference implementation** of the "extract a pure, Qt-free unit + Qt-free tests" pattern (~½ day ahead), then run **B ∥ C ∥ D** concurrently in separate worktrees. A is not a hard dependency — it just de-risks the shared pattern. If staffing one coder, serial order **A → C → D → B** (B last; highest risk).
- Each stream is internally sequential (its own task chain).

### Verification gates
- **Gate 1 (per stream):** tester runs the stream's new tests + `pytest -k` for touched areas → green before reviewer.
- **Gate 2 (per stream):** reviewer confirms no behavior change + `check_architecture_boundaries.py` clean → merge stream.
- **Gate 3 (final):** full `pytest`, harness, architecture-boundary, and manual smoke (open study; tag export CSV/XLSX; 3D volume; status-bar W/L readout; **MPR axial/coronal/sagittal reslice + scroll/cine**) before closing the plan.

### File / area ownership (disjoint → safe for separate worktrees)
- Stream A → `core/tag_export_controller.py` (new), `gui/dialogs/tag_export_dialog.py`, `tests/` → coder
- Stream B → `gui/volume/` (new pkg), `gui/volume_viewer_widget.py`, `tests/` → coder
- Stream C → `gui/main_window_status_controller.py` (new), `gui/main_window.py`, `tests/` → coder
- Stream D → `core/mpr_reslice.py` (new), `gui/mpr_controller.py`, `tests/` → coder

---

## Phases

### Phase A — Tag export controller (lowest risk, highest value; score 4.0) — **IMPLEMENTED 2026-06-14**
- [x] (A1) Inventory the non-UI logic in `tag_export_dialog.py`: format resolution + writer dispatch + variation-analysis/default-filename calls (the selection→dict derivation `_update_selected_*` stays in the dialog as it reads QTreeWidget state). (owner: coder, stream: A)
- [x] (A2) Create **`core/tag_export_controller.py`** — Qt-free `TagExportController` + `resolve_export_format`; delegates to `analyze_tag_variations` / `tag_export_writer`; XLSX→`[path]`, CSV/TXT→writer list; unknown format raises. **No PySide6 import** (boundary check clean). (owner: coder, stream: A)
- [x] (A3) Rewire `tag_export_dialog.py` `_export_to_excel` to build the controller and use `resolve_export_format` + `controller.export(...)`; removed direct writer/analysis imports. Dialog −39 lines (1195→1156). (owner: coder, stream: A)
- [x] (A4) Add `tests/test_tag_export_controller.py` (Qt-free): 15 tests — format resolution (filter/extension/default/no-double-ext), writer dispatch per format, XLSX single-path, unknown-format raises, analyze/default-filename delegation. (owner: coder, stream: A)
- [~] (A5) **Gate 1 green** (35 tag-export tests pass; boundary check 0 violations; import smoke OK; **basedpyright 0 errors** on both changed files — deprecation/unused-result warnings are codebase-wide). **Gate 2 (reviewer) pending.** Note: `basedpyright` had a corrupt partial install (missing `dist/pyright.js` → `MODULE_NOT_FOUND`); fixed via `pip install --force-reinstall basedpyright` (env-only, `.venv` untracked).

### Phase C — main_window status controller (score 3.5) — **IMPLEMENTED 2026-06-14** (by parent in main tree; subagent route blocked, see Execution note)
- [x] (C1) Inventoried: `_create_status_bar` (3 permanent labels), `update_status` (file/study), `update_zoom_preset_status` (zoom + W/L via `format_status_bar_wl`); `pixel_info_label` also set externally by `core/view_state_handlers.py`.
- [x] (C2) Created **`gui/main_window_status_controller.py`**: `MainWindowStatusController` (owns the 3 labels; `set_file_study`/`set_zoom_preset`/`set_pixel_info`) + **Qt-free** `format_zoom_preset_status` helper.
- [x] (C3) `main_window._create_status_bar` delegates to the controller (keeps `self.*_label` refs for backward compat); `update_status`/`update_zoom_preset_status` forward to it.
- [x] (C4) `tests/test_main_window_status_controller.py`: 8 tests — pure formatter (zoom-only, rounding, zoom+W/L matches catalog, partial-W/L ignored) + offscreen-Qt controller (label creation + set_* delegation).
- [~] (C5) **Gate 1 green**: 20 tests pass (8 new + 12 theme); boundary 0 violations; import smoke OK; basedpyright **0 new errors** (new file 0 errors). **Pre-existing (not mine):** 4 `layout_*_action` attribute errors at `main_window.py:1675-1681` (dynamic toolbar-builder attrs, from the asymmetric-layout feature) — flag for separate cleanup. **Gate 2 (reviewer) pending.**

### Phase B — volume viewer helpers — **IMPLEMENTED 2026-06-14 (conservative scope)**
**Finding:** like Stream D, the preset/transfer-function **data already lives in core**
(`volume_renderer`, `volume_3d_user_presets`, `volume_opacity_model`); the widget's bulk is
**Qt UI construction** (`_build_controls` ≈ 535 lines) + VTK event wiring, which **cannot be verified
headlessly**. Moving intricate Qt signal-wiring blind would be unsafe, so Stream B extracted the
genuinely-**pure** helpers and **deferred** the large Qt control-builder split (needs interactive 3D).
- [x] Created `gui/volume/` package (`__init__.py`, `overlay_text.py`).
- [x] Extracted **`gui/volume/overlay_text.py`** `build_overlay_text` (pure) from the widget.
- [x] Consolidated opacity-response math into **`core/volume_opacity_model.py`**: `response_to_gamma`
      + `RESPONSE_NEUTRAL/RESPONSE_GAMMA_MIN/RESPONSE_GAMMA_MAX` (removed the widget's duplicates).
- [x] Rewired widget imports + call sites; **caught & fixed** a would-be runtime `NameError`
      (leftover `_RESPONSE_NEUTRAL` slider default) via a basedpyright before/after error-count diff —
      it would only have surfaced on actual 3D widget construction (not import-smoke).
- [x] Tests: `tests/test_volume_overlay_text.py` (5) + `response_to_gamma` cases in
      `tests/test_volume_opacity_model.py`. 71 volume tests pass; boundary 0 violations; basedpyright
      **0 new errors** (widget stays at its pre-existing 45); import smoke OK.
- [ ] **Deferred follow-up:** extract `_build_controls` (~535 Qt lines) into `gui/volume/controls_builder.py`
      (mirrors `main_window_*_builder`) and VTK `pipeline.py` helpers — **requires manual 3D verification**;
      track as a separate item. (This is why volume_viewer_widget shrank only modestly here.)
- [ ] **Manual 3D smoke (Gate, user):** open a volume; change preset/opacity/W-L (incl. the
      contrast-depth/response slider); rotate; close — no regression/leak.

#### (original Phase B plan, superseded by the conservative scope above)
- [ ] (B1) Map `volume_viewer_widget.py` sections to targets: **Preset catalog** → `gui/volume/presets.py`; **Rendering** + **Progressive refinement** → `gui/volume/pipeline.py` (functions taking renderer/volume/mapper); transfer-function/opacity → consolidate with `core/volume_opacity_model.py` (extend, don't duplicate). (owner: coder, parallel-safe: yes, stream: B, after: none)
- [ ] (B2) Create `gui/volume/` package; move **preset catalog** (built-in + user-saved load/save/list) into `presets.py` — pure data/logic, unit-testable. (owner: coder, stream: B, after: B1)
- [ ] (B3) Extract VTK **pipeline build/update + progressive-refinement** helpers into `pipeline.py` as functions; widget calls them. Keep VTK objects owned by the widget; helpers operate on passed-in handles. (owner: coder, stream: B, after: B1)
- [ ] (B4) Add `tests/test_volume_presets.py` (pure; no VTK) for preset catalog; pipeline helpers covered by an import-smoke + existing `test_volume_render_facade_lifecycle.py`. (owner: coder, stream: B, after: B2)
- [ ] (B5) **Manual 3D smoke** (GPU-fallback CPU on Parallels — see [[user_dev_environment]]): open a volume, change preset, opacity, W/L, close — no regression/leak. (owner: coder, stream: B, after: B3)
- [ ] (B6) Gate 1+2 for Stream B.

### Phase D — MPR view-math extraction — **IMPLEMENTED 2026-06-14** (scope corrected)
**Finding (D1):** the per-plane **reslice math already lives in `core/mpr_builder.py` + `core/mpr_volume.py`** — the controller only *orchestrates* them (no raw reslice math to extract). The plan's premise was outdated. So Stream D extracted the remaining **pure view/display helpers** instead, into **`core/mpr_view_math.py`** (renamed from the planned `mpr_reslice.py` for honesty).
- [x] (D1) Inventoried `mpr_controller.py`; confirmed reslice math is already in `mpr_builder`/`mpr_volume`; identified pure helpers (combine-range, banner text, auto-W/L, array→PIL).
- [x] (D2) Created **`core/mpr_view_math.py`** (Qt/VTK-free; numpy + PIL): `compute_mpr_combine_range`, `build_mpr_banner_text`, `auto_window_level`, `array_to_pil`. Boundary check confirms no `gui`/PySide6/vtk import.
- [x] (D3) Rewired `mpr_controller.py`: the static methods `_compute_mpr_combine_range`/`_build_mpr_banner_text`/`_array_to_pil` and the `_get_window_level` auto-fallback now **delegate** to `mpr_view_math` (kept as thin wrappers to preserve the controller's API + existing tests). Controller 1650→1622.
- [x] (D4) Added `tests/test_mpr_view_math.py` (9 Qt-free deterministic tests — combine-range center/edges/clamps, banner variants, auto-W/L known/empty/constant, array→PIL linear-map + clip). These are the "golden" checks; existing `test_mpr_overlay_and_rescale.py` still exercises the controller wrappers (delegation verified).
- [x] (D5) **Manual MPR smoke** still recommended (axial/coronal/sagittal + scroll/cine) — pure helpers are behavior-identical (verbatim move), so low risk; fold into Gate 3.
- [~] (D6) **Gate 1 green**: 41 MPR tests pass (9 new + existing); boundary 0 violations; basedpyright **0 errors**; import smoke OK. **Gate 2 (reviewer) pending.**

### Phase E — Finalize
- [ ] (E1) Gate 3: full `pytest`, harness, boundary check, manual smoke across all four areas. (owner: tester/reviewer, after: A5,B6,C5,D6)
- [ ] (E2) Update the refactor assessment with post-refactor line counts. (owner: coder)

## Risks and mitigations
- **Behavior drift during move** → move code verbatim first, refactor shape second; rely on existing suites (`test_tag_export_*`, `test_main_window_theme`, volume facade lifecycle) + new tests.
- **Architecture-boundary regression** (core importing Qt) → `tag_export_controller` stays Qt-free; run `check_architecture_boundaries.py` in each Gate 1.
- **VTK/3D under-tested** (Stream B) → keep helpers thin and widget-owned; mandatory manual 3D smoke (B5); do Stream B last.
- **Hidden coupling in `main_window`** (71 methods) → scope Stream C to the status cluster only; defer broader splits to a follow-up.
- **MPR reslice numerical drift** (Stream D) → highest-consequence risk (wrong pixels are silent). Capture pre-refactor golden arrays for axial/coronal/sagittal on a synthetic volume **before** moving code; assert exact/within-tolerance equality after. Prefer extending existing `core/mpr_geometry`/`mpr_volume` over re-deriving math.

## Modularity and file-size guardrails
- Target: each new module ≤ ~400 lines; each touched file trending toward ≤ 600.
- Prefer pure functions + explicit args over reaching back into the widget/dialog for state.
- No new file should import across the `core → gui` boundary.

## Testing strategy
- **Add:** `test_tag_export_controller.py` (Qt-free), `test_main_window_status_controller.py`, `test_volume_presets.py`, `test_mpr_reslice.py` (Qt-free golden-array reslice).
- **Keep green:** `test_tag_export_writer.py`, `test_tag_export_catalog.py`, `test_roi_export_service_*`, `test_main_window_theme.py`, `test_volume_render_facade_lifecycle.py`, existing MPR suites (`test_mpr_*`), full `pytest`.
- **Harness:** `check_repo_harness.py`, `check_architecture_boundaries.py`, `agent_smoke_harness.py` at Gate 3.
- **Manual smoke:** tag export (CSV+XLSX, incl. a formula-like tag value to confirm `spreadsheet_safety` still applies), 3D volume preset/opacity/W-L, status-bar W/L + pixel-info readouts.

## UX / UI (deferred to ux subagent — do not finalize visual design here)
- These are **behavior-preserving** refactors; **no visual/UX change intended**. If any layout/label change becomes necessary, stop and route to ux.

## Resolved decisions (user, 2026-06-14)
1. **Scope = all four** — `mpr_controller` → `core/mpr_reslice` added as **Stream D**.
2. **Stream B layout = new `gui/volume/` subpackage** (`presets.py`, `pipeline.py`).
3. **Execution = parallel** streams in separate worktrees; land **Stream A first** as the reference pattern, then **B ∥ C ∥ D**.

_No blocking questions remain._

## Completion notes (filled by reviewer/coder later)
- …

---

**HANDOFF → orchestrator:** Plan ready for implementation (all decisions resolved). Assign **coder(s)** — no ux needed unless a UI change surfaces. Four parallel-safe streams (A: tag-export controller, B: `gui/volume/` helpers, C: main-window status controller, D: `core/mpr_reslice`). Recommend branch `feature/refactor-top3-extractions` (or per-stream `feature/refactor-<stream>` worktrees). **Land Stream A first** as the reference pattern, then run **B ∥ C ∥ D** concurrently. Per-stream Gate 1 (tests) + Gate 2 (review + boundary check); Gate 3 full suite + manual smoke before close. Note Stream D's golden-array requirement (capture pre-refactor reslice output before moving math).
