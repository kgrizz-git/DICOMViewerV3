# Multi-Frame Instance Navigation – Implementation Plan

This document is a multi-phase implementation plan for improved handling of multi-frame DICOM instances within a series, following the Tier 1 and Tier 2 recommendations in [FUTURE_WORK_DETAIL_NOTES.md](../FUTURE_WORK_DETAIL_NOTES.md).

**References:**
- Background and recommendations: `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` – *Differentiating Frame # vs. Slice # vs. Instance #*
- Multi-frame detection and splitting: `src/core/multiframe_handler.py` (`is_multiframe`, `get_frame_count`, `FrameDatasetWrapper`)
- Series organizer (frame splitting at load): `src/core/dicom_organizer.py` (`_organize_files_into_batch`, `merge_batch`)
- Overlay formatting: `src/gui/overlay_manager.py` (`_format_tag_for_corner`)
- Series navigator and thumbnail: `src/gui/series_navigator.py` (`SeriesNavigator`, `SeriesThumbnail`)
- Config pattern: `src/utils/config/display_config.py` (see existing bool config keys, e.g. `smooth_image_when_zoomed`)
- Test datasets: `git-ignore-sample-DICOM/` – CCL2 (multi-frame per instance) and VC192 (single-frame per instance)

---

## 1. Overview of Changes

| Area | Current behavior | Target behavior |
|------|-----------------|-----------------|
| **DICOMOrganizer** | Splits multi-frame instances into frame wrappers at load; no series-level multi-frame stats recorded. | After each organize/merge pass, compute and store `instance_count` and `max_frame_count` per series in a `series_multiframe_info` dict. |
| **Series thumbnail** | Shows series number (e.g. "S3") in top-left corner; no frame info. | For multi-frame series, additionally shows a compact indicator (e.g. `5i×12f` or `12fr`) in the bottom-left corner. |
| **Overlay label** | Shows `Slice X/Y (Frame A/B)` (parenthetical) when a multi-frame dataset is displayed. | Shows `Instance N/M · Frame A/B` (cleaner primary label); extended to `Instance N/M · Frame A/B (time)` etc. in Tier 2. |
| **Navigator expand** | All frames from all instances are flattened into one series entry; no per-instance navigation mode. | Optional "Show Instances Separately" toggle expands the series into per-instance sub-thumbnails in the navigator. |
| **Config** | No multi-frame config keys. | `show_instances_separately` bool key; persisted and applied on load. |
| **Tier 2 – frame type** | No frame-type classification; generic `Frame A/B` label. | Semantic tag inspection classifies each instance's frames (temporal, cardiac, diffusion, spatial, unknown); overlay label reflects the type. |

---

## 2. Scope and Out-of-Scope

**In scope**
- `series_multiframe_info` dict on `DICOMOrganizer`: computed at organize/merge time; stores `instance_count` and `max_frame_count` per `(study_uid, series_key)`.
- `SeriesThumbnail` multi-frame indicator: compact annotation drawn in `paintEvent` when `max_frame_count > 1`.
- Overlay label: replace `(Frame A/B)` parenthetical with `Instance N/M · Frame A/B`, computing instance index from the current position in the flattened series list.
- "Show Instances Separately" toggle: View menu + navigator context-menu; per-series sub-thumbnail expansion in `SeriesNavigator`.
- Config key `show_instances_separately`: get/set, default `False`.
- Tier 2 semantic classification: `classify_frame_type()` helper inspecting tags on the original dataset; stored in extended `MultiFrameSeriesInfo`; drives specific overlay label text.

**Out of scope**
- Tier 3 enhanced IOD navigation (independent 2D-axis scroll via `PerFrameFunctionalGroupsSequence`; see Tier 3 TO_DO for a future dedicated plan).
- Changing the internal storage model (flattened list remains; expansion is a display-only concept for Tiers 1–2).
- Merge/split operations at the series level (Horos-style database actions).
- Automatic series splitting by `InstanceNumber` for single-frame series (VC192 behavior is correct and unchanged).

