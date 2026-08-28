# Plan: Pylinac ACR — full metrics export, batch CT CSV, and multi-series MRI batch

**Last updated:** 2026-08-28
**Status:** Active — planning slice (no product code yet)
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

Physicists can export **all useful numerical pylinac outputs** for **ACR CT** and **ACR MRI Large** runs — single or batch — as **CSV and XLSX**, without digging through JSON. **Multi-series MRI batch** matches the existing CT batch UX.

Success means:

1. **Canonical metric rows** — one stable flattened row model per run (provenance + every extractable scalar/list metric), shared by CSV, XLSX Detail, and future CLI/DB.
2. **Full ACR metric coverage** — not only CNR intermediates; include uniformity, SNR, percent-signal ghosting (PSG), low-contrast detectability/score, relative MTF / spatial resolution, slice thickness, slice position / geometry, HU linearity / material ROIs, and any other values pylinac exposes for ACR CT/MRI (via `results_data(as_dict=True)` plus live-analyzer extraction where dict output is incomplete — same pattern as CT CNR).
3. **Batch CT** — **Export CSV…** on the batch summary dialog (today: XLSX + JSON only).
4. **Batch MRI** — **Tools → Automated QA → ACR MRI Batch (pylinac)…** — checkbox series list + **Add folder…**, shared MRI options, serial N-of-M progress, cooperative cancel, per-series error isolation; result dialog with **Export CSV / JSON / XLSX**.
5. **Single-run parity** — ACR CT and MRI save dialogs export the **same full metric set** in CSV/XLSX (JSON unchanged except additive `metrics_flat` or documented flatten in export only).
6. **MRI compare mode unchanged** — same-series 1–3-run low-contrast compare stays separate (`schema_version` 1.2); this plan does not replace compare JSON/PDF.

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

Runners: `src/qa/pylinac_acr_ct.py`, `src/qa/pylinac_acr_mri.py`. Export: `src/qa/qa_export.py`, `src/qa/qa_xlsx_export.py`. Facade: `src/gui/qa_app_facade.py`. CT batch UI: `src/gui/dialogs/ct_batch_result_dialog.py`, `acr_ct_series_selection_dialog.py`.

---

## Metric catalog (target extraction)

Extract when present; omit column/row when module failed or pylinac version omits field. Namespace keys as `module.metric` (e.g. `hu_linearity.air_hu`, `spatial_resolution.mtf_50_pct_lp_mm`).

### ACR CT (`ACRCT` / `run_acr_ct_analysis`)

| Family | Examples (non-exhaustive) | Primary source |
|--------|---------------------------|----------------|
| HU linearity / materials | Per-material HU, scaling, measured vs expected | `raw_pylinac` HU module + live ROIs if needed |
| Slice thickness | Measured thickness, ramp metrics | `slice_thickness_module` |
| Slice position / geometry | Phantom roll, offsets, measured distances | top-level + geometry modules |
| Uniformity | Integral/differential uniformity, ROI stats | `uniformity_module` |
| Low contrast | CNR, object/background means & σ (existing F1) | `metrics.low_contrast_cnr` + `low_contrast_module` |
| Spatial resolution / MTF | MTF at rMTF %, lp/mm, relative resolution grid | `spatial_resolution_module` |
| SNR | Module SNR if exposed | uniformity / pylinac SNR helpers |
| PSG (percent signal ghosting) | Ghosting ratio if in ACR CT result model | verify against pylinac 3.43.2 `ACRCTResult` |

### ACR MRI Large (`ACRMRILarge` / `run_acr_mri_large_analysis`)

| Family | Examples | Primary source |
|--------|----------|----------------|
| Geometric / slice | Slice thickness, slice position accuracy, phantom roll | `raw_pylinac` geometry modules |
| Uniformity | UFOV/CFOV-style uniformity metrics | uniformity module dict |
| SNR | SNR per pylinac module | `results_data` + docs |
| PSG | Percent signal ghosting | ghosting module if present |
| Low contrast | Score, detectability, per-slice LC metrics | `low_contrast_multi_slice_module`, existing `_extract_lc_score` |
| MTF | Row/column rMTF % → lp/mm grid (10–90% step) | `spatial_resolution_module` / pylinac MTF outputs |
| Other | `has_sagittal_module`, echo-specific fields | already partially in `metrics` |

