# Plan: Pylinac Nuclear SPECT / Tomographic Tests

Last updated: 2026-06-12

## Goal and success criteria

Integrate the six remaining `pylinac.nuclear` tests into DICOM Viewer V3's Nuclear Medicine QC workflow, reusing the shipped planar scaffolding (per-class `NuclearOptions` tagged union, dispatcher runner, options/result dialogs, JSON/CSV/PNG export). The tests differ in inputs and result shapes, so this plan sequences them **by scaffolding impact** — ship the trivial ones fast, then the new-UI ones, then the one that breaks single-file assumptions.

Tests in scope: `CenterOfRotation`, `TomographicResolution`, `MaxCountRate`, `TomographicUniformity`, `TomographicContrast`, `SimpleSensitivity`.

Success criteria:

- Each test is selectable in the existing Nuclear Medicine QC dialog with only the parameters it needs, runs off the UI thread, and shows results in a table.
- Each test's result shape is normalized into `QAResult` and rendered (flat, nested-per-item, or single-value) without regressing the planar trio.
- A **new per-class `NuclearOptions` dataclass** is added for each test (no field piling — the tagged-union refactor is already in place).
- `SimpleSensitivity`'s **second input (background) file** and **Nuclide enum + required activity** are supported without polluting the single-file flow used by all other tests.
- Provenance, JSON, and CSV export work for every test; figure export works where the class exposes `plot()`.
- Validation uses the local IAEA samples already on disk (no new committed data). Gate C (pass/fail thresholds) is **out of scope** — metrics-only.

Branch recommendation: `feature/nuclear-spect-tests` (orchestrator-approved). Tiers may ship as separate PRs onto `WIP`.

## Context and links

- Builds on shipped slices: `PYLINAC_NUCLEAR_MEDICINE_MODULE_INTEGRATION_PLAN.md` (PlanarUniformity), `PYLINAC_NUCLEAR_FOURBAR_RESOLUTION_PLAN.md` (FourBar + multi-class generalization). QuadrantResolution and the per-class options refactor are also shipped on `WIP`.
- Research note: `dev-docs/info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md` §2.
- Integration overview: `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` (nuclear row).
- Reusable seams: `src/qa/analysis_types.py` (`NuclearOptions` base + per-class dataclasses, `build_nuclear_analysis_profile`), `src/qa/pylinac_nuclear.py` (`_NUCLEAR_RUNNERS` dispatcher, `_resolve_run_inputs`), `src/utils/config/qa_nuclear_config.py`, `src/qa/qa_export.py`, `src/qa/pylinac_nuclear_plots.py`, `src/gui/dialogs/nuclear_qa_dialog.py` (`QStackedWidget` per-test pages), `src/gui/dialogs/nuclear_result_dialog.py` (frame / quadrant / flat tables), `src/gui/qa_app_facade.py` (`_NUCLEAR_CLASS_ROUTING`, `open_nuclear_qc_analysis`).
- **Do NOT reuse `_frame_count_warning` for these tests.** That helper warns "first frame only" and exists for the planar resolution tests (FourBar/Quadrant). Every SPECT/tomographic test here — and MaxCountRate (dynamic) — **uses all frames**, so the runners must mirror **PlanarUniformity** (no frame-count warning), not FourBar. Adding the warning would be incorrect/misleading.

## Verified API (probed against pinned pylinac 3.43.2 — S1 confirmed on real data 2026-06-12)

| Class | Constructor | analyze() | results_data shape | `plot()` | Local IAEA sample (verified run) |
|-------|-------------|-----------|--------------------|----------|----------------------------------|
| `CenterOfRotation` | `(path)` | `()` — no params | flat: `x_deviation_mm`, `y_deviation_mm` | ✓ | `COR/COR_102.dcm` |
| `TomographicResolution` | `(path)` | `()` — no params | flat: `x/y/z_fwhm`, `x/y/z_fwtm` (6) | ✓ | `TomoResolution.dcm` |
| `MaxCountRate` | `(path)` | `(frame_duration=1.0)` | flat: `max_countrate`, `max_frame`, `frame_duration` + **`sums`** (frame-keyed dict, ~24 frames) | ✓ | `MaxCountRate.dcm` |
| `TomographicUniformity` | `(*args, **kwargs)` → plain **path works** | `(first_frame=0, last_frame=-1, ufov_ratio=0.8, cfov_ratio=0.75, center_ratio=0.4, threshold=0.75, window_size=5)` | flat: cfov/ufov integral+differential, `center_border_ratio`, `first/last_frame` | ✓ | `Jaszack.dcm` |
| `TomographicContrast` | `(path)` | `(sphere_diameters_mm=(38,31.8,25.4,19.1,15.9,12.7), sphere_angles=(-10,-70,-130,-190,110,50), ufov_ratio=0.8, search_window_px=5, search_slices=3)` | `uniformity_baseline` (float) + **`spheres`** (dict keyed "1".."6"; each: `x,y,z,radius,mean,mean_contrast,max_contrast`) | ✓ | **`Jaszack.dcm` works with default spheres** |
| `SimpleSensitivity` | `(phantom_path, background_path=None)` | `(activity_mbq, nuclide: Nuclide)` — **both required** | flat: `phantom_cps`, `background_cps`, `half_life_s`, `duration_s`, `decay_correction`, `sensitivity_mbq`, `sensitivity_uci` | **✗ no plot()** | `sensitivity/PetriDish` (+ optional `sensitivity/Background`) |

