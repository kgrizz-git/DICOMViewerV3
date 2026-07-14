# QA Results Export, CLI, and History Plan

## Goal and success criteria

Extend the pylinac/automated-QA subsystem so results are easier to reuse outside the GUI and easier to trend over time.

Success means:

- QA results can be exported to CSV and Excel (`.xlsx`) in addition to the existing JSON/PDF outputs.
- A command-line interface can run supported QA analyses, including pylinac-backed analyses, without launching the GUI.
- A local QC analysis results database can store runs by equipment identity such as DICOM `StationName` and allow viewing, filtering, plotting, and comparing results over time.
- All outputs preserve reproducibility metadata: app version, pylinac version, analysis type, parameters, stock-vs-viewer pylinac mode, input identity, run timestamp, warnings/errors, and source study/series identifiers where available.

## Context and links

- Backlog cluster: [`dev-docs/TO_DO.md`](../../TO_DO.md) under `Further integrate pylinac and other automated QC analysis tools`.
- Current QA seams:
  - `src/qa/analysis_types.py` defines `QARequest`, `QAResult`, `MRICompareRequest`, and `MRIBatchResult`.
  - `src/qa/pylinac_runner.py` re-exports worker-safe pylinac entrypoints.
  - `src/gui/qa_app_facade.py` runs GUI QA flows and currently exports structured JSON plus PDF where available.
  - `src/qa/mri_compare_export.py` already shapes compare-mode JSON.
  - `requirements.txt` already includes `openpyxl`, so `.xlsx` writing should not require a new dependency.
  - The local study index already uses SQLite/SQLCipher patterns that can inform the QC history database, but QC results should be modeled separately from study metadata.

## Task graph and gates

### Ordering

- T1 -> T2/T3.
- T1 -> T4 -> T5.
- T1 -> T6 -> T7/T8.
- T9/T10 after the relevant feature slice.

### Verification gates

- Gate 1: reviewer approves the canonical flattened QA result schema before CSV/XLSX or DB work starts.
- Gate 2: tester verifies GUI JSON/PDF behavior is unchanged after export refactoring.
- Gate 3: reviewer approves CLI argument shape and output contract before it is documented for automation.
- Gate 4: reviewer approves QC history schema and privacy boundaries before storing persistent run records.

## Phases

### Phase 1 - Canonical QA result serialization

- [ ] (T1) Define a reusable `qa.result_serialization` module that converts `QAResult` and `MRIBatchResult` into a stable normalized dict plus flattened tabular rows. (owner: coder, parallel-safe: no, stream: none, after: none)
- [ ] (T2) Refactor GUI JSON export to use the shared serializer without changing existing schema fields except for documented additive fields. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T3) Add tests for single-run ACR CT/MRI, MRI compare mode, nuclear QA, failed runs, warnings, and missing pylinac results. (owner: tester, parallel-safe: yes, stream: A, after: T1)

### Phase 2 - CSV and Excel export

- [ ] (T4) Add CSV export for QA results with one row per run and stable columns for metrics, provenance, warnings/errors, station/device identifiers, and source study/series UIDs. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T5) Add Excel export using `openpyxl`: summary sheet, metrics sheet, raw/provenance sheet, and warnings/errors sheet; support compare-mode multi-run output. (owner: coder, parallel-safe: no, stream: none, after: T4)
- [ ] (T6) Add GUI actions/buttons for exporting QA result dialogs to CSV/XLSX while preserving existing JSON/PDF choices and last QA output directory behavior. (owner: coder, parallel-safe: no, stream: none, after: T5)

### Phase 3 - CLI analysis runner

- [ ] (T7) Add a CLI entrypoint such as `python -m qa.cli` or `python scripts/run_qa_analysis.py` for supported analysis types, input path(s), output folder, optional JSON/PDF/CSV/XLSX outputs, and stock-vs-viewer pylinac mode. (owner: coder, parallel-safe: no, stream: none, after: T1)
- [ ] (T8) Support batch input via folder, manifest file, or repeated `--input` arguments; return machine-readable exit codes for success, partial success, unsupported input, analysis failure, and export failure. (owner: coder, parallel-safe: no, stream: none, after: T7)
- [ ] (T9) Keep CLI analysis code GUI-free and route through the same `QARequest`/runner/serializer stack as the GUI. (owner: coder, parallel-safe: no, stream: none, after: T7)