**Discovery step (Phase 0):** run `results_data(as_dict=True)` against committed synthetic fixtures + one local phantom folder per modality; document exact key paths in this plan’s **Metric registry** appendix (add during implementation). Where dict lacks background σ (CT CNR precedent), add guarded live-analyzer harvest in the runner and stash under `metrics.*`.

---

## Architecture

```
run_acr_ct_analysis / run_acr_mri_large_analysis
        │
        ▼
   QAResult (metrics + raw_pylinac + provenance)
        │
        ▼
qa_result_flatten.py  (NEW — Qt-free)
  build_metric_rows(result) -> list[tuple[str, Any]]  # stable sort, dotted keys
  build_run_provenance(result, label?) -> dict       # study/series, versions, status
  build_tabular_run(result, label?) -> dict           # one wide row for batch CSV
        │
        ├── qa_export.build_metrics_csv (refactor to use flatten)
        ├── qa_export.build_batch_metrics_csv (NEW)
        ├── qa_xlsx_export.build_qa_workbook (Summary from key columns + full Detail)
        └── (future) QA_RESULTS_EXPORT CLI / DB

QAMRIBatchWorker (NEW) — mirror QACTBatchWorker serial semantics
MRIBatchResult / reuse CTBatchResult pattern with analysis_type discriminator
mri_batch_result_dialog.py (NEW) — mirror ct_batch_result_dialog
acr_mri_series_selection_dialog.py (NEW) — mirror CT selection; MR series filter
```

**Locked decisions**

- **Serial batch execution** for MRI (same rationale as CT batch in `worker.py`).
- **One wide CSV row per run** for batch export; multi-run workbook = one Summary sheet + Detail + Images.
- **Do not break** existing JSON schemas; flattened export is additive or export-layer only.
- **Formula injection:** reuse ROI/tag export neutralization for string cells in CSV/XLSX.
- **Nuclear / CatPhan:** out of scope for this plan (separate serializers already exist for nuclear CSV).

---

## Phases

### Phase 0 — Metric registry spike

- [ ] **(P0-SPIKE)** Document `results_data(as_dict=True)` key paths for ACR CT and MRI on synthetic fixtures; list gaps requiring live-analyzer extraction. (owner: coder)
- [ ] **(P0-SPIKE)** Confirm PSG / SNR / MTF field names against installed pylinac pin (`requirements.txt`). (owner: coder)

### Phase 1 — Canonical flattening (`qa_result_flatten.py`)

- [ ] **(P1-F1)** Add `qa_result_flatten.py` with provenance + full metric flatten (raw_pylinac walk + `metrics` overlay + CNR/LC live fields). (owner: coder)
- [ ] **(P1-F2)** Refactor `build_metrics_csv` to emit full flatten; keep two-column `metric,value` for single-run. (owner: coder, after: P1-F1)
- [ ] **(P1-F3)** Add `build_batch_metrics_csv(results, labels)` — one header row, one row per run (wide). (owner: coder, after: P1-F1)
- [ ] **(P1-F4)** Tests: golden key sets from fixtures for CT and MRI; failed run; warnings present. (owner: tester, after: P1-F1)

### Phase 2 — XLSX upgrade

- [ ] **(P1-X1)** Extend `build_qa_workbook` Summary sheet with modality-aware key columns (CNR + uniformity + SNR + PSG + LC score + MTF@50% + slice thickness — best-effort). (owner: coder, after: P1-F1)
- [ ] **(P1-X2)** Detail sheet uses full flatten (replaces metrics-only flatten). (owner: coder, after: P1-F1)
- [ ] **(P1-X3)** Tests: workbook sheet rows match flatten output. (owner: tester, after: P1-X2)