`Nuclide` enum members: `Ga67`, `I131`, `In111`, `Lu177`, `Tc99m`, `Y90`. The IAEA `sensitivity/` files have **no `.dcm` extension** — pydicom `force=True` (already used) reads them fine.

**S1 resolutions (Gate A cleared):**
- TomographicUniformity's `(*args, **kwargs)` constructor accepts a plain path — no special loader needed.
- TomographicContrast runs on the local `Jaszack.dcm` with default sphere geometry → its integration test is **not** blocked.
- SimpleSensitivity: two-file works; **background is genuinely optional** (omitting it gives `background_cps=0.0`). It has **no `plot()`**, so Save Figure must be disabled for it (see T3.3 / figure-dispatch note).
- All other five expose `plot()` and produce flat results; only `MaxCountRate.sums` and `TomographicContrast.spheres` are nested.

## Tiers (drives sequencing)

- **Tier 1 — trivial (fit current single-file scaffolding):** `CenterOfRotation`, `TomographicResolution`, `MaxCountRate`. No/one scalar param; flat results. `MaxCountRate.sums` is a nested dict to keep in `raw_pylinac` but omit from the headline table.
- **Tier 2 — new parameter UI, still single-file:** `TomographicUniformity` (frame-range + ratio params), `TomographicContrast` (two 6-element sequence params + nested `spheres` result table).
- **Tier 3 — breaks single-file assumptions:** `SimpleSensitivity` (second/background file, `Nuclide` enum dropdown, required `activity_mbq`, required nuclide). Largest scaffolding change.

## Task graph and gates

### Ordering

- S1 (API/sample spike) → Gate A — **done** (see Verified API table + Completion notes). Tiers may now proceed.
- Tier 1 (T1.x) → Tier 2 (T2.x) → Tier 3 (T3.x). Tiers are sequential for review sanity but tests within a tier are largely parallel-safe (disjoint per-class options + config constants; shared dispatcher/dialog edits are small and must serialize).
- Result-dialog and export generalizations (nested-dict tables) land with the first test that needs them (MaxCountRate `sums`, TomographicContrast `spheres`).
- Docs (T4) after each tier stabilizes; Gate B before each tier merges.

### Verification gates

- **Gate A (after S1):** reviewer confirms every class's constructor/analyze/results_data is as tabled, the TomographicContrast sample is identified, and the SimpleSensitivity two-file + nuclide contract is confirmed on real data. No product code until then.
- **Gate B (per tier, before merge):** unit + dialog + export + gated integration suites green on real IAEA samples; repo harness + architecture + doc-links green; one manual UI run per new test.
- **Gate C (unchanged):** physicist review before any pass/fail labels — out of scope here.

### File / area ownership

- `src/qa/*` → coder (per-class options, config, runners, export, figure dispatch).
- `src/gui/dialogs/*`, `src/gui/qa_app_facade.py` → ux/coder (per-test param pages, second-file + nuclide UI, result tables).
- `tests/*` → tester/coder.
- `user-docs/`, `dev-docs/` → docwriter after behavior stabilizes.

## Phases

### Phase 0 — Spike (timebox: 2h, owner: coder)

- [x] (S1) Confirm remaining API details on real data (owner: coder, parallel-safe: no, stream: A, after: none) — **Done 2026-06-12.** Findings folded into the Verified API table above (exact keys, nested shapes, `plot()` availability, samples). TomographicUniformity path constructor, TomographicContrast-on-Jaszack, and SimpleSensitivity two-file+optional-background all confirmed. SimpleSensitivity has no `plot()`.
- [x] Gate A — cleared (see S1 resolutions above).

