# Plan: Pylinac ACR — full metrics export, batch CT CSV, and multi-series MRI batch

**Last updated:** 2026-08-28
**Status:** Active — planning slice (no product code yet); **external review incorporated** (OpenCode Hy3 Free — needs revision; Kilo LongCat 2.0 — no usable output; GLM 5.3 Flash — incorporated; see **Review notes**)
**Priority:** P1
**Branch suggestion:** `feature/pylinac-acr-full-metrics-export-mri-batch`
**Area:** Automated QA / pylinac (ACR CT + ACR MRI Large only)

**Related (completed):**

- [Pylinac CT CNR, batch, and XLSX](../completed/PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md) — F1 CNR intermediates, F2 CT multi-series batch, F3 XLSX (Summary/Detail/Images; CNR-centric Summary)
- [Pylinac MRI compare runs and PDF](../completed/PYLINAC_MRI_COMPARE_RUNS_AND_PDF_INTERPRETATION_PLAN.md) — same-series 1–3-run low-contrast compare
- [Pylinac Stage 1 spine](../completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md)

**Related (umbrella — defer CLI/DB to later):**

- [QA results export, CLI, and history](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md) — Phase 1–2 **ACR CT/MRI slice is implemented here first**; CLI (Phase 3) and QC history DB (Phase 4) stay in that plan

---

## Goal and success criteria

Physicists can export **everything pylinac exposes** for **ACR CT** and **ACR MRI Large** runs — single or batch — as **CSV and XLSX**, without digging through JSON. **Multi-series MRI batch** matches the existing CT batch UX.

**Definition of “full”:** flatten `result.raw_pylinac` (full `results_data(as_dict=True)` tree stored at analysis time) plus necessary **live-analyzer harvest** where dict output is incomplete (CT CNR / F1 precedent). Omit any family pylinac does not populate — do not fabricate SNR, PSG, or other columns.

Success means:

1. **Canonical metric rows** — one stable flattened row model per run (provenance + every pylinac-exposed scalar/list metric), shared by CSV, XLSX Detail, and future CLI/DB.
2. **Pylinac-exposed ACR coverage** — not only CNR intermediates; include uniformity, low-contrast detectability/score, relative MTF / spatial resolution, slice thickness, slice position / geometry, HU linearity / material ROIs, and modality-specific fields (e.g. MRI SNR/PSG) **when present** in `raw_pylinac` or live harvest; SNR on CT and PSG on CT are **expected absent** unless Phase 0 proves otherwise.
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

Runners: `src/qa/pylinac_acr_ct.py`, `src/qa/pylinac_acr_mri.py`. Export: `src/qa/qa_export.py`, `src/qa/qa_xlsx_export.py`. Facade: `src/gui/qa_app_facade.py`. CT batch UI: `src/gui/dialogs/ct_batch_result_dialog.py`, `ct_batch_select_dialog.py` (`prompt_batch_series_selection`).

**Target:** XLSX Images uses **`save_images()`** (PDF parity). Today’s composite-only CT path is replaced when the embed option is on (default). Toggle off → skip Images sheet (Summary note only), same graceful degradation as missing Pillow.

---

## Metric catalog (target extraction)

Extract when present; omit column/row when module failed or pylinac version omits field. Namespace keys as `module.metric` (e.g. `ct_module.rois.air`; exact dotted keys come from the Phase 0 appendix — do not invent names here).

### ACR CT (`ACRCT` / `run_acr_ct_analysis`)

| Family | Examples (non-exhaustive) | Primary source | Confidence |
|--------|---------------------------|----------------|------------|
| HU linearity / materials | Per-material HU, ROI distances/radii, measured vs expected | `raw_pylinac.ct_module` (rois per material) + live ROIs if needed | Verify R0-1 |
| Slice thickness | Measured thickness, ramp metrics | **No such module in pylinac 3.43.2 `ACRCT`** — result model has only `ct_module`, `uniformity_module`, `low_contrast_module`, `spatial_resolution_module` | **Absent (CT)** — omit unless R0-1 proves otherwise |
| Slice position / geometry | Phantom roll, origin slice, image count | top-level `phantom_roll_deg`, `origin_slice`, `num_images` (no separate geometry module on CT) | Verify R0-1 |
| Uniformity | Integral/differential uniformity, ROI stats | `uniformity_module` | Verify R0-1 |
| Low contrast | CNR, object/background means & σ (existing F1) | `metrics.low_contrast_cnr` + `low_contrast_module` | Shipped F1 + R0-1 |
| Spatial resolution / MTF | MTF at rMTF %, lp/mm, relative resolution grid | `spatial_resolution_module` | Verify R0-1 |
| SNR | Module SNR if exposed | — | **Absent (CT)** — no SNR field in pylinac 3.43.2 `acr.py` results |
| PSG (percent signal ghosting) | Ghosting ratio | N/A for CT phantom | **Expected absent (CT)** |

