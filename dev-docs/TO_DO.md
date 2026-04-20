# To-Do Checklist

**Last updated:** 2026-04-17  
**Changes:** PySkinDose P1 links to [`plans/supporting/PYSKINDOSE_INTEGRATION_PLAN.md`](plans/supporting/PYSKINDOSE_INTEGRATION_PLAN.md) only; highdicom/SR item points at SR plans directly. *(Prior: 2026-04-16 — moved linked implementation plans into [`plans/supporting/`](plans/supporting/) and refreshed `plans/…` links; unequal pane splitters + cine axes linked to [`SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md`](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md); 2026-04-15: RDSR shipped, ROI per-channel stats shipped, histogram projection pixels shipped, export formula-injection hardening.)*

---

## Purpose

This file tracks active and near-term tasks.

- Detailed implementation notes and tradeoffs: [FUTURE_WORK_DETAIL_NOTES.md](FUTURE_WORK_DETAIL_NOTES.md); **multi-pane splitters + cine axes:** [SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md)
- Parallel implementation ownership/workstreams: [plans/supporting/PARALLEL_WORKSTREAM_OWNERSHIP_PLAN.md](plans/supporting/PARALLEL_WORKSTREAM_OWNERSHIP_PLAN.md)

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

- [x] **[P2]** Cross-view **slice position lines** could linger after **MPR clear/detach** or inconsistent clear paths — addressed by dropping the per-pane line manager at **MPR tear-down** (and existing clear-window path); coordinator refresh rebuilds lines. *(Shipped 2026-04-14.)*
- [x] **[P0]** SR dose event viewer seems not to show all info per dose event - primary angle, secondary angle, source-to-detector distance, collimated field area, etc. *Done (2026-04-16): expanded per-event extraction columns (angles, source-detector/isocenter distance, collimated field area, detector-field-size fallback), added Enhanced X-Ray RDSR synthetic fixture (`...88.76`), and added tests against fixture + optional local Siemens sample.*

## Performance / Packaging