### Phase 1 — Tier 1 (trivial single-file tests)

- [x] (T1.1) Config + per-class options for CenterOfRotation, TomographicResolution, MaxCountRate (owner: coder, parallel-safe: yes, stream: B, after: Gate A)
  - Add `NUCLEAR_*` ids, `*_CLASS` names, and `MaxCountRate` `frame_duration` default/bounds in `qa_nuclear_config.py`.
  - Add `CenterOfRotationOptions` (no params), `TomographicResolutionOptions` (no params), `MaxCountRateOptions(frame_duration)` to `analysis_types.py`.
- [x] (T1.2) Runners + dispatcher registration (owner: coder, parallel-safe: no, stream: B, after: T1.1)
  - Add three runners mirroring the **PlanarUniformity** pattern (single-file load, NM preflight via `_resolve_run_inputs`, **no `_frame_count_warning`** — these use all frames). Register in `_NUCLEAR_RUNNERS`.
  - Normalize flat `results_data` into `metrics["results"]`. For MaxCountRate, **strip `sums`** out of `metrics["results"]` (keep the full payload incl. `sums` in `raw_pylinac`); headline metrics are `max_countrate` / `max_frame` / `frame_duration`.
- [x] (T1.3) Dialog pages + facade routing (owner: ux/coder, parallel-safe: no, stream: C, after: T1.1)
  - Add dropdown entries; CenterOfRotation/TomographicResolution pages show "no parameters" note; MaxCountRate shows `frame_duration`. Extend `_NUCLEAR_CLASS_ROUTING`.
- [x] (T1.4) Figure dispatch + flat result reuse (owner: coder, parallel-safe: yes, stream: B, after: T1.2)
  - Add CenterOfRotation, TomographicResolution, MaxCountRate to `_PLOTTABLE_CLASSES` (all expose `plot()` per S1). Flat results reuse the existing Metric/Value table + `build_nuclear_flat_csv`.
  - **Disable Save Figure for non-plottable classes:** the result dialog should enable the figure button only when the run's class is in `_PLOTTABLE_CLASSES` (relevant in Tier 3 — SimpleSensitivity has no `plot()`). Add an exported `is_plottable(analysis_class)` helper in `pylinac_nuclear_plots.py` and gate `self._fig_btn` on it.
- [x] (T1.5) Tests: mocked runners, dialog pages, export, gated real-data on COR/TomoResolution/MaxCountRate (owner: tester/coder, parallel-safe: yes, stream: D, after: T1.2,T1.3)
- [x] Gate B (Tier 1) — 70 nuclear+ACR tests pass (real-data COR/TomoRes/MaxCountRate), arch/harness green.

### Phase 2 — Tier 2 (new parameter UI, single-file)

- [x] (T2.1) TomographicUniformity options + runner (owner: coder, parallel-safe: no, stream: B, after: Gate B Tier 1)
  - `TomographicUniformityOptions(first_frame, last_frame, ufov_ratio, cfov_ratio, center_ratio, threshold, window_size)`; runner normalizes flat result (`metrics["results"]`).
  - Dialog page: frame-range spinboxes (allow `-1` for last) + the ratio/threshold/window controls.
- [x] (T2.2) TomographicContrast options + runner + nested `spheres` table (owner: coder/ux, parallel-safe: no, stream: B, after: Gate B Tier 1)
  - `TomographicContrastOptions(sphere_diameters_mm, sphere_angles, ufov_ratio, search_window_px, search_slices)` — two 6-element sequences as editable rows.
  - Runner normalizes the `spheres` nested dict into `metrics["spheres"]` and stores the scalar `uniformity_baseline` alongside (e.g. `metrics["uniformity_baseline"]`, shown in the dialog header/params line). Full payload in `raw_pylinac`.
  - Result dialog: add a **per-sphere table** branch (mirrors the quadrant table) — include `"spheres"` in the `has_output` check, a `_build_sphere_table`, and a `"spheres"` branch in `_export_csv`. New `build_nuclear_spheres_csv` in `qa_export.py` (columns `sphere, x, y, z, radius, mean, mean_contrast, max_contrast`).
  - Dialog page: a small table/grid for the 6 sphere diameters + angles, plus the scalar params.
- [x] (T2.3) Tests for Tier 2 (owner: tester/coder, parallel-safe: yes, stream: D, after: T2.1,T2.2)
- [x] Gate B (Tier 2) — 80 nuclear+ACR tests pass (real Jaszack TU+TC + figure), arch/harness green.

