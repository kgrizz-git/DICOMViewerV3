# To-Do Checklist

**Last updated:** 2026-03-16  
**Changes:** Reorganized into active categories; rolled FUTURE_WORK items into this checklist; added detail-note section links.

---

## Purpose

This file tracks active and near-term tasks.

- Detailed implementation notes and tradeoffs: [FUTURE_WORK_DETAIL_NOTES.md](FUTURE_WORK_DETAIL_NOTES.md)

## Priority Legend

- **P0** = critical
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
- [ ] **[P0]** After creating MPRs, clearing, closing all files, and loading new files, creating new MPR does not load/display ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-planar-reconstructions-mprs-and-oblique-reconstructions))

- [ ] **[P0]** REFACTORING SMOKE TESTS:
    - Launch app, open one study by file and by folder, confirm first image displays.
    - Toggle privacy mode and confirm overlays/metadata hide correctly.
    - Open overlay config and quick window/level dialog from focused pane.
    - Open export dialog and verify it opens with populated options.
    - Open tag export dialog, perform CSV export with one small study.
    - Open quick start and fusion docs, verify content renders.

## Performance / Packaging

- [ ] **[P1]** Try to make code faster (startup, file loading, fusion, and general responsiveness) ([details](FUTURE_WORK_DETAIL_NOTES.md#performance-initial-load-file-loading-fusion-and-general-responsiveness))
    - [P2] Particularly w/ large dataset (large files or many files) - would loading compressed initially save time? If we make a database, keep compressed cache?
- [ ] **[P2]** See if executables can be made smaller (especially on macOS) ([details](FUTURE_WORK_DETAIL_NOTES.md#executable-size-especially-on-macos))
- [ ] **[P1]** Check fusion responsiveness on Parallels with 3D fusion

## UX / Workflow

- [ ] **[P2]** Make window map thumbnail in navigator interactive (click square to focus and reveal) ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#1-window-map-thumbnail-interactive))
- [ ] **[P2]** Make toolbar contents and ordering customizable ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#2-toolbar-customization))
- [ ] **[P2]** Improve discoverability/documentation of existing window/level drag interaction ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#3-alternative-windowlevel-interaction))
- [ ] **[P1]** Set min/max window width/level using min/max pixel value possible (raw or rescaled) based on bit depth ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#4-minmax-windowlevel-from-bit-depth))
- [ ] **[P1]** Add overlay configuration to image right-click context menu ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#5-overlay-configuration-in-right-click-context-menu))
- [ ] **[P2]** Make default line thicknesses and annotation font sizes smaller (for ROIs, text annotation, measurements) - say line thickness 3 and font size 12 ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#6-reduce-default-line-thicknesses-and-font-sizes))
- [ ] **[P1]** Differentiate frame # vs slice # (maybe also consider instance #, acquisition number, anything else?) in UI and backend ([details](FUTURE_WORK_DETAIL_NOTES.md#differentiating-frame--vs-slice)) See CCL2 example datset for one example - seems to be grouping by file or instance number, and each of those have multiple frames - all have same series number. Maybe we should separate in the navigator by series AND by instance number? No, others like VC192 dataset have instance number corresponding to slice number. So maybe separate by series and instance if instances have multiple frames? Make it an option (via right-click context menu in navigator and View menu)?
- [ ] **[P2]** Follow-up for multi-frame instance navigation: audit ROI / measurement / annotation / cine / projection code paths that use `current_slice_index` as slice identity before attempting bounded per-instance scrolling ([plan](plans/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md#phase-4-show-instances-separately-toggle-and-config))
- [ ] **[P2]** Make right pane minimum width before collapsing 250 instead of 200
- [ ] **[P2]** Consider more sophisticated smoothing (PIL/NumPy) vs Qt-only scaling
- [ ] **[P2]** Add ability to edit a drawn ellipse or rectangle ROI ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#1-roi-editing-resize-handles))
- [ ] **[P2]** Make window/level settings remembered when switching series and then switching back ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#2-windowlevel-remembered-per-series))
- [ ] **[P1]** Add scale markers on left and bottom (small ticks every image mm, large every cm) ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#3-scale-markers-ruler-ticks))
- [ ] **[P1]** Add direction labels (A/P/L/R/S/I) on viewer window ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#4-direction-labels-aplrsi))
- [ ] **[P2]** Allow flipping and rotating image ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#5-flip-and-rotate-image))
- [ ] **[P1]** Slice / frame slider bars in subwindows - ideally only appears when you mouse over near some edge of the window (right?) ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#6-subwindow-slice--frame-slider-bars))
- [ ] **[P1]** Hovering on a study label in the navigator should show a popup tooltip with the study description, date, and patient name (but should respect privacy mode). Hovering on a thumbnail should show a tooltip with that same info, plus series description ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#1-navigator-tooltips-privacy-aware))
- [ ] **[P2]** The toast that pops up when already loaded files are skipped and not added during loading should appear in the center of the screen and have a slightly more opaque background ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#2-duplicate-skip-toast-center--more-opaque))
- [ ] **[P1]** Make the large-file warning (and any related file handling checks) trigger for >50 MB instead of 25 MB ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#3-large-file-warning-threshold-50-mb)) - *NOTE: maybe hold off on this for now - 50 might be too high?*
- [ ] **[P2]** Allow further subdivision of subwindows into up to 4 "tiles"?
- [ ] **[P1]** Make a "View Fullscreen" menu item and shortcut - make app full-screen, hide left/right/bottom panes, toolbar
- [ ] **[P2]** Give options for slice position lines on windows to show middle of slice or begin and end
- [ ] **[P2]** When show instances separately is enabled, allow left/right keys to switch between instances


## Features (Near-Term)

- [ ] **[P1]** Be able to associate with DICOM extension and add to Open With menus ([details](FUTURE_WORK_DETAIL_NOTES.md#file-association-and-open-with-integration))
- [ ] **[P2]** Add basic image processing for creating new DICOMs (kernels, smoothing, edge enhancement, sharpening, custom kernels) ([details](FUTURE_WORK_DETAIL_NOTES.md#basic-image-processing-and-creating-new-dicoms))
- [ ] **[P2]** Integrate pylinac and other automated QC analysis tools ([details](FUTURE_WORK_DETAIL_NOTES.md#integrating-pylinac-and-other-automated-qc-tools))
- [ ] **[P1]** Add ability to save MPRs as DICOM
- [ ] **[P1]** Enable export mpg/gif/avi for cine
- [ ] **[P2]** Add measure angle as another measurement/annoation - user clicks, line extends, clicks again to drop a second point, another line extends from there, click a third time to create endpoint. angle between these two line segments is measured and reported on-screen. can use same settings (color, line thickness, etc) as the measurement tool
- [ ] **[P2]** Interactive oblique rotation on MPR (drag handles/crosshairs) ([details](FUTURE_WORK_DETAIL_NOTES.md#interactive-oblique-rotation-on-mpr))
- [ ] **[P2]** Add measurements and ROI tools on MPR subwindows, including window/level ROIs ([details](FUTURE_WORK_DETAIL_NOTES.md#measurements-and-roi-tools-on-mpr))
- [ ] **[P1]** Combine slices on MPR (MIP/MinIP/AIP options) ([details](FUTURE_WORK_DETAIL_NOTES.md#combine-slices-on-mpr-mipminipaip))
- [ ] **[P2]** Fusion overlays on MPR views ([details](FUTURE_WORK_DETAIL_NOTES.md#fusion-on-mpr))
- [ ] **[P2]** Advanced ROI/contouring roadmap (contouring, auto-detect ROI, 3D ROI across views) ([details](FUTURE_WORK_DETAIL_NOTES.md#advanced-roi-and-contouring))
- [ ] **[P2]** Allow hanging protocols? Configuration of windows/tiles, certain views/phases/priors loaded
- [ ] **[P2]** Once database is added, allow pulling priors
- [ ] **[P1]** Also try RDSR parsing/export support - have some examples, add to repo

## Data / Platform (Future)

- [ ] **[P2]** PACS-like query/archive capabilities ([details](FUTURE_WORK_DETAIL_NOTES.md#pacs-like-query-and-archive-integration))
- [ ] **[P1]** Local study database and indexing/search workflow ([details](FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing))
- [ ] **[P2]** Multi-tab / multi-workspace study sessions ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-workspace--multi-tab-study-sessions))
- [ ] **[P2]** Enhanced multi-frame IOD navigation (Tier 3): parse `PerFrameFunctionalGroupsSequence` / `SharedFunctionalGroupsSequence` to reconstruct per-frame spatial and temporal metadata; enable independent 2D-axis navigation (scroll = slice axis, Alt+scroll = secondary axis such as time or b-value) ([details](FUTURE_WORK_DETAIL_NOTES.md#differentiating-frame--vs-slice--vs-instance-))

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