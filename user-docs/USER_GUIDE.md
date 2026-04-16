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
- **Radiation dose SR report:** For DICOM **Radiation Dose SR (RDSR)** instances the viewer recognizes (often CT-related dose concepts), open **Tools → Radiation dose report…** (or image right-click menu when available) to review summary dose quantities (e.g. CTDIvol/DLP when present) and export JSON/CSV. The report updates masking live when Privacy Mode is toggled.
- **ROI statistics (RGB):** For multi-channel slices, ROI statistics can include per-channel values (mean/std/min/max) in the panel and exports. Toggle this under **Annotation options → ROI statistics**.
- **Histogram and projection:** In the histogram dialog, use **Use intensity projection pixels** to match histogram bins to the active AIP/MIP/MinIP slab instead of the single current slice.

## Source and versioning

These files live in the repository under `user-docs/` and match the **main** branch on [GitHub](https://github.com/kgrizz-git/DICOMViewerV3). For release-specific behavior, check [CHANGELOG.md](../CHANGELOG.md).

## Further reading (developers / deep dives)

Implementation notes, research, and plans are under `dev-docs/` (for example [PYLINAC_INTEGRATION_OVERVIEW.md](../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md)).