### Phase 4 - QC results database and trend UI

- [ ] (T10) Design a local QC results database schema separate from the study index, keyed by run id and indexed by station name, modality, analysis type, phantom type, acquisition date, run date, app version, pylinac version, and source study/series UIDs. (owner: coder, parallel-safe: no, stream: none, after: Gate 4)
- [ ] (T11) Store equipment identity from DICOM metadata where available: `StationName` `(0008,1010)`, `Manufacturer`, `ManufacturerModelName`, `DeviceSerialNumber`, institution/site fields, and explicit user override when metadata is missing or inconsistent. (owner: coder, parallel-safe: no, stream: none, after: T10)
- [ ] (T12) Add import/export for QC history records so a site can back up or move trend data without bundling DICOM pixel data. (owner: coder, parallel-safe: no, stream: none, after: T10)
- [ ] (T13) Add a QC history UI for filtering by station, modality, analysis type, phantom, date range, pass/fail, and warnings/errors. (owner: ux/coder, parallel-safe: no, stream: none, after: T10)
- [ ] (T14) Add plots and comparisons for numeric metrics over time, side-by-side run comparisons, and optional pass/fail threshold overlays. (owner: ux/coder, parallel-safe: no, stream: none, after: T13)

### Phase 5 - Documentation and verification

- [ ] (T15) Update `user-docs/USER_GUIDE_QA_PYLINAC.md` with CSV/XLSX export, CLI usage, and QC history behavior. (owner: docs, parallel-safe: yes, stream: B, after: T6/T9/T14)
- [ ] (T16) Update `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` with the final result schema, CLI contract, and QC database boundaries. (owner: docs, parallel-safe: yes, stream: B, after: T1/T9/T10)
- [ ] (T17) Add focused tests for serializers, CSV/XLSX files, CLI exit codes, QC database migrations, filtering, and plotting data preparation. (owner: tester, parallel-safe: yes, stream: C, after: T6/T9/T14)

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| CSV/XLSX columns drift as new metrics are added | Use a stable common prefix plus metric namespace columns; test representative analysis types. |
| CLI and GUI produce different results | Share `QARequest`, runner, and serializer code; keep CLI GUI-free. |
| QC history mixes PHI with QA trend data | Store only the metadata needed for trending by default; document and gate any patient/study identifiers. |
| Station names are missing or inconsistent | Store multiple equipment identifiers and allow user-defined station aliases. |
| Database duplicates repeated runs | Compute a run fingerprint from input identifiers, analysis type, parameters, and timestamp; allow duplicates but surface them clearly. |
| Trend plots compare non-equivalent runs | Filter/label by analysis profile, stock-vs-viewer pylinac mode, phantom type, and version before plotting. |

## Modularity and file-size guardrails

- Keep serialization in `src/qa/` and independent of Qt.
- Keep CLI code under `src/qa/` or `scripts/` without importing `src/main.py`.
- Keep QC history persistence separate from `LocalStudyIndexService`; share helper patterns only where appropriate.
- Keep plotting data preparation separate from Qt widgets so tests can verify series selection and comparisons without GUI.

## Testing strategy

- Serializer tests:
  - one successful ACR CT result,
  - one successful ACR MRI result,
  - MRI compare-mode multi-run result,
  - nuclear QA result,
  - failed/missing-pylinac result,
  - warnings and non-stock pylinac profile.
- Export tests:
  - CSV headers and row count,
  - `.xlsx` workbook sheet names and key cells,
  - stable JSON backward compatibility for existing fields.
- CLI tests:
  - help text,
  - invalid analysis type,
  - missing input,
  - fake runner success/failure with deterministic exit codes,
  - output file creation under a workspace-local temp directory.
- QC history tests:
  - migration creates schema,
  - insert/query by station name,
  - filters by modality/date/analysis type,
  - metric time-series extraction,
  - export/import round trip.

## Questions for user

- Should the QC history database live beside the existing study index by default, or use a separate default path and settings control?
- Should patient/study identifiers be stored by default for traceability, or should the first implementation store equipment/run metadata only?
- Which output is most important first for CSV/XLSX: one compact summary row per run, detailed per-module rows, or both?

## Completion notes

Not started. This is a docs-only backlog/supporting plan as of 2026-06-11.
