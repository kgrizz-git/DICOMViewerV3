# De-identification (anonymized export)

**Last updated:** 2026-06-16

The viewer can export DICOM with patient and site identifiers removed, conforming to the **DICOM PS3.15 Annex E Basic Application Level Confidentiality Profile** (the "Basic Profile"). Both entry points below use the **same conformant engine** — there is no weaker "patient tags only" mode.

> **Important — burned-in text is *not* removed.** De-identification strips identifying **metadata** only. Patient names, IDs, dates, or other PHI **burned into the pixels** (for example ultrasound annotations, scanned-film labels, or screen captures) are **not** detected or removed. Review images visually before sharing.

> De-identification only applies to **DICOM** output. PNG/JPG, screenshot, and cine exports are not de-identified.

## Two ways to export de-identified DICOM

| Entry point | Best for |
|-------------|----------|
| **File → Export…**, then check **De-identify (PS3.15 Basic Profile)** | A quick de-identified export alongside a normal export, using the default preset (or a preset you pick via **Options…**). |
| **File → De-identify & Export DICOM (PS3.15)…** | A dedicated dialog focused on de-identification, with the same selection tree, presets, and per-option control. |

Both produce identical output for the same options.

### From the Export dialog

1. **File → Export…**
2. Set the format to **DICOM** (the de-identify control is disabled for other formats).
3. Check **De-identify (PS3.15 Basic Profile)**.
4. (Optional) Click **Options…** to choose a preset or fine-tune individual options (see below). The button is enabled only when DICOM + de-identify are both selected.
5. Choose what to export and **Export**.

### From the dedicated dialog

**File → De-identify & Export DICOM (PS3.15)…** opens a window with the selection tree plus the de-identification options inline. Pick a preset (or customize), select studies/series, and export.

## Presets

The **Preset** dropdown sets all options at once. Editing any individual option switches the dropdown to **Custom…**.

| Preset | What it does |
|--------|--------------|
| **Standard share (recommended)** | Basic Profile with UIDs re-minted and dates **shifted** (relative timing preserved). The safe default for sharing. |
| **Maximal strip (remove dates)** | Basic Profile with dates **blanked** entirely. Use when even shifted dates are unwanted. |
| **Research (keep device identity)** | Basic Profile but **retains** scanner/station/manufacturer identity, for studies where the device matters but the site/patient must not be identifiable. |

## Individual options

Available under **Options…** (Export dialog) or inline (dedicated dialog):

- **Retain institution identity** — keep institution name/address/department (declares PS3.16 code **113112**). Off by default.
- **Retain device identity** — keep station name, device serial number, and manufacturer/model (declares **113109**). Off by default; on in the *Research* preset.
- **Strip operator and physician names** — remove operator, performing/referring/reading physician names.
- **Re-mint UIDs** — replace Study/Series/SOP Instance UIDs with new ones, kept **consistent within a single export** so cross-references between the exported files stay intact. Turning this **off** keeps the original UIDs and declares **113110**. (SOP Class and Transfer Syntax UIDs are always preserved so files still load.)
- **Dates** — one of:
  - **Keep dates** (declares **113106**) — dates unchanged.
  - **Shift dates to ~1900** (declares **113107**) — every date moved by one batch-wide offset that anchors the earliest study near 1900, preserving all relative gaps; a random per-batch jitter hides the absolute baseline.
  - **Remove dates** — date values blanked but kept present so the file stays DICOM-valid (Type-2 conformant).
- **Remove private tags** — drop all private (odd-group) elements.
- **Remove free-text comments and descriptions** — drop comment/description fields that commonly leak names.

## What the exported files record

Each de-identified instance is marked so downstream tools know it was processed:

- **PatientIdentityRemoved (0012,0062)** = `YES`.
- **DeidentificationMethod (0012,0063)** and **DeidentificationMethodCodeSequence (0012,0064)** record the Basic Profile (**113100**) plus codes for every retain/date choice you made (the `113xxx` codes listed above), so the exact options are auditable from the file itself.
- **File Meta** is regenerated and the 128-byte preamble zeroed; `MediaStorageSOPInstanceUID (0002,0003)` is kept in sync with `SOPInstanceUID (0008,0018)` so no original instance UID leaks.

## Scope and limits

- Conforms to the **Basic Profile**. It does **not** claim *Clean Pixel Data* (no burned-in-text removal) or *Clean Descriptors* (113105).
- Patient identifiers are removed recursively, including inside sequences, and Type-2 attributes are **blanked, not deleted**, to stay DICOM-conformant.
- Always confirm the result loads cleanly in another tool and that no PHI survives before sharing — especially for unusual private data or burned-in pixels.

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [CONFIGURATION.md](CONFIGURATION.md) · [CHANGELOG.md](../CHANGELOG.md).