### ACR MRI Large (`ACRMRILarge` / `run_acr_mri_large_analysis`)

| Family | Examples | Primary source | Confidence |
|--------|----------|----------------|------------|
| Geometric / slice | Slice thickness/position, phantom roll | `raw_pylinac` `slice1` / `slice11` / `geometric_distortion_module` | Verify R0-2 |
| Uniformity | PIU, uniformity ROI stats | `uniformity_module` (incl. `piu`) | Verify R0-2 |
| SNR | SNR per pylinac module | — | **Absent (both modalities)** — verified no `snr` field in installed pylinac 3.43.2 `acr.py`; re-confirm on dumps in R0-2; do not fabricate SNR columns |
| PSG | Percent signal ghosting | `uniformity_module.psg` / `ghosting_ratio` (dict-present in 3.43.2) | Verify R0-2 |
| Low contrast | Score, detectability, per-slice LC metrics | `low_contrast_multi_slice_module`, existing `_extract_lc_score` | Verify R0-2 |
| MTF | Row/column rMTF % → lp/mm grid (10–90% step) | `slice1.row_mtf` / `col_mtf` outputs (`lpmm_to_rmtf`-style grids) | Verify R0-2; Summary MTF@50% only |
| Other | `has_sagittal_module`, echo-specific fields | already partially in `metrics` | Verify R0-2 |

**Discovery step (Phase 0):** run `results_data(as_dict=True)` once per modality on a **local (gitignored) phantom folder** via `scripts/spike_pylinac_acrct.py` (or MRI equivalent); **commit redacted dumps** as `tests/fixtures/qa/acr_ct_results_data.json` and `tests/fixtures/qa/acr_mri_results_data.json` (numeric metrics only — no pixel data, no filesystem paths; strip/redact any absolute paths before committing, e.g. `phantom_model`/UID-like strings stay, paths go). The dump commit must pass the staged artifact gate (`scripts/check_no_phi_artifacts.py` / privacy hooks) — never `--no-verify`. Document exact key paths in this plan’s **Metric registry appendix**. CI golden tests consume the committed dumps — **no `analyze()` in CI** (no synthetic ACR image fixtures exist today). Where dict lacks background σ (CT CNR precedent), add guarded live-analyzer harvest in the runner and stash under `result.metrics` (see merge rule in the architecture sketch — top-level keys, not a literal `metrics.` prefix).

---

## Research first (Phase 0 — blocking implementation)

Do **not** start Phase 1 until Phase 0 deliverables are checked in (appendix + resolved open questions marked decided).