---

## 3. Principles

- **Backups:** Per project rules (`AGENTS.md`), back up any code file before modifying it (e.g. in `backups/`).
- **VC192 regression safety:** At every phase, single-frame series (`NumberOfFrames <= 1` for all files) must behave exactly as before—no changes to overlay, navigator, or scroll behavior.
- **Graceful handling:** Missing or null `NumberOfFrames` treated as 1; absent semantic tags do not crash; unknown frame type falls back to "Frame N/M".
- **Overlay opt-in:** New overlay format activates only when the current series is confirmed multi-frame (`max_frame_count > 1`); single-frame series see no overlay change.
- **Config default:** `show_instances_separately` defaults to `False`; VC192-type users are unaffected.
- **No artificial test changes:** Do not alter tests solely to make them pass; fix behavior or document gaps.

---

## 4. Review Corrections and Required Clarifications

This section records issues found while comparing the plan against the current codebase.

- **Organizer helper name:** the current batching helper is `DICOMOrganizer._organize_files_into_batch()`, not `_organize_batch()`.
- **Flattened data model is already in use:** the organizer currently expands multi-frame instances into one flattened series list of `FrameDatasetWrapper` objects. Any per-instance UI is therefore a presentation layer on top of an already-flattened list.
- **`current_slice_index` is used as slice identity in several subsystems:** ROI, measurements, text annotations, arrow annotations, and parts of the display manager currently key state by `current_slice_index`, not by `(instance_index, frame_index)`. This makes “stay within selected instance while scrolling” a broader behavioral change than the original Phase 4 wording suggests.
- **Navigator signal contract is too narrow for Phase 4 as originally written:** `SeriesNavigator.series_selected` currently emits only `series_uid`. A per-instance click path should use a new signal carrying at least `(study_uid, series_uid, target_slice_index)` rather than overloading the existing signal.
- **Navigator context menu placement:** the existing context menu is owned by `SeriesThumbnail`, not by `SeriesNavigator`. A per-series override should therefore be added to thumbnail context menus unless the navigator is refactored to own context actions centrally.
- **Recommended scope reduction for initial Phase 4:** implement visual expansion plus click-to-jump first, but keep existing flattened scroll behavior unchanged. If bounded per-instance scrolling is still desired, treat that as a separate follow-up after storage/indexing impact is evaluated.

### Open Questions Requiring Explicit Implementation Decisions

- Should expanded instance thumbnails appear inline in the same row, or in a temporary second row beneath only the expanded parent series?
- Should the initial Phase 4 support only a global toggle, or both a global toggle and a per-series override in thumbnail context menus?
- When a user clicks an expanded instance thumbnail, should the app jump to that instance's first frame only, or also remember the last frame visited within that instance for later returns?
- Should the navigator display instance labels using `InstanceNumber` only, or fall back immediately to ordinal labels like `#1`, `#2`, ... when `InstanceNumber` is missing or duplicated?

---

## 5. Phase Overviews

### Phase 1: Multi-frame series metadata in DICOMOrganizer

**Goal:** At organize/merge time, compute and store per-series multi-frame statistics so downstream phases can query them without re-scanning series data.

**Scope:**
- Add a `MultiFrameSeriesInfo` dataclass (or `typing.NamedTuple`) with fields `instance_count: int` and `max_frame_count: int`; place it in `dicom_organizer.py` or a small companion module.
- Add `self.series_multiframe_info: Dict[Tuple[str, str], MultiFrameSeriesInfo]` to `DICOMOrganizer.__init__`.
- In `organize()`, reset `self.series_multiframe_info` alongside `self.studies`, `self.file_paths`, `self.presentation_states`, and `self.key_objects`.
- After `_organize_files_into_batch()` builds `batch_studies`, iterate each series in `batch_studies`: group its slice list by `_original_dataset` identity (for `FrameDatasetWrapper`) or count unique dataset objects (for single-frame); record `instance_count` (number of distinct original datasets) and `max_frame_count` (max frame count seen, using `get_frame_count(original_dataset)`).
- In `merge_batch`, update (replace) the entry for each affected series after merging.
- In `remove_study()` / any `remove_series()` helper, pop the corresponding `series_multiframe_info` entries.
- Do **not** store this information on the individual `FrameDatasetWrapper` objects; keep it at the organizer level.

