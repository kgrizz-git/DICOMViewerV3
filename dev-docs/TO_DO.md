# To-Do Checklist

**Last updated:** 2026-03-27  
**Changes:** Linked Stage 1 plan for pylinac + automated QA (`plans/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md`).

---

## Purpose

This file tracks active and near-term tasks.

- Detailed implementation notes and tradeoffs: [FUTURE_WORK_DETAIL_NOTES.md](FUTURE_WORK_DETAIL_NOTES.md)
- Parallel implementation ownership/workstreams: [plans/PARALLEL_WORKSTREAM_OWNERSHIP_PLAN.md](plans/PARALLEL_WORKSTREAM_OWNERSHIP_PLAN.md)

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
- [ ] **[P1]** Should we block showing DICOM tags when an MPR window is selected (show just "MPR")? Or add some kind of warning that it is the underlying series data somehow?
- [ ] **[P0]** After creating MPRs, clearing, closing all files, and loading new files, creating new MPR does not load/display ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-planar-reconstructions-mprs-and-oblique-reconstructions)) *NOTE: seems fixed*
- [ ] **[P0]** "Close All" did not clear thumbnails in layout map
- [ ] **[P1]** Fusion seems to add two sets of scale markers? Or for some reason markers look too dense. Goes away when focusing on window, reappaears when unfocused. Appears (and disappears) on windows without fusion enabled as well (maybe only ones showing same series as fusion base or overlay).
- [ ] **[P1]** Found one weird instance of slice markers not being correct - QAMR the 3-plane loc when displaying axial slices shows lines on T1 and T2 axial when they display the same approximate slice location, and vice versa - they position and slope of the lines are the same on both. Saved a screenshot. Lines are angled (not vertical or horizontal) and offset from center of image. IOP for T1 [0.99986, -0.00006, -0.01671, 0.00011, 1.00000, 0.00290], for 3-plane axial slice [1.00000, -0.00000, 0.00000, -0.00000, 1.00000, 0.00000] - maybe it is correct. IPP for 3-plane [-124.5117034912, -124.5117034912, 10.0000000000], for T1 is [-123.6437759399, -129.4394531250, 10.5523557663]. *NOTE: seems correct actually -slightly angled. Took another screenshot.*
- [ ] **[P1]** Fusion not working for T2 dual-echo as base series (QAMR) - no T1 overlay appears. It did after switching to T2 as overlay (still on T2) and then back to T1.

## Performance / Packaging

