# DICOM RDSR / radiation dose SR test fixtures

## Role

Tiny **Structured Report** objects used by **`tests/test_rdsr_dose_sr.py`** and the parser in
**`src/core/rdsr_dose_sr.py`**. They exercise **X-Ray Radiation Dose SR** (DICOM **TID 10001**
CT dose family) **ContentSequence** walks only — **not** for clinical validation.

## Files

| File | Description |
|------|-------------|
| **`synthetic_ct_dose_xray_rdsr.dcm`** | **Synthetic** SR: **SOP Class** = X-Ray Radiation Dose SR Storage (`1.2.840.10008.5.1.4.1.1.88.67`). |
| **`synthetic_ct_dose_comprehensive_sr.dcm`** | **Synthetic** SR: **SOP Class** = Comprehensive SR Storage (`1.2.840.10008.5.1.4.1.1.88.33`) with the same dose-related **NUM** content (parser **secondary** detection path). |
| **`synthetic_enhanced_xray_rdsr.dcm`** | **Synthetic** SR: **SOP Class** = Enhanced X-Ray Radiation Dose SR Storage (`1.2.840.10008.5.1.4.1.1.88.76`) with one event containing primary/secondary angles, source-detector distance, and collimated field area. |

## Provenance

- **Source:** Generated in-repo by **`tests/scripts/generate_rdsr_dose_sr_fixtures.py`** using **pydicom**
  (no vendor software, no clinical PACS export).
- **Regenerate:** from repository root, with venv activated:
  `python tests/scripts/generate_rdsr_dose_sr_fixtures.py`

## License

- **Tooling / structure:** project **MIT** (or the repo’s root license) applies to the **generator script**
  and test code.
- **DICOM attribute names and UID values** are specified in the **DICOM Standard** (NEMA). Use of
  standard UIDs and template codes for interoperability is **not** a separate encumbrance on these
  synthetic blobs beyond your compliance with the **DICOM Standard** terms as published by NEMA
  (see [https://www.dicomstandard.org/](https://www.dicomstandard.org/)).

## De-identification

- Fixtures contain **only** synthetic **Patient Name** / **Patient ID** placeholders and **newly
  generated** Study/Series/SOP Instance UIDs at generation time.
- **No** real patient, accession, or institution identifiers are intended to appear. If you
  regenerate files, keep placeholders and **do not** paste production metadata.

## Max size policy (git)

- Target **≤ 200–512 KiB** per file; these synthetic files are **well under 4 KiB** each.
- If future curated real-world samples are added, each file must stay within policy or use
  **Git LFS** if the project adopts it — today the repo standard is **small** tracked binaries only.

## SecOps / PHI

- **No PHI in git:** fixtures are synthetic. Any replacement with real SR must follow the
  checklist in **`dev-docs/plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md`** §3.6 (provenance, license,
  de-ID, size) plus a **secops** spot-check before merge.