**Implementation checklist:**
- [x] Add `MultiFrameSeriesInfo` type and `self.series_multiframe_info` storage.
- [x] Reset `series_multiframe_info` in `organize()`.
- [x] Add one internal helper to compute per-series stats from a list of datasets.
- [x] Update `_organize_files_into_batch()` callers so stats are stored for full loads and additive loads.
- [x] Remove stale stats when studies or series are removed.
- [ ] Add or update tests for CCL2-like and VC192-like series stats.

**Success criteria:**
- After loading the CCL2 dataset: `series_multiframe_info[(study_uid, series_key)]` has `instance_count > 1` and `max_frame_count > 1`.
- After loading a VC192 CT dataset: `series_multiframe_info[...]` has `max_frame_count == 1`.
- Additive load (second study added) updates stats correctly without duplicating entries.
- Removing a study cleans up `series_multiframe_info`.
- Existing test suite passes; no new exceptions.

**Estimated effort:** Small.

---

### Phase 2: Navigator thumbnail multi-frame indicator

**Goal:** Series thumbnails for multi-frame series display a compact label so the user immediately understands the structure.

**Scope:**
- `SeriesThumbnail`: add `set_multiframe_info(instance_count: int, max_frame_count: int)` method; stores values and calls `update()`. In `paintEvent`, when `max_frame_count > 1`, draw a small label in the bottom-left corner of the thumbnail using the same yellow-text-on-dark-background style as the series number label. Format rules:
  - Multiple instances with multiple frames: `{instance_count}i×{max_frame_count}f` (e.g. `5i×12f`).
  - Single instance with multiple frames: `{max_frame_count}fr` (e.g. `12fr`).
- `SeriesNavigator.update_series_list()`: after creating or reusing each `SeriesThumbnail`, look up the corresponding entry in `series_multiframe_info` and call `set_multiframe_info`.
- Prefer a lightweight `SeriesNavigator.set_multiframe_info_map(...)` setter over passing the full organizer into the navigator; this keeps the widget focused on rendering rather than data ownership.
- When a series has no entry in `series_multiframe_info` (single-frame), call `set_multiframe_info(1, 1)`; the thumbnail draws nothing extra.

**Implementation checklist:**
- [x] Add `set_multiframe_info()` storage and repaint support to `SeriesThumbnail`.
- [x] Draw the compact indicator without colliding with the top-left series number or top-right subwindow dots.
- [x] Add a navigator setter for the multiframe info map.
- [x] Populate the info map before every `update_series_list()` call path.
- [ ] Verify indicator behavior after close/reopen and additive load flows.

**Success criteria:**
- CCL2 thumbnail displays the multi-frame indicator with correct counts.
- VC192 thumbnail shows no indicator; visual appearance unchanged.
- Indicator repaints correctly after a series close → re-open cycle.
- No layout shifts or clipping introduced to existing thumbnail elements (series number, subwindow dots).

**Estimated effort:** Small.

---

### Phase 3: Overlay label – "Instance N/M · Frame A/B"

**Goal:** Replace the current parenthetical `(Frame A/B)` suffix in the overlay with a primary `Instance N/M · Frame A/B` label that correctly identifies the instance index and frame index.

**Scope:**
- In the display path (`_display_slice` → overlay refresh), when the dataset is a `FrameDatasetWrapper` and the series is in `series_multiframe_info` with `instance_count > 1` and `max_frame_count > 1`:
  - Compute `instance_index` (1-based): iterate the current series list from the organizer, group by `_original_dataset` identity (ordered), and find the group index for `dataset._original_dataset`.
  - Compute `total_instances` from `series_multiframe_info.instance_count`.
  - Compute `frame_index` (1-based) from `dataset._frame_index + 1`.
  - Compute `total_frames` from `get_frame_count(dataset._original_dataset)` (specific to this instance, not the series max).