- [ ] **[P1]** Try to make code faster (startup, file loading, fusion, and general responsiveness) ([details](FUTURE_WORK_DETAIL_NOTES.md#performance-initial-load-file-loading-fusion-and-general-responsiveness))
    - [P2] Particularly w/ large dataset (large files or many files) - would loading compressed initially save time? If we make a database, keep compressed cache?
- [ ] **[P2]** See if executables can be made smaller (especially on macOS) ([details](FUTURE_WORK_DETAIL_NOTES.md#executable-size-especially-on-macos))
- [ ] **[P1]** Check fusion responsiveness on Parallels with 3D fusion


## Maintenance

- [ ] **[P1]** Review what is included in git repo unnecessarily
- [ ] **[P1]** Massively trim down old backup files, possibly exclude from git
- [ ] **[P1]** Regularly run all scan templates and update TO_DO.md
- [ ] **[P1]** Examine github actions, CI, CD, etc., and look for opportunities to optimize, simplify, or improve, including reducing use of limited storage quota
- [ ] **[P1]** Check for pyright warnings, errors - run pyright

## UX / Workflow

- [ ] **[P2]** Make window map thumbnail in navigator interactive (click square to focus and reveal) ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#1-window-map-thumbnail-interactive))
- [ ] **[P2]** Make toolbar contents and ordering customizable ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#2-toolbar-customization))
- [ ] **[P2]** Improve discoverability/documentation of existing window/level drag interaction ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#3-alternative-windowlevel-interaction))
- [ ] **[P1]** Set min/max window width/level using min/max pixel value possible (raw or rescaled) based on bit depth ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#4-minmax-windowlevel-from-bit-depth))
- [ ] **[P1]** Add overlay configuration to image right-click context menu ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#5-overlay-configuration-in-right-click-context-menu))
- [ ] **[P2]** Make default line thicknesses and annotation font sizes smaller (for ROIs, text annotation, measurements) - say line thickness 3 and font size 12 ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#6-reduce-default-line-thicknesses-and-font-sizes))
- [ ] **[P2]** Follow-up for multi-frame instance navigation: audit ROI / measurement / annotation / cine / projection code paths that use `current_slice_index` as slice identity before attempting bounded per-instance scrolling ([plan](plans/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md#phase-4-show-instances-separately-toggle-and-config))
- [ ] **[P2]** Make right pane minimum width before collapsing 250 instead of 200
- [ ] **[P2]** Consider more sophisticated smoothing (PIL/NumPy) vs Qt-only scaling
- [ ] **[P2]** Add ability to edit a drawn ellipse or rectangle ROI ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#1-roi-editing-resize-handles))
- [ ] **[P2]** Make window/level settings remembered when switching series and then switching back ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#2-windowlevel-remembered-per-series))
- [ ] **[P2]** Allow flipping and rotating image ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#5-flip-and-rotate-image))
- [ ] **[P1]** Slice / frame slider bars in subwindows - ideally only appears when you mouse over near some edge of the window (right?) ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#6-subwindow-slice--frame-slider-bars))
- [ ] **[P1]** Hovering on a study label in the navigator should show a popup tooltip with the study description, date, and patient name (but should respect privacy mode). Hovering on a thumbnail should show a tooltip with that same info, plus series description ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#1-navigator-tooltips-privacy-aware))
- [ ] **[P2]** The toast that pops up when already loaded files are skipped and not added during loading should appear in the center of the screen and have a slightly more opaque background ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#2-duplicate-skip-toast-center--more-opaque))
- [ ] **[P1]** Make the large-file warning (and any related file handling checks) trigger for >50 MB instead of 25 MB ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#3-large-file-warning-threshold-50-mb)) - *NOTE: maybe hold off on this for now - 50 might be too high?*
- [ ] **[P2]** Allow further subdivision of subwindows into up to 4 "tiles"? ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#1-subwindow-further-subdivision-up-to-4-tiles))
- [ ] **[P1]** Make a "View Fullscreen" menu item and shortcut - make app full-screen, hide left/right/bottom panes, toolbar ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#2-view-fullscreen-command-and-shortcut))
- [ ] **[P2]** Give options for slice position lines on windows to show middle of slice or begin and end ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#3-slice-position-line-display-options-middle-vs-beginend))
- [ ] **[P2]** When show instances separately is enabled, allow left/right keys to switch between instances ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#4-leftright-keys-for-instance-switching-show-instances-separately))
- [ ] **[P2]** When exporting PNG or JPG, allow anonymization and make using embedded window/level the default option ([plan](plans/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md#goal))
- [ ] **[P2]** Make default pixel size and slice thickness more reasonable and make editing them easier (default to 1.0 mm, 1.0 mm?)
- [ ] **[P2]** Make a Settings menu for grouping lots of options?
- [ ] **[P2]** Consider a dedicated **Pylinac Configuration...** menu/dialog if more persisted QA customization options are added (likely), so pylinac/site defaults do not keep expanding the per-analysis Tools dialogs.
- [ ] **[P2]** Allow dragging window dividers to make unequal divisions
- [ ] **[P2]** Enable right-click on a Recent menu item to open context menu to remove it from the recent list
- [ ] **[P2]** Add ability to use toolbar icons 
- [ ] **[P0]** Menu item "Show Lines" should say "Show Slice Location Lines"


## Features (Near-Term)


- [ ] **[P1]** Add a "Deep Anonymizer" export option that strips out all tag data that could be used to indentify a scanner, institution, address, etc., as well as patient informaion. Should include institution name, address, station name, device serial number, etc.
- [ ] **[P1]** Add a simple "DICOM metadata browser" mode that can ingest, browse, and export DICOM metadata, without any image display or processing (hopefully fast and efficient)
- [x] **[P2]** ACR MRI compare mode: run low-contrast analysis with up to 3 parameter sets; comparison table dialog, compare JSON export (schema 1.2), and PDF notes ([plan](plans/PYLINAC_MRI_COMPARE_RUNS_AND_PDF_INTERPRETATION_PLAN.md))
- [ ] **[P1]** Be able to associate with DICOM extension and add to Open With menus ([details](FUTURE_WORK_DETAIL_NOTES.md#file-association-and-open-with-integration))
- [ ] **[P2]** Add basic image processing for creating new DICOMs (kernels, smoothing, edge enhancement, sharpening, custom kernels) ([details](FUTURE_WORK_DETAIL_NOTES.md#basic-image-processing-and-creating-new-dicoms))
- [ ] **[P2]** Integrate pylinac and other automated QC analysis tools ([details](FUTURE_WORK_DETAIL_NOTES.md#integrating-pylinac-and-other-automated-qc-tools), [pylinac integration overview](info/PYLINAC_INTEGRATION_OVERVIEW.md), [additional automated QA analysis (ACR gaps + CT checks)](info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md), [Stage 1 implementation plan](plans/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md))
- [ ] **[P2]** Make more robust to pylinac errors and processing limitations—for example, if pylinac expects at least a 100 mm scan extent but the scan extent is 99.5 mm, find a way to still run analysis and report results (see [pylinac flexibility & workarounds](info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md)).
- [ ] **[P1]** Add ability to save MPRs as DICOM ([plan](plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md#1-save-mprs-as-dicom))
- [ ] **[P1]** Enable export mpg/gif/avi for cine ([plan](plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md#2-cine-video-export-mpg-gif-avi))
- [ ] **[P2]** Add measure angle as another measurement/annoation - user clicks, line extends, clicks again to drop a second point, another line extends from there, click a third time to create endpoint. angle between these two line segments is measured and reported on-screen. can use same settings (color, line thickness, etc) as the measurement tool ([plan](plans/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md#3-angle-measurement-tool))
- [ ] **[P2]** Interactive oblique rotation on MPR (drag handles/crosshairs) ([details](FUTURE_WORK_DETAIL_NOTES.md#interactive-oblique-rotation-on-mpr))
- [ ] **[P2]** Fusion overlays on MPR views ([details](FUTURE_WORK_DETAIL_NOTES.md#fusion-on-mpr))
- [ ] **[P2]** Advanced ROI/contouring abilities (contouring, auto-detect ROI, 3D ROI across views) ([details](FUTURE_WORK_DETAIL_NOTES.md#advanced-roi-and-contouring))
- [ ] **[P2]** Allow hanging protocols? Configuration of windows/tiles, certain views/phases/priors loaded ([plan](plans/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#1-hanging-protocols))
- [ ] **[P2]** Once database is added, allow pulling priors ([plan](plans/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#2-pulling-priors-after-local-database))
- [ ] **[P1]** Also try RDSR parsing/export support - have some examples, add to repo ([plan](plans/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#3-rdsr-parsing-and-export))
- [ ] **[P1]** Allow some configuration to interpret MTF results (separately for MRI and CT) where the user needs to review some images along with pylinac MTF plots and decide the "visibility cutoff" MTF value which they think corresponds to the limit of visibility and we report the (interpolated) spatial frequency that gives that MTF value, OR we could have them define a "passing" MTF value and state which inserts pass/fail a visibility check based on that. ([details](FUTURE_WORK_DETAIL_NOTES.md#interpreting-mtf-results))

## Documentation

**Plan (2026-04-03):** [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md) — README slimming, `tests/README.md`, in-app Quick Start (TOC + browser links), `user-docs/` hub, MPR + pylinac user guides.

- [ ] **[P1]** Conduct documentation audit to ensure all features are documented and up to date.
- [x] **[P1]** Introduce Help → Documentation, shorten Quick Start (`resources/help/quick_start_guide.html`), link to full docs in browser — see [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md).
- [x] **[P1]** Add documentation for the pylinac integration and the automated QA analysis tools — [user-docs/USER_GUIDE_QA_PYLINAC.md](../user-docs/USER_GUIDE_QA_PYLINAC.md) (developer depth remains in `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`).
- [x] **[P1]** Add documentation for the MPR features — [user-docs/USER_GUIDE_MPR.md](../user-docs/USER_GUIDE_MPR.md).


## Data / Platform (Future)

- [ ] **[P2]** Add some sample DICOMs
- [ ] **[P2]** PACS-like query/archive capabilities ([details](FUTURE_WORK_DETAIL_NOTES.md#pacs-like-query-and-archive-integration))
- [ ] **[P1]** Local study database and indexing/search workflow ([details](FUTURE_WORK_DETAIL_NOTES.md#local-study-database-and-indexing))
- [ ] **[P2]** Multi-tab / multi-workspace study sessions ([details](FUTURE_WORK_DETAIL_NOTES.md#multi-workspace--multi-tab-study-sessions))
- [ ] **[P2]** Enhanced multi-frame IOD navigation (Tier 3): parse `PerFrameFunctionalGroupsSequence` / `SharedFunctionalGroupsSequence` to reconstruct per-frame spatial and temporal metadata; enable independent 2D-axis navigation (scroll = slice axis, Alt+scroll = secondary axis such as time or b-value) ([details](FUTURE_WORK_DETAIL_NOTES.md#differentiating-frame--vs-slice--vs-instance-))


## Fusion Follow-up

- [ ] **[P1]** Check visual registration accuracy on usual PET/CT studies in 2D vs 3D
- [ ] **[P2]** Ask AI/cloud agent to estimate registration differences for sample PET-to-CT points and capture screenshots
- [ ] **[P1]** Check fusion with additional studies
- [ ] **[P1]** Improve Window/Level preset/auto behavior in fusion mode
- [ ] **[P1]** Use slice sync to quick check fusion on several studies


## Release / Product

- [ ] **[P2]** See IMAIOS (iOS) disclaimer as an example
- [ ] **[P2]** Reduce old backup files
- [ ] **[P1]** Figure out license
- [ ] **[P0]** Make versioned release with exectutables
- [ ] **[P2]** Announce on LinkedIn and share with people
- [ ] **[P2]** Build a technical guide ([details](FUTURE_WORK_DETAIL_NOTES.md#technical-guide-scope))
- [ ] **[P2]** Naming exploration: "DICOM Viewer + ?" ([details](FUTURE_WORK_DETAIL_NOTES.md#product-naming-exploration))