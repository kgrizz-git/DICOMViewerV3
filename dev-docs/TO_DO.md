# To-Do Checklist

**Last updated:** 2026-04-09  
**Changes:** P0 macOS PyInstaller A/B size + build-time exclude strategy under Performance / Packaging.

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

## Performance / Packaging

- [ ] **[P0]** **macOS PyInstaller — A/B `du` and safety:** On macOS, from the **same git ref**, build twice: (1) **current** spec with **`MACOS_PYSIDE6_MODULE_EXCLUDES`** applied, (2) a branch or env-gated spec that **does not** apply those darwin-only excludes. Compare **`du -sh dist/DICOMViewerV3.app`** (and top `Frameworks/` contributors); record numbers in **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**. **Smoke both** `.app` builds (launch, open DICOM, histogram, export/QA paths). *Why:* PyInstaller usually **does not** ship modules that never appear in the import graph, so excludes may save **little** until hooks/deps pull extra Qt; but **`excludes` can still cause `ImportError`** if any code path (including a **third-party** lazy import) touches a trimmed module — so **prefer default = include everything PyInstaller collects** and treat aggressive macOS trims as a **build-time opt-in** (e.g. env var or spec flag) only after A/B numbers justify it and smoke passes on the slim build.
- [ ] **[P1]** Try to make code faster (startup, file loading, fusion, and general responsiveness) ([details](FUTURE_WORK_DETAIL_NOTES.md#performance-initial-load-file-loading-fusion-and-general-responsiveness))
    - [P2] Particularly w/ large dataset (large files or many files) - would loading compressed initially save time? If we make a database, keep compressed cache?
- [ ] **[P0]** See if executables can be made smaller (especially on macOS) ([details](FUTURE_WORK_DETAIL_NOTES.md#executable-size-especially-on-macos))
- [ ] **[P1]** Check fusion responsiveness on Parallels with 3D fusion

## Maintenance

- [ ] **[P1]** Review what is included in git repo unnecessarily
- [ ] **[P1]** Massively trim down old backup files, possibly exclude from git
- [ ] **[P1]** Regularly run all scan templates and update TO_DO.md
- [ ] **[P1]** Examine github actions, CI, CD, etc., and look for opportunities to optimize, simplify, or improve, including reducing use of limited storage quota
- [ ] **[P1]** Check for pyright warnings, errors - run pyright

## UX / Workflow

- [x] **[P1]** make slice display lines able to show middle of slice (or slab when combining) or begin and end of slice (or slab when combining) *(Done: Added slice position line mode config (middle/begin-end) with UI in overlay config dialog and updated rendering logic.)*
- [x] **[P1]** Should be able to right-click and select "Clear Subwindow" or something (check whether in-app we call them windows or subwindows) to clear current images/series from a given subwindow. *(Done: **Clear This Window** in image context menu; in-app user strings use “Window”.)*
- [x] **[P1]** Add thumbnail for an MPR view in the navigator. Make it clickable and draggable like other thumbnails. Indicate it is an MPR in some way (like a little floating MPR tag similar to what is shown in the viewer but smaller). *(Done: Added `MprThumbnailWidget` in `src/gui/mpr_thumbnail_widget.py` with MPR badge overlay and subwindow dot indicator. `SeriesNavigator` has a persistent MPR section with `set_mpr_thumbnail`/`clear_mpr_thumbnail`. `MprController` emits `mpr_activated`/`mpr_cleared` signals. Clicking focuses the MPR subwindow; dragging to a subwindow emits `application/x-dv3-mpr-assign` MIME handled by `SubWindowContainer.mpr_focus_requested`.)*
    - [ ] **[P1]** Cannot click or drag to assign to new window. Also cannot clear window without deleting MPR.
- [ ] **[P1]** Add option to have one large window on left and two smaller on right (above and below), or one large window on top and smaller on bottom (left and right), and maybe vice versa for each case. Make "2" key switch between 1x2 and 2x1, while "3" switches between different 3-window layouts just described.
- [ ] **[P2]** Make window map thumbnail in navigator interactive (click square to focus and reveal) ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#1-window-map-thumbnail-interactive))
- [ ] **[P2]** Make toolbar contents and ordering customizable ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#2-toolbar-customization))
- [ ] **[P2]** Improve discoverability/documentation of existing window/level drag interaction ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#3-alternative-windowlevel-interaction))
- [ ] **[P1]** Set min/max window width/level using min/max pixel value possible (raw or rescaled) based on bit depth ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#4-minmax-windowlevel-from-bit-depth))
- [x] **[P1]** Add overlay configuration to image right-click context menu ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#5-overlay-configuration-in-right-click-context-menu)) *(Done: Added "Overlay Configuration" submenu with Overlay Settings… and Configure Overlay Tags… entries to image right-click context menu.)*
- [ ] **[P2]** Make default line thicknesses and annotation font sizes smaller (for ROIs, text annotation, measurements) - say line thickness 3 and font size 12 ([plan](plans/UX_IMPROVEMENTS_BATCH1_PLAN.md#6-reduce-default-line-thicknesses-and-font-sizes))
- [ ] **[P2]** Follow-up for multi-frame instance navigation: audit ROI / measurement / annotation / cine / projection code paths that use `current_slice_index` as slice identity before attempting bounded per-instance scrolling ([plan](plans/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md#phase-4-show-instances-separately-toggle-and-config))
- [ ] **[P2]** Make right pane minimum width before collapsing 250 instead of 200
- [ ] **[P2]** Consider more sophisticated smoothing (PIL/NumPy) vs Qt-only scaling
- [ ] **[P2]** Add ability to edit a drawn ellipse or rectangle ROI ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#1-roi-editing-resize-handles))
- [ ] **[P2]** Make window/level settings remembered when switching series and then switching back ([plan](plans/VIEWER_UX_FEATURES_PLAN.md#2-windowlevel-remembered-per-series))
- [ ] **[P1]** Hovering on a study label in the navigator should show a popup tooltip with the study description, date, and patient name (but should respect privacy mode). Hovering on a thumbnail should show a tooltip with that same info, plus series description ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#1-navigator-tooltips-privacy-aware))
- [ ] **[P2]** The toast that pops up when already loaded files are skipped and not added during loading should appear in the center of the screen and have a slightly more opaque background ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#2-duplicate-skip-toast-center--more-opaque))
- [ ] **[P1]** Make the large-file warning (and any related file handling checks) trigger for >50 MB instead of 25 MB ([plan](plans/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#3-large-file-warning-threshold-50-mb)) - *NOTE: maybe hold off on this for now - 50 might be too high?*
- [ ] **[P2]** Allow further subdivision of subwindows into up to 4 "tiles"? ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#1-subwindow-further-subdivision-up-to-4-tiles))
- [ ] **[P1]** Make a "View Fullscreen" menu item and shortcut - make app full-screen, hide left/right/bottom panes, toolbar ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#2-view-fullscreen-command-and-shortcut))
- [ ] **[P2]** When show instances separately is enabled, allow left/right keys to switch between instances ([plan](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#4-leftright-keys-for-instance-switching-show-instances-separately)) **(already done?)**
- [ ] **[P2]** When exporting PNG or JPG, allow anonymization and make using embedded window/level the default option ([plan](plans/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md#goal))
- [ ] **[P2]** Make default pixel size and slice thickness more reasonable and make editing them easier (default to 1.0 mm, 1.0 mm?)
- [ ] **[P2]** Make a Settings menu for grouping lots of options?
- [ ] **[P2]** Consider a dedicated **Pylinac Configuration...** menu/dialog if more persisted QA customization options are added (likely), so pylinac/site defaults do not keep expanding the per-analysis Tools dialogs.
- [ ] **[P2]** Allow dragging window dividers to make unequal divisions
- [ ] **[P2]** Add ability to use toolbar icons 
- [ ] **[P2]** Show a small colored icon on each subwindow title bar in a "sync group"to indicate which group it belongs to (group color), so the user can see at a glance which windows are linked.
- [ ] **[P1]** Add **"Create MPR view…"** to the **Tools** or **View** menu?
- [ ] **[P1]** Add ability to customize slice position display line thickness
- [ ] **[P1]** Differentiate between frames, instances, and slices in the cine player
- [ ] **[P2]** Add option to show # frames or slices in a series in navigator? 
- [ ] **[P2]** Where is it getting frame rate from?
- [ ] **[P1]** Should we block showing DICOM tags when an MPR window is selected (show just "MPR")? Or add some kind of warning that it is the underlying series data somehow?
- [ ] **[P1]** Make spacebar cycle overlay visibility state on all windows?

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
- [ ] **[P2]** For ROIs, allow computing and displaying stats per color channel (RGB, etc.) (off by default, can be enabled in settings)
- [ ] **[P2]** For screenshot export, allow choosing to export multi-window view as single image, as well. Maybe also entire application window as single image, including left/right panes and toolbar etc (if currently displayed).
- [ ] **[P2]** In overlay  config, allow something like "simple view" and "detailed view", where additional tags can be shown, and spacebar cycles through simple, detailed, and hidden views.
- [ ] **[P2]** When projection is enabled, allow to show projection pixel values on histogram.
- [ ] **[P2]** Enable adding multiple images distributions to histogram for comparison (probably via button histogram). Use different colors for each distribution.
- [ ] **[P2]** Add toggle/preference to have up/down keys and scroll wheel up/down navigate by slice # or image position patient (eg, if increasing slice # has decreasing image position patient along the orientation vector, allow choosing whether up moves up in slice number (and lower on patient), or up in image position patient (and lower on slice number)).

## Documentation

**Plan (2026-04-03):** [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md) — README slimming, `tests/README.md`, in-app Quick Start (TOC + browser links), `user-docs/` hub, MPR + pylinac user guides.

- [ ] **[P1]** Conduct documentation audit to ensure all features are documented and up to date.
- [x] **[P1]** Introduce Help → Documentation, shorten Quick Start (`resources/help/quick_start_guide.html`), link to full docs in browser — see [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md).
- [x] **[P1]** Add documentation for the pylinac integration and the automated QA analysis tools — [user-docs/USER_GUIDE_QA_PYLINAC.md](../user-docs/USER_GUIDE_QA_PYLINAC.md) (developer depth remains in `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`).
- [x] **[P1]** Add documentation for the MPR features — [user-docs/USER_GUIDE_MPR.md](../user-docs/USER_GUIDE_MPR.md).
- [ ] **[P2]** implement offline doc bundle + `file://` and policy in `BUILDING_EXECUTABLES.md` / installer notes. 


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