- Add a small helper at the organizer or display-manager layer to compute this context once per displayed dataset instead of recomputing it ad hoc in `overlay_manager`.
- Pass these values to `overlay_manager` (e.g. as an optional `multiframe_context` argument to `_get_corner_text()` / `_format_tag_for_corner()`). In `overlay_manager`, when that context is present and valid, produce the label `Instance {instance_index}/{total_instances} · Frame {frame_index}/{total_frames}` in place of the current `Slice X/Y (Frame A/B)` construction.
- Single-instance multi-frame (only one original dataset in the series): show `Frame {frame_index}/{total_frames}` without the `Instance N/M ·` prefix.
- Single-frame series: no change to overlay output whatsoever.
- The existing `InstanceNumber`-based `Slice X/Y` label path remains for single-frame datasets.

**Required clarification:** do not compute the instance context inside `_display_slice()` itself if it can be centralized in `SliceDisplayManager` or `DICOMOrganizer`; that logic will be needed again if Phase 4 introduces jump-to-instance behavior.

**Implementation checklist:**
- [x] Add one helper that resolves per-dataset multiframe context from the current series list.
- [x] Thread the resolved context into overlay generation.
- [x] Replace the current parenthetical frame text with the new primary label only for true multi-frame series.
- [x] Preserve existing projection-range formatting for single-frame series.
- [x] Verify privacy mode still masks patient tags and does not affect the new label.

**Success criteria:**
- CCL2: overlay shows `Instance N/{total_instances} · Frame A/{frames_per_instance}` while scrolling through the series.
- VC192: overlay shows `Slice X/Y` exactly as before; no instance/frame suffix appears.
- Privacy mode masking behavior is not affected by the new label paths.
- No `KeyError` or `AttributeError` from missing tags or missing structure.

**Estimated effort:** Small–medium.

---

### Phase 4: "Show Instances Separately" toggle and config

**Goal:** Provide a user-accessible toggle that expands a multi-frame series into per-instance sub-thumbnails in the navigator, with each sub-thumbnail navigating only the frames of that instance.

**Scope:**
- Config (`src/utils/config/display_config.py` or `overlay_config.py`): add `show_instances_separately` bool key with `get_show_instances_separately()` / `set_show_instances_separately()`; default `False`.
- View menu (`main_window_menu_builder.py`): add checkable "Show Instances Separately" action and a small `MainWindow` sync helper mirroring the existing smoothing/privacy pattern. Grey it out when the active series has `max_frame_count <= 1`. Wire it to a `DICOMViewerApp` handler that persists the config value, refreshes the navigator, and updates the action enabled/checked state.
- Thumbnail context menu: add the same action to `SeriesThumbnail.contextMenuEvent()` for per-series discoverability if the global-only approach is deemed insufficient.
- `SeriesNavigator` expansion mode: when `show_instances_separately` is `True` and a series has `instance_count > 1` in `series_multiframe_info`, render one sub-thumbnail per instance beneath or beside the parent series entry. Each sub-thumbnail uses the first frame of that instance as its preview image and is labelled with the instance's `InstanceNumber` (or ordinal `#1`, `#2`, ... if absent).
- Add a **new** signal for expanded-instance clicks, carrying enough information to avoid ambiguity across studies. Recommended shape: `(study_uid, series_uid, target_slice_index)`.
- Initial navigation behavior: clicking a sub-thumbnail jumps to the first frame of that instance. Keep the existing flattened scroll behavior unchanged in the first release.
- **Deferred from initial Phase 4:** changing wheel/cine navigation so it stays within the selected instance. That behavior currently collides with ROI/measurement/annotation storage keyed by `current_slice_index` in `SliceDisplayManager` and related tools, and should be treated as a follow-up task rather than part of the first expansion delivery.
- Greying logic: the View menu action is enabled only when the focused series satisfies `max_frame_count > 1` from `series_multiframe_info`; disabled (greyed) for single-frame series.
- On toggle change, refresh the navigator and re-display the current position.

