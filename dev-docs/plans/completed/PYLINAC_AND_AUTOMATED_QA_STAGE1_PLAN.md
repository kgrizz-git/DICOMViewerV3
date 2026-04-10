# Pylinac + Automated QA — Stage 1 Plan

**Scope:** First integration slice for [TO_DO: pylinac and automated QC](../TO_DO.md) — prove the **spine** (dependency, wrapper, UI hook, worker, results, export) with **minimal automation**, before mammography MAP, native CT primitives, auto phantom detection, or full multi-test pipelines.

**Related docs:** [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md) (architecture, phases), [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](../info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md) (gaps, MAP, Rose calibration — mostly **after** Stage 1), [FUTURE_WORK_DETAIL_NOTES.md](../FUTURE_WORK_DETAIL_NOTES.md) (Integrating Pylinac section). **Stage 1b+ robustness:** [PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md](PYLINAC_SCAN_EXTENT_TOLERANCE_AND_REPRODUCIBILITY_PLAN.md) (optional scan-extent tolerance, `pylinac_analysis_profile` / JSON).

---

## 1. How to start (recommended order)

1. **Do not touch the main viewer until a spike works off-app.** Validate pylinac + pinned versions against **one known-good ACR CT DICOM folder** (and optionally one ACR MRI Large folder) from a small script in `scripts/` — activate venv, `pip install pylinac scipy scikit-image`, run `ACRCT(...).analyze()` and capture `results_data()` / PDF. This de-risks dependency and API drift before Qt threading and paths enter the picture.

2. **Pick one phantom class for the first in-app path.** **ACR CT (`ACRCT`)** is the recommended default first target: contiguous axial stack, fewer MR-specific caveats (sagittal second UID, echo selection, 11-slice expectations). Add **ACR MRI (`ACRMRILarge`)** as the second Stage 1 milestone once CT is stable.

3. **Keep the UI deliberately manual (progressive automation).** User chooses: **phantom type = ACR CT** (fixed in Stage 1 menu or a simple combo), **data source = active series** (ordered file paths from the existing loader) **or** folder picker fallback, and **optional** origin-slice override only if auto-detection fails. No phantom auto-classification in Stage 1.

4. **Implement a thin boundary.** New package `src/qa/` (or equivalent): lazy import of pylinac, normalized **result dataclass** + **error types**, single entrypoint e.g. `run_acr_ct_analysis(paths: list[str | Path], ...) -> QAResult`. The GUI and `main.py` call only this layer — no pylinac imports in dialogs except through the runner.

5. **Run analysis off the GUI thread** with a progress state and cancellation; show a small results dialog (text summary + “open report” if PDF path returned) and **always offer JSON export** of normalized metrics + metadata (`pylinac.__version__`, app version, series UID, timestamp). Treat cancellation as **best-effort UI cancellation** in Stage 1 (cancel/close progress, ignore late result) unless hard interrupt becomes feasible.

6. **Defer for Stage 2+:** CatPhan, MAP mammography scoring, native CT water/noise primitives, Rose calibration UI, auto phantom detection, batch queues, overlay of pylinac ROIs on the live viewer, and configurable site-specific QA thresholds/pass-fail policy.

---

## 2. Stage 1 phases (checklist)

### Phase 0 — Dependency and API spike (no product UI)

- [ ] Create venv; install `pylinac`, `scipy`, `scikit-image`; note **exact versions** that work with project Python (see README Python guidance).
- [ ] Script: load ACR CT folder → `ACRCT` → `analyze()` → print or save `results_data()`; same smoke test for `ACRMRILarge` if sample data available.
- [x] Add `pylinac`, `scipy`, `scikit-image` to default install path (`requirements.txt`) with pinned/tested versions; document dependency rationale and version pinning in README/AGENTS.

### Phase 1a — `src/qa` runner + optional import

- [x] Add `src/qa/` with runner module(s), normalized `QAResult` / failure reasons, **graceful “pylinac not installed”** message for the UI.
- [ ] Unit-test the runner with **mocked** pylinac if feasible, or mark integration test optional when pylinac absent.

### Phase 1b — Minimal GUI integration

- [x] One menu action under **Tools** (or **Analyze**): e.g. “ACR CT phantom (pylinac)…” with dialog: confirm series / pick folder, **Run**, progress, results.
- [x] Add menu wiring in `_connect_dialog_signals()` (or equivalent signal-wiring submethod) to match project conventions.
- [x] Wire **active focused subwindow** series → ordered paths using existing APIs: focused subwindow context (`_get_subwindow_study_uid`, `_get_subwindow_series_uid`, `_get_subwindow_dataset`, `_get_subwindow_slice_index`) + file path resolution via `_file_series_coordinator.get_file_path_for_dataset(...)`; provide a small helper that returns `(study_uid, series_uid, ordered_file_paths)`.
- [x] Worker thread / `QThread` pattern; no blocking `analyze()` on GUI thread.

### Phase 1c — Preflight + export

- [x] Preflight: modality CT, non-empty path list, monotonic slice positions where tags exist — **warn** and allow continue.
- [x] Save **JSON** export (normalized fields + raw pylinac payload or subset); optional **PDF** via pylinac `publish_pdf` to user-chosen path.
- [x] Second menu path or sub-action: **ACR MRI (pylinac)** with documented options (`echo_number`, `check_uid` for sagittal — surface in advanced section of dialog).

### Stage 1 exit criteria

- [x] A physicist or developer can run **ACR CT** analysis on a real series from the viewer without crashes; JSON documents the run.
- [x] Optional MRI path works on **ACR Large** sample with default parameters.
- [x] Missing pylinac shows a clear install hint, not a traceback.
- [x] Changelog / version note if dependencies or user-visible behavior changes.

---

## 3. Minimal JSON schema sketch (Stage 1)

```json
{
  "schema_version": "1.0",
  "run": {
    "timestamp_utc": "2026-03-30T12:34:56Z",
    "app_version": "x.y.z",
    "pylinac_version": "x.y.z",
    "analysis_type": "acr_ct",
    "status": "success|failed|cancelled"
  },
  "series": {
    "study_uid": "1.2.3...",
    "series_uid": "1.2.3...",
    "modality": "CT",
    "num_images": 123
  },
  "inputs": {
    "origin_slice_override": null,
    "options": {}
  },
  "metrics": {},
  "warnings": [],
  "errors": [],
  "artifacts": {
    "pdf_report_path": "C:/.../report.pdf"
  },
  "raw_pylinac": {}
}
```

`metrics` should contain normalized Stage 1 fields for UI/export stability; `raw_pylinac` is optional and may be omitted or subsetted if payloads are too large.

## 4. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Pylinac API/version drift | Pin in `requirements.txt`; spike on upgrade; store `pylinac.__version__` in every export. |
| Large dependency tree for executables | Document frozen bundle strategy later (dependency included by default install policy). |
| Wrong slice order / orientation | Preflight warnings; document “use same order as viewer” from organizer. |
| MR sagittal separate Series UID | Document `check_uid=False` in dialog advanced options for Stage 1c MRI. |

---

## 5. After Stage 1 (pointer only)

- CatPhan adapters, phantom-type auto-suggest, batch runs, in-viewer overlays — per [PYLINAC_INTEGRATION_OVERVIEW.md](../info/PYLINAC_INTEGRATION_OVERVIEW.md) Phase 2–3.
- Native QA primitives, MAP mammography, Rose profiles — per [AUTOMATED_QA_ADDITIONAL_ANALYSIS.md](../info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md); treat as **parallel tracks** once `src/qa` patterns exist.