- [ ] **[P0]** **macOS PyInstaller — A/B `du` and safety:** On macOS, from the **same git ref**, build twice: (1) **current** spec with **`MACOS_PYSIDE6_MODULE_EXCLUDES`** applied, (2) a branch or env-gated spec that **does not** apply those darwin-only excludes. Compare **`du -sh dist/DICOMViewerV3.app`** (and top `Frameworks/` contributors); record numbers in **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**. **Smoke both** `.app` builds (launch, open DICOM, histogram, export/QA paths). *Why:* PyInstaller usually **does not** ship modules that never appear in the import graph, so excludes may save **little** until hooks/deps pull extra Qt; but **`excludes` can still cause `ImportError`** if any code path (including a **third-party** lazy import) touches a trimmed module — so **prefer default = include everything PyInstaller collects** and treat aggressive macOS trims as a **build-time opt-in** (e.g. env var or spec flag) only after A/B numbers justify it and smoke passes on the slim build.
- [ ] **[P1]** Try to make code faster (startup, file loading, fusion, and general responsiveness) ([details](FUTURE_WORK_DETAIL_NOTES.md#performance-initial-load-file-loading-fusion-and-general-responsiveness))
    - [P2] Particularly w/ large dataset (large files or many files) - would loading compressed initially save time? If we make a database, keep compressed cache?
- [ ] **[P0]** See if executables can be made smaller (especially on macOS) ([details](FUTURE_WORK_DETAIL_NOTES.md#executable-size-especially-on-macos))
- [ ] **[P1]** Check fusion responsiveness on Parallels with 3D fusion

## Maintenance

- [ ] **[P1]** Review what is included in git repo unnecessarily
- [ ] **[P1]** Regularly run all scan templates and update TO_DO.md
- [ ] **[P1]** Examine github actions, CI, CD, etc., and look for opportunities to optimize, simplify, or improve, including reducing use of limited storage quota
- [ ] **[P1]** Check for pyright warnings, errors - run pyright

## UX / Workflow

- [ ] **[P1]** **Confirmed:** Ctrl+X does not cut ROIs/measurements/annotations like Ctrl+C / Ctrl+V—Edit only wires `StandardKey.Copy` / `StandardKey.Paste` to `AnnotationPasteHandler` (`main_window_menu_builder.py`, `app_signal_wiring.py`); there is no Cut shortcut or handler. **Implement:** add Edit → Cut with `QKeySequence.StandardKey.Cut`, call the same clipboard path as copy, then delete the same selected items using the existing per-type delete APIs already used elsewhere.
- [ ] **[P2]** Give option (on by default) to suppress certain tag names (not values) on overlay - StudyDescription, SeriesDescription, InstitutionName, PatientName; abbreviate ImagePositionPatient as IPP and ImageOrientationPatient as IOP.
- [x] **[P1]** When user clicks on a SR thumbnail, show something like "No Image" in the window where they loaded it, and perhaps embed a button like "Open SR..." to open the SR browser in a new window. *Done (2026-04-16): placeholder image + bottom **Open tag browser…** bar (modeless tag viewer); metadata/tag refresh no longer skipped for no-pixel instances.*
- [x] **[P1]** SR dialog should not necessarily say "CT radiation dose summary" - it will definitely be a Structured Report, but may be RDSR from CT or fluoroscopy or X-ray, and at some point we may want to support other types of SRs. *Done (2026-04-16): dose report dialog + menu tooltip + USER_GUIDE use modality-agnostic / RDSR wording.*
- [ ] **[P0]** Full-fidelity Structured Report browsing: dynamic `ContentSequence` tree (all value types), template-aware **RDSR** views with **per-event** rows (fluoroscopy / TID 10003 family), registry for major **SR SOP classes**, not only the fixed dose-summary table or flat tags. *Prior (2026-04-16): file meta merged into `get_all_tags`; no-pixel `display_slice` path refreshes metadata/tag list—covers **tags**, not SR document semantics.* **Plan:** [SR full fidelity browser](plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md).
- [x] **[P0]** Not all SRs showing up in navigator when loaded. Eg, sample ones from PySkinDose (said 0 studies, 0 series, 4 files loaded). Note those are not CT. See test-DICOM-data/pyskindose_samples/ for samples.
- [ ] **[P1]** Allow MPRs to be loaded to multiple windows, and allow more than one MPR to be constructed and detached. **Plan:** [MPR multi-window + multiple detached](plans/supporting/MPR_MULTI_WINDOW_AND_NAVIGATOR_THUMBNAIL_FALLBACK_PLAN.md#mpr-multi-window-detached).
- [ ] **[P2]** If a series's first image is totally empty (or perhaps has less than 0.1% contrast or something), instead of using that for the thumbnail in the navigator, use the middle image of the series. **Plan:** [Navigator thumbnail fallback](plans/supporting/MPR_MULTI_WINDOW_AND_NAVIGATOR_THUMBNAIL_FALLBACK_PLAN.md#navigator-thumbnail-fallback).
- [ ] **[P1]** Add option to have one large window on left and two smaller on right (above and below), or one large window on top and smaller on bottom (left and right), and maybe vice versa for each case. Make "2" key switch between 1x2 and 2x1, while "3" switches between different 3-window layouts just described.
- [x] **[P2]** **T3 —** Make window map thumbnail in navigator interactive (click square to focus and reveal) ([plan](plans/supporting/UX_IMPROVEMENTS_BATCH1_PLAN.md#1-window-map-thumbnail-interactive)). *Shipped:* inline bar + popup map; **1×1** re-arranges the single visible pane to the focused slot; **1×2 / 2×1** reveal row/column for that slot. *Validated*
- [ ] **[P2]** Make toolbar contents and ordering customizable ([plan](plans/supporting/UX_IMPROVEMENTS_BATCH1_PLAN.md#2-toolbar-customization))
- [ ] **[P2]** Improve discoverability/documentation of existing window/level drag interaction ([plan](plans/supporting/UX_IMPROVEMENTS_BATCH1_PLAN.md#3-alternative-windowlevel-interaction))
- [ ] **[P1]** Set min/max window width/level using min/max pixel value possible (raw or rescaled) based on bit depth ([plan](plans/supporting/UX_IMPROVEMENTS_BATCH1_PLAN.md#4-minmax-windowlevel-from-bit-depth))
- [ ] **[P2]** Make default line thicknesses and annotation font sizes smaller (for ROIs, text annotation, measurements) - say line thickness 3 and font size 12 ([plan](plans/supporting/UX_IMPROVEMENTS_BATCH1_PLAN.md#6-reduce-default-line-thicknesses-and-font-sizes))
- [ ] **[P2]** Follow-up for multi-frame instance navigation: audit ROI / measurement / annotation / cine / projection code paths that use `current_slice_index` as slice identity before attempting bounded per-instance scrolling ([plan](plans/completed/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md#phase-4-show-instances-separately-toggle-and-config))
- [ ] **[P2]** Make right pane minimum width before collapsing 250 instead of 200
- [ ] **[P2]** Consider more sophisticated smoothing (PIL/NumPy) vs Qt-only scaling
- [ ] **[P2]** Add ability to edit a drawn ellipse or rectangle ROI ([plan](plans/supporting/VIEWER_UX_FEATURES_PLAN.md#1-roi-editing-resize-handles))
- [ ] **[P1]** Make the large-file warning (and any related file handling checks) trigger for >50 MB instead of 25 MB ([plan](plans/supporting/NAVIGATOR_AND_FILE_LOADING_FEEDBACK_PLAN.md#3-large-file-warning-threshold-50-mb)) - *NOTE: maybe hold off on this for now - 50 might be too high?*
- [ ] **[P2]** Allow further subdivision of subwindows into up to 4 "tiles"? ([plan](plans/supporting/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md#1-subwindow-further-subdivision-up-to-4-tiles))
- [ ] **[P2]** When exporting PNG or JPG, allow anonymization and make using embedded window/level the default option ([plan](plans/supporting/EXPORT_PRIVACY_AND_WL_DEFAULT_PLAN.md#goal))
- [ ] **[P2]** Make default pixel size and slice thickness more reasonable and make editing them easier (default to 1.0 mm, 1.0 mm?)
- [ ] **[P2]** Make a Settings menu for grouping lots of options?
- [ ] **[P2]** Consider a dedicated **Pylinac Configuration...** menu/dialog if more persisted QA customization options are added (likely), so pylinac/site defaults do not keep expanding the per-analysis Tools dialogs.
- [ ] **[P2]** Allow dragging window dividers to make unequal divisions ([implementation notes](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md#1-unequal-divisions-between-image-panes))
- [ ] **[P2]** Add ability to use toolbar icons instead of text
- [ ] **[P1]** Differentiate between frames, instances, and slices in the cine player ([implementation notes](SPLITTER_UNEQUAL_PANES_AND_CINE_PLAYBACK_AXES.md#2-frames-instances-and-slices-in-the-cine-player))
- [ ] **[P2]** Where is it getting frame rate from?
- [ ] **[P1]** Should we block showing DICOM tags when an MPR window is selected (show just "MPR")? Or add some kind of warning that it is the underlying series data somehow?
- [ ] **[P1]** Make spacebar cycle overlay visibility state on all windows?

## Features (Near-Term)

- [ ] **[P1]** Integrate with PySkinDose? — **Plan:** [PySkinDose integration](plans/supporting/PYSKINDOSE_INTEGRATION_PLAN.md).
- [ ] **[P1]** Add highdicom and further SR support — **phased rollout:** [normalization & highdicom (Stage 1 → Stage 2)](plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md); umbrella [SR full fidelity plan](plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md#4-dependencies---highdicom-allowed); [research: capabilities & fit](info/HIGHDICOM_OVERVIEW.md)
- [ ] **[P2]** Add SQLite **FTS5** full-text search for the local study index (e.g. study/series description); see [LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md](plans/supporting/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md).
- [ ] **[P1]** Add a "Deep Anonymizer" export option that strips out all tag data that could be used to indentify a scanner, institution, address, etc., as well as patient informaion. Should include institution name, address, station name, device serial number, etc.
- [ ] **[P1]** Add a simple "DICOM metadata browser" mode that can ingest, browse, and export DICOM metadata, without any image display or processing?(hopefully fast and efficient)
- [ ] **[P1]** Be able to associate with DICOM extension and add to Open With menus ([details](FUTURE_WORK_DETAIL_NOTES.md#file-association-and-open-with-integration))
- [ ] **[P1]** Add basic image processing for creating new DICOMs (kernels, smoothing, edge enhancement, sharpening, custom kernels) ([details](FUTURE_WORK_DETAIL_NOTES.md#basic-image-processing-and-creating-new-dicoms))
- [ ] **[P1]** Further integrate pylinac and other automated QC analysis tools ([details](FUTURE_WORK_DETAIL_NOTES.md#integrating-pylinac-and-other-automated-qc-tools), [pylinac integration overview](info/PYLINAC_INTEGRATION_OVERVIEW.md), [additional automated QA analysis (ACR gaps + CT checks)](info/AUTOMATED_QA_ADDITIONAL_ANALYSIS.md), [Stage 1 implementation plan](plans/completed/PYLINAC_AND_AUTOMATED_QA_STAGE1_PLAN.md))
    - [ ] **[P2]** [Catphan module](info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md#1-catphan-and-related-ct-phantom-classes-pylinacct-quartdvt)
    - [ ] **[P1]** [Nuclear module](info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md#2-nuclear-module-pylinacnuclear)
- [ ] **[P2]** Make more robust to pylinac errors and processing limitations—for example, if pylinac expects at least a 100 mm scan extent but the scan extent is 99.5 mm, find a way to still run analysis and report results (see [pylinac flexibility & workarounds](info/PYLINAC_FLEXIBILITY_AND_WORKAROUNDS.md)).
- [x] **[P1]** Enable export mpg/gif/avi for cine ([plan](plans/supporting/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md#2-cine-video-export-mpg-gif-avi))
    - [x] **[P0]** MPEG and AVI exports are not opening in Windows Media Player - for AVI said it was encoded as MPNG - are we using widely compatible codecs? — **2026-04-17:** AVI → **MPEG-4 Part 2** (`mpeg4` + `yuv420p`). **2026-04-17c (0.2.10):** **MP4** export (same codec, `+faststart`); Win11 Media Player treats **`.mpg`** as MPEG-1/2 only — **MPG** = **MPEG-2** PS + install **MPEG-2 Video Extension** for WMP, or use **MP4**/**AVI**. **No H.264** in this pass (licensing/product).
    - [x] **[P0]** Frame rate taking effect? Eg, on GIF — **2026-04-17 / 2026-04-17b:** `gif_frame_duration_milliseconds` (imageio Pillow plugin expects **ms**, not seconds) + `effective_fps_for_encoder`; tests + GIF metadata check vs FPS.
    - [x] **[P0]** Mimic handling for exporting JPG/PNG/etc. (scaling, etc.) — **2026-04-17:** Cine dialog **resolution** combo (native…4×) + `main.py` passes `export_scale`, **`scale_annotations_with_image=False`**, **`subwindow_annotation_managers`** (same aggregation as **Export Images**).
    - [x] **[P1]** Capitalize words in Export Cine As...  — **2026-04-17:** Menu, dialog title, **QMessageBox** / save-as caption title case (**Export Cine As…** / **Export Cine**).
    - [ ] check above (verified mp4 works, gif works)
- [x] **[P2]** Add measure angle as another measurement/annotation - ([plan](plans/supporting/MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md#3-angle-measurement-tool)) — **2026-04-14:** toolbar **Angle** / **Shift+M**, three-click at-vertex angle; export + clipboard + tests
    - [x] **[P1]** Check if export ROI statistics includes angle measurement (and distance measurement) — **2026-04-18:** **Export ROI Statistics** (TXT/CSV/XLSX) includes **distance** and **angle** measurements per slice via `roi_export_service.collect_roi_data` + `measurement_tool`; CSV adds trailing measurement columns.
- [ ] **[P2]** Interactive oblique rotation on MPR (drag handles/crosshairs) ([details](FUTURE_WORK_DETAIL_NOTES.md#interactive-oblique-rotation-on-mpr))
- [ ] **[P2]** Fusion overlays on MPR views ([details](FUTURE_WORK_DETAIL_NOTES.md#fusion-on-mpr))
- [ ] **[P2]** Advanced ROI/contouring abilities (contouring, auto-detect ROI, 3D ROI across views) ([details](FUTURE_WORK_DETAIL_NOTES.md#advanced-roi-and-contouring))
- [ ] **[P2]** Allow hanging protocols? Configuration of windows/tiles, certain views/phases/priors loaded ([plan](plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#1-hanging-protocols))
- [ ] **[P2]** Once database is added, allow pulling priors ([plan](plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#2-pulling-priors-after-local-database))
- [x] **[P1]** Also try RDSR parsing/browsing/export support - have some examples, add to repo ([plan](plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md#3-rdsr-parsing-and-export)) — **2026-04-15:** CT dose SR parse support + report dialog via **Tools** and image context menu; privacy-aware display and JSON/CSV export with optional anonymization.
- [ ] **[P1]** Allow some configuration to interpret MTF results (separately for MRI and CT) where the user needs to review some images along with pylinac MTF plots and decide the "visibility cutoff" MTF value which they think corresponds to the limit of visibility and we report the (interpolated) spatial frequency that gives that MTF value, OR we could have them define a "passing" MTF value and state which inserts pass/fail a visibility check based on that. ([details](FUTURE_WORK_DETAIL_NOTES.md#interpreting-mtf-results))
- [x] **[P2]** For ROIs, allow computing and displaying stats per color channel (RGB, etc.) (on by default, when RGB data present, can be enabled in settings) — **2026-04-15:** per-channel mean/std/min/max in ROI panel/overlay, persisted setting, and per-channel ROI statistics export columns/rows.
    - [x] **[P1]** Seems to only show means, not std/min/max — **2026-04-18:** On-image ROI overlay (`roi_manager.create_statistics_overlay`) now adds **Ch std / Ch min / Ch max** compact lines when those stats are toggled on; the statistics panel already listed per-channel std/min/max.
- [x] **[P2]** For screenshot export, allow choosing to export multi-window view as single image, as well. Maybe also entire application window as single image, including left/right panes and toolbar etc (if currently displayed). ([plan](plans/supporting/SCREENSHOT_COMPOSITE_OVERLAY_DETAIL_HISTOGRAM_COMPARE_PLAN.md#2-screenshot-export-composite-grid-and-full-application-window)) — **2026-04-18:** **Export Screenshots** dialog: separate per view (default), **single composite** (`MultiWindowLayout.get_screenshot_grid_cells`), **entire main window** grab after hiding the dialog.
- [x] **[P2]** In overlay  config, allow something like "simple view" and "detailed view", where additional tags can be shown, and spacebar cycles through simple, detailed, and hidden views. ([plan](plans/supporting/SCREENSHOT_COMPOSITE_OVERLAY_DETAIL_HISTOGRAM_COMPARE_PLAN.md#3-overlay-simple--detailed-in-config--spacebar-cycles-modes)) — **2026-04-18:** **Overlay Tags Configuration** default mode combo; **Space** cycles **minimal → detailed → hidden** app-wide; **Shift+Space** legacy visibility on focused view; context menu + wiring updates.
- [x] **[P2]** When projection is enabled, allow to show projection pixel values on histogram. — **2026-04-15:** histogram dialog toggle uses intensity-projection slab pixels (AIP/MIP/MinIP), persisted via `histogram_use_projection_pixels`.
- [ ] **[P2]** Enable adding multiple images distributions to histogram for comparison (probably via button histogram). Use different colors for each distribution. ([plan](plans/supporting/SCREENSHOT_COMPOSITE_OVERLAY_DETAIL_HISTOGRAM_COMPARE_PLAN.md#4-histogram-multiple-distributions-for-comparison))
- [ ] **[P2]** Add toggle/preference to have up/down keys and scroll wheel up/down navigate by slice # or image position patient (eg, if increasing slice # has decreasing image position patient along the orientation vector, allow choosing whether up moves up in slice number (and lower on patient), or up in image position patient (and lower on slice number)).
- [ ] **[P2]** Do we allow cine playback of multiple windows? We should be able to play each window's cine in sync, or independently, or a combination of both.
- [ ] **[P1]** Allow export of AIP, MIP, MinIP stack as DICOM or images.

## Documentation

**Plan (2026-04-03):** [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/completed/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md) — README slimming, `tests/README.md`, in-app Quick Start (TOC + browser links), `user-docs/` hub, MPR + pylinac user guides.

- [ ] **[P1]** Conduct documentation audit to ensure all features are documented and up to date.
- [x] **[P1]** Introduce Help → Documentation, shorten Quick Start (`resources/help/quick_start_guide.html`), link to full docs in browser — see [DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md](plans/completed/DOCUMENTATION_IMPROVEMENT_PLAN_2026-04-03-200500.md).
- [x] **[P1]** Add documentation for the pylinac integration and the automated QA analysis tools — [user-docs/USER_GUIDE_QA_PYLINAC.md](../user-docs/USER_GUIDE_QA_PYLINAC.md) (developer depth remains in `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md`).
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
- [ ] **[P0]** Figure out license; also check which libraries are covered by which licenses and make sure we are compliant.
- [ ] **[P0]** Make versioned release with exectutables
- [ ] **[P2]** Announce on LinkedIn and share with people
- [ ] **[P2]** Build a technical guide ([details](FUTURE_WORK_DETAIL_NOTES.md#technical-guide-scope))
- [ ] **[P2]** Naming exploration: "DICOM Viewer + ?" ([details](FUTURE_WORK_DETAIL_NOTES.md#product-naming-exploration))