**Required clarification:** if bounded per-instance scrolling is still desired after the initial release, create a separate follow-up plan section that explicitly audits ROI, measurement, text annotation, arrow annotation, cine, and projection interactions that currently use `current_slice_index` as the storage identity.

**Implementation checklist:**
- [x] Add `show_instances_separately` get/set methods and default config key.
- [x] Add a `MainWindow` action plus sync helper and app-level handler.
- [x] Add enabled/disabled refresh logic based on the focused series' `series_multiframe_info`.
- [x] Add expanded instance thumbnails in `SeriesNavigator` without breaking existing study separators and width calculations.
- [x] Add a new navigator signal for per-instance selection.
- [x] Implement click-to-jump to the first frame of the selected instance.
- [x] Keep existing flattened scroll behavior unchanged for the initial release.
- [ ] Re-run overlay/ROI/measurement smoke checks to confirm no index regressions were introduced by jump-to-instance.

**Success criteria:**
- Toggling on for CCL2: navigator shows one sub-thumbnail per instance; clicking any navigates to that instance's first frame; overlay shows `Instance N/M · Frame 1/M`.
- Toggling off: collapses to single thumbnail; scrolling traverses all frames as before.
- Action is greyed for VC192 and any series with `max_frame_count <= 1`.
- Setting persists across app restarts.
- Navigator layout does not break for mixed studies (some multi-frame, some single-frame).
- Existing ROI, measurement, and annotation behavior remains stable after jump-to-instance operations.

**Estimated effort:** Medium–large (navigator layout changes required; signal/data model extension).

---

### Tier 1 Validation

**Goal:** Verify that all Tier 1 phases function end-to-end and do not regress existing single-frame behavior.

**Test cases:**
- **CCL2 multi-frame dataset:** series thumbnail shows multi-frame indicator with correct counts; overlay shows `Instance N/M · Frame A/B` while scrolling; "Show Instances Separately" toggle expands navigator to per-instance sub-thumbnails and navigation within an instance works correctly.
- **VC192 CT dataset:** no indicator on thumbnail; overlay shows `Slice X/Y` unchanged; "Show Instances Separately" action is greyed.
- **Single-instance multi-frame** (e.g. a cine loop in a single file): thumbnail shows single-instance format (e.g. `12fr`); overlay shows `Frame A/B` (no `Instance` prefix); toggle greyed (nothing to expand).
- **Regression – all single-frame series:** no visual changes anywhere; no performance regression; all existing automated tests pass.
- **Additive load:** loading a second study after the first does not corrupt `series_multiframe_info`; newly loaded multi-frame series shows indicator immediately.

**Success criteria:** All test cases above pass; no Python exceptions or tracebacks introduced by new code paths; existing automated test suite passes.

**Validation checklist:**
- [ ] Load CCL2 and confirm `series_multiframe_info` values are correct.
- [ ] Confirm the CCL2 thumbnail indicator matches instance/frame counts.
- [ ] Confirm CCL2 overlay shows `Instance N/M · Frame A/B`.
- [ ] Toggle "Show Instances Separately" on and confirm click-to-jump works.
- [ ] Confirm VC192 shows no indicator and unchanged overlay text.
- [ ] Confirm single-instance multi-frame behavior shows `Frame A/B` without `Inst` prefix.
- [ ] Run automated tests.

---

### Phase 5: Semantic frame-type detection (Tier 2)

**Goal:** For each multi-frame series, inspect DICOM tags on the original dataset to classify the frame type (temporal, cardiac, diffusion, spatial, or unknown), and store the classification for use in Phase 6.

