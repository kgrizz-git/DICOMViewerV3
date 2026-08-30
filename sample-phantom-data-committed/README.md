# Reviewed de-identified ACR phantom DICOM

**Last updated:** 2026-08-29

Local ACR CT and MRI phantom series exported with **File → De-identify & Export DICOM (PS3.15)…** using **Standard share** (institution and device identity not retained). Instance folders are generic (`ct/series-NNN/`, `mr/series-NNN/`).

These files are for pylinac QA and decoder work. They are **not** diagnostic studies.

## Review

- Metadata: Standard share; patient text tags are the dummy `ANONYMIZED` where present; site/station tags stripped.
- **Pixel review (2026-08-29):** human visual review of the series, including the two CT slices that EasyOCR had flagged (false positives on phantom inserts / corner BBs). No burned-in names, IDs, or dates observed.
- Hash-pinned in `security/approved-media-sha256.json`. Each `.dcm` is gitignore-allowlisted by **exact path**.

Do not add further DICOM here without de-identification, artifact-gate, and a new pixel review plus hash-manifest update.