| ID | Research task | Method | Deliverable |
|----|---------------|--------|-------------|
| **R0-1** | Dump full `ACRCT.results_data(as_dict=True)` tree | Local phantom folder via `scripts/spike_pylinac_acrct.py`; redact paths; commit `tests/fixtures/qa/acr_ct_results_data.json` | **Metric registry appendix §CT** — dotted key paths |
| **R0-2** | Dump full `ACRMRILarge.results_data(as_dict=True)` tree | Same pattern as R0-1; commit `tests/fixtures/qa/acr_mri_results_data.json` | **Metric registry appendix §MRI** |
| **R0-3** | Live-analyzer gap analysis | Compare appendix keys vs user-requested families (PSG, SNR, MTF grid, HU per material); introspect `analyzer.*_module` when dict incomplete | **Gap table**: dict-only vs needs `metrics.*` harvest |
| **R0-4** | PSG on ACR CT | Read pylinac 3.43.2 `acr.py` / `ACRCTResult`; confirm whether PSG exists for CT or is MRI-only | Confirm **OQ-1** (pre-decided absent unless found) |
| **R0-5** | MTF column strategy | Document which rMTF % values pylinac emits (MRI 10–90 step grid per `PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md`); Summary MTF@50% row/col only; full grid Detail-only | Answer **OQ-4** |
| **R0-6** | Batch type naming | Introduce `ACRMBatchResult` mirroring `CTBatchResult`; do **not** overload compare-mode `MRIBatchResult` | Answer **OQ-2** |
| **R0-7** | Wide CSV column order | Prototype header list from R0-1/R0-2; stable sort: provenance block → module families → `raw_pylinac` overflow | Answer **OQ-3** |
| **R0-8** | Formula-injection policy | Wire `neutralize_spreadsheet_value` from `src/core/spreadsheet_safety.py` into QA CSV/XLSX builders (not wired today; `qa_export.py` uses bare `csv.writer` — reuse the module's `SafeCsvWriter` wrapper). XLSX matters too: openpyxl treats leading-`=` strings as formulas on open, and Series/Run labels + warnings are DICOM-derived strings | Implementation note in Phase 1 + Phase 2 XLSX test |
| **R0-9** | Committed golden dumps | Assert redacted JSON fixtures have no PHI paths (test also rejects absolute filesystem paths); run staged artifact gate on the dump commit; key-name smoke test loads dumps without `analyze()` | Enables CI flatten tests |
| **R0-10** | XLSX module images (PDF parity) | Confirm `publish_pdf` uses `save_images(to_stream=True)`; document per-modality figure names from `plot_images()` (CT: hu, uniformity, spatial resolution, low contrast, mtf, side; MRI: geometric, slices, LC slices, rMTF, side, …) | **Locked** — see **OQ-9**; implement `save_images(directory=…)` when embed on |

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
| **OQ-3** | **Wide batch CSV**: fixed column order vs sparse (only populated metrics)? | Fixed order + empty cells for Excel ergonomics | **Fixed column order** (provenance → families → overflow) |
| **OQ-4** | **Summary sheet**: which metrics are mandatory columns vs Detail-only? | Gate each column on R0-3 presence; add modality discriminator; MTF@50% row+col only in Summary (not 10–90% grid) | **Hybrid allowlist** — see R0-5 |
| **OQ-5** | Flatten **`raw_pylinac`** nested dicts/lists into dotted keys for **all** leaves, or curated allowlist per modality? | | **Hybrid**: curated Summary + full `raw_pylinac` walk in Detail; overlay the curated `result.metrics` entries on top (see merge rule) |
| **OQ-6** | MRI batch **PDF**: optional per-series path like single-run, or batch JSON/XLSX only (match CT batch)? | CT batch has no batch PDF | **No batch PDF** for MRI |
| **OQ-7** | MRI batch **echo_number** / compare options: one shared dialog (like CT options) — include compare toggle? | Compare stays on single-run menu; batch bypasses `compare_request` | _Locked: no compare in batch_ |
| **OQ-8** | Add `metrics_flat` to JSON export or keep flatten export-layer-only? | `raw_pylinac` already carries data | **Export-layer-only** — no JSON schema churn |
| **OQ-9** | Embed **PDF-parity module images** in XLSX Images sheet? | `save_images()` vs composite; workbook size | **Yes, default on** — persisted `acr_qa_embed_module_images_in_xlsx`; user can disable in ACR CT/MRI options (single + batch) |

## Tests to add (required before merge)

All new tests under `tests/qa/` unless noted. Use **committed redacted `results_data` dumps** (`tests/fixtures/qa/`) for golden flatten tests; no PHI paths; no live `analyze()` in CI.

### Phase 0 / research

- [ ] **`tests/qa/test_pylinac_results_data_spike.py`** — load committed `acr_*_results_data.json`; assert dict shape; optional snapshot of key names (not values) for regression; assert no absolute filesystem paths in the dumps (cheap PHI redaction regression per R0-9).

### Phase 1 — flattening

- [ ] **`tests/qa/test_qa_result_flatten.py`**
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

- [ ] **`tests/gui/test_ct_batch_result_dialog.py`** (or facade test) — Export CSV invokes `build_batch_metrics_csv` with batch labels (mock facade).

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
| **`dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`** | Document canonical flatten keys, batch MRI flow, export surfaces (CSV wide vs metric/value), JSON vs export-layer flatten, **module image embed toggle** |
| **`dev-docs/info/PYLINAC_CUSTOMIZATION_AND_EXTENSIONS.md`** | MTF grid / metric extraction notes if live harvest added |
| **`dev-docs/info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md`** | Cross-link metric families now exported |
| **`dev-docs/plans/supporting/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md`** | Metric registry appendix (Phase 0 output); mark open questions decided |
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

```
run_acr_ct_analysis / run_acr_mri_large_analysis
  (when embed_module_images_in_xlsx: analyzer.save_images(dir) → analyzed_module_images)
        │
        ▼
   QAResult (metrics + raw_pylinac + provenance + analyzed_module_images)
        │
        ▼
qa_result_flatten.py  (NEW — Qt-free; or extend qa_export.flatten_metrics if module count is a concern)
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
- **XLSX module images:** PDF parity via `save_images()`; **default on**, persisted **`acr_qa_embed_module_images_in_xlsx`**; user can disable per run from options dialogs.
- **Do not break** existing JSON schemas; flattened export is additive or export-layer only.
- **Formula injection:** wire `neutralize_spreadsheet_value` (`src/core/spreadsheet_safety.py`) into QA CSV/XLSX builders.
- **Nuclear / CatPhan:** out of scope for this plan (separate serializers already exist for nuclear CSV).

---

## Phases

### Phase 0 — Research and metric registry (blocking)

- [ ] **(R0-1)** CT `results_data(as_dict=True)` key dump → appendix §CT + committed `tests/fixtures/qa/acr_ct_results_data.json`. (owner: coder)
- [ ] **(R0-2)** MRI `results_data(as_dict=True)` key dump → appendix §MRI + committed `tests/fixtures/qa/acr_mri_results_data.json`. (owner: coder)
- [ ] **(R0-3)** Live-analyzer gap table (dict vs harvest). (owner: coder, after: R0-1, R0-2)
- [ ] **(R0-4)** Confirm **OQ-1** (CT PSG absent unless found). (owner: coder)
- [ ] **(R0-5)** Resolve **OQ-4**, **OQ-5** (Summary vs Detail flatten strategy). (owner: coder + reviewer)
- [ ] **(R0-6)** Lock **OQ-2** (`ACRMBatchResult`), **OQ-3** (wide CSV order). (owner: coder)
- [ ] **(R0-7)** Add `tests/qa/test_pylinac_results_data_spike.py` (loads committed dumps). (owner: tester, after: R0-9)
- [ ] **(R0-8)** Document formula-injection wiring for Phase 1. (owner: coder)
- [ ] **(R0-9)** Commit redacted dumps; assert no PHI paths. (owner: coder, after: R0-1, R0-2)
- [ ] **(R0-10)** Document module figure names per modality (R0-10 table); lock **OQ-9**. (owner: coder)
- [ ] **(P0-GATE)** Reviewer signs off appendix + open-question decisions before Phase 1. (owner: reviewer)

### Phase 1 — Canonical flattening (`qa_result_flatten.py`)

- [ ] **(P1-F1)** Add `qa_result_flatten.py` (or extend `qa_export`) with provenance + flatten: walk `raw_pylinac`, overlay `metrics.*` (metrics wins for curated provenance scalars), add CNR/LC live fields. (owner: coder)
- [ ] **(P1-F2)** Refactor `build_metrics_csv` to emit full flatten; keep two-column `metric,value` for single-run. (owner: coder, after: P1-F1)
- [ ] **(P1-F3)** Add `build_batch_metrics_csv(results, labels)` — one header row, one row per run (wide). (owner: coder, after: P1-F1)
- [ ] **(P1-F4)** Tests: golden key sets from **committed dumps** for CT and MRI; failed run; warnings present. (owner: tester, after: R0-9, P1-F1)

### Phase 2 — XLSX upgrade

- [ ] **(P1-I1)** `QARequest` / `QAResult`: `embed_module_images_in_xlsx`, `module_images_out_dir`, `analyzed_module_images`; runners call `save_images()` when enabled. (owner: coder)
- [ ] **(P1-I2)** Config + dialogs: `acr_qa_embed_module_images_in_xlsx` (default **True**); checkbox on ACR CT/MRI options + batch options; profile/JSON `inputs` audit field. (owner: coder)
- [ ] **(P1-I3)** Facade/worker temp-dir lifecycle for module image dirs (CT single, CT batch, MRI single, MRI batch). (owner: coder, after: P1-I1)
- [ ] **(P1-X1)** Extend `build_qa_workbook` Summary sheet with modality-aware key columns (CNR, uniformity, PSG/LC score where present, MTF@50% row+col, slice thickness/position on MRI only — best-effort; omit SNR and CT slice-thickness columns unless Phase 0 finds fields). (owner: coder, after: P1-F1)
- [ ] **(P1-X2)** Detail sheet uses full flatten (replaces metrics-only flatten). (owner: coder, after: P1-F1)
- [ ] **(P1-X3)** Images sheet: multi-module embed from `analyzed_module_images`; graceful skip when toggle off / no Pillow. (owner: coder, after: P1-I1, P1-X2)
- [ ] **(P1-X4)** Tests: Images sheet module count + toggle off skips sheet; paths not in JSON/CSV. (owner: tester, after: P1-X3)

### Phase 3 — Batch CT CSV + export parity

- [ ] **(P1-C1)** Add **Export CSV…** to `ct_batch_result_dialog` → `export_ct_batch_csv` in facade. (owner: coder, after: P1-F3)
- [ ] **(P1-C2)** Verify single-run CT/MRI save dialog CSV/XLSX pick up full flatten without UI change. (owner: tester, after: P1-F2, P1-X2)

### Phase 4 — Multi-series MRI batch

- [ ] **(P1-M1)** Add `QAMRIBatchWorker` (serial `run_acr_mri_large_analysis` per series); `ACRMBatchResult`. (owner: coder)
- [ ] **(P1-M2)** `acr_mri_series_selection_dialog` — loaded MR series + Add folder; shared options from existing MRI dialog. (owner: coder)
- [ ] **(P1-M3)** Menu: **ACR MRI Batch (pylinac)…**; progress N-of-M; cancel semantics match CT. (owner: coder, after: P1-M1, P1-M2)
- [ ] **(P1-M4)** `mri_batch_result_dialog` — table per series; Export CSV / JSON / XLSX; module Images per **OQ-9**. (owner: coder, after: P1-M3, P1-F3, P1-X3)
- [ ] **(P1-M5)** Tests: worker isolation, label parity, export hooks (mock runner); mirror patterns in `tests/test_qa_ct_batch_worker.py`. (owner: tester, after: P1-M4)

### Phase 5 — Docs and closure

- [ ] **(P1-D1)** User-docs: `USER_GUIDE_QA_PYLINAC.md` — update incrementally as CT CSV (Phase 3) and MRI batch (Phase 4) land; hub `USER_GUIDE.md` if needed. (owner: docs, after: P1-C2, P1-M4)
- [ ] **(P1-D2)** Dev-docs: `PYLINAC_INTEGRATION_OVERVIEW.md`, appendix in this plan, `MAINTENANCE_LOG.md`. (owner: docs, after: P1-D1)
- [ ] **(P1-D3)** In-app strings: menu, dialogs, tooltips, save-dialog titles (see **Documentation updates**). (owner: coder, with P1-M3, P1-C1)
- [ ] **(P1-D4)** `CHANGELOG.md` **minor** when shipped. (owner: orchestrator)
- [ ] **(P1-D5)** `check_user_docs_links.py` + move plan to `completed/`; trim `TO_DO.md`. (owner: orchestrator)

---

## Metric registry appendix

_Fill during Phase 0 (R0-1, R0-2). Do not guess keys — paste from fixture runs._

### §CT — `ACRCT` keys

_(pending Phase 0)_

### §MRI — `ACRMRILarge` keys

_(pending Phase 0)_

### §Live harvest — `metrics.*` extensions

| Key | Modality | Source | Reason dict incomplete |
|-----|----------|--------|------------------------|
| `low_contrast_cnr` | CT | live analyzer | background σ not in `results_data` (shipped F1) |
| `psg` | MRI | `uniformity_module` dict | expected dict-complete (`psg`, `ghosting_ratio`); harvest only if dump proves gap |
| _snr_ | _both_ | — | **No live harvest planned** — absent in pylinac 3.43.2 `acr.py`; omit unless R0-2/R0-3 find a field |
| _…_ | | | |

---

## Verification gates

- **G0:** Phase 0 appendix complete; **OQ-1–OQ-9** decided.
- **G1:** Reviewer approves metric key naming convention before GUI wiring.
- **G2:** Fixture tests prove CT + MRI flatten includes ≥1 value from each **present** target family using committed `results_data` dumps (not live `analyze()`).
- **G3:** Manual smoke on one local CT + one local MRI phantom (optional): single-run export, CT batch CSV, MRI batch export; **optional G3b:** XLSX Images module set matches PDF figure count when embed on.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| `raw_pylinac` shape changes on pylinac bump | Pin + regression tests; treat as opaque in JSON, stable flatten keys in tests |
| Wide CSV too many columns | Document column order; Summary sheet highlights key metrics; MTF grid Detail-only |
| Live-analyzer extraction fragile | Guard all attribute access; partial dict on failure (CT CNR pattern) |
| MRI batch vs compare mode confusion | Distinct menu labels; `ACRMBatchResult` not `MRIBatchResult`; plan text + user-docs |
| No synthetic ACR image fixtures | Phase 0 commits redacted `results_data` JSON dumps; CI uses dumps only |
| Duplicate keys in `metrics` + `raw_pylinac` | Explicit merge rule in P1-F1 (metrics wins for curated scalars) |
| MRI XLSX Images sheet empty | **OQ-9 locked:** `save_images()` + temp-dir owner for CT/MRI single + batch; toggle off skips sheet |
| Large XLSX files (many embedded PNGs) | Default on but user can disable; batch runs × ~6–12 images; document size in user guide |
| Formula injection not wired today | R0-8 + Phase 1 wire `neutralize_spreadsheet_value` |

---

## File map (expected touch)

| File | Change |
|------|--------|
| `src/qa/qa_result_flatten.py` | **New** — canonical flatten (or extend `qa_export.flatten_metrics`) |
| `src/qa/qa_export.py` | CSV builders use flatten; wire `neutralize_spreadsheet_value` |
| `src/qa/qa_xlsx_export.py` | Summary + Detail + multi-module Images sheet |
| `src/qa/pylinac_acr_ct.py` / `pylinac_acr_mri.py` | Optional extra `metrics.*` harvest; `save_images()` when `embed_module_images_in_xlsx` |
| `src/qa/worker.py` | `QAMRIBatchWorker`; module image temp dirs per series |
| `src/qa/analysis_types.py` | **`ACRMBatchResult` (new)**; `QARequest`/`QAResult` module image fields |
| `src/utils/config/qa_pylinac_config.py` | **`acr_qa_embed_module_images_in_xlsx`** (default True) |
| `src/gui/dialogs/acr_ct_qa_dialog.py` / `acr_mri_qa_dialog.py` | Embed checkbox |
| `src/gui/qa_app_facade.py` | MRI batch flow + batch CSV exports |
| `src/gui/dialogs/acr_mri_series_selection_dialog.py` | **New** |
| `src/gui/dialogs/mri_batch_result_dialog.py` | **New** |
| `src/gui/dialogs/ct_batch_result_dialog.py` | CSV button |
| `tests/qa/test_qa_result_flatten.py` | **New** |
| `tests/fixtures/qa/acr_ct_results_data.json` | **New** — redacted Phase 0 dump |
| `tests/fixtures/qa/acr_mri_results_data.json` | **New** — redacted Phase 0 dump |
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
- Marked **SNR absent** for both modalities in installed `acr.py`; MRI **PSG dict-present** via `uniformity_module`.
- Fixed existing CT batch dialog path → **`ct_batch_select_dialog.py`**; pointed MRI batch tests at **`tests/test_ct_batch_select_dialog.py`** / **`tests/test_qa_ct_batch_worker.py`**.
- Clarified **merge rule** (top-level curated keys, F1 `low_contrast_cnr` contract, no literal `metrics.` prefix).
- **R0-8/R0-9:** `SafeCsvWriter`, openpyxl `=` formula risk, staged PHI gate on fixture dumps.
- **P1-X1** Summary columns gated (no CT slice thickness / SNR unless Phase 0 finds fields).

**Deferred / out of scope (confirmed):** batch PDF, CLI/DB, CatPhan/nuclear, compare-mode schema changes.

---

## Out of scope (this plan)

- QA CLI runner and QC history database ([QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md) Phases 3–4)
- CatPhan, nuclear, X-ray QC phantoms
- Changing MRI compare-mode JSON schema or combined PDF
