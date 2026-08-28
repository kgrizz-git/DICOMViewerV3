# Pylinac ACR `results_data` golden fixtures (Phase 0)

## Role

Redacted **`results_data(as_dict=True)`** JSON dumps for **ACR CT** and **ACR MRI Large** used by
`tests/qa/test_pylinac_results_data_spike.py` and flatten golden tests. **No DICOM pixels** —
metrics only.

## Files (when committed)

| File | Generator |
|------|-----------|
| `acr_ct_results_data.json` | `python scripts/spike_pylinac_acrct.py --folder <gitignored-phantom> --dump-json tests/fixtures/qa/acr_ct_results_data.json` |
| `acr_mri_results_data.json` | `python scripts/spike_pylinac_acrmri.py --folder <gitignored-phantom> --dump-json tests/fixtures/qa/acr_mri_results_data.json` |

## Maintainer workflow

1. Place ACR phantom DICOM under a **gitignored** folder (e.g. `test-DICOM-data/`).
2. Run the spike commands above from repo root with venv activated.
3. Review JSON for absolute paths (should be `<redacted-path>`); run staged artifact gate before commit.

Until dumps exist, Phase 1–5 implementation may proceed; golden tests (**P1-F4**, **G2**) wait for **R0-9**.

## De-identification

- No patient identifiers or filesystem paths in committed JSON.
- Numeric QA metrics and phantom model strings only.
