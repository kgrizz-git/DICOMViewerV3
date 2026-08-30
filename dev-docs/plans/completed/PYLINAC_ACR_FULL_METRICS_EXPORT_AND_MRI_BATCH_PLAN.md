# Plan: Pylinac ACR — full metrics export, batch CT CSV, and multi-series MRI batch

**Last updated:** 2026-08-30
**Status:** Completed — **Phases 0–6 shipped** (P0-GATE signed 2026-08-29); PRs #97 and #98 are merged to `main`. Optional real-phantom smoke is tracked in [`TO_DO.md`](../../TO_DO.md#manual-smoke-checks).
**Priority:** P1
**Branch:** `plan/pylinac-acr-full-metrics-export-mri-batch` (implementation: `feature/pylinac-acr-full-metrics-export-mri-batch`)
**Area:** Automated QA / pylinac (ACR CT + ACR MRI Large only)

**Related (investigation):**

- [ACR MRI phantom QA metrics and pylinac gaps](../../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md) — accreditation tests, QC manual metrics, SNR definitions, pylinac gap table (**Phase 6**)

**Related (completed):**

- [Pylinac CT CNR, batch, and XLSX](../completed/PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md) — F1 CNR intermediates, F2 CT multi-series batch, F3 XLSX (Summary/Detail/Images; CNR-centric Summary)
- [Pylinac MRI compare runs and PDF](../completed/PYLINAC_MRI_COMPARE_RUNS_AND_PDF_INTERPRETATION_PLAN.md) — same-series 1–3-run low-contrast compare
- [Pylinac Stage 1 spine](../completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md)

**Related (umbrella — defer CLI/DB to later):**

- [QA results export, CLI, and history](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md) — Phase 1–2 **ACR CT/MRI slice is implemented here first**; CLI (Phase 3) and QC history DB (Phase 4) stay in that plan

---

## Goal and success criteria

Physicists can export **everything pylinac exposes** for **ACR CT** and **ACR MRI Large** runs — single or batch — as **CSV and XLSX**, without digging through JSON. **Multi-series MRI batch** matches the existing CT batch UX.

**Definition of “full”:** flatten `result.raw_pylinac` (full `results_data(as_dict=True)` tree stored at analysis time) plus necessary **live-analyzer harvest** where dict output is incomplete (CT CNR / F1 precedent; **MRI SNR** in Phase 6). Omit any family pylinac does not populate — do not fabricate PSG or other columns; **MRI SNR** is the one planned viewer-computed exception (not in pylinac).

Success means:

1. **Canonical metric rows** — one stable flattened row model per run (provenance + every **pylinac-exposed or Phase 6 viewer-harvest** scalar/list metric), shared by CSV, XLSX Detail, and future CLI/DB.
2. **ACR metric coverage** — not only CNR intermediates; include uniformity, low-contrast detectability/score, relative MTF / spatial resolution, slice thickness / slice position (MRI; pylinac 3.43.2 `ACRCT` analyzes no thickness module), HU linearity / material ROIs, and modality-specific fields (e.g. MRI PSG) **when present** in `raw_pylinac` or live harvest; **MRI SNR** in **Phase 6** (viewer-computed); **CT SNR** and **CT PSG** remain **expected absent**.
3. **Batch CT** — **Export CSV…** on the batch summary dialog (today: XLSX + JSON only).
4. **Batch MRI** — **Tools → Automated QA → ACR MRI Batch (pylinac)…** — checkbox series list + **Add folder…**, shared MRI options, serial N-of-M progress, cooperative cancel, per-series error isolation; result dialog with **Export CSV / JSON / XLSX**.
5. **Single-run parity** — ACR CT and MRI save dialogs export the **same pylinac-exposed metric set** in CSV/XLSX; JSON unchanged (`raw_pylinac` already carries full dict — flatten is **export-layer only**, no `metrics_flat` in JSON).
6. **MRI compare mode unchanged** — same-series 1–3-run low-contrast compare stays separate (`schema_version` 1.2); this plan does not replace compare JSON/PDF.
7. **XLSX module images (PDF parity)** — when enabled (default **on**), XLSX **Images** sheet embeds the **same per-module PNGs** pylinac puts in PDF reports (`analyzer.save_images()` / `plot_images()`), not only the single composite from `save_analyzed_image()`. User can turn off via persisted option in ACR CT/MRI options dialogs (single-run and batch).

---

## Current state (2026-08-28)

| Capability | ACR CT | ACR MRI Large |
|------------|--------|----------------|
| Single-run analyze | Yes | Yes |
| Single-run JSON | Yes (`schema_version` 1.3 CT / 1.1 MRI; full `raw_pylinac`) | Yes |
| Single-run CSV/XLSX | Yes — but CSV/XLSX Detail flatten **`result.metrics` only** (~10 keys + `low_contrast_cnr`), not full `raw_pylinac` | Same |
| Multi-series batch | Yes (`QACTBatchWorker`, batch dialog) | **No** — only same-series compare (1–3 LC configs) |
| Batch export | XLSX + JSON | N/A |
| XLSX Summary | CNR-centric columns | N/A (no batch) |
| XLSX Images | One **composite** PNG per run (`save_analyzed_image`) when CT temp dir wired | **None** (no image save in runner) |
| PDF figures | Full module set via `save_images()` inside `publish_pdf` | Same |

Runners: `src/qa/pylinac_acr_ct.py`, `src/qa/pylinac_acr_mri.py`. Export: `src/qa/qa_export.py`, `src/qa/qa_xlsx_export.py`. Facade: `src/gui/qa_app_facade.py`. CT batch save dialogs: `src/gui/qa_ct_batch_export.py`. CT batch UI: `src/gui/dialogs/ct_batch_result_dialog.py`, `ct_batch_select_dialog.py` (`prompt_batch_series_selection`).

**Target:** XLSX Images uses **`save_images()`** (PDF parity). Today’s composite-only CT path is replaced when the embed option is on (default). Toggle off → skip Images sheet (Summary note only), same graceful degradation as missing Pillow.

---

## Metric catalog (target extraction)

Extract when present; omit column/row when module failed or pylinac version omits field. Namespace keys as `module.metric` (e.g. `ct_module.rois.air`; exact dotted keys come from the Phase 0 appendix — do not invent names here).

### ACR CT (`ACRCT` / `run_acr_ct_analysis`)

| Family | Examples (non-exhaustive) | Primary source | Confidence |
|--------|---------------------------|----------------|------------|
| HU linearity / materials | Per-material HU, ROI distances/radii, measured vs expected | `raw_pylinac.ct_module` (rois per material) + live ROIs if needed | **Confirmed** 2026-08-29 dump |
| Slice thickness | Measured thickness, ramp metrics | **No such module in pylinac 3.43.2 `ACRCT`** — result model has only `ct_module`, `uniformity_module`, `low_contrast_module`, `spatial_resolution_module` | **Absent (CT)** — omitted on dump |
| Slice position / geometry | Phantom roll, origin slice, image count | top-level `phantom_roll_deg`, `origin_slice`, `num_images` (no separate geometry module on CT) | **Confirmed** 2026-08-29 dump |
| Uniformity | Integral/differential uniformity, ROI stats | `uniformity_module` | **Confirmed** 2026-08-29 dump |
| Low contrast | CNR, object/background means & σ (existing F1) | `metrics.low_contrast_cnr` + `low_contrast_module` | Shipped F1 + dump (`low_contrast_module.cnr`) |
| Spatial resolution / MTF | MTF at rMTF %, lp/mm, relative resolution grid | `spatial_resolution_module` | **Confirmed** 2026-08-29 dump |
| SNR | Module SNR if exposed | — | **Absent (CT)** — no SNR field in pylinac 3.43.2 `acr.py` results |
| PSG (percent signal ghosting) | Ghosting ratio | N/A for CT phantom | **Expected absent (CT)** |

### ACR MRI Large (`ACRMRILarge` / `run_acr_mri_large_analysis`)

| Family | Examples | Primary source | Confidence |
|--------|----------|----------------|------------|
| Geometric / slice | Slice thickness/position, phantom roll | `raw_pylinac` `slice1` / `slice11` / `geometric_distortion_module` | **Confirmed** 2026-08-29 T1 dump |
| Uniformity | PIU, uniformity ROI stats | `uniformity_module` (incl. `piu`) | **Confirmed** 2026-08-29 dump |
| SNR | SNR (viewer-computed) | — | **Absent in pylinac** — **Phase 6** viewer harvest; see [ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md](../../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md) |
| PSG | Percent signal ghosting | `uniformity_module.psg` / `ghosting_ratio` (dict-present in 3.43.2) | **Confirmed** 2026-08-29 dump |
| Low contrast | Score, detectability, per-slice LC metrics | `low_contrast_multi_slice_module`, existing `_extract_lc_score` | **Confirmed** 2026-08-29 dump |
| MTF | Row/column rMTF % → lp/mm grid (10–90% step) | `slice1.row_mtf` / `col_mtf` outputs (`lpmm_to_rmtf`-style grids) | **Confirmed** 2026-08-29 dump; Summary MTF@50% only |
| Other | `has_sagittal_module`, echo-specific fields | already partially in `metrics` | T1 dump includes empty `sagittal_localizer_module` dicts (no flatten leaves); `has_sagittal_module` still not in `results_data` |