**Scope:**
- Add a `FrameType` enum (`TEMPORAL`, `CARDIAC`, `DIFFUSION`, `SPATIAL`, `UNKNOWN`) and a `classify_frame_type(original_dataset: Dataset) -> FrameType` function in `src/core/multiframe_handler.py` (or a new `src/core/frame_classifier.py` if the file becomes too large).
- Classification logic (checked in priority order, first match wins):
  1. `TemporalPositionIdentifier` (0020,0100) present → `TEMPORAL`
  2. `FrameTime` (0018,1063) or `ActualFrameDuration` (0018,1242) present → `TEMPORAL`
  3. `TriggerTime` (0018,1060) or `CardiacNumberOfImages` (0018,1090) present → `CARDIAC`
  4. `DiffusionBValue` (0018,9087) present → `DIFFUSION`
  5. `ImagePositionPatient` (0020,0032) present (spatial info; frame positions differ) → `SPATIAL`
  6. Otherwise → `UNKNOWN`
- Extend `MultiFrameSeriesInfo` with `frame_type: FrameType` (default `UNKNOWN`).
- Compute `frame_type` in the organize/merge stats pass (Phase 1 code), by calling `classify_frame_type` on the first original dataset found for the series. If multiple instances have different types (unlikely but possible), use the dominant type or fall back to `UNKNOWN`.

**Success criteria:**
- `series_multiframe_info[...]` has a populated `frame_type` for all series.
- CCL2 is classified correctly (inspect which tags it carries to verify the expected result).
- `classify_frame_type` is unit-testable and returns `UNKNOWN` for a bare dataset with no semantic tags.
- No performance regression on load time (tag inspection is O(1) per instance).

**Estimated effort:** Small.

---

### Phase 6: Specialized overlay labels (Tier 2)

**Goal:** Use the frame-type classification from Phase 5 to render specific overlay labels in place of the generic `Frame A/B`.

**Scope:**
- In the overlay formatting code path updated in Phase 3, after determining the frame context, read `frame_type` from `series_multiframe_info` for the current series.
- Map `FrameType` to the label suffix:

  | `FrameType` | Label format |
  |-------------|-------------|
  | `TEMPORAL` | `Frame A/B (time)` |
  | `CARDIAC` | `Phase N/M` or `Phase N/M (T ms)` when `TriggerTime` is available |
  | `DIFFUSION` | `b=X` where X is read from `DiffusionBValue` tag on the current `FrameDatasetWrapper` (fall back to `Frame A/B` if tag absent) |
  | `SPATIAL` | `Slice A/B` |
  | `UNKNOWN` | `Frame A/B` |

- For cardiac series, `Phase N/M` means ordinal cardiac phase position, not heart rate or percent of the R-R interval. If `TriggerTime` is available for the current frame, append it as milliseconds: `Phase N/M (320 ms)`.
- Full overlay format (multi-instance, typed): `Instance N/M · Phase N/M` or `Instance N/M · Phase N/M (320 ms)` or `Instance N/M · Frame A/B (time)` etc.
- Full overlay format (single-instance, typed): `Phase N/M` or `Phase N/M (320 ms)` or `Frame A/B (time)` etc.
- If the per-frame tag needed for the label (e.g. `DiffusionBValue`) is absent on a specific frame, fall back gracefully to `Frame A/B`.
- Single-frame series: overlay unchanged.

**Success criteria:**
- CCL2 overlay shows the type-specific label matching its classification.
- Other multi-frame test datasets (if available) show correct labels.
- VC192 overlay is unchanged.
- Privacy mode masking is not affected.
- No exception when a per-frame tag required for the label is absent.

**Estimated effort:** Small.

---

### Tier 2 Validation

**Goal:** Verify that Tier 2 label specialization works correctly and does not regress Tier 1 behavior.

**Test cases:**
- **CCL2 dataset:** overlay displays the expected type-specific label (verify which type CCL2 is classified as; confirm visually while scrolling).
- **Any additional multi-frame datasets available in test data:** classify each and verify overlay label is appropriate.
- **Regression – Tier 1 tests re-run:** CCL2 indicator, instance/frame counts, toggle behavior, and VC192 unchanged—all still pass.
- **Regression – all single-frame series:** no overlay changes.

**Success criteria:** Overlay labels are type-specific and accurate; no Python exceptions from new classification or label formatting code; existing automated tests still pass.
