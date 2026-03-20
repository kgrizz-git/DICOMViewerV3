# To-Do Checklist

**Last updated:** 2026-03-16  
**Changes:** Reorganized into active categories; rolled FUTURE_WORK items into this checklist; added detail-note section links.

---

## Purpose

This file tracks active and near-term tasks.

- Detailed implementation notes and tradeoffs: [FUTURE_WORK_DETAIL_NOTES.md](FUTURE_WORK_DETAIL_NOTES.md)

## Priority Legend

- **P0** = critical correctness/release blocker
- **P1** = important near-term
- **P2** = useful improvement / lower urgency

---

## Validation / QA

- [ ] **[P1]** Run assessment templates
- [ ] **[P0]** RUN SMOKE TESTS for exporting (various export options, magnified, with ROIs/text, without)
- [ ] **[P1]** See qi-assessment recommendations
- [ ] **[P1]** Also see to-dos on Unpushed Edits Google Sheet

## Bugs / Correctness

- [ ] **[P0]** Sometimes when scrolling slices, the image seems to drift up or left. The scrollbars move, too. See [details](Image_Drift.md). *SEEMS TO BE RESOLVED*
- [ ] **[P1]**  After making an MPR in a window, clearing it, then making a new MPR in that window using a different series, the default (embedded) window/level from the first base series was applied instead of from the second.
- [ ] **[P0]** If the base series for an MPR uses rescaled pixel values, the MPR pixel values should be rescaled the same way ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-planar-reconstructions-mprs-and-oblique-reconstructions))
- [ ] **[P0]** ROI focus bug: when changing subwindows, selected ROI should auto-unselect and right-pane statistics should clear ([details](FUTURE_WORK_DETAIL_NOTES.md#roi-selection-behavior-across-subwindows))
- [ ] **[P0]** After creating MPRs, clearing, closing all files, and loading new files, creating new MPR does not load/display ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-planar-reconstructions-mprs-and-oblique-reconstructions))
- [ ] **[P1]** Investigate ~10 second lag before loading progress window appears when loading PET/CT study
- [ ] **[P1]** Klaus reported Windows error about a file with "gemini" in the name
- [ ] **[P1]** Check for any hardcoded absolute paths (including resources like images/icons)

## Performance / Packaging

- [ ] **[P1]** Try to make code faster (startup, file loading, fusion, and general responsiveness) ([details](FUTURE_WORK_DETAIL_NOTES.md#performance-initial-load-file-loading-fusion-and-general-responsiveness))
- [ ] **[P2]** See if executables can be made smaller (especially on macOS) ([details](FUTURE_WORK_DETAIL_NOTES.md#executable-size-especially-on-macos))
- [ ] **[P1]** Check fusion responsiveness on Parallels with 3D fusion

## UX / Workflow

- [ ] **[P2]** Make window map thumbnail in navigator interactive (click square to focus and reveal)
- [ ] **[P2]** Make toolbar contents and ordering customizable
- [ ] **[P1]** Add alternative window/level interaction (e.g., hold W + drag, or middle/right drag)
- [ ] **[P1]** Set min/max window width/level using min/max pixel value (raw or rescaled)
- [ ] **[P1]** Add overlay configuration to image right-click context menu
- [ ] **[P1]** Differentiate frame # vs slice # in UI and backend ([details](FUTURE_WORK_DETAIL_NOTES.md#differentiating-frame--vs-slice))
- [ ] **[P2]** Make right pane minimum width before collapsing 250 instead of 200
- [ ] **[P2]** Consider more sophisticated smoothing (PIL/NumPy) vs Qt-only scaling

## Features (Near-Term)

- [ ] **[P0]** Add simple launcher to root directory
- [ ] **[P2]** Add option to choose font from included ones in resources/fonts
- [ ] **[P2]** Add basic image processing for creating new DICOMs (kernels, smoothing, edge enhancement, sharpening, custom kernels) ([details](FUTURE_WORK_DETAIL_NOTES.md#basic-image-processing-and-creating-new-dicoms))
- [ ] **[P2]** Integrate pylinac and other automated QC analysis tools ([details](FUTURE_WORK_DETAIL_NOTES.md#integrating-pylinac-and-other-automated-qc-tools))
- [ ] **[P1]** Add ability to save MPRs as DICOM
- [ ] **[P1]** Support key image features on MPRs (ROIs, slice combining, window/level ROI)
- [ ] **[P2]** Enable export mpg/gif/avi for cine
- [ ] **[P2]** Add measure angle
- [ ] **[P2]** Add scale markers on left and bottom (small ticks every image mm, large every cm)
- [ ] **[P2]** Add direction labels (A/P/L/R/S/I)
- [ ] **[P2]** Allow flipping and rotating image
- [ ] **[P2]** Make default line thicknesses and annotation font sizes a bit smaller
- [ ] **[P2]** Interactive oblique rotation on MPR (drag handles/crosshairs) ([details](FUTURE_WORK_DETAIL_NOTES.md#interactive-oblique-rotation-on-mpr))
- [ ] **[P2]** Measurements and ROI tools on MPR subwindows ([details](FUTURE_WORK_DETAIL_NOTES.md#measurements-and-roi-tools-on-mpr))
- [ ] **[P2]** Combine slices on MPR (MIP/MinIP/AIP options) ([details](FUTURE_WORK_DETAIL_NOTES.md#combine-slices-on-mpr-mipminipaip))
- [ ] **[P2]** Fusion overlays on MPR views ([details](FUTURE_WORK_DETAIL_NOTES.md#fusion-on-mpr))
- [ ] **[P2]** Advanced ROI/contouring roadmap (contouring, auto-detect ROI, 3D ROI across views) ([details](FUTURE_WORK_DETAIL_NOTES.md#advanced-roi-and-contouring))

## Data / Platform (Future)

- [ ] **[P2]** PACS-like query/archive capabilities ([details](FUTURE_WORK_DETAIL_NOTES.md#pacs-like-query-and-archive-integration))
- [ ] **[P2]** Local study database and indexing/search workflow ([details](FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing))
- [ ] **[P2]** Multi-tab / multi-workspace study sessions ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-workspace--multi-tab-study-sessions))

## Fusion Follow-up

- [ ] **[P1]** Check visual registration accuracy on usual PET/CT studies in 2D vs 3D
- [ ] **[P2]** Ask AI/cloud agent to estimate registration differences for sample PET-to-CT points and capture screenshots
- [ ] **[P1]** Check fusion with additional studies
- [ ] **[P1]** Improve Window/Level preset/auto behavior in fusion mode

## Release / Product

- [ ] **[P2]** See IMAIOS (iOS) disclaimer as an example
- [ ] **[P2]** Reduce old backup files
- [ ] **[P1]** Figure out license
- [ ] **[P0]** Make versioned release with exectutables
- [ ] **[P2]** Announce on LinkedIn and share with people
- [ ] **[P2]** Build a technical guide ([details](FUTURE_WORK_DETAIL_NOTES.md#technical-guide-scope))
- [ ] **[P2]** Naming exploration: "DICOM Viewer + ?" ([details](FUTURE_WORK_DETAIL_NOTES.md#product-naming-exploration))