**Discovery step (Phase 0):** run `results_data(as_dict=True)` once per modality on a **local (gitignored) phantom folder** via `scripts/spike_pylinac_acrct.py` / `scripts/spike_pylinac_acrmri.py` with **`--dump-json`**. Use **repo-relative** folders only in docs (`sample-DICOM-gitignored/CT-phantoms/`, `sample-DICOM-gitignored/MR-phantoms/`) — never machine-absolute paths. **Commit redacted dumps** as `tests/fixtures/qa/acr_ct_results_data.json` and `tests/fixtures/qa/acr_mri_results_data.json` (numeric metrics + phantom model only — no pixel data, no filesystem paths, no institution/address/station or other site/patient/UID keywords). Spike redaction drops those keys and replaces remaining absolute paths with `<redacted-path>`. The dump commit must pass the staged artifact gate (`scripts/check_no_phi_artifacts.py` / privacy hooks) — never `--no-verify`. Document exact key paths in this plan’s **Metric registry appendix**. CI golden tests consume the committed dumps — **no `analyze()` in CI** (no synthetic ACR image fixtures exist today). Where dict lacks background σ (CT CNR precedent), add guarded live-analyzer harvest in the runner and stash under `result.metrics` (see merge rule in the architecture sketch — top-level keys, not a literal `metrics.` prefix).

**Maintainer note:** Local ACR phantoms may live under `sample-DICOM-gitignored/CT-phantoms/`, `sample-DICOM-gitignored/MR-phantoms/`, or `test-DICOM-data/` (all gitignored) and need not be present before **coding** Phases 1–6. **Committed dumps** (R0-1, R0-2, R0-9) are produced when phantom data is available; they block **P0-GATE close**, **P1-F4**, and **G2** only—not spike tooling or flatten/export implementation. If DICOM itself must be tracked later, run **File → De-identify & Export DICOM (PS3.15)…** first (do not retain institution/device identity).

---

## Research first (Phase 0 — blocking golden tests, not all coding)

Do **not** close **P0-GATE** or claim **G2** until redacted dumps and the metric appendix are checked in. **Phases 1–5 coding** may proceed once **R0-0** (spike scripts), **OQ-1–OQ-10** (locked below), and appendix **structure** exist; use maintainer dumps when landed for golden tests.

