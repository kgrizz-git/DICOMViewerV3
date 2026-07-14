# Plan: Pylinac Nuclear FourBarResolution Integration

Last updated: 2026-06-11

## Goal and success criteria

Add `pylinac.nuclear.FourBarResolution` as the **second** nuclear-medicine QC test in DICOM Viewer V3, reusing the PlanarUniformity slice's runner/worker/dialog/export/figure plumbing. Because this is the first time the nuclear subsystem carries **two** tests with **different parameters and different result shapes**, the slice must also generalize the parts that were PlanarUniformity-specific — without regressing PlanarUniformity.

Success criteria:

- A user can pick **Four Bar Resolution** in the existing Nuclear Medicine QC dialog, supply a single planar NM DICOM, set `separation_mm` / `roi_width_mm`, run off the UI thread, and review results.
- FourBar's **flat single result** (8 floats) is normalized into `QAResult` and shown in the result dialog as a metric/value table (PlanarUniformity's per-frame table still works).
- Export JSON, Export CSV, and Save Figure (PNG) all work for FourBar.
- Provenance records the FourBar class, its parameters, and stock-equivalence — without leaking PlanarUniformity-only fields.
- PlanarUniformity behavior, tests, and JSON are unchanged.
- No new third-party data is committed; FourBar validation uses the local IAEA `FourBar.dcm` (already present under `sample-DICOM-gitignored/nmqc/`).

Branch recommendation: `feature/nuclear-fourbar-resolution` (orchestrator-approved).

## Context and links

- Builds on completed slice: `dev-docs/plans/supporting/PYLINAC_NUCLEAR_MEDICINE_MODULE_INTEGRATION_PLAN.md` (PlanarUniformity, T1–T14, Gates A/B; figure export T9 done).
- Research note: `dev-docs/info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md` §2 (`pylinac.nuclear`).
- Integration overview: `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` (nuclear row, JSON-schema and figure notes).
- Reusable code seams (all shipped by the PlanarUniformity slice):
  - `src/qa/pylinac_nuclear.py` — `run_nuclear_analysis` dispatcher + `_NUCLEAR_RUNNERS`; add a FourBar runner here.
  - `src/qa/analysis_types.py` — `NuclearQAOptions` (nested on `QARequest`) and `build_nuclear_analysis_profile`.
  - `src/utils/config/qa_nuclear_config.py` — class names, analysis-type ids, defaults, bounds.
  - `src/qa/worker.py` — routes `analysis_type in NUCLEAR_ANALYSIS_TYPES` to `run_nuclear_analysis` (no change needed if the new type is registered).
  - `src/qa/qa_export.py` — `build_single_run_document`, `build_metrics_csv` (flat metric,value), `build_nuclear_frames_csv` (per-frame).
  - `src/qa/pylinac_nuclear_plots.py` — `render_nuclear_figures` (main-thread PNG; currently PlanarUniformity-only).
  - `src/gui/dialogs/nuclear_qa_dialog.py` — options dialog with the supported-test dropdown (`_SUPPORTED_TESTS`).
  - `src/gui/dialogs/nuclear_result_dialog.py` — per-frame table + Export JSON/CSV + Save Figure buttons.
  - `src/gui/qa_app_facade.py` — `open_nuclear_qc_analysis`, nuclear routing in `on_result`.

## Verified API (probed against pinned pylinac 3.43.2)

```
FourBarResolution(path: str | Path)
FourBarResolution.analyze(separation_mm: float = 100, roi_width_mm: float = 10) -> None
FourBarResolution.plot(show: bool = True) -> (list[Figure], list[Axes])
FourBarResolution.results_data(as_dict=...) -> FourBarResolutionResults | dict | str
```

`results_data(as_dict=True)` returns a **single flat dict** (not frame-keyed):

```
x_fwhm, y_fwhm, x_fwtm, y_fwtm,
x_measured_pixel_size, y_measured_pixel_size,
x_pixel_size_difference, y_pixel_size_difference   # all float
```

Confirmed on local `FourBar.dcm` (Modality NM, 1 frame). Per upstream docs FourBar uses **only the first frame** of a multi-frame image.

## Key differences from PlanarUniformity (these drive the work)

1. **Result shape:** flat single result (8 floats) vs PlanarUniformity's frame-keyed dict. The runner normalization, the result dialog table, and CSV must handle **both** shapes.
2. **Parameters:** `separation_mm` / `roi_width_mm` vs `ufov_ratio` / `cfov_ratio` / `window_size` / `threshold`. The options dialog must show **different parameter controls per selected test**.
3. **Figure rendering:** `render_nuclear_figures` currently hardcodes `PlanarUniformity`; it must dispatch by class.
4. **First-frame-only:** warn when a multi-frame image is supplied (FourBar silently uses frame 1).

## Task graph and gates

### Ordering

