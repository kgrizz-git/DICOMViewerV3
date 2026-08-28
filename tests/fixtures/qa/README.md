# Pylinac ACR `results_data` golden fixtures (Phase 0)

## Role

Redacted **`results_data(as_dict=True)`** JSON dumps for **ACR CT** and **ACR MRI Large** used by
`tests/qa/test_pylinac_results_data_spike.py` and flatten golden tests. **No DICOM pixels** —
metrics only.

## Files (when committed)

| File | Source |
|------|--------|
| `acr_ct_results_data.json` | Reviewed copy of a private maintainer dump (see workflow below) |
| `acr_mri_results_data.json` | Same |

## Maintainer workflow

1. Place ACR phantom DICOM under a **gitignored** folder (e.g. `test-DICOM-data/`).
2. From repo root (venv activated), write dumps to a **private path** (not straight into this
   tracked folder):

   ```bash
   python scripts/spike_pylinac_acrct.py --folder test-DICOM-data/<acr-ct> \
     --dump-json tmp/acr_ct_results_data.json
   python scripts/spike_pylinac_acrmri.py --folder test-DICOM-data/<acr-mri> \
     --dump-json tmp/acr_mri_results_data.json
   ```

   (`tmp/` is gitignored; any path outside the checkout is fine.)

3. Review JSON for absolute paths (should be `<redacted-path>` only).
4. Copy the reviewed files into `tests/fixtures/qa/` and commit (staged artifact gate required).

Until dumps exist, Phase 1–5 implementation may proceed; golden tests (**P1-F4**, **G2**) wait for **R0-9**.

## De-identification

- No patient identifiers or filesystem paths in committed JSON.
- Numeric QA metrics and phantom model strings only.