### Phase 3 — Tier 3 (SimpleSensitivity — multi-file + enum)

- [x] (T3.1) Add optional second input path to the request contract (owner: coder, parallel-safe: no, stream: B, after: Gate B Tier 2)
  - Add an optional `background_path`/second-input field used **only** by SimpleSensitivity; keep all other runners single-file. Decide: a dedicated field on the nuclear options vs a second entry in `dicom_paths` (prefer an explicit `background_path` on `SimpleSensitivityOptions` to avoid ambiguity).
- [x] (T3.2) SimpleSensitivity options + runner (owner: coder, parallel-safe: no, stream: B, after: T3.1)
  - `SimpleSensitivityOptions(activity_mbq: float, nuclide: str, background_path: Optional[str])` — `nuclide` is a **string name** (the dialog must not import pylinac). Add a `NUCLIDE_NAMES` tuple to `qa_nuclear_config.py` for the dropdown so it doesn't drift from the enum.
  - **Runner does not use the generic `analyze(**analyze_kwargs())` splat** (unlike the other runners): `background_path` is a *constructor* arg and `nuclide` must be converted string→enum. So the runner explicitly does `SimpleSensitivity(phantom_path, background_path=opts.background_path)` then `analyze(activity_mbq=opts.activity_mbq, nuclide=getattr(Nuclide, opts.nuclide))` (lazy import). `analyze_kwargs()` on the options stays provenance-only (activity, nuclide name, background_path) for JSON/profile.
  - Validate `activity_mbq > 0` and a recognized nuclide; surface readable errors (don't let pylinac assertions leak). Omitted/None background ⇒ `background_cps` 0.
  - Normalize flat result into `metrics["results"]`.
- [x] (T3.3) Dialog: second-file picker + Nuclide dropdown + activity input (owner: ux/coder, parallel-safe: no, stream: C, after: T3.2)
  - SimpleSensitivity page: required activity (MBq), Nuclide dropdown (`Ga67/I131/In111/Lu177/Tc99m/Y90`), and an optional background-file picker (omitting it yields `background_cps=0`, per S1). The facade's `open_nuclear_qc_analysis` resolves the primary file as today; the background file is chosen here.
  - **No figure for SimpleSensitivity** (no `plot()`): rely on the `is_plottable` gate from T1.4 so Save Figure is hidden/disabled for this test.
- [x] (T3.4) Provenance/JSON for the second input + nuclide (owner: coder, parallel-safe: yes, stream: B, after: T3.2)
  - Record `background_path`, `activity_mbq`, `nuclide` in `build_nuclear_analysis_profile` output / JSON inputs.
- [x] (T3.5) Tests for SimpleSensitivity incl. gated real-data (PetriDish + Background) (owner: tester/coder, parallel-safe: yes, stream: D, after: T3.3)
- [x] Gate B (Tier 3) — 88 nuclear+ACR tests pass (real PetriDish/Background incl. validation + no-bg), arch/harness green.

### Phase 4 — Docs

- [x] (T4) Update user + developer docs after each tier (owner: docwriter, parallel-safe: yes, stream: E, after: each tier's Gate B)
  - User guide: add each test to the supported-tests table with its inputs/params/outputs; note SimpleSensitivity's two-file + nuclide flow.
  - Integration overview: list all nine nuclear tests and the result-shape handling (flat / per-frame / per-quadrant / per-sphere / single-value).

## Risks and mitigations

- **Heterogeneous inputs:** SimpleSensitivity's second file + enum is unlike every other test. Mitigate by isolating it in Tier 3 with its own options field and dialog page; do not generalize `QARequest` to multi-file for the single-file tests.
- **Nested result shapes:** `MaxCountRate.sums` and `TomographicContrast.spheres` are dicts. Mitigate: keep `sums` in `raw_pylinac` only (headline = max_countrate/max_frame); give `spheres` a dedicated per-sphere table + CSV (columns `sphere, x, y, z, radius, mean, mean_contrast, max_contrast`; mirrors the quadrant table pattern).
- **Sample coverage (RESOLVED by S1):** TomographicContrast runs on the local `Jaszack.dcm` with default sphere geometry — its integration test is not blocked.
- **TomographicUniformity constructor (RESOLVED by S1):** `(*args, **kwargs)` accepts a plain path; no special loader needed.
- **SimpleSensitivity has no `plot()`:** Save Figure must be disabled for it. Mitigate with the `is_plottable` gate (T1.4) so the result dialog hides/disables the figure button when the class is not plottable.
- **Nuclide/activity validation:** required fields with no defaults. Mitigate with dialog-level validation and readable runner errors (don't let pylinac assertions leak).
- **Dispatcher/dialog churn across tiers:** shared files (`_NUCLEAR_RUNNERS`, dialog stack, `_NUCLEAR_CLASS_ROUTING`) are touched by every tier. Mitigate by serializing those small edits per tier (not parallel) and keeping per-class logic in disjoint new files/dataclasses.

## Modularity and file-size guardrails

- One new `*Options` dataclass per test (the tagged union already supports this) — no field piling.
- Keep runners in `pylinac_nuclear.py` next to the others; if the module grows large (>~600 lines), split per-tier runner helpers but keep one dispatcher.
- Result-table builders stay pure/Qt-light where possible; CSV builders stay in `qa_export.py`.
- Defer a generic "results renderer" abstraction until after Tier 2 shows the real shape variety; do not over-abstract up front.

## Testing strategy

- `python -m pytest tests/test_pylinac_nuclear*.py tests/test_nuclear_*.py tests/test_qa_export_builders.py -q --basetemp=.codex-tmp\\pytest-nuclear-spect`
- `python scripts/check_repo_harness.py`; `python scripts/check_architecture_boundaries.py`; `python scripts/check_user_docs_links.py` when docs change.
- Integration gated on `DICOMVIEWER_NMQC_SAMPLE_PATH`; samples: `COR/COR_102.dcm`, `TomoResolution.dcm`, `MaxCountRate.dcm`, `Jaszack.dcm`, `sensitivity/PetriDish` + `sensitivity/Background`.
- Manual smoke per test: Tools → Automated QA → Nuclear Medicine QC → select test → run → review table → export JSON/CSV → Save Figure (where supported).

## UX / UI (deferred to ux subagent — do not finalize visual design here)

- Same Nuclear Medicine QC dialog; each test adds a `QStackedWidget` page.
- TomographicContrast: a 6-row editor for sphere diameter/angle pairs.
- SimpleSensitivity: activity (MBq) field, Nuclide dropdown, optional background-file picker; clear "second image" labeling.
- Result dialog: add a per-sphere table for TomographicContrast; single-value/flat tables for the rest.

## Questions for user (blocking if empty before coding)

- Priority/order within Tier 1–3, or just ship in the tiered order above? (Default: tiered order; Tier 1 first.)
- For SimpleSensitivity, is the optional background image required in practice for your workflow, or should background be truly optional? (Default: optional, per pylinac.)
- Display precision for SPECT metrics — 3 decimals like the existing tables? (Default: 3 decimals.)
- ~~Should TomographicContrast ship even if the local IAEA sample doesn't fit?~~ **Resolved by S1:** `Jaszack.dcm` works with default spheres; ships with a real integration test.

## Completion notes (filled by reviewer/coder later)

### S1 spike (2026-06-12) — Gate A cleared

Ran `analyze()` + `results_data(as_dict=True)` for all six classes on the local IAEA samples (see Verified API table). Highlights:
- **Flat results:** CenterOfRotation (2), TomographicResolution (6), TomographicUniformity (7), SimpleSensitivity (7) — reuse the existing Metric/Value table + `build_nuclear_flat_csv`.
- **Nested results:** `MaxCountRate.sums` (frame→count dict; keep in `raw_pylinac`, headline = max_countrate/max_frame/frame_duration). `TomographicContrast.spheres` ("1".."6" → `x,y,z,radius,mean,mean_contrast,max_contrast`) → new per-sphere table + `build_nuclear_spheres_csv`.
- **`plot()`:** present for all except **SimpleSensitivity** → add `is_plottable(analysis_class)` gate.
- **SimpleSensitivity:** two-file confirmed; background optional (`background_cps=0` without it); `Nuclide.Tc99m` used. Sample files have no extension (pydicom `force=True` handles it).
- No blockers remain; Tier 1 can start.

---

**HANDOFF → orchestrator:** Plan ready. Spike S1 (Gate A) closes the remaining API/sample unknowns; then Tier 1 → Tier 2 → Tier 3, docs per tier. Per-class options + dispatcher make Tier 1 nearly free; Tier 3 (SimpleSensitivity) carries the only structural change (second input + nuclide). Recommend branch `feature/nuclear-spect-tests`, tiers as separate PRs onto `WIP`. **Ready for orchestrator to assign coder (and ux for the SimpleSensitivity / TomographicContrast pages).** Four non-blocking questions above have proposed defaults so Tier 1 can start immediately after Gate A.
