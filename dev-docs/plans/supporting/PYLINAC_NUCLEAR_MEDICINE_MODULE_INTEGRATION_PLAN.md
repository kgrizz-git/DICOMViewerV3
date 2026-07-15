# Plan: Pylinac Nuclear Medicine Module Integration

Last updated: 2026-06-11

## Pre-spike verification (already confirmed against the installed venv)

These facts were checked against the project venv (`.venv`) so Phase 0 can start from a known baseline instead of re-discovering them:

- **The pinned `pylinac==3.43.2` already includes `pylinac.nuclear`.** No version bump is required, so the ACR CT/MRI integration is not put at risk by this work. All candidate classes import cleanly: `PlanarUniformity`, `FourBarResolution`, `QuadrantResolution`, `CenterOfRotation`, `TomographicUniformity`, `TomographicContrast`, `TomographicResolution`, `SimpleSensitivity`, `MaxCountRate`, plus matching `*Results` objects.
- **Recommended first class API (confirmed):**
  - `PlanarUniformity(path: str | Path)` then `analyze(ufov_ratio=0.95, cfov_ratio=0.75, window_size=5, threshold=0.75)`.
  - `FourBarResolution(path: str | Path)` then `analyze(separation_mm=100, roi_width_mm=10)`.
  - Both expose `results_data()`, `results()`, and `plot()`, so the normalize-to-`QAResult` and optional-figure strategies in T2/T9 are viable.
- **Input shape:** nuclear constructors take a **single DICOM file path** (`str | Path`), not a folder/stack like the ACR CT path. The dialog and runner must agree on a single-file convention (see T1/T5).

S1 still owns verifying exception types, the exact `results_data()` payload shape, and multi-frame behavior; the import/signature unknowns above are resolved.

## Goal and success criteria

Integrate selected `pylinac.nuclear` analyses into DICOM Viewer V3's automated QA workflows without weakening the existing ACR CT/MRI pylinac integration. The first shipped slice should be deliberately manual and traceable: the user selects a nuclear medicine QC test, supplies the correct DICOM input(s), reviews explicit assumptions, runs the analysis off the UI thread, and can export normalized JSON with enough provenance to reproduce the run.

Success criteria:

- A dedicated nuclear medicine QA path exists under the existing automated QA / pylinac surface, not as a one-off script.
- The first supported analysis is chosen after a spike against the project-pinned pylinac version and representative NM QC data.
- Every run records the pylinac version, analysis class, input paths or source UIDs, user-supplied analysis parameters, warnings, and raw pylinac result payload where available.
- Missing pylinac, unsupported data, wrong modality, bad parameters, and pylinac exceptions produce user-readable errors, not tracebacks.
- The implementation reuses the existing `src/qa` boundary, worker pattern, result dialog/export conventions, and last-output-path behavior where practical.
- No external sample archive is committed or redistributed until its license and terms are reviewed.
- The UI avoids clinical pass/fail claims unless a physicist validates the specific algorithm, phantom, and site thresholds.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` under "Further integrate pylinac and other automated QC analysis tools" -> "Nuclear module".
- Research note: `dev-docs/info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md`, especially section 2 (`pylinac.nuclear`) and section 3.3 (IAEA / NMQC reference data).
- Existing pylinac integration overview: `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`.
- Completed ACR spine plan: `dev-docs/plans/completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md`.
- Current code seams:
  - `src/qa/analysis_types.py`: `QARequest`, `QAResult`, and `build_pylinac_analysis_profile`. Note: `build_pylinac_analysis_profile` is **ACR-shaped** (emits `relaxed_image_extent`, `scan_extent_tolerance_mm`, `vanilla_equivalent`, `origin_slice_override`) and is called for **every** result in `worker.py`, including failures. A nuclear run routed through it as-is would record misleading ACR-only provenance — see T1a.
  - `src/qa/worker.py`: `QAAnalysisWorker` routing by `analysis_type` (`acr_ct` / `acr_mri_large`, else an unsupported-type `QAResult`). This worker is a `QThread`; anything that builds matplotlib figures must respect that (see T9).
  - `src/qa/preflight.py`: existing QA preflight/modality-gating helpers. NM modality (NM vs CT/MR), planar-vs-tomographic, and multi-frame checks belong here, not inline in the runner.
  - `utils/config/qa_pylinac_config.py`: ACR default constants imported by `analysis_types.py`. Nuclear defaults (UFOV/CFOV ratios, window size, threshold, bar separation) should follow this pattern — see T1b.
  - `src/qa/pylinac_runner.py`: facade re-export layer for pylinac-backed runners.
  - `src/gui/qa_app_facade.py`: existing ACR CT/MRI pylinac preflight, worker launch, result dialog, JSON export, and optional PDF opening.
  - `src/gui/main_window_menu_builder.py`, `src/gui/main_window.py`, `src/gui/app_signal_wiring.py`, and `src/gui/actions/dialog_actions.py`: Tools menu signal/action path for current ACR QA entries.

`pylinac.nuclear` is documented as a Python alternative to the IAEA NMQC ImageJ toolkit. That makes it directly relevant to the ImageJ/Fiji evaluation backlog item, but this plan is scoped to integrating pylinac's Python module first. ImageJ/Fiji integration, external process launching, or Java plugin porting should remain separate work unless the spike finds that pylinac is insufficient for a required NM QC workflow.

## Candidate analyses

Initial candidates from `pylinac.nuclear`:

| Class | Likely first-slice fit | Notes |
|-------|-------------------------|-------|
| `PlanarUniformity` | High | Single planar NM DICOM, familiar UFOV/CFOV uniformity output, likely simplest UI. |
| `FourBarResolution` | Medium | Single-frame bar-pattern workflow; may require clear phantom geometry and pixel-size assumptions. |
| `QuadrantResolution` | Medium | Resolution / lp-mm style output; likely useful but requires quadrant ROI assumptions. |
| `CenterOfRotation` | Medium | SPECT QC value; needs appropriate dynamic/tomographic acquisition and parameter review. |
| `TomographicUniformity` | Medium | Useful for cylinder/Jaszczak-style SPECT uniformity; may need frame/slice selection options. |
| `TomographicContrast` | Lower first-slice fit | Requires sphere diameters/angles and more phantom-specific parameters. |
| `TomographicResolution` | Lower first-slice fit | More complex 3D centroid/profile/fitting assumptions. |
| `SimpleSensitivity` | Lower first-slice fit | Requires activity, nuclide, optional background path, and stronger workflow validation. |
| `MaxCountRate` | Lower first-slice fit | Useful but not a generic first path; depends on dynamic acquisition conventions. |

Recommended first target unless the spike disproves it: `PlanarUniformity`, followed by one resolution-oriented planar test (`FourBarResolution` or `QuadrantResolution`).

## Task graph and gates

### Ordering

- S1 -> S2 -> Gate A: confirm pylinac API behavior, sample-data path, and first target class before implementation.
- T1 -> T2 -> T3: data contracts and runner must land before worker/menu/UI wiring.
- T4 can run after T2 and in parallel with T5 only if UI work does not touch the same files.
- T6 -> Gate B: tests and docs must be green before marking the backlog item complete or partially complete.
- Gate C sits after Gate B and before any release that adds pass/fail labels, site thresholds, or accreditation-style language; the first metrics-only release does not require it but must not ship such language.

### Verification gates

- Gate A: reviewer approves the spike recommendation for the first supported `pylinac.nuclear` class and confirms no sample-data licensing issue is being introduced.
- Gate B: tester verifies unit tests, optional local integration smoke, repo harness, and at least one manual UI run with a known NM QC input.
- Gate C: physicist/domain review before any pass/fail labeling, site thresholds, or accreditation-style language ships.

### File / area ownership

- `src/qa/` -> coder for contracts, runner, and worker routing.
- `src/gui/dialogs/` and `src/gui/qa_app_facade.py` -> coder or UX/coder pair for nuclear QA options and result flow.
- `src/gui/main_window*.py`, `src/gui/app_signal_wiring.py`, `src/gui/actions/dialog_actions.py` -> coder for Tools menu signal path.
- `tests/` -> tester/coder for mocked pylinac and export tests.
- `user-docs/` and `dev-docs/` -> docwriter after behavior stabilizes.

## Phases

### Phase 0 - API, data, and workflow spike

- [~] (S1) Spike: confirm remaining `pylinac.nuclear` API details under the pinned version (owner: coder, parallel-safe: no, stream: A, after: none) — import/signatures/`results_data()` shape done (see Completion notes); exception types + `plot()` contract still need the IAEA sample
  - Import success, constructor signatures, and `analyze(...)` kwargs for `PlanarUniformity` / `FourBarResolution` are **already verified** in the Pre-spike section above; do not redo that.
  - Still open: exact `results_data(...)` payload shape/fields, `results()` string format, `plot()` figure/return contract, exception types raised on a non-NM modality / missing pixel data / bad parameters, and multi-frame handling.
  - Outcome: short spike note under `dev-docs/spikes/` or this plan's completion notes recommending the first supported class and recording the `results_data()` field map to normalize in T2.
- [ ] (S2) Spike: identify usable NM QC example inputs (owner: researcher, parallel-safe: yes, stream: B, after: none)
  - Prefer local clinic/developer test data or the IAEA/NMQC simulated image archive referenced by pylinac docs.
  - Do not commit third-party data. Record only source, terms, acquisition type, expected test class, and local setup instructions.
- [ ] (S3) Spike: compare `pylinac.nuclear` coverage with ImageJ/Fiji/NMQC expectations (owner: researcher, parallel-safe: yes, stream: B, after: S2)
  - Outcome: note whether pylinac covers the needed workflow or whether the separate ImageJ/Fiji backlog item should become a blocker or extension.
- [ ] Gate A: choose first supported class and minimum parameter set before product-code work starts.

### Phase 1 - Contracts and runner boundary

- [ ] (T1) Define nuclear-specific request/options without overloading ACR-only fields (owner: coder, parallel-safe: no, stream: A, after: Gate A)
  - Preferred shape: keep `QAResult` as the common output, add a nuclear-specific options dataclass or nested `options` field rather than adding many unrelated fields to `QARequest`.
  - Include analysis class name, input role(s), selected frame/slice if applicable, numeric parameters, and whether output is stock-pylinac equivalent.
  - **Single-file input convention:** nuclear classes take one DICOM file path. Decide and document how that maps onto `QARequest` (e.g. a single entry in `dicom_paths`, or a dedicated `primary_path` on the nuclear options) so the dialog (T5) and runner (T2) agree. Reserve a second optional path only for `SimpleSensitivity` background later.
- [x] (T1a) Make run provenance nuclear-aware instead of ACR-shaped (owner: coder, parallel-safe: no, stream: A, after: T1)
  - `build_pylinac_analysis_profile` emits ACR-only fields and runs for every result in `worker.py`. Add a nuclear branch or a sibling `build_nuclear_analysis_profile` that records pylinac version, nuclear analysis class, the nuclear parameter set, and stock-equivalence — without the irrelevant `relaxed_image_extent` / `scan_extent_tolerance_mm` / `origin_slice_override` keys.
  - This is what satisfies success criterion #3 for nuclear runs; do not let nuclear inherit the ACR profile by default.
- [x] (T1b) Add nuclear default constants (owner: coder, parallel-safe: yes, stream: A, after: Gate A)
  - Mirror `utils/config/qa_pylinac_config.py`: define defaults for the first class (`ufov_ratio=0.95`, `cfov_ratio=0.75`, `window_size=5`, `threshold=0.75`; bar `separation_mm=100`, `roi_width_mm=10`) in a small config module rather than hardcoding them in the dialog or runner.
- [x] (T2) Add `src/qa/pylinac_nuclear.py` runner entrypoints (owner: coder, parallel-safe: no, stream: A, after: T1)
  - Use lazy imports and the same missing-pylinac behavior as ACR runners.
  - Normalize `results_data()` / `results()` into `QAResult.metrics` and `QAResult.raw_pylinac` using the field map recorded in S1.
  - Do NM modality / planar-vs-tomographic / missing-pixel-data gating via `src/qa/preflight.py` (extend it), not inline.
  - Capture warnings for unsupported modality, missing pixel data, parameter omissions, and any UI-assisted assumptions.
- [x] (T3) Re-export public nuclear runner names from `src/qa/pylinac_runner.py` only if compatibility with the existing facade pattern is useful (owner: coder, parallel-safe: no, stream: A, after: T2)
- [x] (T4) Extend worker routing for the selected nuclear `analysis_type` (owner: coder, parallel-safe: no, stream: A, after: T2)

### Phase 2 - UI and user flow

- [x] (T5) Add a nuclear QA options dialog under `src/gui/dialogs/` (owner: ux/coder, parallel-safe: no, stream: C, after: T1) — `gui/dialogs/nuclear_qa_dialog.py` (`prompt_nuclear_options`): supported-test dropdown (PlanarUniformity only), the four analyze params, read-only assumptions/validation note.
- [x] (T6) Add Tools menu entry and signal wiring (owner: coder, parallel-safe: no, stream: C, after: T5) — `Nuclear Medicine QC (pylinac)...` under Automated QA; `nuclear_qc_requested` signal wired through `app_signal_wiring` → `dialog_actions` → `main._open_nuclear_qc_analysis`. ACR labels unchanged.
- [x] (T7) Extend `QAAppFacade` or add a small sibling facade for nuclear QA (owner: coder, parallel-safe: no, stream: C, after: T4) — `open_nuclear_qc_analysis` reuses `start_qa_worker`/`show_qa_result_dialog`/`export_qa_json`; single-file input (focused image or file picker), best-effort identity read for the NM preflight.
  - Reuse progress dialog, worker lifetime handling, result dialog, JSON export, last output directory, and user-readable preflight patterns.
  - If nuclear logic starts making `QAAppFacade` too broad, split a `NuclearQAAppFacade` instead of growing the ACR facade indefinitely.

### Phase 3 - Export, plots, and documentation

- [x] (T8) Define JSON schema additions for nuclear QA (owner: coder, parallel-safe: yes, stream: D, after: T2) — kept `schema_version` "1.1" (ACR unchanged); discriminator is `run.analysis_type`, with a convenience `run.nuclear_analysis_class` added only for nuclear payloads (`export_qa_json`). Per-frame results under `metrics.frames`, full payload under `raw_pylinac`, provenance under `pylinac_analysis_profile` (nuclear keys). Documented in the integration overview + user guide.
- [x] (T9) Decide + implement plot/report output strategy (owner: coder, parallel-safe: yes, stream: D, after: S1)
  - `PlanarUniformity.plot()` returns one matplotlib `Figure` per frame and has no `publish_pdf`. The QA worker is a `QThread` and the app uses a Qt matplotlib backend (`tools/histogram_widget.py` → `FigureCanvasQTAgg`), so figures must not be built on the worker thread.
  - **Implemented (2026-06-11):** `qa/pylinac_nuclear_plots.py` `render_nuclear_figures` re-runs the (fast) analysis and saves one PNG per frame on the **main thread**; wired to a **Save Figure (PNG)…** button on the nuclear result dialog. No PDF assembly. Tests: dialog button wiring + gated single/multi-frame real-data render. Recorded in the integration overview and user guide.
  - If the selected class exposes only matplotlib plots, prefer optional PNG export or "save figure" rather than pretending it has pylinac-style PDF support.
  - **Threading:** the runner executes inside a `QThread` (`QAAnalysisWorker`). `plot()` is matplotlib-based; force a non-interactive backend (`Agg`) and generate/save figures without touching the GUI thread or a global pyplot state, the way the ACR PDF path already does. Never hand a live figure back across the thread boundary.
  - Do not add reportlab/PDF assembly until a concrete report requirement exists.
- [x] (T10) Add user and developer docs after behavior is stable (owner: docwriter, parallel-safe: yes, stream: E, after: T7) — User: new "Nuclear Medicine QC (`pylinac.nuclear`)" section in `user-docs/USER_GUIDE_QA_PYLINAC.md` (supported test, single-file input, options, JSON output, not-clinically-validated note). Dev: nuclear row + JSON-schema/figure notes in `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` linking this plan and the research note. Doc-link checker green.
  - User docs should say which NM QC tests are supported, what inputs are expected, what is exported, and what is not clinically validated by the app.
  - Developer docs should link this plan, the research note, and any spike output.

### Phase 4 - Test and validation coverage

- [x] (T11) Add unit tests for missing pylinac and mocked-success runner paths (owner: tester/coder, parallel-safe: yes, stream: F, after: T2) — `tests/test_pylinac_nuclear.py` (8 tests: missing-pylinac, mocked success/per-frame, non-default params, non-NM warning, multi-file, no-input, analyze exception, unknown-type dispatch)
- [x] (T12) Add options-dialog tests for the first supported nuclear class (owner: tester/coder, parallel-safe: yes, stream: F, after: T5) — `tests/test_nuclear_qa_dialog.py` (defaults, custom round-trip, supported-test list)
- [x] (T13) Add JSON export tests for nuclear fields and warnings (owner: tester/coder, parallel-safe: yes, stream: F, after: T8) — `tests/test_nuclear_qa_export.py` (nuclear schema/fields incl. `run.nuclear_analysis_class`, per-frame metrics, warnings; plus an ACR-export guard that the nuclear-only key is absent)
- [x] (T14) Add optional integration smoke gated on an environment variable or local path to NM QC sample data (owner: tester/coder, parallel-safe: yes, stream: F, after: S2) — `tests/test_pylinac_nuclear_integration.py`, gated on `DICOMVIEWER_NMQC_SAMPLE_PATH`; skips when unset (no CI download). Verified: 2 passed on local IAEA data, 2 skipped without.
  - Do not make CI download IAEA/NMQC data unless licensing and reliability are approved.
- [x] Gate B: run focused tests plus repo harness before implementation is marked done. — Done 2026-06-11: nuclear unit + dialog + integration suites green, repo harness / agent smoke / architecture clean, and `tests/test_pylinac_nuclear_e2e.py` drives the real `QAAppFacade.open_nuclear_qc_analysis` chain (file picker → worker thread → pylinac.nuclear → JSON export) end-to-end on a real IAEA image. Optional remaining: hands-on click-through in the running app.

## Risks and mitigations

- **Pinned-version availability (RESOLVED):** `pylinac.nuclear` is present in the pinned `pylinac==3.43.2`, so no version bump and no ACR-regression exposure for this work. If a future nuclear class needs a newer pylinac, treat the bump as a separate change gated on the existing ACR CT/MRI regression suite (`dev-docs/plans/DEPENDENCY_BUMP_VERIFICATION_PLAN.md`).
- **API drift:** `pylinac.nuclear` may expose different result objects than ACR CT/MRI. Mitigate with a spike and narrow first-class support.
- **ACR-shaped provenance leakage:** the shared `build_pylinac_analysis_profile` runs for every worker result and emits ACR-only fields. Mitigate with T1a so nuclear runs record meaningful provenance.
- **Worker-thread plotting:** matplotlib `plot()` invoked from the QThread can corrupt global pyplot state or crash. Mitigate with the Agg-backend/off-main-thread approach in T9.
- **Sample data licensing:** IAEA/NMQC examples may be usable for local validation but not redistribution. Mitigate by documenting source/terms and keeping data out of the repo.
- **Wrong input assumptions:** NM planar, dynamic, and tomographic DICOMs differ from CT/MR stacks. Mitigate with explicit test selection and preflight warnings instead of auto-detection first.
- **Overloaded QARequest:** ACR-specific fields already exist. Mitigate with nuclear-specific options or a nested options payload rather than adding many unrelated fields.
- **UI bloat:** A single dialog for every nuclear class could become confusing. Mitigate by shipping one class first and using progressive disclosure for advanced parameters.
- **Clinical overclaiming:** Pylinac output is not the same as site validation. Mitigate with transparent metrics, provenance, and no pass/fail thresholds before physicist review.
- **ImageJ/Fiji overlap:** Some desired NMQC workflows may be better served by ImageJ/Fiji or direct algorithm porting. Mitigate by cross-checking the ImageJ/Fiji backlog item during Phase 0.

## Modularity and file-size guardrails

- Prefer `src/qa/pylinac_nuclear.py` plus small helpers over adding nuclear code to `pylinac_acr_ct.py`, `pylinac_acr_mri.py`, or the facade `pylinac_runner.py`.
- Keep GUI parameter collection in a dedicated dialog module, not in `main_window_menu_builder.py` or `QAAppFacade`.
- If `QAAppFacade` grows materially, split nuclear launch/result/export behavior into a sibling facade and keep app signal delegates thin.
- Keep result normalization pure enough to test without Qt.
- Avoid introducing a general plugin framework for this slice; defer until multiple external QA backends need the same runtime abstraction.

## Testing strategy

Focused checks to add/run during implementation:

- `python -m pytest tests/test_pylinac_nuclear*.py -q --basetemp=.codex-tmp\\pytest-pylinac-nuclear`
- `python -m pytest tests/test_*qa*.py tests/test_mri_compare_phase_e.py -q --basetemp=.codex-tmp\\pytest-qa`
- `python scripts/check_repo_harness.py`
- `python scripts/check_user_docs_links.py` if user docs are edited.
- Manual smoke: load or choose a known NM QC DICOM, run the selected nuclear analysis, review warnings/results, export JSON, and verify the app remains responsive during analysis.

Optional local integration:

- Use a local environment variable such as `DICOMVIEWER_NMQC_SAMPLE_PATH` to point at non-redistributed NM QC data.
- Skip the integration test when the variable is unset.
- Record the pylinac version and sample provenance in test output or a local-only note.

## UX / UI

- Entry point: Tools -> Automated QA -> Nuclear Medicine QC (pylinac)...
- First dialog should be work-focused, not a broad wizard:
  - Test type dropdown limited to supported classes.
  - Input source: active/focused item when appropriate, file picker fallback for single-DICOM classes, optional second file for background only when needed.
  - Parameter controls only for the selected class.
  - Read-only assumptions/warnings area for modality, frame behavior, and validation status.
- Result dialog should reuse the existing QA summary style but include the nuclear class name and key metrics.
- JSON export should be offered for every completed or failed run, as with ACR pylinac workflows.
- Plot/report export should be optional and class-specific after the API spike confirms what pylinac exposes.

## Decisions (2026-06-11)

- **First shipped class: `PlanarUniformity`.** Dialog/runner expose `ufov_ratio`, `cfov_ratio`, `window_size`, `threshold` (defaults 0.95 / 0.75 / 5 / 0.75).
- **Validation data: IAEA/NMQC `Simulated_images.zip`**, downloaded locally and **not committed**. Precondition: review the IAEA terms of use before download; record source + terms in a local-only note and wire it via `DICOMVIEWER_NMQC_SAMPLE_PATH` for the optional integration smoke (T14). Real-data validation at Gate B uses this archive.
- **Input: single DICOM file** (matches the pylinac constructor); active-viewer-item support deferred.
- **First release exports metrics + warnings only**, no pass/fail labels or site thresholds (Gate C not required for the first release, but no accreditation-style language may ship).

## Completion notes

### S1 partial findings (2026-06-11, PlanarUniformity, pylinac 3.43.2)

- `PlanarUniformityResults` is a **pydantic** model (not a dataclass) with four float fields: `ufov_integral_uniformity`, `ufov_differential_uniformity`, `cfov_integral_uniformity`, `cfov_differential_uniformity`.
- **`results_data()` returns a frame-keyed dict**, not a single result object: `{ "Frame 1": PlanarUniformityResults, "Frame 2": ..., ... }`. `as_dict=True` yields `model_dump()` dicts per frame; `as_json=True` yields a JSON string. This differs from the ACR single-result shape.
- **Implications captured for T2/T5/T8:**
  - T2 normalization must flatten the frame-keyed dict into `QAResult.metrics` (e.g. `metrics["Frame 1"] = {...}`) and keep the `as_dict=True` payload in `QAResult.raw_pylinac`. Use `.model_dump()` (pydantic v2), not `dataclasses.asdict`.
  - T5/result UI must present **per-frame rows**, since a single planar acquisition can yield multiple frames.
  - T8 JSON export gets per-frame metrics for free via `model_dump()`; no custom serializer needed.
- Still open in S1: exception types on missing pixel data / bad params, and `plot()`'s figure/return contract.

### Real-data validation (2026-06-11, IAEA NMQC `Simulated_images.zip`, pylinac 3.43.2)

- IAEA `Simulated_images.zip` downloaded to `sample-DICOM-gitignored/nmqc/` (gitignored, untracked, not redistributed; source, SHA-256, and terms are retained only in local untracked research notes). pylinac's own nuclear test DICOMs are in a private GCP bucket (403 without credentials), so the IAEA set is the public origin.
- `run_planar_uniformity_analysis` validated end-to-end through the real runner:
  - `Uniformity/UNIFORMIDAD_1_Ok.dcm` — Modality NM, 1 frame → success, UFOV integral uniformity ≈ 2.38%.
  - `Uniformity/Point_Source.dcm` — Modality NM, 2 frames → success, `frame_count=2`, distinct per-frame metrics (confirms frame-keyed normalization).
- Live `results_data(as_dict=True)` shape matches the mocked tests exactly (frame-keyed dict of 4 floats), so T11 mocks are faithful.
- pylinac emits internal skimage `FutureWarning`/`RuntimeWarning` during analysis (not viewer-originated). Decision (2026-06-11): **do not filter/suppress** them — they stay visible in logs/stderr during development. A future enhancement may surface them in the result payload only behind the existing `DEBUG_PYLINAC_QA` gate; not building suppression now.
- Remaining for Gate B: a manual run through the real UI once T5–T7 land.
