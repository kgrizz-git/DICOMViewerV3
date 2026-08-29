# Pylinac ACR `results_data` golden fixtures (Phase 0)

## Role

Redacted **`results_data(as_dict=True)`** JSON dumps for **ACR CT** and **ACR MRI Large** used by
`tests/qa/test_pylinac_results_data_spike.py` and flatten golden tests. **No DICOM pixels** —
numeric metrics and phantom-model strings only.

## Files (when committed)

| File | Source |
|------|--------|
| `acr_ct_results_data.json` | Reviewed copy of a private maintainer dump (see workflow below) |
| `acr_mri_results_data.json` | Same |

## Local phantom folders (gitignored — never stage)

Place private ACR series under **repo-relative** gitignored roots only. Do **not**
record machine-absolute paths (`/Users/…`, `C:\…`) in docs, dumps, logs, or commits.

| Root | Use |
|------|-----|
| `sample-DICOM-gitignored/CT-phantoms/` | Local ACR CT phantom series |
| `sample-DICOM-gitignored/MR-phantoms/` | Local ACR MRI phantom series |
| `test-DICOM-data/` | Alternate local-only phantom root |

## Maintainer workflow

1. Keep phantom DICOM in a gitignored folder from the table above.
2. From repo root (venv activated), write dumps **outside** the source checkout
   (`assert_safe_internal_path` rejects in-repo targets, including gitignored
   `tmp/`):

   ```bash
   python scripts/spike_pylinac_acrct.py --folder sample-DICOM-gitignored/CT-phantoms/<series> \
     --dump-json ~/private-qa-dumps/acr_ct_results_data.json
   python scripts/spike_pylinac_acrmri.py --folder sample-DICOM-gitignored/MR-phantoms/<series> \
     --dump-json ~/private-qa-dumps/acr_mri_results_data.json
   ```

   Spike console lines never print the folder or dump destination. Dual-echo ACR
   T2 series should use the highest echo (echo 2). The MRI spike now resolves
   auto-highest ``EchoNumber`` the same way the viewer runner does before
   ``analyze()``.
3. Review JSON: no absolute paths; no `InstitutionName` / `InstitutionAddress` /
   `StationName` (or other site/patient/UID keywords). Spike redaction drops
   those keys and replaces absolute paths with `<redacted-path>`.
4. Copy the reviewed files into `tests/fixtures/qa/` and commit (staged artifact
   gate required). Never `--no-verify`.

Until dumps exist, Phase 1–6 implementation may proceed; golden tests (**P1-F4**, **G2**) wait for **R0-9**.

## De-identification

- Committed JSON: numeric QA metrics and phantom model strings only. No patient
  identifiers, institution/address/station names, or filesystem paths.
- **If we later keep DICOM fixtures in the repo**, export them first with
  **File → De-identify & Export DICOM (PS3.15)…** (Standard share; do **not**
  enable retain-institution or retain-device identity). Then run the staged
  artifact gate and the usual human review before any hash-manifest update.
  Gitignored local phantoms stay gitignored; de-identification is the gate for
  anything that would be tracked.
