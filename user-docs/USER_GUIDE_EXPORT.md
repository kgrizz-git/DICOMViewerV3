# Exporting images & data

**Last updated:** 2026-07-12

The viewer can export your loaded images as **DICOM**, **PNG**, or **JPG**, with a hierarchical study/series/instance picker. This guide covers the main **Export Images** dialog. Other, more specialized exports (screenshots, cine, de-identified DICOM, tags, ROI statistics) have their own entry points and are cross-linked at the bottom.

## Opening the dialog

**File → Export…** (**Ctrl+E**) opens the **Export Images** dialog.

## Choosing a format

At the top, pick one **format** (PNG is the default):

| Format | What it writes |
|--------|----------------|
| **PNG** | Rendered 8-bit image of each selected instance, **as displayed** — current window/level and (optionally) overlays/ROIs are baked in. Lossless. |
| **JPG** | Same rendered image as PNG, but JPEG-compressed (smaller, lossy). |
| **DICOM** | The DICOM dataset(s) themselves — pixel data and tags. Window/level and overlay options do **not** apply; the file is a real DICOM instance, optionally de-identified. |

For DICOM export, the app writes the currently loaded in-memory dataset, including tag edits made in the tag viewer/editor. It does not directly save over the originally opened file unless you deliberately export to that same path and confirm the overwrite prompt.

The window/level, overlay, and resolution options below the format are only relevant to **PNG/JPG**; the de-identify option is only relevant to **DICOM**. The dialog enables and disables each group as you switch formats.

## PNG / JPG options

- **Window/Level (for PNG/JPG):**
  - **Use currently focused sub-window window/level** — renders with the window center/width you are viewing in the focused pane (the label shows the pane number and the current center/width, e.g. *sub-window 1 — 44/486*). This is the default when a viewer W/L is available.
  - **Use dataset default window/level** — renders with the window/level stored in the DICOM dataset.
- **Include overlays and ROIs (PNG/JPG only):** when checked (default), corner metadata overlays, ROIs, measurements, text, and arrows are drawn into the exported image. Uncheck for a clean image.
- **Resolution (PNG/JPG):** choose **Native resolution** (default), **1.5×**, **2×**, or **4×**. Larger exports are capped so the longest side stays at or under **8192 px** — any image that would exceed this is exported at a lower magnification automatically, and the completion message lists exactly which files were stepped down (e.g. *requested 4×, exported at 2×*). This matches the cap used by **Export Screenshots**.

> Annotation line/text sizes are formula-based and are **not** scaled with the export magnification, so they stay legible at every resolution.

## DICOM option

- **De-identify (PS3.15 Basic Profile) (DICOM only):** when checked, each exported DICOM is run through the conformant PS3.15 de-identification engine before writing (the **Standard share** preset by default). Use **Options…** to choose a preset or toggle individual rules. Full details — presets, per-option rules, what is recorded, and limits — are in the [de-identified export guide](USER_GUIDE_ANONYMIZATION.md). Unchecked, the DICOM is written as-is.

## Combine Slices (intensity projection)

If **Combine Slices** (AIP / MIP / MinIP) is enabled in the viewer, the dialog shows a note and exports use that projection with the configured number of slices combined, rather than single slices.

## Selecting what to export

The **Select Studies, Series, and Slices** tree lists everything loaded:

- **Study** → **Series N: description (modality)** → **Instance N**, with a **Count** column showing how many instances each level holds.
- Tick a checkbox at any level. Checking a study or series checks everything under it; a partially-selected parent shows a mixed (tri-state) check.
- **Select All** / **Deselect All** buttons toggle every item at once.
- The **Selected: N items** label tracks the running count.

## Output and running the export

- **Output Directory → Browse…** chooses the destination folder (the dialog remembers your last export folder for next time).
- Click **Export**. If any target files already exist you are warned and asked to confirm before overwriting.
- On success a summary reports how many files were written and where, plus any resolution step-downs. Errors are reported without exposing full file paths.

You must select at least one item **and** an output directory, or **Export** warns you.

## Other export paths

These are separate from the main Export Images dialog:

| Export | Where | Covered in |
|--------|-------|------------|
| Rendered **screenshots** of panes / whole window | **File → Export Screenshots…** | [Hub → General viewing](USER_GUIDE.md#general-viewing-2d) |
| **Cine** loop (GIF / AVI / MP4 / MPG) | **File → Export Cine As…** | [Hub → General viewing](USER_GUIDE.md#general-viewing-2d) |
| **De-identified** DICOM (dedicated dialog) | **File → De-identify & Export DICOM (PS3.15)…** | [De-identified export](USER_GUIDE_ANONYMIZATION.md) |
| **DICOM tags** (CSV / TXT / XLSX) | **Tools → Export DICOM Tags…** (**Ctrl+Shift+T**) | [Hub → DICOM tags](USER_GUIDE.md) |
| **ROI statistics** & measurements | **Tools → Export ROI Statistics…** | [Measurements & annotations](USER_GUIDE_ANNOTATIONS.md) |

---

See also: [USER_GUIDE.md](USER_GUIDE.md) (hub) · [USER_GUIDE_ANONYMIZATION.md](USER_GUIDE_ANONYMIZATION.md) · [USER_GUIDE_ANNOTATIONS.md](USER_GUIDE_ANNOTATIONS.md) · [USER_GUIDE_SHORTCUTS.md](USER_GUIDE_SHORTCUTS.md).
