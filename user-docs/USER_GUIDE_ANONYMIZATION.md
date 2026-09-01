# De-identification (anonymized export)

**Last updated:** 2026-09-01

The viewer offers DICOM **metadata de-identification** settings that remove or
replace selected identifiers during the DICOM export workflows described below.
The implementation is being reassessed against the DICOM PS3.15 Attribute
Confidentiality Profiles; do not treat this feature as a declaration of DICOM
profile conformance, HIPAA compliance, legal anonymization, or suitability for
unreviewed sharing.

> **Review before sharing.** DICOM PS3.15 itself says that applying its
> attribute profiles does not guarantee all identifying information is removed.
> This tool cannot determine the recipient's context, legal obligations, or all
> identifying content in an individual object. Use your organization's required
> review process before disclosing an export.

> **Important — burned-in text is *not* removed.** De-identification strips identifying **metadata** only. Patient names, IDs, dates, or other PHI **burned into the pixels** (for example ultrasound annotations, scanned-film labels, or screen captures) are **not** detected or removed. Review images visually before sharing.

> De-identification only applies to **DICOM** output. PNG/JPG, screenshot, and cine exports are not de-identified.

## DICOM export workflows with metadata de-identification

| Entry point | Best for |
|-------------|----------|
| **File → Export…**, then check **De-identify DICOM metadata** | A quick metadata-de-identified export alongside a normal export, using the default preset (or a preset you pick via **Options…**). |
| **File → De-identify & Export DICOM…** | A dedicated dialog focused on DICOM metadata de-identification, with the same selection tree, presets, and per-option control. |
| **File → Save MPR as DICOM…**, then check **De-identify DICOM metadata** | Derived MPR DICOM only. Uses the same metadata settings and preset defaults after the MPR instances are constructed. |

The normal and dedicated DICOM export dialogs use the same settings. MPR export
applies those settings to its derived instances; its pixels remain out of scope.

### From the Export dialog

1. **File → Export…**
2. Set the format to **DICOM** (the de-identify control is disabled for other formats).
3. Check **De-identify DICOM metadata**.
4. (Optional) Click **Options…** to choose a preset or fine-tune individual options (see below). The button is enabled only when DICOM + de-identify are both selected.
5. Choose what to export and **Export**.

### From the dedicated dialog

**File → De-identify & Export DICOM…** opens a window with the selection tree plus the de-identification options inline. Pick a preset (or customize), select studies/series, and export.

## Presets

The **Preset** dropdown sets all options at once. Editing any individual option switches the dropdown to **Custom…**.

| Preset | What it does |
|--------|--------------|
| **Standard share (recommended)** | Re-mints selected UIDs and **shifts** selected dates (relative timing preserved). It is a configured metadata transformation, not a general assurance that the output is safe to share. |
| **Maximal strip (remove dates)** | Blanks selected dates. Use when even shifted dates are unwanted, subject to the review limitations above. |
| **Research (keep device identity)** | Retains scanner/station/manufacturer identity for equipment-correlated analysis. Retained device information can increase re-identification risk. |

## Individual options

Available under **Options…** (Export dialog) or inline (dedicated dialog):

- **Retain institution identity** — keep institution name/address/department. Off by default.
- **Retain device identity** — keep station name (including performed station name/AE title), device serial number, and manufacturer/model. Off by default; on in the *Research* preset.
- **Strip operator and physician names** — remove operator, performing/referring/reading physician names.
- **Re-mint UIDs** — replace Study/Series/SOP Instance UIDs with new ones, kept **consistent within a single export** so cross-references between the exported files stay intact. Turning this **off** keeps the original UIDs. (SOP Class and Transfer Syntax UIDs are always preserved so files still load.)
- **Dates** — one of:
  - **Keep dates** — dates unchanged.
  - **Shift dates to ~1900** — every date moved by one batch-wide offset that anchors the earliest study near 1900, preserving all relative gaps; a random per-batch jitter hides the absolute baseline.
  - **Remove dates** — date values are blanked; required Type-2 fields remain present.
- **Remove private tags** — drop all private (odd-group) elements.
- **Remove free-text comments and descriptions** — drop comment/description fields that commonly leak names.

## What the exported files record

Each instance processed through these DICOM export workflows records the
following factual transformation detail:

- **DeidentificationMethod (0012,0063)** identifies the application's metadata transformation. It does not certify that all identifying information was removed.
- The application deliberately does **not** write `PatientIdentityRemoved = YES` or a PS3.16 CID 7050 profile/option code sequence while its PS3.15 assessment is incomplete.
- **File Meta** is regenerated and the 128-byte preamble zeroed; `MediaStorageSOPInstanceUID (0002,0003)` is kept in sync with `SOPInstanceUID (0008,0018)` to avoid a mismatch. When Re-mint UIDs is off, the original UID remains by design.

## Scope and limits

- The implementation does **not** claim *Clean Pixel Data*, *Clean Recognizable Visual Features*, or *Clean Descriptors*. It does not detect or remove burned-in text.
- Patient identifiers are removed recursively, including inside sequences, and Type-2 attributes are **blanked, not deleted**.
- Confirm the result loads cleanly in another tool and apply the required human/organizational review — especially for unusual private data, free text, and burned-in pixels. A successful load or metadata scan alone does not establish that no identifying information remains.

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [CONFIGURATION.md](CONFIGURATION.md) · [CHANGELOG.md](../CHANGELOG.md).