| ID | Research task | Method | Deliverable |
|----|---------------|--------|-------------|
| **R0-0** | Spike tooling | `spike_pylinac_acrct.py` / `spike_pylinac_acrmri.py` + `pylinac_spike_common.py`; **`--dump-json`** writes `results_data(as_dict=True)` with path redaction **and** drop of institution/address/station (and other site/patient/UID keywords); console never prints folder or dump paths | Scripts ready before maintainer runs phantoms |
| **R0-1** | Dump full `ACRCT.results_data(as_dict=True)` tree | Local phantom folder via `scripts/spike_pylinac_acrct.py --dump-json …`; redact paths; commit `tests/fixtures/qa/acr_ct_results_data.json` | **Metric registry appendix §CT** — dotted key paths |
| **R0-2** | Dump full `ACRMRILarge.results_data(as_dict=True)` tree | `scripts/spike_pylinac_acrmri.py --dump-json …`; commit `tests/fixtures/qa/acr_mri_results_data.json` | **Metric registry appendix §MRI** |
| **R0-3** | Live-analyzer gap analysis | Compare appendix keys vs user-requested families (PSG, SNR, MTF grid, HU per material); introspect `analyzer.*_module` when dict incomplete | **Gap table**: dict-only vs needs `metrics.*` harvest |
| **R0-4** | PSG on ACR CT | Read pylinac 3.43.2 `acr.py` / `ACRCTResult`; confirm whether PSG exists for CT or is MRI-only | Confirm **OQ-1** (pre-decided absent unless found) |
| **R0-5** | MTF column strategy | Document which rMTF % values pylinac emits (MRI 10–90 step grid per `PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md`); Summary MTF@50% row/col only; full grid Detail-only | Answer **OQ-4** |
| **R0-6** | Batch type naming | Introduce `ACRMBatchResult` mirroring `CTBatchResult`; do **not** overload compare-mode `MRIBatchResult` | Answer **OQ-2** |
| **R0-7** | Wide CSV column order | Prototype header list from R0-1/R0-2; stable sort: provenance block → module families → `raw_pylinac` overflow | Answer **OQ-3** |
| **R0-8** | Formula-injection policy | Wire `neutralize_spreadsheet_value` from `src/core/spreadsheet_safety.py` into QA CSV/XLSX builders (not wired today; `qa_export.py` uses bare `csv.writer` — reuse the module's `SafeCsvWriter` wrapper). XLSX matters too: openpyxl treats leading-`=` strings as formulas on open, and Series/Run labels + warnings are DICOM-derived strings | Implementation note in Phase 1 + Phase 2 XLSX test |
| **R0-9** | Committed golden dumps | Assert redacted JSON fixtures have no PHI paths (test also rejects absolute filesystem paths); run staged artifact gate on the dump commit; key-name smoke test loads dumps without `analyze()` | Enables CI flatten tests |
| **R0-10** | XLSX module images (PDF parity) | Confirm `publish_pdf` uses `save_images(to_stream=True)`; document per-modality figure names from `plot_images()` (CT: hu, uniformity, spatial resolution, low contrast, mtf, side; MRI: geometric, slices, LC slices, rMTF, side, …) | **Locked** — see **OQ-9**; implement `save_images(directory=…)` when embed on |
| **R0-3b** | Gap table result (from source) | See appendix §Live harvest below. CT: only `low_contrast_cnr` needs live harvest (background σ absent from dict). CT SNR/PSG/slice-thickness confirmed absent. MRI: PSG dict-complete (`uniformity_module.psg` + `ghosting_ratio`); SNR absent (Phase 6 viewer harvest). MTF grid dict-complete (`slice1.row_mtf_lp_mm` / `col_mtf_lp_mm`, keys 10–90). | **Gap table filled** |

**Optional (non-blocking):** one local phantom run per modality to validate appendix numbers match UI and that XLSX Images matches PDF figure set (Manual Smoke Checks — not required to merge code).

---

## XLSX module images (PDF parity)

Pylinac PDFs embed **multiple module plots**, not the single composite from `save_analyzed_image()`:

```text
publish_pdf()  →  save_images(to_stream=True)  →  plot_images()  →  one figure per module
```

| Modality | Typical figures (from pylinac 3.43.2 `plot_images`) |
|----------|------------------------------------------------------|
| **ACR CT** | `hu`, `uniformity`, `spatial resolution`, `low contrast`, `mtf`, `side` |
| **ACR MRI Large** | `geometric`, `slice 1`, `signal uniformity`, `slice 11`, LC slice keys, optional `sagittal`, `rMTF`, `side` |

**Implementation sketch**

1. **`QARequest.embed_module_images_in_xlsx: bool`** (default `True`) — when true, runner calls `analyzer.save_images(directory=module_images_dir)` after `analyze()`; filenames are pylinac module keys + `.png`.
2. **`QAResult.analyzed_module_images: dict[str, str]`** — module label → absolute PNG path (transient; **not** in JSON/CSV, same rule as today’s `analyzed_image_path`).
3. **Facade/worker** owns `TemporaryDirectory` per run (single-run) or per batch worker (batch), same lifecycle as current CT `analyzed_image_temp_dir`: **held open until after `workbook.save()`**, cleaned in a `finally` (so `analyzed_module_images` paths remain valid at embed time; the Images sheet already `os.path.isfile`-checks each path and degrades per run).
4. **`qa_xlsx_export._build_images_sheet`** — per run: label row, then stacked labeled module images (stable key sort); skip sheet + Summary note when toggle off, no images, or Pillow missing.
5. **Persisted default** — `acr_qa_embed_module_images_in_xlsx` in `qa_pylinac_config.py` (**default `True`**); checkbox on **ACR CT** and **ACR MRI** options dialogs (and batch shared-options flow). Record choice in `pylinac_analysis_profile` / JSON `inputs` for audit.
6. **Deprecate composite-only path** — stop calling `save_analyzed_image` for XLSX when module embed is on; `analyzed_image_path` may remain on `QAResult` for backward compat but XLSX reads `analyzed_module_images` first.

**Out of scope for Images sheet:** viewer-authored MRI compare summary PDF page (reportlab); optional per-run PDF paths remain separate artifacts.

## Open questions (resolve in Phase 0)

| ID | Question | Options / notes | Decision |
|----|----------|-----------------|----------|
| **OQ-1** | Does **ACR CT** expose **percent signal ghosting (PSG)** in pylinac 3.43.2, or only MRI? | Ghosting is MRI-only; omit CT PSG columns unless R0-3 finds a field | **Absent on CT** (confirm in R0-4) |
| **OQ-2** | Batch result type for multi-series MRI? | `MRIBatchResult` is **compare-mode** (carries `run_configs: list[LcRunConfig]`; drives `run_acr_mri_large_batch`); do not overload | **New `ACRMBatchResult`** mirroring `CTBatchResult` (`run_results` + `run_labels`) |
| **OQ-3** | **Wide batch CSV**: fixed column order vs sparse (only populated metrics)? | Fixed order + empty cells for Excel ergonomics | **Locked P0-GATE 2026-08-29:** two-band interim — provenance columns first, then remaining metric columns A–Z. Each metric is its own column. Revisit a third “family” band only if Excel use needs it. |
| **OQ-4** | **Summary sheet**: which metrics are mandatory columns vs Detail-only? | Gate each column on R0-3 presence; add modality discriminator; MTF@50% row+col only in Summary (not 10–90% grid) | **Locked P0-GATE 2026-08-29:** hybrid allowlist (PIU, PSG, LC score, MTF@50% row/col, MRI slice thickness/shift, `mri_snr`). **No CT SNR.** Pylinac ACR CT has no measured-thickness module; **TO_DO** tracks exporting nominal DICOM `SliceThickness` (not a ramp measurement). |
| **OQ-5** | Flatten **`raw_pylinac`** nested dicts/lists into dotted keys for **all** leaves, or curated allowlist per modality? | | **Locked P0-GATE 2026-08-29 (v1; revisit if Detail keys confuse):** curated Summary + full `raw_pylinac` walk in Detail; overlay curated `result.metrics` (metrics wins). |
| **OQ-6** | MRI batch **PDF**: optional per-series path like single-run, or batch JSON/XLSX only (match CT batch)? | CT batch has no batch PDF | **No batch PDF** for MRI |
| **OQ-7** | MRI batch **echo_number** / compare options: one shared dialog (like CT options) — include compare toggle? | Compare stays on single-run menu; batch bypasses `compare_request` | **Locked: no compare in batch** (P0-GATE: ok for now) |
| **OQ-8** | Add `metrics_flat` to JSON export or keep flatten export-layer-only? | `raw_pylinac` already carries data | **Locked P0-GATE 2026-08-29 (v1; revisit if a consumer needs flat JSON):** export-layer only — JSON keeps nested `raw_pylinac`; CSV/XLSX get the flat columns. |
| **OQ-9** | Embed **PDF-parity module images** in XLSX Images sheet? | `save_images()` vs composite; workbook size | **Yes, default on** — persisted `acr_qa_embed_module_images_in_xlsx`; user can disable in ACR CT/MRI options (single + batch) |
| **OQ-10** | **MRI SNR** noise term: apply NEMA **0.655** Rayleigh correction on background σ? | PMC8321175 / NEMA MS 1 vs ACR-style uncorrected **S̄ / σ_bkg** (~80% phantom diameter on the uniformity slice) | **Locked: no 0.655 in v1** — export key **`mri_snr`** is **uncorrected** ACR-style ratio (≠ NEMA SNR); document in user guide |

## Tests to add (required before merge)

All new tests under `tests/qa/` unless noted. Use **committed redacted `results_data` dumps** (`tests/fixtures/qa/`) for golden flatten tests; no PHI paths; no live `analyze()` in CI.

### Phase 0 / research

- [x] **`tests/qa/test_pylinac_results_data_spike.py`** — load committed `acr_*_results_data.json`; assert dict shape; optional snapshot of key names (not values) for regression; assert no absolute filesystem paths in the dumps (cheap PHI redaction regression per R0-9).

### Phase 1 — flattening

- [x] **`tests/qa/test_qa_result_flatten.py`** (synthetic) **+ `test_pylinac_results_data_spike.py`** (golden dumps, P1-F4)
  - CT success: flatten includes keys from each target family present in committed dump (≥1 key per family per G2).
  - MRI success: same.
  - Failed run: provenance + errors; no crash on empty `raw_pylinac`.
  - Warnings preserved in provenance or dedicated keys.
  - Stable sort order of metric keys (golden list).
  - `low_contrast_cnr` / LC score paths match F1 contract.
- [ ] **`tests/qa/test_qa_export_csv.py`** (or extend `tests/test_qa_pylinac_acr_ct_cnr.py`)
  - Single-run CSV row count > legacy metrics-only export.
  - Formula-like values neutralized if any string cells (via `SafeCsvWriter`).
  - Wide batch CSV: N rows + header; columns align with `build_tabular_run`.

### Phase 2 — XLSX

- [ ] **`tests/test_qa_xlsx_export.py`** (existing, flat under `tests/`) — extend, or add `tests/qa/test_qa_xlsx_export.py`
  - Summary sheet headers include modality-aware columns.
  - Detail sheet row count matches `build_metric_rows`.
  - Images sheet: multiple module PNGs per run when embed on; skipped with note when embed off.
  - Module image paths do not leak into JSON/CSV.
  - Formula-like string cells (e.g. a Series/Run label beginning with `=`) are neutralized in every sheet — openpyxl writes leading-`=` strings as live formulas.
  - Batch workbook: one Summary row per run.

### Phase 3 — batch CT CSV

- [x] **`tests/gui/test_ct_batch_result_dialog.py`** (or facade test) — Export CSV invokes `build_batch_metrics_csv` with batch labels (mock facade).

### Phase 4 — MRI batch

- [ ] **`tests/qa/test_qa_mri_batch_worker.py`** (mirror the `tests/test_qa_ct_batch_worker.py` scaffold)
  - Serial execution; cancel mid-batch returns partial `run_results`.
  - Per-series failure isolation (one bad series does not abort batch).
  - Labels parallel to requests.
- [ ] **`tests/test_qa_pylinac_config.py`** — `acr_qa_embed_module_images_in_xlsx` default true, persist round-trip.
- [ ] **`tests/gui/test_acr_ct_qa_dialog.py`** (exists) / **`tests/gui/test_acr_mri_qa_dialog.py`** (create if absent) — embed checkbox default and save to config.
- [ ] **`tests/gui/test_mri_batch_selection_dialog.py`** — MR series filter (`Modality=="MR"` on first dataset, mirror `tests/test_ct_batch_select_dialog.py`); Add folder wiring (mock organizer).
- [ ] **`tests/test_main_signal_wiring.py`** — new menu action wired (if added to signal map).

### Regression / harness

- [ ] Full `tests/qa/` + existing `test_qa_pylinac_acr_ct_cnr.py` green.
- [ ] `python scripts/check_user_docs_links.py` after user-docs edits.
- [ ] `python scripts/check_doc_feature_coverage.py` — new menu strings covered (optional triage).

---

## Documentation updates

### Repository (`dev-docs/`)

| File | Update |
|------|--------|
| **`dev-docs/info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md`** | ACR CT/MRI metric reference + pylinac gap table; deferred resolution-read roadmap |
| **`dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`** | Document canonical flatten keys, batch MRI flow, export surfaces (CSV wide vs metric/value), JSON vs export-layer flatten, **module image embed toggle**, **MRI SNR (Phase 6)** |
| **`dev-docs/info/PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md`** | MTF grid / metric extraction notes if live harvest added |
| **`dev-docs/info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md`** | Cross-link metric families now exported |
| **`dev-docs/plans/completed/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md`** | Metric registry appendix (Phase 0 output); mark open questions decided |
| **`dev-docs/MAINTENANCE_LOG.md`** | Implementation completion note |
| **`CHANGELOG.md`** | **Minor** — MRI batch menu + enriched CSV/XLSX exports |
| **`dev-docs/TO_DO.md`** | Close/consolidate bullets when plan completes |

### User-facing (`user-docs/`)

| File | Update |
|------|--------|
| **`user-docs/USER_GUIDE_QA_PYLINAC.md`** | **ACR MRI Batch** menu; batch CT **Export CSV**; full metric list in CSV/XLSX (Summary vs Detail); **Embed module images in XLSX** option (default on, PDF parity); clarify JSON still has full `raw_pylinac`; compare mode unchanged |
| **`user-docs/USER_GUIDE.md`** | Hub bullet for MRI batch if not redundant with QA guide |
| **`user-docs/CONFIGURATION.md`** | **`acr_qa_embed_module_images_in_xlsx`** (default true) |

### In-app (UI strings)

| Location | Update |
|----------|--------|
| **`src/gui/main_window_menu_builder.py`** | **ACR MRI Batch (pylinac)…** action + tooltip (parallel CT batch) |
| **`src/gui/dialogs/mri_batch_result_dialog.py`** | Button labels: Export CSV / JSON / XLSX; column headers matching Summary metrics |
| **`src/gui/dialogs/ct_batch_result_dialog.py`** | Add **Export CSV…** button + tooltip |
| **`src/gui/dialogs/acr_ct_qa_dialog.py`** / **`acr_mri_qa_dialog.py`** | **Embed module images in XLSX** checkbox (default on) |
| **`src/gui/dialogs/acr_mri_series_selection_dialog.py`** | Title, instructions (mirror CT selection dialog) |
| **Progress / status strings** | `qa_app_facade.py` — N-of-M MRI batch progress (mirror CT) |
| **Save dialogs** | Update filter text if batch CSV title differs from single-run |
| **Optional:** **Help** menu | Only if QA guide is linked from a new in-app Help topic — today pylinac is user-docs only; **no new Help dialog required** unless hub policy changes |

Run **`python scripts/check_user_docs_links.py`** after `user-docs/` edits.

---

```text
run_acr_ct_analysis / run_acr_mri_large_analysis
  (when embed_module_images_in_xlsx: analyzer.save_images(dir) → analyzed_module_images)
        │
        ▼
   QAResult (metrics + raw_pylinac + provenance + analyzed_module_images)
        │
        ▼
qa_result_flatten.py  (NEW — **locked** module `src/qa/qa_result_flatten.py`; do not rely on extending `qa_export` alone)
  build_metric_rows(result) -> list[tuple[str, Any]]  # stable sort, dotted keys
  build_run_provenance(result, label?) -> dict       # study/series, versions, status
  build_tabular_run(result, label?) -> dict           # one wide row for batch CSV
  # Merge rule: walk raw_pylinac; overlay the curated result.metrics entries on top.
  # Curated/harvested keys stay TOP-LEVEL (low_contrast_cnr, low_contrast_score, num_images,
  # phantom_roll, origin_slice, …) — matching today's CSV paths and the F1 contract; the
  # "metrics.*" notation elsewhere in this plan means "a member of result.metrics", not a
  # literal `metrics.` key prefix. For a genuine dotted-key collision, metrics wins
  # (provenance-curated scalars); all other raw_pylinac leaves pass through untouched.
        │
        ├── qa_export.build_metrics_csv (refactor to use flatten)
        ├── qa_export.build_batch_metrics_csv (NEW)
        ├── qa_xlsx_export.build_qa_workbook (Summary from key columns + full Detail)
        └── (future) QA_RESULTS_EXPORT CLI / DB

QAMRIBatchWorker (NEW) — mirror QACTBatchWorker serial semantics
ACRMBatchResult (NEW) — mirror CTBatchResult; do not reuse compare-mode MRIBatchResult
mri_batch_result_dialog.py (NEW) — mirror ct_batch_result_dialog
acr_mri_series_selection_dialog.py (NEW) — mirror CT selection; MR series filter (Modality MR)
```

**Locked decisions**

- **Serial batch execution** for MRI (same rationale as CT batch in `worker.py`).
- **One wide CSV row per run** for batch export; multi-run workbook = one Summary sheet + Detail + Images (module PNGs when embed on).
- **Wide-row key collisions:** `build_tabular_run` overlays flatten keys onto provenance **in place** (metrics/flatten wins; keys stay top-level). Do **not** rename to `metric.<key>`. Typical overlap: `num_images`.
- **XLSX module images:** PDF parity via `save_images()`; **default on**, persisted **`acr_qa_embed_module_images_in_xlsx`**; user can disable per run from options dialogs.
- **Do not break** existing JSON schemas; flattened export is additive or export-layer only.
- **Formula injection:** wire `neutralize_spreadsheet_value` (`src/core/spreadsheet_safety.py`) into QA CSV/XLSX builders.
- **Nuclear / CatPhan:** out of scope for this plan (separate serializers already exist for nuclear CSV).

---

## Phases

### Phase 0 — Research and metric registry

- [x] **(R0-0)** Spike scripts + `pylinac_spike_common.py`; CT/MRI `--dump-json` (path redaction). (owner: coder) — **in repo**; run on maintainer phantom when `test-DICOM-data/` populated
- [x] **(R0-1)** CT `results_data(as_dict=True)` key dump → appendix §CT + committed `tests/fixtures/qa/acr_ct_results_data.json`. (owner: maintainer) — **2026-08-29** from `deid-phantoms/ct/series-001/`
- [x] **(R0-2)** MRI `results_data(as_dict=True)` key dump → appendix §MRI + committed `tests/fixtures/qa/acr_mri_results_data.json`. (owner: maintainer) — **2026-08-29** from `deid-phantoms/mr/series-005/` (T1; 1 mm extent)
- [x] **(R0-3)** Live-analyzer gap table (dict vs harvest) — **filled from source** (see appendix §Live harvest; CT only needs `low_contrast_cnr` live harvest; MRI PSG/SNR/MTF confirmed dict-complete except SNR = Phase 6). (owner: coder)
- [x] **(R0-4)** Confirm **OQ-1** — **CT PSG absent** in pylinac 3.43.2: `ACRCTResult` has no `psg`/`ghosting_ratio`/`ghost_rois` fields; `ACRCT` has no `uniformity_module.ghost_rois`. PSG is MRI-only (`MRUniformityModuleOutput.psg` + `ghosting_ratio` present). (owner: coder)
- [x] **(R0-5)** Resolve **OQ-4**, **OQ-5** (Summary vs Detail flatten strategy). (owner: coder + reviewer) — **P0-GATE 2026-08-29:** hybrid Summary allowlist; Detail = full dotted walk; no CT SNR; CT measured thickness still absent (see TO_DO for DICOM `SliceThickness`).
- [x] **(R0-6)** Lock **OQ-2** (`ACRMBatchResult`). (owner: coder) — **landed**: `ACRMBatchResult` added to `src/qa/analysis_types.py`, mirroring `CTBatchResult` (`run_results` + `run_labels` only); docstring states it is **not** compare-mode `MRIBatchResult`.
- [x] **(R0-7)** Lock **OQ-3** (wide CSV column order prototype). (owner: coder) — **P0-GATE 2026-08-29:** keep two-band interim (provenance insertion order → remaining keys `str`-sorted). Each metric is its own column. No third family band unless Excel use requires it.
- [x] **(R0-8)** Document formula-injection wiring for Phase 1 — `qa_export.build_metrics_csv` uses bare `csv.writer`; Phase 1 (P1-F2) must wrap with `SafeCsvWriter` from `src/core/spreadsheet_safety.py` and apply `neutralize_spreadsheet_value` to every cell. XLSX: openpyxl writes leading-`=` strings as live formulas on open — same neutralization applies to Series/Run labels and warnings in XLSX cells. (owner: coder) — **landed**: CSV wired in P1-F2; XLSX Summary, Detail, and Images Series/Run labels neutralized in P2-X2.
- [x] **(R0-9)** Commit redacted dumps; assert no PHI paths. (owner: maintainer, after: R0-1, R0-2) — hygiene + family tests in `tests/qa/test_pylinac_results_data_spike.py`
- [x] **(R0-10)** Document module figure names per modality from `plot_images()` source — see appendix §Figure names. **OQ-9 locked**: embed via `save_images(directory=…)` when toggle on. (owner: coder)
- [x] **(P0-T1)** Add `tests/qa/test_pylinac_results_data_spike.py` (loads committed dumps). (owner: tester, after: R0-9)
- [x] **(P0-GATE)** Reviewer signs off appendix + **OQ-1–OQ-10** before claiming Phase 0 complete. (owner: reviewer) — **signed 2026-08-29.** OQ-5/OQ-8 locked for v1 with revisit-if-wrong. CT SNR stays omitted. CT image thickness (DICOM `SliceThickness`) tracked in `TO_DO.md`, not this plan’s v1 Summary.

### Phase 1 — Canonical flattening (`qa_result_flatten.py` — **locked new module**)

- [x] **(P1-F1)** Add **`src/qa/qa_result_flatten.py`** (do not extend `qa_export` only): provenance + flatten walk `raw_pylinac`, overlay `metrics.*` (metrics wins for curated provenance scalars), add CNR/LC live fields. Synthetic tests in `tests/qa/test_qa_result_flatten.py`; golden dumps **P1-F4** landed 2026-08-29. (owner: coder)
- [x] **(P1-F2)** Refactor `build_metrics_csv` to emit full flatten; keep two-column `metric,value` for single-run. (owner: coder, after: P1-F1) — **landed**
- [x] **(P1-F3)** Add `build_batch_metrics_csv(results, labels)` — one header row, one row per run (wide). (owner: coder, after: P1-F1) — **landed**
- [x] **(P1-F4)** Tests: golden key sets from **committed dumps** for CT and MRI; failed run; warnings present. (owner: tester, after: R0-9, P1-F1) — `test_pylinac_results_data_spike.py` + synthetic failed-run coverage in `test_qa_result_flatten.py`

### Phase 2 — XLSX upgrade

- [x] **(P2-I1)** `QARequest` / `QAResult`: `embed_module_images_in_xlsx`, `module_images_out_dir`, `analyzed_module_images`; runners call `save_images()` when enabled. (owner: coder) — **landed**: CT/MRI runners share `capture_analyzed_module_images` (`save_images` **return** paths, not glob); CT skips composite when embed on + dir set; denylisted from flatten/JSON/CSV; failures swallowed.
- [x] **(P2-I2)** Config + dialogs: `acr_qa_embed_module_images_in_xlsx` (default **True**); checkbox on ACR CT/MRI options + batch options; profile/JSON `inputs` audit field. (owner: coder) — **landed**: config mixin + default; checkbox on ACR CT, ACR MRI, and CT batch shared-options flows; persisted on accept; recorded in `QARequest.embed_module_images_in_xlsx`, `pylinac_analysis_profile`, and JSON `inputs`.
- [x] **(P2-I3)** Facade/worker temp-dir lifecycle for module image dirs (CT single, CT batch, MRI single, MRI batch). (owner: coder, after: P2-I1) — **landed**: CT single nests module dir under composite image temp dir (single cleanup in ``start_qa_worker``); CT batch and MRI batch workers each own a sibling ``module_images_temp_dir`` with a **per-series uuid subdirectory** (MRI batch: ``QAMRIBatchWorker``, P4-M1; cleaned on summary-dialog destroy in ``qa_mri_batch_flow``). MRI single gets a standalone dir cleaned via ``module_images_cleanup`` (assigned only on the non-compare branch). Extent-retry clears ``module_images_out_dir``.
- [x] **(P2-X1)** Extend `build_qa_workbook` Summary sheet with modality-aware key columns (uniformity PIU, PSG, LC score where present, MTF@50% row+col, slice thickness/shift on MRI only — best-effort; omit **CT** slice-thickness and **CT SNR**; add **`mri_snr`** Summary column when Phase 6 harvest ships). (owner: coder, after: P1-F1) — **landed**: `_SUMMARY_HEADERS` has 8 modality-aware columns including **MRI SNR** (`mri_snr`); `_summary_extra_values` pulls each from `build_metric_rows` (canonical flatten) so missing keys degrade to blank cells and CT/MRI rows share one header with blanks where a metric does not apply; numeric cells stay numbers. Locked gaps respected: no CT slice-thickness, no CT SNR. Tests in `tests/qa/test_qa_xlsx_summary_columns.py`.
- [x] **(P2-X2)** Detail sheet uses full flatten (replaces metrics-only flatten). (owner: coder, after: P1-F1) — **landed**: `_build_detail_sheet` now iterates `build_metric_rows(result)`; Summary, Detail, and Images Series/Run labels (plus Summary warnings) are neutralized via `neutralize_spreadsheet_value`; list/tuple cells joined with `"; "` (matches CSV).
- [x] **(P2-X3)** Images sheet: multi-module embed from `analyzed_module_images`; graceful skip when toggle off / no Pillow. (owner: coder, after: P2-I1, P2-X2) — **landed**: `_build_images_sheet` reads `analyzed_module_images` first (stable `str` sort, missing files dropped), per run writes Series/Run label then stacked labeled module images (480×480, stride 34), module labels neutralized via `_xlsx_cell`; falls back to legacy composite `analyzed_image_path` when module dict empty; when the sheet exists, a run with nothing embeddable still gets ``(no analyzed image for this run)``; skips sheet + Summary note when Pillow missing or no embeddable image from either source.
- [x] **(P2-X4)** Tests: Images sheet module count + toggle off skips sheet; paths not in JSON/CSV. (owner: tester, after: P2-X3) — **landed**: multiple module PNGs embed in stable key order; mixed modules+composite workbook; per-run placeholder when a sibling run has no image; formula-like module + run labels neutralized on Images; missing module files dropped; composite fallback when module dict empty; module-image paths do not leak into JSON/CSV; existing composite stride regression passes. **Remaining closed**: `save_composite_analyzed_image` now skips composite save when `embed_module_images_in_xlsx` is False (the composite's only purpose is XLSX embedding), so toggle-off produces `analyzed_image_path=None` and the workbook's composite fallback cannot run → Images sheet skipped with Summary note. CT/MRI dialog checkbox already stamps `embed_module_images_in_xlsx` on `QARequest` (P2-I2; not re-clicked in these tests); MRI runner never saved a composite, so it was already correct. Runner+workbook tests verify: `QARequest(embed=False)` → no embeddable path → `build_qa_workbook` skips Images; embed-on regression still embeds modules; embed-on-no-dir composite fallback preserved.

### Phase 3 — Batch CT CSV + export parity

- [x] **(P3-C1)** Add **Export CSV…** to `ct_batch_result_dialog` → `export_ct_batch_csv` in facade. (owner: coder, after: P1-F3)
- [x] **(P3-C2)** Verify single-run CT/MRI save dialog CSV/XLSX pick up full flatten without UI change. (owner: tester, after: P1-F2, P2-X2) — **landed**: `QAAppFacade.export_qa_results` already routes `.csv` → `build_metrics_csv` (full flatten) and `.xlsx` → `build_qa_workbook` (Detail = `build_metric_rows`); no production change needed. Five tests in `tests/gui/test_qa_app_facade_export_slice.py` (`test_export_qa_results_csv_full_flatten_ct/mri`, `test_export_qa_results_xlsx_detail_full_flatten_ct/mri`, `test_export_qa_results_json_has_no_metrics_flat`) prove nested `raw_pylinac` dotted leaves survive the save-dialog path for both CT and MRI, curated-metrics overlay wins on a planted collision (`raw_pylinac.low_contrast_cnr` / `.low_contrast_score` vs metrics), and denylisted `analyzed_image_path`/`analyzed_module_images` paths never reach CSV or XLSX Detail (including when those keys live under `raw_pylinac`); JSON schema unchanged (no `metrics_flat` at any depth).

### Phase 4 — Multi-series MRI batch

- [x] **(P4-M1)** Add `QAMRIBatchWorker` (serial `run_acr_mri_large_analysis` per series); `ACRMBatchResult`. (owner: coder) — **landed**: `ACRMBatchResult` in `src/qa/analysis_types.py` (mirrors `CTBatchResult`; docstring clarifies it is **not** compare-mode `MRIBatchResult`); `QAMRIBatchWorker` in `src/qa/worker.py` (serial per-series, cooperative cancel, per-series error isolation, `series_completed` + `batch_result_ready`, worker-owned `image_temp_dir` + optional `module_images_temp_dir` with per-series uuid subdirs). Tests in `tests/test_qa_mri_batch_worker.py`.
- [x] **(P4-M2)** `acr_mri_series_selection_dialog` — loaded MR series + Add folder; shared options from existing MRI dialog. (owner: coder) — **landed**: `src/gui/dialogs/acr_mri_series_selection_dialog.py` (`build_mri_series_entries` filters `Modality == "MR"`; `prompt_mri_batch_series_selection` returns parallel `(requests, labels)` with `analysis_type="acr_mri_large"` / `modality="MR"`, checkbox list + Add folder, skip/warn/info boxes mirroring CT); `stamp_mri_batch_options` helper applies echo/check_uid/origin_slice/scan extent/vanilla/embed/LC fields via `dataclasses.replace` (no compare-mode field). Tests in `tests/gui/test_mri_batch_selection_dialog.py`.
- [x] **(P4-M3)** Menu: **ACR MRI Batch (pylinac)…**; progress N-of-M; cancel semantics match CT. (owner: coder, after: P4-M1, P4-M2) — **landed**: ``acr_mri_batch_requested`` signal + ``ACR MRI Batch (pylinac)…`` menu item; signal wired to ``_open_acr_mri_batch_analysis`` thin slot → ``dialog_actions.open_acr_mri_batch_analysis`` → ``gui.qa_mri_batch_flow.open_acr_mri_batch_analysis`` (selection → options → ``stamp_mri_batch_options`` → ``QAMRIBatchWorker`` → N-of-M progress → cancel calls ``worker.cancel()`` → minimal non-modal summary; temp dirs cleaned on dialog destroy or immediately when batch empty). ``compare_request`` ignored (OQ-7). Flow lives in ``src/gui/qa_mri_batch_flow.py`` so ``QAAppFacade`` does not grow. Tests in ``tests/gui/test_qa_mri_batch_flow.py``.
- [x] **(P4-M4)** `mri_batch_result_dialog` — table per series; Export CSV / JSON / XLSX; module Images per **OQ-9**. (owner: coder, after: P4-M3, P1-F3, P2-X3) — **landed**: ``src/gui/dialogs/mri_batch_result_dialog.py`` (``create_mri_batch_result_dialog`` — one row per series: label, status, LC score, warnings; Export XLSX/JSON/CSV buttons; failed-series title suffix); ``src/gui/qa_mri_batch_export.py`` (``save_mri_batch_xlsx``/``json``/``csv`` — typed on ``ACRMBatchResult``; XLSX reuses ``build_qa_workbook`` so Images sheet embeds module PNGs per OQ-9; JSON emits per-run document array; CSV uses ``build_batch_metrics_csv``); wired from ``src/gui/qa_mri_batch_flow.py`` (flow module unchanged in role; buttons wired from the flow, not the facade). Tests in ``tests/gui/test_mri_batch_result_dialog.py`` + ``tests/gui/test_qa_mri_batch_export.py``.
- [x] **(P4-M5)** Tests: worker isolation, label parity, export hooks (mock runner); mirror patterns in `tests/test_qa_ct_batch_worker.py`. (owner: tester, after: P4-M4) — **landed (export hooks + dialog)**: export hooks fire on button click (mock save path); workbook built from ``ACRMBatchResult.run_results``; CSV uses flatten (no ``analyzed_image_path`` / ``analyzed_module_images`` leak); JSON emits per-run document array with ``series_label``; dialog renders one row per series with LC score (including 0). Worker-isolation and label-parity coverage already in ``tests/test_qa_mri_batch_worker.py`` (P4-M1).

### Phase 5 — Docs and closure

- [x] **(P5-D1)** User-docs: `USER_GUIDE_QA_PYLINAC.md` — MRI batch moved to its own `### ACR MRI batch` section (was a paragraph under `### ACR CT`); single-run CSV/XLSX now documented as full flatten (Summary vs Detail); **Embed module images in XLSX** option documented (default on, PDF parity, uncheck skips Images sheet); JSON still full `raw_pylinac` (no `metrics_flat`); compare mode unchanged; hub `USER_GUIDE.md` bullet updated; `CONFIGURATION.md` row expanded. (owner: docs) — **landed**
- [x] **(P5-D2)** Dev-docs: `PYLINAC_INTEGRATION_OVERVIEW.md` — ACR CT CNR/batch/XLSX row updated to document canonical flatten (`qa_result_flatten.py`, metrics-overlay-wins, path denylist), wide batch CSV vs single-run metric/value, XLSX Summary/Detail/Images + embed toggle, `ACRMBatchResult` + `QAMRIBatchWorker` (not compare-mode `MRIBatchResult`), MRI batch menu + export; stale "batch for other modalities remain future work" corrected to "shipped for ACR CT and ACR MRI"; Phase 6 SNR kept **not shipped**. Plan appendix P5-D1/D2/D3 marked. `MAINTENANCE_LOG.md` dated completion note for Phases 1–5. (owner: docs) — **landed**
- [x] **(P5-D3)** In-app strings: menu, dialogs, tooltips, save-dialog titles audited against the **Documentation updates** table — **all strings already landed** from P3/P4 (MRI batch menu in `main_window_menu_builder.py`; Export CSV/JSON/XLSX buttons in `mri_batch_result_dialog.py` + `ct_batch_result_dialog.py`; "Embed module images in XLSX" checkbox in `acr_ct_qa_dialog.py` + `acr_mri_qa_dialog.py`; selection dialog title/instructions in `acr_mri_series_selection_dialog.py`). **Zero Python changed.** (owner: coder) — **landed; no code change**
- [x] **(P5-D4)** `CHANGELOG.md` — existing **Unreleased** **Added** (minor: MRI batch menu P4-M3, MRI batch export P4-M4, full-flatten CSV, XLSX Summary modality-aware columns P2-X1, embed-module-images toggle P2-I2, XLSX multi-module Images P2-X3) + **Fixed** P2-X4 (embed-off skips Images sheet, patch) already cover the ship. **No new CHANGELOG bullet needed** — user-docs facts are all represented. (owner: docs) — **landed; no new entry**
- [x] **(P5-D5)** `check_user_docs_links.py` + move plan to `completed/`; trim `TO_DO.md`. (owner: orchestrator) — **completed 2026-08-30:** PRs #97 and #98 merged; plan archived and the optional manual smoke moved to `TO_DO.md`.

### Phase 6 — Viewer-computed MRI SNR (extension slice)

**Goal:** Export a defensible **ACR-style SNR** for MRI Large runs even though pylinac does not compute it. SNR is **not** one of the seven ACR accreditation phantom tests, but it is required in the **ACR MRI QC Manual** (weekly/annual) and is commonly reported alongside PIU/PSG.

**Canonical formula (uncorrected ACR-style ratio — same family as NEMA without 0.655, LCD-paper SNR, and PMC8321175 Eq. 7):**

```text
SNR = mean(pylinac Center ROI on the uniformity slice)
      / mean(σ in two background ROIs along frequency-encode axis)
```

- **Signal (S̄):** pylinac `MRUniformityModule` **Center** disk ROI mean (`pixel_value`), used as-is (roi radius 80 in pylinac 3.43.2). Do **not** invent a separate ~80% phantom-diameter circle. Do **not** call this a “flood” (nuclear-medicine term).
- **Noise:** average of pixel **standard deviations** in the two **ghost-free** background rectangles on the **frequency-encode axis** — select the pair from pylinac `ghost_rois` (**Left/Right** when phase encode is DICOM **COL** / top–bottom; **Top/Bottom** when phase encode is DICOM **ROW** / left–right). **Do not hard-code Left/Right** without `InPlanePhaseEncodingDirection`. **Fallback when DICOM tags missing:** assume phase encode = ROW, frequency encode = COL (PMC8321175 §2.2) → **Top/Bottom** for noise. Same ROI family as PSG §6, but use **σ** not mean intensity.
- **Encode direction:** read DICOM (`InPlanePhaseEncodingDirection`, orientation) before selecting axes; document fallback above in R6-3.
- **Slice:** uniformity module slice (same as PIU/PSG).
- **NEMA:** same S̄ / σ_bkg, times **0.655** — not applied in v1 (OQ-10).

**References:** [ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md](../../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md) (definitions, links, pylinac gap table).

| ID | Task | Deliverable |
|----|------|-------------|
| **R6-1** | Literature + site review | Confirm the uncorrected **S̄ / σ_bkg** ratio (80% phantom diameter, uniformity slice) vs NEMA MS 1 (same ratio × 0.655); keep export key `mri_snr` |
| **R6-2** | Local phantom validation | Compare viewer SNR vs manual ROI on one gitignored ACR MRI series; record in investigation doc |
| **R6-3** | DICOM encode-direction helper | Qt-free helper: map phase vs frequency image axis; return which `ghost_rois` pair is ghost-free (freq-encode). **Fallback:** phase=ROW / freq=COL when tags missing |
| **R6-4** | Runner harvest | `_extract_mri_snr_acr_style(analyzer)` in `pylinac_acr_mri.py` → `metrics.mri_snr` (+ optional intermediates: `mri_snr_signal_mean`, `mri_snr_noise_mean`). Noise ROIs = freq-encode pair from R6-3, not fixed Left/Right |
| **R6-5** | Export | Include in flatten Summary column + Detail rows; user guide must state **`mri_snr` is uncorrected ACR-style ratio** (not NEMA MS 1 SNR — differs by ~0.655× if NEMA air-ROI method used) |
| **R6-6** | Tests | Unit tests with mocked uniformity module ROIs / synthetic pixel arrays; optional golden values from R6-2 (gitignored notes, not PHI fixtures) |

**OQ-10 (locked):** **No 0.655** Rayleigh factor in v1; **`mri_snr`** is uncorrected — see open-questions table.

**Out of scope for Phase 6:** two-image difference SNR, NEMA air-ROI SNR with 0.655 correction, CT SNR, legacy 1999 nickel-vial SNR.

**Phase 6+ (after `mri_snr` ships):** optional **SNRU** slice-6÷7 ratio ([PMC8321175 §2.3.3.B](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/)); export only, no default pass/fail.

- [x] **(P6-R1)** R6-1 literature + Center-ROI decision locked (pylinac Center as-is; no 0.655). **R6-2 landed 2026-08-29:** manual vs viewer SNR on tracked `deid-phantoms/mr/series-005` (T1, SeriesNumber 3, COL); numbers in [ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md](../../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md#r6-2--local-t1-snr-compare-2026-08-29). (owner: coder + physicist reviewer)
- [x] **(P6-H1)** Implement R6-3/R6-4 harvest. (owner: coder, after: P6-R1, Phase 1 flatten exists) — **landed:** `src/qa/pylinac_mri_snr.py` (`extract_mri_snr_acr_style`) + runner overlay; `src/qa/pylinac_mri_echo.py` auto-highest echo when `QARequest.echo_number is None`.
- [x] **(P6-E1)** R6-5 export + docs. (owner: coder + docs, after: P6-H1) — **landed:** XLSX Summary **MRI SNR** column; user guide uncorrected labeling; CHANGELOG minor.
- [x] **(P6-T1)** R6-6 tests. (owner: tester, after: P6-H1) — **landed:** mocked ROI SNR tests, echo header tests, dialog default, flatten overlay, Summary column. No live `analyze()` in CI.

**Dependency:** Phase 6 can land **after Phase 2** (flatten + XLSX) or in parallel with Phase 4; does not block Phase 0–5 accreditation-metric export.

---

## Metric registry appendix

_Dotted key paths below are copied from pylinac 3.43.2 result dataclass field names (`ACRCTResult` line 256, `ACRMRIResult` line 1614) and `results_data(as_dict=True)` output. Do not invent names. Optional/version-dependent fields noted._

### §CT — `ACRCT` keys

Top-level (`ACRCTResult`, `results_data` root):

- `phantom_model: str`
- `phantom_roll_deg: float`
- `origin_slice: int`
- `num_images: int`
- `date_of_analysis`, `pylinac_version`, `warnings` — present on the 2026-08-29 committed dump (analysis-run metadata, not patient tags)

`ct_module` (`CTModuleOutput`):

- `ct_module.offset: float`
- `ct_module.roi_distance_from_center_mm: float`
- `ct_module.roi_radius_mm: float`
- `ct_module.roi_settings: dict` (material → {angle, distance, radius}; dumps also include runtime-mutated `angle_corrected`, `distance_pixels`, `radius_pixels` from `_convert_units_in_settings`)
- `ct_module.rois: dict[str, float]` (material → mean HU; keys: Air, Poly, Acrylic, Bone, Water)

`uniformity_module` (`UniformityModuleOutput` extends `CTModuleOutput`):

- `uniformity_module.offset: float`
- `uniformity_module.roi_distance_from_center_mm: float`
- `uniformity_module.roi_radius_mm: float`
- `uniformity_module.roi_settings: dict`
- `uniformity_module.rois: dict[str, float]` (keys: Top, Right, Bottom, Left, Center)
- `uniformity_module.center_roi_stdev: float`

`low_contrast_module` (`LowContrastModuleOutput` extends `CTModuleOutput`):

- `low_contrast_module.offset: float`
- `low_contrast_module.roi_distance_from_center_mm: float`
- `low_contrast_module.roi_radius_mm: float`
- `low_contrast_module.roi_settings: dict`
- `low_contrast_module.rois: dict[str, float]` (key: ROI)
- `low_contrast_module.cnr: float`

`spatial_resolution_module` (`SpatialResolutionModuleOutput` extends `CTModuleOutput`):

- `spatial_resolution_module.offset: float`
- `spatial_resolution_module.roi_distance_from_center_mm: float`
- `spatial_resolution_module.roi_radius_mm: float`
- `spatial_resolution_module.roi_settings: dict`
- `spatial_resolution_module.rois: dict[str, float]` (keys: `10oclock`, `9oclock`, `7oclock`, `6oclock`, `4oclock`, `3oclock`, `2oclock`, `12oclock` — no 1/5/8/11 o'clock)
- `spatial_resolution_module.lpmm_to_rmtf: dict` (lp/mm → relative MTF)

**CT families confirmed ABSENT in 3.43.2** (do not emit columns): SNR, PSG, slice thickness (no thickness module on `ACRCT`), ghost ROIs.

### §MRI — `ACRMRILarge` keys

Top-level (`ACRMRIResult`, `results_data` root):

- `phantom_model: str`
- `phantom_roll_deg: float`
- `origin_slice: int`
- `num_images: int`
- `date_of_analysis`, `pylinac_version`, `warnings` — present on the 2026-08-29 committed dump

`slice1` (`MRSlice1ModuleOutput`):

- `slice1.offset: int`
- `slice1.roi_settings: dict`
- `slice1.rois: dict[str, ROIResult]` (via `rois_to_results`; each ROI has `name`, `value`, `stdev`, `difference`, `nominal_value`, `passed` — flatten leaves e.g. `slice1.rois.Row 1.1.value`)
- `slice1.bar_difference_mm: float`
- `slice1.slice_shift_mm: float`
- `slice1.measured_slice_thickness_mm: float`
- `slice1.row_mtf_50: float`
- `slice1.col_mtf_50: float`
- `slice1.row_mtf_lp_mm: dict[int, float]` (keys 10–90 → lp/mm)
- `slice1.col_mtf_lp_mm: dict[int, float]` (keys 10–90 → lp/mm)

`slice11` (`MRSlice11ModuleOutput`):

- `slice11.offset: int`
- `slice11.roi_settings: dict`
- `slice11.rois: dict[str, ROIResult]` (bar ROIs via `rois_to_results`)
- `slice11.bar_difference_mm: float`
- `slice11.slice_shift_mm: float`

`uniformity_module` (`MRUniformityModuleOutput`):

- `uniformity_module.offset: int`
- `uniformity_module.roi_settings: dict`
- `uniformity_module.rois: dict[str, ROIResult]` (Center ROI via `rois_to_results`)
- `uniformity_module.ghost_roi_settings: dict`
- `uniformity_module.ghost_rois: dict[str, ROIResult]` (keys: Top, Bottom, Left, Right)
- `uniformity_module.psg: float`
- `uniformity_module.ghosting_ratio: float`
- `uniformity_module.piu_passed: bool`
- `uniformity_module.piu: float`

`geometric_distortion_module` (`MRGeometricDistortionModuleOutput`):

- `geometric_distortion_module.offset: int`
- `geometric_distortion_module.profiles: dict[str, dict]` (keys: horizontal, vertical, negative diagonal, positive diagonal; each → {"width (mm)": float, "line": LineSerialized})
- `geometric_distortion_module.distances: dict` (direction → "mm" string)

`sagittal_localizer_module` (`MRSagittalLocalizationModuleOutput`):

- `sagittal_localizer_module.profiles: dict[str, dict]` (keys: ROI1–ROI4; each → {"width (mm)": float, "line": LineSerialized})
- `sagittal_localizer_module.distances: dict`

`low_contrast_multi_slice_module` (`MRLowContrastMultiSliceModuleOutput`):

- `low_contrast_multi_slice_module.score: int`
- `low_contrast_multi_slice_module.low_contrast_rois: dict` (keys: slice_8, slice_9, slice_10, slice_11; each → `MRLowContrastModuleOutput`: offset, slice_num, spoke_settings, background_settings, spokes)

**MRI note:** `has_sagittal_module: bool` is an instance attribute on `ACRMRILarge` (not in `results_data`). The 2026-08-29 T1-only dump still includes `sagittal_localizer_module` with empty `distances`/`profiles` dicts; flatten emits no sagittal leaves. Populate sagittal metrics only when a sagittal image is detected.

### §Live harvest — `metrics.*` extensions

| Key | Modality | Source | Reason dict incomplete |
|-----|----------|--------|------------------------|
| `low_contrast_cnr` | CT | live analyzer | background σ not in `results_data` (shipped F1) |
| `psg` | MRI | `uniformity_module` dict | dict-complete (`psg`, `ghosting_ratio`); no harvest needed |
| _snr_ | MRI | viewer harvest (Phase 6) | pylinac 3.43.2 has no SNR; see [ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md](../../info/ACR_PHANTOM_QA_METRICS_AND_PYLINAC_GAPS.md) |

**R0-3 gap summary (from source):** CT needs live harvest only for `low_contrast_cnr` (background σ absent). CT SNR/PSG/slice-thickness confirmed absent — omit. MRI PSG, MTF grid, PIU, geometric distortion, slice thickness, low-contrast score are all dict-complete. MRI SNR is the sole planned viewer-computed harvest (Phase 6).

### §Figure names — `plot_images()` keys (R0-10)

From pylinac 3.43.2 `acr.py` source:

**ACR CT** (`ACRCT.plot_images`, line 462): `hu`, `uniformity`, `spatial resolution`, `low contrast`, `mtf`, `side`

**ACR MRI Large** (`ACRMRILarge.plot_images`, line 1967): `geometric`, `slice 1`, `signal uniformity`, `slice 11`, plus per-slice LC keys from `low_contrast_multi_slice.slices` (`slice_8`, `slice_9`, `slice_10`, `slice_11`), optional `sagittal` (only when `has_sagittal_module`), `rMTF`, `side`

---

## Verification gates

- **G0:** Phase 0 appendix complete on committed dumps; **OQ-1–OQ-10** locked. **Met 2026-08-29** (P0-GATE).
- **G1:** Reviewer approves metric key naming convention before GUI wiring. **Met 2026-08-29** with P0-GATE (dotted `raw_pylinac` paths in the appendix).
- **G2:** Fixture tests prove CT + MRI flatten includes ≥1 value from each **present** target family using committed `results_data` dumps (not live `analyze()`). **Met 2026-08-29** in `tests/qa/test_pylinac_results_data_spike.py`.
- **G3:** Manual smoke on one local CT + one local MRI phantom (optional): single-run export, CT batch CSV, MRI batch export; **optional G3b:** XLSX Images module set matches PDF figure count when embed on. **Transferred 2026-08-30** to [`TO_DO.md` Manual Smoke Checks](../../TO_DO.md#manual-smoke-checks) after merge.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| `raw_pylinac` shape changes on pylinac bump | Pin + regression tests; treat as opaque in JSON, stable flatten keys in tests |
| Wide CSV too many columns | Document column order; Summary sheet highlights key metrics; MTF grid Detail-only |
| Live-analyzer extraction fragile | Guard all attribute access; partial dict on failure (CT CNR pattern) |
| MRI batch vs compare mode confusion | Distinct menu labels; `ACRMBatchResult` not `MRIBatchResult`; plan text + user-docs |
| No synthetic ACR image fixtures | Phase 0 commits redacted `results_data` JSON dumps; CI uses dumps only; **maintainer produces dumps** when gitignored phantoms available — coding not blocked |
| Duplicate keys in `metrics` + `raw_pylinac` | Explicit merge rule in P1-F1 (metrics wins for curated scalars) |
| MRI XLSX Images sheet empty | **OQ-9 locked:** `save_images()` + temp-dir owner for CT/MRI single + batch; toggle off skips sheet |
| Large XLSX files (many embedded PNGs) | Default on but user can disable; batch runs × ~6–12 images; document size in user guide |
| Formula injection not wired today | R0-8 + Phase 1 wire `neutralize_spreadsheet_value` |

---

## File map (expected touch)

| File | Change |
|------|--------|
| `src/qa/qa_result_flatten.py` | **New** — canonical flatten (**locked**; dedicated module) |
| `src/qa/qa_export.py` | CSV builders use flatten; wire `neutralize_spreadsheet_value` |
| `src/qa/qa_xlsx_export.py` | Summary + Detail + multi-module Images sheet |
| `src/qa/pylinac_acr_ct.py` / `pylinac_acr_mri.py` | Optional extra `metrics.*` harvest; `save_images()` when `embed_module_images_in_xlsx`; **Phase 6:** `extract_mri_snr_acr_style` in `pylinac_mri_snr.py` (runner overlays) |
| `src/qa/worker.py` | `QAMRIBatchWorker`; module image temp dirs per series |
| `src/qa/analysis_types.py` | **`ACRMBatchResult` (new)**; `QARequest`/`QAResult` module image fields |
| `src/utils/config/qa_pylinac_config.py` | **`acr_qa_embed_module_images_in_xlsx`** (default True) |
| `src/gui/dialogs/acr_ct_qa_dialog.py` / `acr_mri_qa_dialog.py` | Embed checkbox |
| `src/gui/qa_app_facade.py` | MRI batch flow + batch CSV exports |
| `src/gui/dialogs/acr_mri_series_selection_dialog.py` | **New** |
| `src/gui/dialogs/mri_batch_result_dialog.py` | **New** |
| `src/gui/dialogs/ct_batch_result_dialog.py` | CSV button |
| `tests/qa/test_qa_result_flatten.py` | **New** |
| `scripts/spike_pylinac_acrct.py` / `scripts/spike_pylinac_acrmri.py` | **`--dump-json`** Phase 0 dumps |
| `scripts/pylinac_spike_common.py` | Shared redaction + `results_data(as_dict=True)` writer |
| `tests/fixtures/qa/acr_ct_results_data.json` | **New** — redacted Phase 0 dump (maintainer) |
| `tests/fixtures/qa/acr_mri_results_data.json` | **New** — redacted Phase 0 dump (maintainer) |
| `tests/test_qa_pylinac_*` | Extend export assertions |

---

## Review notes (2026-08-28)

**Verdict (Hy3):** Needs revision → **addressed in this revision**; approve implementation after Phase 0 proves appendix on real dumps.

| Reviewer | Outcome |
|----------|---------|
| **OpenCode Hy3 Free** | Full structured review — incorporated above (OQ decisions, `ACRMBatchResult`, committed dumps, merge rule, MRI Images R0-10, formula wiring) |
| **OpenCode GLM 5.3 Flash** | Grounding review — incorporated (pylinac 3.43.2 catalog fixes, dialog/test paths, merge-rule clarity, privacy gates, XLSX formula-injection test) |
| **Kilo LongCat 2.0** | No assistant output (provider resolved to image model); not incorporated |

**Hy3 highlights retained in plan:**

- Source of truth is **`raw_pylinac`**, not `result.metrics`; live harvest only for dict gaps (F1 CNR).
- Do **not** overload **`MRIBatchResult`** (compare-mode) for multi-series batch.
- **No synthetic ACR fixtures** — commit redacted `results_data` JSON for CI golden tests.
- **CT SNR / CT PSG** expected absent; gate Summary columns on R0-3.
- **MTF 10–90% grid** Detail-only; Summary MTF@50% only.
- **`neutralize_spreadsheet_value`** exists but is not wired in QA export today — Phase 1 must wire it.
- Docs incrementally per phase, not only Phase 5 cliff.

**Maintainer decision (2026-08-28):** **OQ-9** — XLSX Images uses **`save_images()`** (PDF parity), **default on**, persisted toggle **`acr_qa_embed_module_images_in_xlsx`** on ACR CT/MRI options dialogs.

### Review notes — GLM 5.3 Flash (2026-08-28)

**Verdict:** Approve with edits incorporated — proceed to Phase 0 after appendix on redacted dumps.

**Changes made:**

- Corrected **ACR CT metric catalog** against pylinac 3.43.2 (`ACRCT` has no slice-thickness module; geometry is top-level `phantom_roll_deg` / `origin_slice`; HU via `ct_module`).
- Marked **CT SNR absent** in installed `acr.py`; **MRI SNR** planned as **Phase 6** viewer harvest (see investigation doc); MRI **PSG dict-present** via `uniformity_module`.
- Fixed existing CT batch dialog path → **`ct_batch_select_dialog.py`**; pointed MRI batch tests at **`tests/test_ct_batch_select_dialog.py`** / **`tests/test_qa_ct_batch_worker.py`**.
- Clarified **merge rule** (top-level curated keys, F1 `low_contrast_cnr` contract, no literal `metrics.` prefix).
- **R0-8/R0-9:** `SafeCsvWriter`, openpyxl `=` formula risk, staged PHI gate on fixture dumps.
- **P1-X1** Summary columns gated (no CT slice thickness / CT SNR unless Phase 0 finds fields); **`mri_snr`** when Phase 6 lands.
- **Success criterion 2** — pylinac-exposed metrics + **Phase 6 MRI SNR**; CT SNR absent; CT slice thickness absent on `ACRCT`.
- **Phase 0 dump hygiene** — numeric metrics only (no pixel data, no absolute paths); spike test rejects absolute paths; staged artifact gate required on the dump commit.
- **Temp-dir lifecycle** — module-image `TemporaryDirectory` held open until after `workbook.save()`, cleaned in `finally` (single-run and batch).
- **OQ-2 / OQ-5 precision** — compare-mode `MRIBatchResult` grounding (`run_configs: list[LcRunConfig]`, `run_acr_mri_large_batch`); curated `result.metrics` overlay stays top-level per the F1 contract.
- _Process note:_ this grounding review ran in a shared working tree alongside a parallel reviewer pass over the same revision; the combined edits were captured together in commit `cde3bdd` and this follow-up commit.

**Deferred / out of scope (confirmed):** batch PDF, CLI/DB, CatPhan/nuclear, compare-mode schema changes.

### Review notes — Kilo Hy3 Free (2026-08-28)

**Verdict:** Approve with edits — incorporated below.

| Reviewer | Outcome |
|----------|---------|
| **Kilo `tencent/hy3:free`** (plan mode) | Grounded against pylinac 3.43.2 `acr.py` + [PMC8321175](https://pmc.ncbi.nlm.nih.gov/articles/PMC8321175/) |

**Confirmed:** seven accreditation tests; SNR not an accreditation test; pylinac gap table (PIU, PSG, MTF, no SNR); PSG ghost ROI geometry; Phase 6 tasks/deps; OQ-10 default; cross-links.

**Edits incorporated:**

- Geometric accuracy limit → **±2 mm** (PMC Table 1)
- PIU row split: **ACR 87.5/82** vs pylinac **`piu_passed` 85/80**
- PSG formula aligned to pylinac **`|(L+R)−(T+B)|`**
- R6-3/R6-4: **freq-encode axis selection** + DICOM fallback (phase=ROW / freq=COL)
- R6-5 / OQ-10: **`mri_snr` uncorrected** labeling (not NEMA SNR)
- SNR limits, SNRU slice-6 pointer, freq-encode noise rationale in investigation doc

**SNR formula recommendation (reviewer + maintainer):** ship the uncorrected ACR-style **S̄ / σ_bkg** on the uniformity slice (~80% phantom diameter; freq-encode background σ) as default; no 0.655 in v1; two-image difference remains a different method and stays out of scope.

### Review notes — Cursor Grok 4.5 (2026-08-28)

**Verdict:** Approve with edits — incorporated below.

**Highlights:** Phase 0 soft gate (coding vs golden dumps); spike `--dump-json`; R0 checklist ID fix; lock `qa_result_flatten.py`; OQ-10 locked; SNR **80% phantom diameter** on the uniformity slice (not “flood”, not √0.80 area); Phase 2–5 task IDs renumbered (P2–P5).

### Review notes — Cursor Grok 4.6 (2026-08-28)

**Verdict:** Deferred-work roadmap accepted — MTF interpret UI first, then assisted visual scoring; demote ROI σ; fold calibration into interpret UI; gaps doc stays reference-only; cross-link **C2** / **C24**; deferred roadmap in gaps doc §Direct resolution reads.

### Review notes — P1-F1 implementation (2026-08-29)

**Verdict:** Approve with edits — incorporated in this commit.

| Reviewer | Outcome |
|----------|---------|
| **Kilo LongCat 2.0 (paid)** | Remapped to image model; no code |
| **Kilo LongCat 2.0 (free)** | Implemented flatten module + appendix from pylinac 3.43.2 source |
| **OpenCode Hy3 Free** | Needs revision → tabular `metric.` rename and unused denylist **fixed** |
| **OpenCode GLM 5.3 Flash** | Pass with nits → MRI `ROIResult` fixture shape, CT lp ROI key list, `roi_settings` mutated dump keys **fixed** |

---

## Out of scope (this plan)

- QA CLI runner and QC history database ([QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md) Phases 3–4)
- CatPhan, nuclear, X-ray QC phantoms
- Changing MRI compare-mode JSON schema or combined PDF
