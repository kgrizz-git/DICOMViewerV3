# DICOM Viewer V3 — User guide

This hub links topic guides for the application. **In the running app**, use **Help → Quick Start Guide** for a short overview (with a table of contents and links that open these pages in your browser when you are online).

## Topics

| Guide | Contents |
|-------|-----------|
| [USER_GUIDE_MPR.md](USER_GUIDE_MPR.md) | Multi-planar reformation (MPR): creating and clearing MPR views |
| [USER_GUIDE_QA_PYLINAC.md](USER_GUIDE_QA_PYLINAC.md) | ACR CT / ACR MRI phantom analysis (pylinac), JSON/PDF, compare mode |
| [IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md](IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md) | Image fusion (PET/SPECT on CT/MR): options, accuracy, algorithms |

## General viewing (2D)

- **Cine:** In the left pane **Cine Playback** group, use the **Play / Pause** toggle, **Stop**, and **Loop** (plus speed and frame slider). On multi-frame series, the image **right-click** menu offers the same play/pause toggle, stop, and loop when cine is available.
- **Clear This Window:** **Right-click** the image background (not on an ROI) → **Clear This Window** removes the series from **that pane only**; loaded studies and series remain in the navigator.
- **Structured Report browser:** For DICOM **Structured Report** instances (**SR** modality or SR storage SOP classes), open **Tools → Structured Report…** (or image right-click **Structured Report…** when available) to browse the full **ContentSequence** tree, a **Dose events** table (irradiation event containers **113706** / **113819** per PS3.16 where present, with standard fluoroscopy/geometry columns plus extra columns for vendor-specific **NUM** / **CODE** / **TEXT** / **DATETIME** / **UIDREF** leaves under each event). Vendor **source-to-detector** distances that use alternate concept names (for example *Final Distance Source to Detector*) are folded into the main distance column when standard **113750** is absent, and exposure time accepts common DCM codes (**113735** / **113824**). **Patient orientation** and **orientation modifier** map standard **113743** / **113744** codes when present. A **Dose summary** tab shows the legacy CT-style metrics when parsing succeeds, and **exports** include document tree JSON and dose events CSV/XLSX. Use **Raw tags → Open DICOM Tag Viewer** for flat tags with search. Privacy Mode masks free text and UIDs in the tree; the dose summary tab follows the same masking rules as before. **Dose events** is template-guided and heuristic (not a full TID validator); orange **warnings** may note ambiguous values, subtree flatten limits, or vendor-specific duplicates—use the **Document** tab when you need the full SR tree.
- **ROI statistics (RGB):** For multi-channel slices, ROI statistics can include per-channel values (mean/std/min/max) in the panel and exports. Toggle this under **Annotation options → ROI statistics**.
- **Histogram and projection:** In the histogram dialog, use **Use intensity projection pixels** to match histogram bins to the active AIP/MIP/MinIP slab instead of the single current slice.

## Source and versioning

These files live in the repository under `user-docs/` and match the **main** branch on [GitHub](https://github.com/kgrizz-git/DICOMViewerV3). For release-specific behavior, check [CHANGELOG.md](../CHANGELOG.md).

## Further reading (developers / deep dives)

Implementation notes, research, and plans are under `dev-docs/` (for example [PYLINAC_INTEGRATION_OVERVIEW.md](../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md)).