- T1 → T2 → T3 (contracts → config → runner) before any UI/export work.
- T4 (result-dialog generalization) and T5 (options-dialog dynamic params) are UI; T4 ∥ T6 (figure dispatch) since disjoint files; T5 depends on T1.
- T7 (facade default-stem / labels) after T5.
- Tests (T8–T11) follow their targets; docs (T12) last.
- Gate A after T3 (runner verified against real `FourBar.dcm`). Gate B before merge (tests + harness + one manual UI run).

### Verification gates

- **Gate A:** reviewer confirms the FourBar runner returns normalized metrics on real `FourBar.dcm` and that PlanarUniformity still passes (no shared-shape regressions).
- **Gate B:** tester verifies unit + dialog + export + integration suites, repo harness, and a manual UI run (pick Four Bar Resolution → run → review → export JSON/CSV/PNG).
- **Gate C (unchanged):** physicist review before any pass/fail labels — out of scope here (metrics-only).

### File / area ownership

- `src/qa/*` → coder (contracts, config, runner, export, figure dispatch).
- `src/gui/dialogs/nuclear_qa_dialog.py`, `nuclear_result_dialog.py` → ux/coder (dynamic params, generalized result table).
- `tests/*` → tester/coder.
- `user-docs/`, `dev-docs/` → docwriter after behavior stabilizes.

## Phases

### Phase 1 — Contracts, config, runner

- [x] (T1) Extend `NuclearQAOptions` for FourBar without breaking PlanarUniformity (owner: coder, parallel-safe: no, stream: A, after: none)
  - Add `separation_mm` / `roi_width_mm` fields (defaults from config). Extend `analyze_kwargs()` and `is_pylinac_default()` with a FourBar branch keyed on `analysis_class`.
  - Keep one dataclass with per-class branching for now (two classes). Add a **refactor trigger**: if a 3rd/4th class lands, split into per-class option dataclasses.
- [x] (T2) Add FourBar config constants (owner: coder, parallel-safe: yes, stream: A, after: none)
  - `FOUR_BAR_RESOLUTION_CLASS = "FourBarResolution"`, `NUCLEAR_FOUR_BAR_RESOLUTION = "nuclear_four_bar_resolution"`, defaults `separation_mm=100`, `roi_width_mm=10`, and viewer-side bounds.
- [x] (T3) Add `run_four_bar_resolution_analysis` and register it (owner: coder, parallel-safe: no, stream: A, after: T1,T2)
  - Lazy import `FourBarResolution`; reuse missing-pylinac fallback, `_resolve_input_path`, and NM modality preflight from `pylinac_nuclear.py`.
  - Normalize the **flat** `results_data(as_dict=True)` into `QAResult.metrics` under a stable key (e.g. `metrics["results"] = {8 floats}`, plus `analysis_class` and `analysis_parameters`); store the raw dict in `raw_pylinac`.
  - Warn when the input has >1 frame (FourBar uses frame 1 only).
  - Register in `_NUCLEAR_RUNNERS` so `NUCLEAR_ANALYSIS_TYPES` and the worker pick it up automatically.
- [x] Gate A: runner verified on real `FourBar.dcm`; PlanarUniformity unaffected.

### Phase 2 — UI (options dialog + result dialog)

- [x] (T4) Generalize the result dialog for flat (non-frame) results (owner: ux/coder, parallel-safe: yes, stream: B, after: T3)
  - If `metrics["frames"]` present → keep the per-frame table. Else render a 2-column **metric/value** table from the flat result (`metrics["results"]`). Keep class name, parameters, warnings, and the not-validated note.
  - Ensure Export CSV picks the right builder (frames → `build_nuclear_frames_csv`; flat → `build_metrics_csv` over the result fields). Save Figure stays class-dispatched (T6).
- [x] (T5) Add dynamic per-test parameter controls to the options dialog (owner: ux/coder, parallel-safe: no, stream: C, after: T1)
  - Add "Four Bar Resolution" to `_SUPPORTED_TESTS`. Swap the parameter group when the test dropdown changes (e.g. `QStackedWidget`): PlanarUniformity shows the 4 uniformity params; FourBar shows `separation_mm` / `roi_width_mm`.
  - `get_options()` builds a `NuclearQAOptions` with the fields for the selected class only.
- [x] (T6) Dispatch figure rendering by class (owner: coder, parallel-safe: yes, stream: B, after: T3)
  - In `render_nuclear_figures`, map `analysis_class` → pylinac class (PlanarUniformity, FourBarResolution); both expose `plot(show=False)`. Keep main-thread-only contract; FourBar yields a single figure → single PNG.
- [x] (T7) Facade labels / default stems for FourBar (owner: coder, parallel-safe: no, stream: C, after: T5)
  - Route the selected test's `analysis_type` and a sensible `json_default_stem` (e.g. `qa-nuclear-four-bar-resolution`) into the existing `open_nuclear_qc_analysis` flow. No new menu entry (same Nuclear Medicine QC action).

