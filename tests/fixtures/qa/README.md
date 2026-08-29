# Pylinac ACR `results_data` golden fixtures (Phase 0)

## Role

Redacted **`results_data(as_dict=True)`** JSON dumps for **ACR CT** and **ACR MRI Large** used by
`tests/qa/test_pylinac_results_data_spike.py` and flatten golden tests. **No DICOM pixels** —
numeric metrics and phantom-model strings only.

## Files (when committed)

| File | Source |
|------|--------|
| `acr_ct_results_data.json` | Redacted dump from `deid-phantoms/ct/series-001/` (2026-08-29) |
| `acr_mri_results_data.json` | Redacted dump from `deid-phantoms/mr/series-005/` (T1 11-slice; 2026-08-29) |

## Tracked de-identified phantoms (preferred dump source)

Use **`sample-phantom-data-committed/deid-phantoms/`** (PS3.15 Standard share; pixel review 2026-08-29) rather than gitignored clinical copies when producing the golden dumps:

| Folder | What it is |
|--------|------------|
| `deid-phantoms/ct/series-001/` | ACR CT (25 instances) |
| `deid-phantoms/mr/series-005/` | ACR T1 11-slice axial (DICOM SeriesNumber 3) — **not** `mr/series-003` (3-plane localizer) |
| `deid-phantoms/mr/series-004/` | Dual-echo T2 (22 axials). Standard share may omit `EchoNumber`; auto-highest then cannot distinguish echoes |

Spike `analyze()` on these T1 axials needs the viewer's **~1 mm** scan-extent retry (strict pylinac z-extent fails). Dump JSON still goes **outside** the checkout, then a redacted copy into this folder.

## Local phantom folders (gitignored — never stage)

Place private ACR series under **repo-relative** gitignored roots only. Do **not**
record machine-absolute paths (`/Users/…`, `C:\…`) in docs, dumps, logs, or commits.

| Root | Use |
|------|-----|
| `sample-DICOM-gitignored/CT-phantoms/` | Local ACR CT phantom series |
| `sample-DICOM-gitignored/MR-phantoms/` | Local ACR MRI phantom series |
| `test-DICOM-data/` | Alternate local-only phantom root |

## Maintainer workflow

1. Prefer tracked **`sample-phantom-data-committed/deid-phantoms/`** (table above). Gitignored folders remain valid for private regenerations.
2. From repo root (venv activated), write dumps **outside** the source checkout
   (`assert_safe_internal_path` rejects in-repo targets, including gitignored
   `tmp/`):

   ```bash
   python scripts/spike_pylinac_acrct.py --folder sample-phantom-data-committed/deid-phantoms/ct/series-001 \
     --dump-json ~/private-qa-dumps/acr_ct_results_data.json
   python scripts/spike_pylinac_acrmri.py --folder sample-phantom-data-committed/deid-phantoms/mr/series-005 \
     --dump-json ~/private-qa-dumps/acr_mri_results_data.json
   ```

   Spikes construct `ACRCTForViewer` / `ACRMRILargeForViewer` from the folder
   path (no `from_folder`) and retry ``analyze()`` at 0 / 1 / 2 mm scan-extent
   tolerance. Spike console lines never print the folder or dump destination.
   Dual-echo ACR T2 series should use the highest echo (echo 2). The MRI spike
   resolves auto-highest ``EchoNumber`` the same way the viewer runner does
   before ``analyze()``.
3. Review JSON: no absolute paths; no `InstitutionName` / `InstitutionAddress` /
   `StationName` (or other site/patient/UID keywords). Spike redaction drops
   those keys and replaces absolute paths with `<redacted-path>`.
4. Copy the reviewed files into `tests/fixtures/qa/` and commit (staged artifact
   gate required). Never `--no-verify`.

Golden flatten tests (**P1-F4**, **G2**) load these files in
`tests/qa/test_pylinac_results_data_spike.py` — no live ``analyze()`` in CI.

## De-identification

- Committed JSON: numeric QA metrics and phantom model strings only. No patient
  identifiers, institution/address/station names, or filesystem paths.
- **If we later keep DICOM fixtures in the repo**, export them first with
  **File → De-identify & Export DICOM (PS3.15)…** (Standard share; do **not**
  enable retain-institution or retain-device identity). Then run the staged
  artifact gate and the usual human review before any hash-manifest update.
  Gitignored local phantoms stay gitignored; de-identification is the gate for
  anything that would be tracked.