### Phase 3 — Batch CT CSV + export parity

- [ ] **(P1-C1)** Add **Export CSV…** to `ct_batch_result_dialog` → `export_ct_batch_csv` in facade. (owner: coder, after: P1-F3)
- [ ] **(P1-C2)** Verify single-run CT/MRI save dialog CSV/XLSX pick up full flatten without UI change. (owner: tester, after: P1-F2, P1-X2)

### Phase 4 — Multi-series MRI batch

- [ ] **(P1-M1)** Add `QAMRIBatchWorker` (serial `run_acr_mri_large_analysis` per series). (owner: coder)
- [ ] **(P1-M2)** `acr_mri_series_selection_dialog` — loaded MR series + Add folder; shared options from existing MRI dialog. (owner: coder)
- [ ] **(P1-M3)** Menu: **ACR MRI Batch (pylinac)…**; progress N-of-M; cancel semantics match CT. (owner: coder, after: P1-M1, P1-M2)
- [ ] **(P1-M4)** `mri_batch_result_dialog` — table per series; Export CSV / JSON / XLSX. (owner: coder, after: P1-M3, P1-F3, P1-X2)
- [ ] **(P1-M5)** Tests: worker isolation, label parity, export hooks (mock runner). (owner: tester, after: P1-M4)

### Phase 5 — Docs and closure

- [ ] **(P1-D1)** Update `user-docs/USER_GUIDE_QA_PYLINAC.md` and `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`. (owner: docs, after: P1-C2, P1-M4)
- [ ] **(P1-D2)** `CHANGELOG.md` **minor** when shipped (new MRI batch menu + export enrichment). (owner: orchestrator)
- [ ] **(P1-D3)** Move this plan to `completed/` when all P1 phases done; trim duplicate bullets from `TO_DO.md`. (owner: orchestrator)

---

## Verification gates

- **G1:** Reviewer approves metric key naming convention before GUI wiring.
- **G2:** Fixture tests prove CT + MRI flatten includes ≥1 value from each target family when analysis succeeds on synthetic data.
- **G3:** Manual smoke on one local CT + one local MRI phantom (optional; can use Manual Smoke Checks list): single-run export, CT batch CSV, MRI batch export.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| `raw_pylinac` shape changes on pylinac bump | Pin + regression tests; treat as opaque in JSON, stable flatten keys in tests |
| Wide CSV too many columns | Document column order; Summary sheet highlights key metrics |
| Live-analyzer extraction fragile | Guard all attribute access; partial dict on failure (CT CNR pattern) |
| MRI batch vs compare mode confusion | Distinct menu labels; plan text + user-docs |

---

## File map (expected touch)

| File | Change |
|------|--------|
| `src/qa/qa_result_flatten.py` | **New** — canonical flatten |
| `src/qa/qa_export.py` | CSV builders use flatten |
| `src/qa/qa_xlsx_export.py` | Summary + Detail |
| `src/qa/pylinac_acr_ct.py` / `pylinac_acr_mri.py` | Optional extra `metrics.*` harvest |
| `src/qa/worker.py` | `QAMRIBatchWorker` |
| `src/qa/analysis_types.py` | `MRIBatchResult` or reuse `CTBatchResult` name generic |
| `src/gui/qa_app_facade.py` | MRI batch flow + batch CSV exports |
| `src/gui/dialogs/acr_mri_series_selection_dialog.py` | **New** |
| `src/gui/dialogs/mri_batch_result_dialog.py` | **New** |
| `src/gui/dialogs/ct_batch_result_dialog.py` | CSV button |
| `tests/qa/test_qa_result_flatten.py` | **New** |
| `tests/test_qa_pylinac_*` | Extend export assertions |

---

## Out of scope (this plan)

- QA CLI runner and QC history database ([QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md](QA_RESULTS_EXPORT_CLI_AND_HISTORY_PLAN.md) Phases 3–4)
- CatPhan, nuclear, X-ray QC phantoms
- Changing MRI compare-mode JSON schema or combined PDF