### Phase 3 — Tests

- [x] (T8) Unit tests: mocked FourBar runner (success/flat-normalization, missing pylinac, multi-frame warning, options round-trip) (owner: tester/coder, parallel-safe: yes, stream: D, after: T3)
- [x] (T9) Dialog tests: dropdown switches parameter group; FourBar `get_options()`; result dialog renders metric/value table for flat results (owner: tester/coder, parallel-safe: yes, stream: D, after: T4,T5)
- [x] (T10) Export tests: FourBar JSON (`run.nuclear_analysis_class`), CSV (flat builder) (owner: tester/coder, parallel-safe: yes, stream: D, after: T4)
- [x] (T11) Integration (gated on `DICOMVIEWER_NMQC_SAMPLE_PATH`): real `FourBar.dcm` runner + figure render (owner: tester/coder, parallel-safe: yes, stream: D, after: T3,T6)
- [x] Gate B: focused suites + repo harness + one manual UI run green.

### Phase 4 — Docs

- [x] (T12) Update user + developer docs (owner: docwriter, parallel-safe: yes, stream: E, after: T7)
  - User guide: add Four Bar Resolution to the supported-tests table, its inputs/params, first-frame-only note, and outputs.
  - Integration overview: note the second nuclear class and the flat-vs-frame result handling.

## Risks and mitigations

- **Shared-shape regression:** generalizing the result dialog / CSV could break PlanarUniformity. Mitigate by branching on `metrics["frames"]` presence and keeping PlanarUniformity tests green (Gate A/B).
- **Options dataclass bloat:** mixing per-class fields in `NuclearQAOptions`. Mitigate with class-keyed branching now + an explicit refactor trigger at the 3rd class.
- **Dialog complexity:** dynamic parameter swapping can get messy. Mitigate with a simple `QStackedWidget` keyed off the dropdown; defer fancier UX to the ux subagent.
- **First-frame-only confusion:** users may expect per-frame FourBar output. Mitigate with an explicit warning when >1 frame is supplied.
- **Figure dispatch drift:** hardcoded class in `render_nuclear_figures`. Mitigate with a small class map + a gated real-data render test.

## Modularity and file-size guardrails

- Keep the FourBar runner in `pylinac_nuclear.py` next to PlanarUniformity; if that module grows large, split per-class runner helpers but keep one dispatcher.
- Keep result normalization pure/testable without Qt.
- Keep dialog parameter groups in `nuclear_qa_dialog.py`; do not push QA logic into the facade.
- Reuse `qa_export.py` builders rather than adding FourBar-specific serializers (flat results already fit `build_metrics_csv`).

## Testing strategy

- `python -m pytest tests/test_pylinac_nuclear*.py tests/test_nuclear_*.py tests/test_qa_export_builders.py -q --basetemp=.codex-tmp\\pytest-nuclear-fourbar`
- `python scripts/check_repo_harness.py`; `python scripts/check_architecture_boundaries.py`; `python scripts/check_user_docs_links.py` if docs change.
- Integration: set `DICOMVIEWER_NMQC_SAMPLE_PATH` to the local IAEA set; FourBar sample is `PixelSz&Resolution/FourBar.dcm`.
- Manual smoke: Tools → Automated QA → Nuclear Medicine QC → Four Bar Resolution → run → review metric table → Export JSON/CSV → Save Figure (PNG).

## UX / UI (deferred to ux subagent — do not finalize visual design here)

- Same Nuclear Medicine QC dialog; the only new UI is a parameter group that swaps with the test dropdown.
- Result dialog shows a metric/value table for FourBar (x/y FWHM, FWTM, measured pixel size, pixel-size difference) with the existing export buttons.

## Questions for user (blocking if empty before coding)

- Confirm FourBar is the intended next test (vs QuadrantResolution, which produces lp/mm-style output and may be more familiar for some sites).
- For FourBar's measured pixel size, should results display in mm with a fixed precision (e.g. 3 decimals), or echo pylinac's raw floats? (Default: 3 decimals, matching the PlanarUniformity table.)
- Any need to expose the first-frame-only behavior as a frame picker later, or is "uses frame 1 + warn" acceptable for the first release? (Default: warn only.)

## Completion notes (filled by reviewer/coder later)

To be filled during implementation.

---

**HANDOFF → orchestrator:** Plan ready for implementation. Sequential core (T1→T2→T3) then parallel UI/figure (T4 ∥ T5 ∥ T6) and tests (T8–T11), docs last. Gate A after T3 (real-data runner check), Gate B before merge. Recommend branch `feature/nuclear-fourbar-resolution`. **Ready for orchestrator to assign coder (and ux for the dialog work).** Three non-blocking questions for the user are listed above; defaults are proposed so coding can start on the core (T1–T3) without waiting.
