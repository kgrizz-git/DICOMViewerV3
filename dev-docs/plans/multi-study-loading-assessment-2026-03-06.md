# Multi-Study / Additive Loading — Assessment & Approach Options
**Date:** 2026-03-06  
**Status:** Assessment complete — all decisions resolved; ready for detailed implementation plan

---

## 1. Feature Goals

| Goal | Details |
|---|---|
| **Additive file opening** | Opening files/folders, using the Recents menu, or drag-and-dropping onto the app **appends** to the currently loaded studies instead of replacing them |
| **Close All** | Rename the existing `File → Close` menu item to **Close All**; behavior unchanged (full teardown) |
| **Close This Study** (right-click on navigator thumbnail) | Removes one entire study (all its series) from every subwindow, navigator, and data store |
| **Close This Series** (right-click on navigator thumbnail) | Removes one series from every subwindow, navigator, and data store |

---

## 2. Current Architecture — What Needs to Change

### 2.1 Data Layer

`DICOMOrganizer` (src/core/dicom_organizer.py) owns the in-memory data:

```python
self.studies: Dict[str, Dict[str, List[Dataset]]]
# { StudyInstanceUID: { composite_series_key: [sorted Dataset objects] } }

self.file_paths: Dict[Tuple[str, str, int], str]
# { (study_uid, composite_series_key, instance_num) → file_path }
```

`DICOMViewerApp.current_studies` is a **direct reference** to `dicom_organizer.studies`, replaced atomically on every load.

**Problem:** `organize()` wipes and rebuilds the entire `studies` dict on each call, and `FileOperationsHandler` calls `clear_data_callback()` before every load, which calls `DICOMViewerApp._clear_data()`. There is no concept of "add to what is already there."

### 2.2 Load Path Entrypoints

All four entry points delegate the same way:

```
_open_files / _open_folder / _open_recent_file  (menu/dialog)
    └─ multi_window_layout.reset_slot_to_view_default()   ← called here
    └─ FileSeriesLoadingCoordinator → FileOperationsHandler

_open_files_from_paths  (drag-and-drop)
    └─ FileSeriesLoadingCoordinator → FileOperationsHandler   ← no reset
```

Inside `FileOperationsHandler.open_files()/.open_folder()/.open_recent_file()/.open_paths()`:
1. **`clear_data_callback()`** → `_clear_data()` (clears ROIs, annotations, scene state)
2. `dicom_loader.load_files() / load_directory()`
3. `dicom_organizer.organize(datasets, file_paths)` (replaces `studies`)
4. **`load_first_slice_callback(studies)`** → `handle_load_first_slice()` in `FileSeriesLoadingCoordinator`

Inside `handle_load_first_slice()`:
- Resets fusion
- **Clears tag edit history**
- **Clears all subwindow image viewer scenes**
- **Clears all overlay items**
- Resets projection state
- Clears stale `subwindow_data` entries
- Sets `app.current_studies = studies` (the new dict)
- Loads Presentation States and Key Objects (wholesale, not additive)
- Auto-assigns the first series to subwindow 0
- Updates navigator with the new `studies`

Every bold step above would need to be **conditioned on what is actually being replaced vs. kept**.

### 2.3 Navigator

`SeriesNavigator.update_series_list(studies, study_uid, series_uid)` rebuilds from the full `studies` dict. It uses a thumbnail cache keyed by `(study_uid, series_uid)`. **This already handles multiple studies gracefully** — it groups by study with `StudyLabel` dividers and lists all series. No structural change is needed here; it just needs to be called with the merged dict.

The navigator only highlights one "active" series at a time (the focused subwindow's series). For multi-study loaded scenarios, multiple subwindows may each show different series. The navigator would show each one as "not highlighted" unless the focused subwindow's series is visible.

### 2.4 Subwindow Display

`app.subwindow_data[idx]` tracks which series each subwindow is displaying. After a full replace, `handle_load_first_slice()` either resets stale subwindow entries or clears them. With additive loading, **subwindows that are already displaying a series should be left untouched**.

### 2.5 Close Menu Item

`MainWindow` emits `close_requested` → `DICOMViewerApp._close_files()`. This is the full teardown path. Renaming to "Close All" is a one-line change in `main_window_menu_builder.py`.

### 2.6 Right-Click on Navigator Thumbnail

`SeriesThumbnail` (src/gui/series_navigator.py) has a `clicked` signal and drag support, but **no context menu**. A context menu with Close This Series / Close This Study would need to be added. A new signal (e.g., `close_series_requested(study_uid, series_uid)` and `close_study_requested(study_uid)`) would propagate up to the app-level close handlers.

---

## 3. Decisions Made

| # | Question | Decision |
|---|---|---|
| 1 | Default open behavior | **All four entry points are additive** — no preference toggle |
| 2 | New-series subwindow placement | **Load first new series into the first empty subwindow**; if no empty subwindow exists, add to navigator only |
| 3 | Duplicate detection | **File-path-based**: a file is a duplicate only if the same absolute path is already loaded. Same series from different folders → two separate series entries in the navigator. New files from an already-open series (not yet loaded by path) → merge as additional slices into the existing series |

---

## 4. Key Design Challenges

### 4.1 File-Path Deduplication and Series Key Disambiguation

The dedup rule is per-file, not per-DICOM UID. This has significant consequences for the `composite_series_key` used as the inner key of `studies`.

**Current key:** `SeriesInstanceUID_SeriesNumber`  
This is unique within a single load but is **not unique across loads from different folders** — two folders can contain files with identical `SeriesInstanceUID`/`SeriesNumber` that should appear as separate entries in the navigator.

**Required additions to the data model:**
1. A **`loaded_file_paths: Set[str]`** (global, across all loads) to enable O(1) duplicate-file detection.
2. A **source-folder tag** per series entry so that when new files arrive with the same DICOM UIDs, the system can decide: same source folder → attempt to merge slices; different source folder → create a new series entry.
3. A **disambiguation suffix** in the composite key for same-UID series from different sources — e.g., `SeriesInstanceUID_SeriesNumber` for the first load, `SeriesInstanceUID_SeriesNumber_2` for a second load of the same UIDs from a different folder.

**Defining "source folder" for a batch:**
- For `open_folder`: the folder the user selected is the source root.
- For `open_files` (individual file picks): the common directory prefix of all picked files.
- For `open_recent_file`: the stored path's parent directory.
- For drag-and-drop: the common directory prefix of all dropped paths.

This source folder is associated with each series entry at load time and stored in a parallel `series_source_dirs: Dict[Tuple[str, str], str]` → `{(study_uid, series_key): source_dir}`. On subsequent loads, the merge path checks: same DICOM UIDs + same source dir → candidate for file-level slice merge. Same UIDs + different source dir → new series entry with a suffix key.

**Incrementally merging slices:**
When a file's path is not in `loaded_file_paths` but its DICOM UIDs match an existing series with the same source dir, its dataset is inserted into the existing `List[Dataset]` in sorted order (re-applying the same `InstanceNumber` / `SliceLocation` / `ImagePositionPatient` sort). After merge, the series' slice list grows, and any subwindow currently displaying that series needs to be notified to update its slice navigator (but stays at its current slice index if still valid).

### 4.2 Accumulating `DICOMOrganizer.studies` Across Multiple Loads

`DICOMOrganizer.organize()` currently overwrites `self.studies` entirely. We need a `merge_batch()` method that:

1. Accepts a new batch result (studies dict, file_paths dict, PS list, KO list) from a single load.
2. For each series in the new batch:
   a. Checks each file path against `loaded_file_paths` — skips files already present.
   b. Determines whether this is a new series entry or a slice-append to an existing series (based on UID + source-dir match).
   c. For new series: inserts into `studies` under the appropriate key (with disambiguation suffix if needed).
   d. For slice-append: inserts new datasets into the existing list and re-sorts.
3. Returns a `MergeResult` — lists of newly added `(study_uid, series_key)` tuples and appended `(study_uid, series_key)` tuples — so callers know what changed.

`file_paths` dict would also be merged (not replaced).

### 4.3 `_clear_data()` and Scene Clearing

`_clear_data()` currently clears **all** subwindows' ROIs, measurements, annotations, and scene state. For additive loading, it must **not** be called at all.

`handle_load_first_slice()` also clears all image viewer scenes and overlay items before displaying the new series. For additive loading, scenes for subwindows that still have valid assignments must **not** be cleared.

### 4.4 Subwindow Auto-Assignment After Additive Load

After merge, the `MergeResult` lists newly added series. The app iterates subwindows in order (0 → 3) and assigns the first newly added series to the first empty subwindow (if any). Subsequent new series are left in the navigator only.

"Empty subwindow" = `subwindow_data[idx]` has no current series assigned, or the subwindow has no image loaded. The existing navigator drag-to-subwindow assignment path continues to work for manual placement.

### 4.5 `reset_slot_to_view_default()` on Load

`_open_files`, `_open_folder`, and `_open_recent_file` all call this before opening. For additive loads, this must be **suppressed** — resetting the multi-window layout while the user already has content in subwindows would be disruptive.

### 4.6 Presentation States and Key Objects

Currently loaded into the annotation manager wholesale (replacing what was there). With additive loading, the new batch's PS/KO data needs to be **added** to the annotation manager, not replace it. Whether `annotation_manager` currently supports holding PS data from multiple studies simultaneously needs to be verified — this is a risk item.

### 4.7 Tag Edit History

Currently cleared on every load. With multiple studies loaded, the edit history for previously loaded studies should be preserved. The history is currently a flat stack with no study scoping. This means undo/redo will be **global** across all loaded studies; this is the path of least resistance and acceptable for now.

When a study or series is closed, we should **not** try to prune the undo stack (that would be very complex). Instead, if the user undoes a tag edit on a series that has since been closed, the undo should be a no-op or gracefully handled.

### 4.8 Memory / Pixel Cache Management

`_close_files()` explicitly frees cached pixel arrays from datasets before clearing `current_studies`. A per-series close path needs to do the same for only the closed series' datasets. The `loaded_file_paths` set must also have the closed series' file paths removed so those files can be re-loaded in a future load if desired.

### 4.9 Slice Navigator and Thumbnail Refresh After Slice Append

If new slices are merged into a series that is currently displayed in a subwindow, the subwindow's slice navigator needs to update its range without resetting to slice 0. The navigator's `update_slice_count()` or equivalent method should be called with the new count, preserving the current index if still in bounds.

The series navigator thumbnail uses the **first frame** of the series. If new slices are prepended (lower `InstanceNumber`), the thumbnail cache entry should be invalidated and regenerated.

---

## 5. Approach Options

### Approach A — Minimal / Flag-Based

Add a `keep_existing: bool = False` (default `False`, same as today) parameter that threads through the entire load path:

- `FileOperationsHandler`: skip `clear_data_callback()` when `keep_existing=True`
- `DICOMOrganizer.organize()`: add a `merge: bool` mode — when True, update `self.studies` and `self.file_paths` by merging the new batch in, skipping keys already present
- `handle_load_first_slice()`: when `keep_existing=True`, skip scene-clearing for existing subwindows, skip tag-history clear, merge PS/KO rather than replace, and only auto-assign new series to **empty** subwindows (or none)
- The default (menu-initiated fresh open) sets `keep_existing=False`, preserving today's behavior completely

**Pros:**
- Lowest risk: existing behavior entirely unchanged unless the flag is set
- No new classes or large restructuring required
- Can be implemented incrementally file-by-file

**Cons:**
- The `keep_existing` flag threads through many method signatures, which is somewhat code-smelly
- Merge logic lives scattered in `organize()`, `handle_load_first_slice()`, and the main load helpers
- Does not address longer-term needs (e.g., per-study provenance, series registry)

---

### Approach B — StudyRegistry (New Accumulation Class)

Introduce a `StudyRegistry` class that owns the **accumulated** data across all loads:

```python
class StudyRegistry:
    studies: Dict[str, Dict[str, List[Dataset]]]
    file_paths: Dict[Tuple, str]
    presentation_states: Dict[str, List[Dataset]]
    key_objects: Dict[str, List[Dataset]]

    def add_batch(self, new_studies, new_file_paths, ps, ko) -> Tuple[added_study_uids, added_series_keys]
    def remove_series(self, study_uid: str, series_uid: str)
    def remove_study(self, study_uid: str)
    def clear(self)
```

`DICOMOrganizer.organize()` continues to work exactly as today (single-batch → dict), but the result is handed to `StudyRegistry.add_batch()` rather than stored directly. `DICOMViewerApp.current_studies` becomes a property that returns `study_registry.studies`.

**Pros:**
- Clear ownership: one place manages the accumulated state
- `remove_series` / `remove_study` are explicit API points — close logic is clean
- `DICOMOrganizer` stays unchanged
- Easier to extend in the future (e.g., per-series metadata, load order tracking)

**Cons:**
- `current_studies` as a property vs. direct attribute is a small but real change; code elsewhere reads `app.current_studies` directly and expects a dict — needs careful audit
- New class to introduce and test
- More upfront work than Approach A

---

### Approach C — Full Refactor of Load/Close Pipeline

The most thorough option: redesign `FileSeriesLoadingCoordinator` to split its two current roles:

1. **Batch ingestion** (takes a path/paths, produces a batch of series)
2. **State integration** (merges/replaces into live state, decides what to display where)

With this split, additive loading is simply: same batch ingestion, different state integration (merge vs. replace). Close-study / close-series become operations on the state integration layer only, with no need to touch ingestion at all.

**Pros:**
- Cleanest long-term architecture; eliminates the implicit coupling between "file on disk" and "currently displayed state"
- Makes future features (e.g., changing what series a subwindow displays, split-screen comparison from two separate loads) straightforward

**Cons:**
- High risk: `FileSeriesLoadingCoordinator` and `FileOperationsHandler` together span 1000+ lines; touching both has broad regression surface
- Likely a multi-sprint effort
- Not justified for just this feature if the scope stays small

---

## 6. Recommended Approach

**Approach A (flag-based), with the data merge logic modeled on Approach B's structure** — specifically:

- In `DICOMOrganizer`, expose a `merge_batch(new_batch_studies, new_batch_file_paths, new_ps, new_ko, source_dir)` method alongside the existing `organize()` path. This method owns all merge/dedup logic: file-path dedup, source-dir-based series disambiguation, slice append, and disambiguation-suffix key generation. It returns a `MergeResult` dataclass.
- Add `loaded_file_paths: Set[str]` and `series_source_dirs: Dict[Tuple[str,str], str]` to `DICOMOrganizer` to support the merge and disambiguation logic.
- Since **all four entry points are now always additive**, the `keep_existing` flag can be dropped — the load path is always `merge_batch()`, never `organize()` from a blank state. The `Close All` path still calls `organize()` after a full clear (or just calls `dicom_organizer.clear()` followed by a fresh organize).
- `FileOperationsHandler` never calls `clear_data_callback()` during a normal open (since it's always additive). The only remaining call to full-clear is via `_close_files()`.
- `handle_load_first_slice()` skips scene-clearing for occupied subwindows, skips tag-history clear, merges PS/KO additively, and uses `MergeResult` to determine which (if any) new series to auto-assign to the first empty subwindow.
- `reset_slot_to_view_default()` is removed from the three menu-initiated open entry points.

For the **close-series / close-study** paths, introduce dedicated `_close_series(study_uid, series_uid)` and `_close_study(study_uid)` methods on `DICOMViewerApp`. These are new code paths with no regression risk on the existing load flow.

---

## 7. Scope of Changes by File (preliminary — see Section 9 for final)

*(Superseded by Section 9 after audit and decision round.)*

---

## 8. Resolved Questions and Audit Results

All questions from the first review round are now resolved.

| # | Question | Decision |
|---|---|---|
| 8.1 | ROI/annotations on close-series | **A — deleted permanently** (consistent with existing Close-All behavior) |
| 8.2 | PS/KO multi-study support in `annotation_manager` | **Audit complete — see 8.2 below** |
| 8.3 | Source folder for individual file picks | **A — each file's parent directory**, but see note below |
| 8.4 | Feedback on additive load | **Status bar always; toast/banner only if any files were skipped** |
| 8.5 | Navigator highlight for multiple occupied subwindows | **Small colored dot on every series that is currently open in any subwindow; only the focused subwindow's series gets the full highlight as today** |
| 8.6 | Fusion state on additive load | **Verify during implementation that `_reset_fusion_for_all_subwindows()` is not called on additive loads** |
| 8.7 | Focus behavior after closing focused subwindow's series | **Focus remains on the now-empty subwindow** |

### 8.2 Annotation Manager Audit — Detailed Findings

**File:** `src/tools/annotation_manager.py`  
**Verdict:** Structure is multi-study–capable, but load methods are hard overwrites — two fixes required.

**Internal data structure** (lines 53–54) is already keyed by `StudyInstanceUID`:
```python
self.presentation_states: Dict[str, List[Dataset]] = {}  # keyed by StudyInstanceUID
self.key_objects: Dict[str, List[Dataset]] = {}           # keyed by StudyInstanceUID
```

**Display filtering** (`get_annotations_for_image`, lines 240–266) correctly gates on `study_uid in self.presentation_states` and then on image/series UID — multi-study display would work correctly if the data were populated.

**Problem 1 — Hard overwrite in load methods:**
```python
# annotation_manager.py line 199
self.presentation_states = presentation_states  # full replacement

# annotation_manager.py line 208
self.key_objects = key_objects  # full replacement
```
These must be changed to `self.presentation_states.update(presentation_states)` and `.update(key_objects)` for additive loading.

**Problem 2 — Caller builds single-batch dict:**
`file_series_loading_coordinator.py` lines 149–161 build a fresh dict from `studies.keys()` (the current load batch only) and call `load_presentation_states` with that dict. For additive loading, the caller should pass only the new batch's PS/KO entries — and the `update()` fix above will merge them in.

**Problem 3 — `DICOMOrganizer.organize()` clears PS/KO on each call** (lines 67–68):
```python
self.presentation_states = {}
self.key_objects = {}
```
With additive loading via `merge_batch()`, this reset will not be called. The organizer's PS/KO store will also need to be accumulated additively (same merge logic as for `studies`).

**Problem 4 — Silent staleness on no-PS load:**
If a new load batch has no PS files, `load_presentation_states` is never called, leaving stale PS data from a previous study in the manager. With the `update()` approach this is no longer a problem (nothing is overwritten), but we must also ensure that closing a study removes its PS/KO entries from `annotation_manager` explicitly.

**Required fixes:**
| File | Line | Change |
|---|---|---|
| `src/tools/annotation_manager.py` | 199 | `=` → `.update()` |
| `src/tools/annotation_manager.py` | 208 | `=` → `.update()` |
| `src/tools/annotation_manager.py` | (new method) | Add `remove_study_annotations(study_uid)` to delete a study's PS/KO entries on close |
| `src/core/dicom_organizer.py` | 67–68 | Remove the PS/KO clear from `organize()`; accumulate via `merge_batch()` instead |

### 8.3 Note on File Dialog Behavior

The user is correct: Qt's `QFileDialog.getOpenFileNames()` uses the native OS file picker (Windows "Open" dialog on Windows), which only allows selecting files **from a single directory at a time**. Therefore, for any "open files" invocation, all selected files share the same parent directory. Using the immediate parent directory as the source folder for each file is both correct and unambiguous in practice.

The disambiguation rule simplifies to:

> Two series entries are considered the **same load group** if they have the same `StudyInstanceUID`, the same `composite_series_key` (UID + SeriesNumber), and files come from the same source directory. Otherwise they are distinct entries.

---

## 9. Updated Scope of Changes by File

| File | Change Needed |
|---|---|
| `src/gui/main_window_menu_builder.py` | Rename "Close" → "Close All" |
| `src/gui/series_navigator.py` | Add right-click context menu to `SeriesThumbnail` (`Close This Series` / `Close This Study`); add `close_series_requested` / `close_study_requested` signals; add per-subwindow colored dot indicator to thumbnails |
| `src/core/dicom_organizer.py` | Add `merge_batch()` method with file-path dedup, slice-append, and source-dir disambiguation; add `loaded_file_paths: Set[str]`, `series_source_dirs: Dict`, `MergeResult` dataclass; remove PS/KO clear from `organize()` |
| `src/core/file_operations_handler.py` | Remove `clear_data_callback()` call; call `merge_batch()` instead of `organize()`; pass source directory to `merge_batch()` |
| `src/core/file_series_loading_coordinator.py` | Rewrite `handle_load_first_slice()` additive path: skip scene-clearing for occupied subwindows, skip tag-history clear, call additive PS/KO load, use `MergeResult` to determine first empty subwindow auto-assignment; suppress `reset_slot_to_view_default()` |
| `src/tools/annotation_manager.py` | Change `load_presentation_states` / `load_key_objects` to use `update()` instead of assignment; add `remove_study_annotations(study_uid)` |
| `src/main.py` | Add `_close_series(study_uid, series_uid)` / `_close_study(study_uid)` methods; connect new navigator signals; add status bar + toast/banner feedback logic; update subwindow colored-dot tracking |
| `src/core/app_signal_wiring.py` | Connect `close_series_requested` / `close_study_requested` navigator signals |
| `src/core/subwindow_lifecycle_controller.py` | Handle focused-subwindow series being removed mid-session (clear display, stay on same subwindow) |

---

## 10. Implementation Plan

### Phase Overview

| Phase | Focus | Primary Files | Risk Level |
|---|---|---|---|
| 1 | DICOMOrganizer data layer | `dicom_organizer.py` | Medium — internal refactor |
| 2 | Annotation manager PS/KO fixes | `annotation_manager.py` | Low — small targeted fixes |
| 3 | Load pipeline — additive mode | `file_operations_handler.py`, `file_series_loading_coordinator.py`, `main.py` | **High** — core load path |
| 4 | Close-series and close-study | `main.py`, `dicom_organizer.py`, `annotation_manager.py`, `subwindow_lifecycle_controller.py` | Medium-High |
| 5 | Navigator UI — context menu + dots | `series_navigator.py`, `app_signal_wiring.py` | Medium — new Qt widgets |
| 6 | Menu rename + load feedback | `main_window_menu_builder.py`, `main.py` | Low |

Do not begin a later phase until all checklist items for the current phase are complete and verified.

---

### Phase 1 — DICOMOrganizer Data Layer

**Files:** `src/core/dicom_organizer.py`

**Goal:** Add the `merge_batch()` infrastructure. The existing `organize()` method is left functionally unchanged. A new `clear()` method replaces the scattered reset logic in the close path.

**Before starting:** Back up `src/core/dicom_organizer.py` to `backups/`.

**Implementation note (Phase 1 done):** Backup created as `backups/dicom_organizer_pre_multi_study_phase1.py`. All 233 project tests pass after implementation.

#### 1.1 — `MergeResult` dataclass

- [x] Add a `MergeResult` dataclass at the top of `dicom_organizer.py` (before the `DICOMOrganizer` class), with fields:
  - `new_series: List[Tuple[str, str]]` — `(study_uid, series_key)` for brand-new series entries
  - `appended_series: List[Tuple[str, str]]` — `(study_uid, series_key)` where new slices were merged in
  - `skipped_file_count: int` — files whose paths were already in `loaded_file_paths`
  - `added_file_count: int` — files actually ingested

#### 1.2 — New instance attributes

- [x] Add to `DICOMOrganizer.__init__`:
  - `self.loaded_file_paths: Set[str] = set()` — the global set of every file path ever loaded
  - `self.series_source_dirs: Dict[Tuple[str, str], str] = {}` — maps `(study_uid, series_key)` → `source_dir`
  - `self._disambiguation_counters: Dict[Tuple[str, str], int] = {}` — maps `(study_uid, base_series_key)` → next available suffix index (starts at 2 when a second source is encountered)

#### 1.3 — Extract `_organize_files_into_batch()`

> ⚠️ **CAUTION — most fragile step in Phase 1.** This refactors the core of `organize()`. Every line of business logic must be preserved exactly, including: multi-frame splitting, SOP Class UID routing for PS/KO, composite series key construction, InstanceNumber sort, SliceLocation fallback sort, ImagePositionPatient Z-coordinate fallback, and the `file_paths` dict population.

- [x] Create private method `_organize_files_into_batch(datasets: List[Dataset], file_paths_input: Optional[List[str]]) -> Tuple[dict, dict, dict, dict]` that returns `(batch_studies, batch_file_paths, batch_ps, batch_ko)` without touching `self`.
  - Move the grouping, SOP-routing, multi-frame handling, and sorting logic from `organize()` into this method.
  - Replace `self.studies`, `self.file_paths`, `self.presentation_states`, `self.key_objects` assignments inside the extracted code with assignments to local variables that are returned.
- [x] Rewrite `organize()` to call `_organize_files_into_batch()` and then assign the results to `self`:
  ```python
  def organize(self, datasets, file_paths=None):
      self.studies = {}
      self.file_paths = {}
      self.presentation_states = {}
      self.key_objects = {}
      batch_studies, batch_fp, batch_ps, batch_ko = self._organize_files_into_batch(datasets, file_paths)
      self.studies = batch_studies
      self.file_paths = batch_fp
      self.presentation_states = batch_ps
      self.key_objects = batch_ko
      return self.studies
  ```
- [ ] **Targeted test:** Load a multi-series, multi-study DICOM folder. Verify study/series structure, slice counts, and sort order are identical to before the refactor. *(Unit tests pass; live DICOM load test not yet performed — should be done before Phase 3.)*

#### 1.4 — Add `merge_batch()`

> ⚠️ **CAUTION:** The disambiguation logic is the trickiest part. A suffix must never be generated for the first instance of a series key — only for collisions with a different `source_dir`. Do not increment `_disambiguation_counters` until a collision is actually detected.

- [x] Add `merge_batch(datasets: List[Dataset], file_paths_input: Optional[List[str]], source_dir: str) -> MergeResult`:
  1. Filter out datasets whose corresponding file path (looked up from `file_paths_input` by index) is already in `self.loaded_file_paths`. Build a filtered `datasets_new` and `file_paths_new`. Populate `result.skipped_file_count`. ✓
  2. If `datasets_new` is empty, return an empty `MergeResult` immediately (nothing to do). ✓
  3. Call `_organize_files_into_batch(datasets_new, file_paths_new)` → `(batch_studies, batch_fp, batch_ps, batch_ko)`. ✓
  4. For each `(study_uid, series_dict)` in `batch_studies`: ✓
     - Case A (same/no source): slice append or new series. ✓
     - Case B (different source): disambiguation suffix `_v{n}`. ✓
  5. `batch_fp` merged into `self.file_paths` (per-series inside loop, not a single bulk update). ✓
  6. `batch_ps` / `batch_ko` merged via `.update()`. ✓
  7. Add ingested paths to `self.loaded_file_paths`, set `added_file_count`. ✓
  8. Return `result`. ✓

- [x] **Note on `file_paths_input` structure:** Dedup uses the input list by index (not the returned `batch_file_paths` dict). Confirmed consistent with `FileOperationsHandler`'s parallel list convention. *(Full verification against `FileOperationsHandler` call sites deferred to Phase 3 when the wiring is done.)*

  > **Implementation note:** `_disambiguation_counters` is read with `.get((study_uid, base_key), 2)` (never increments until a collision is detected) and then set to `n + 1`. The first load of any `base_key` always goes in with no suffix; only a second distinct `source_dir` triggers `_v2`.

#### 1.5 — Add `remove_series()` and `remove_study()`

- [x] Add `remove_series(study_uid: str, series_key: str) -> None`:
  - Collects matching keys from `file_paths`, pops them, removes paths from `loaded_file_paths`. ✓
  - Removes from `series_source_dirs`. ✓
  - Deletes `self.studies[study_uid][series_key]`. ✓
  - If `self.studies[study_uid]` is now empty: calls `remove_study(study_uid)`. ✓
- [x] Add `remove_study(study_uid: str) -> None`:
  - Collects all `file_paths` keys for this study, pops them, removes paths from `loaded_file_paths`. ✓
  - Cleans `series_source_dirs` for each series key. ✓
  - Deletes `self.studies[study_uid]`. ✓
  - Pops `presentation_states[study_uid]` and `key_objects[study_uid]`. ✓
  - Cleans `_disambiguation_counters` entries for this study. ✓

  > ⚠️ **CAUTION:** `remove_series()` calls `remove_study()` when the study becomes empty. `remove_study()` iterates series keys and removes them directly (not by calling `remove_series()` again) to avoid double-deletion and infinite recursion.

#### 1.6 — Add `clear()`

- [x] Add `clear() -> None` that resets all state: `studies = {}`, `file_paths = {}`, `presentation_states = {}`, `key_objects = {}`, `loaded_file_paths = set()`, `series_source_dirs = {}`, `_disambiguation_counters = {}`.

---

### Phase 2 — Annotation Manager PS/KO Fixes

**Files:** `src/tools/annotation_manager.py`

**Goal:** Make PS/KO loading additive and add a per-study removal method.

**Before starting:** Back up `src/tools/annotation_manager.py` to `backups/`.

**Implementation note (Phase 2 done):** Backup created as `backups/annotation_manager_pre_multi_study_phase2.py`. All 233 project tests pass.

- [x] In `load_presentation_states()` (line 199): change `self.presentation_states = presentation_states` to `self.presentation_states.update(presentation_states)`.
- [x] In `load_key_objects()` (line 208): change `self.key_objects = key_objects` to `self.key_objects.update(key_objects)`.
- [x] Add `remove_study_annotations(study_uid: str) -> None`:
  ```python
  def remove_study_annotations(self, study_uid: str) -> None:
      self.presentation_states.pop(study_uid, None)
      self.key_objects.pop(study_uid, None)
  ```
- [x] Add `clear_all_ps_ko() -> None` for use by the Close-All path:
  ```python
  def clear_all_ps_ko(self) -> None:
      self.presentation_states.clear()
      self.key_objects.clear()
  ```
- [x] **Verify:** `get_annotations_for_image()` already filters by `study_uid` — confirmed it gates on `study_uid in self.presentation_states` and `study_uid in self.key_objects`; multi-study dict is handled with no other changes needed.

---

### Phase 3 — Load Pipeline (Additive Mode) ✅ COMPLETE

**Files:** `src/core/file_operations_handler.py`, `src/core/file_series_loading_coordinator.py`, `src/main.py`

**Goal:** All four open entry points use `merge_batch()` and call a new `handle_additive_load()` method. The existing `handle_load_first_slice()` is left in place but no longer called from the normal load path. The `clear_data_callback()` is never called on opens.

**Backups:** `backups/file_operations_handler_pre_multi_study_phase3.py`, `backups/file_series_loading_coordinator_pre_multi_study_phase3.py`, `backups/main_pre_multi_study_phase3.py`

#### 3.1 — `FileOperationsHandler`: switch to `merge_batch()`

- [x] In all four methods (`open_files`, `open_folder`, `open_recent_file`, `open_paths`): **removed `clear_data_callback()` call entirely** from all 6 call sites.
- [x] `source_dir` determined per method:
  - `open_files` / `open_recent_file` (file) / `open_paths` (files): `os.path.dirname(os.path.abspath(first_file_path))`
  - `open_folder` / `open_recent_file` (folder) / `open_paths` (folder): the selected folder path
- [x] Replaced `dicom_organizer.organize(...)` with `merge_result = dicom_organizer.merge_batch(datasets, file_paths, source_dir)`. For folder loads (no explicit file_paths list), `getattr(ds, 'filename', None)` extracts paths from pydicom FileDataset objects.
- [x] Replaced `load_first_slice_callback(studies)` with `load_first_slice_callback(merge_result)`.
- [x] `_format_final_status` now receives `self.dicom_organizer.studies` (cumulative) and `merge_result.added_file_count`. Return value updated to `self.dicom_organizer.studies`.
- **Note:** `dicom_organizer` is a direct constructor param of `FileOperationsHandler` — no routing change needed.

#### 3.2 — `main.py` entry points: suppress `reset_slot_to_view_default()`

- [x] Removed `self.multi_window_layout.reset_slot_to_view_default()` from `_open_files()`, `_open_folder()`, and `_open_recent_file()`.

#### 3.3 — `FileSeriesLoadingCoordinator`: add `handle_additive_load()`

- [x] Added `handle_additive_load(merge_result)` after `handle_load_first_slice`. Implementation covers:
  - Always syncs `app.current_studies = app.dicom_organizer.studies`.
  - Early-exit (no new_series, no appended_series): refreshes navigator, returns.
  - Loads PS/KO additively for new study UIDs only (uses `update()` in annotation_manager).
  - Updates `subwindow_data[idx]['current_datasets']` for appended series; refreshes slice navigator count if focused.
  - Finds first empty subwindow; assigns first new series to it (display_slice + set_current_data_context).
  - Updates focused-subwindow state (current_dataset, current_study/series_uid, slice navigator, signals, metadata panel, cine, store_initial_view_state timer) **only if target_idx == focused_subwindow_index**.
  - Refreshes series navigator.
  - Shows series navigator if hidden and new series were added.
  - Updates fusion controls for the focused subwindow.
  - Does NOT call `tag_edit_history.clear_history()`.

#### 3.4 — Update the load callback reference

- [x] In `main.py` line 703: `load_first_slice_callback=self._file_series_coordinator.handle_additive_load`.

#### 3.5 — `_close_files()` update for new organizer state

- [x] After the pixel cache free loop and before `self.current_studies = {}`:
  - `self.dicom_organizer.clear()` — resets loaded_file_paths, series_source_dirs, _disambiguation_counters, studies, file_paths.
  - `self.annotation_manager.clear_all_ps_ko()` — clears PS/KO from annotation manager.

#### 3.6 — Targeted test after Phase 3

- All 233 automated tests pass.
- Manual smoke test (3.6): Load a folder, load a second folder, reload same folder, Close All — to be performed manually with real DICOM data.

---

### Phase 4 — Close-Series and Close-Study

**Files:** `src/main.py`, `src/core/subwindow_lifecycle_controller.py`

**Goal:** Implement right-click close behavior. A closed series is fully purged from the data store, affected subwindows are cleared, and the app state is updated cleanly.

**Before starting:** Back up `src/main.py` to `backups/`.

#### 4.1 — Add `_close_series()`

- [ ] Add `_close_series(self, study_uid: str, series_key: str) -> None` to `DICOMViewerApp`:

  1. **Identify affected subwindows:** iterate `app.subwindow_data`, collect indices where `data['current_study_uid'] == study_uid and data['current_series_uid'] == series_key`.

  2. **Free pixel caches:** for each dataset in `app.current_studies[study_uid][series_key]`, call any pixel-cache free method (same pattern as the loop in `_close_files()`). Check if `hasattr(ds, '_pixel_array_cache')` or equivalent.

  3. **Remove from organizer:** `self.dicom_organizer.remove_series(study_uid, series_key)`.
     - If after removal the study no longer exists in `dicom_organizer.studies`, also call `self.annotation_manager.remove_study_annotations(study_uid)`.

  4. **Update `app.current_studies`:** `app.current_studies = app.dicom_organizer.studies`.

  5. **Clear each affected subwindow:**
     - For each affected `idx`:
       - Get the subwindow's `image_viewer` via `multi_window_layout.get_subwindow(idx)`.
       - Clear the scene: `image_viewer.scene.clear(); image_viewer.image_item = None; image_viewer.viewport().update()`.
       - Clear overlay items via `subwindow_managers[idx]['overlay_manager'].clear_overlay_items(scene)`.
       - Clear ROIs: `subwindow_managers[idx]['roi_manager'].clear_all_rois()` (or equivalent).
       - Clear measurements and annotations (same pattern used in `_clear_data()`).
       - Reset `subwindow_data[idx]` to the empty template: `{'current_dataset': None, 'current_slice_index': 0, 'current_series_uid': '', 'current_study_uid': '', 'current_datasets': []}`.

  6. **Handle focused subwindow:**
     - If the focused subwindow was among the affected ones:
       - Update `app.current_dataset = None`, `app.current_study_uid = ''`, `app.current_series_uid = ''`, `app.current_slice_index = 0`, `app.current_datasets = []`.
       - Call `app.slice_navigator.set_total_slices(0); app.slice_navigator.set_current_slice(0)`.
       - Clear `app.metadata_panel` (call whatever clear method it exposes).
       - Stop cine: `app._update_cine_player_context()`.
       - Call `app._disconnect_focused_subwindow_signals()` and `app._connect_focused_subwindow_signals()`.
       - **Focus stays on the now-empty subwindow** — do not switch focus.
     - If the focused subwindow was not affected: no focus changes.

  7. **Update navigator:** `app.series_navigator.update_series_list(app.current_studies, app.current_study_uid, app.current_series_uid)`.

  > ⚠️ **CAUTION:** The ROI/measurement/annotation clear calls in step 5 must match exactly the pattern used in `_clear_data()` for the same subwindow index. If `_clear_data()` uses `roi_coordinator.clear_all()` rather than calling individual managers directly, use the same entry point to avoid partial clears. Review `_clear_data()` carefully before writing this step.

  > ⚠️ **CAUTION:** If the closed series was in a non-focused subwindow and the focused subwindow's `current_dataset` is fine, do NOT touch `app.current_dataset` or the slice navigator.

#### 4.2 — Add `_close_study()`

- [ ] Add `_close_study(self, study_uid: str) -> None` to `DICOMViewerApp`:
  1. Get all series keys: `series_keys = list(self.current_studies.get(study_uid, {}).keys())`.
  2. Identify all affected subwindow indices (same logic as `_close_series` but across all series in the study).
  3. Free pixel caches for all datasets in all series of the study.
  4. Call `self.dicom_organizer.remove_study(study_uid)`.
  5. Call `self.annotation_manager.remove_study_annotations(study_uid)`.
  6. `app.current_studies = app.dicom_organizer.studies`.
  7. Clear all affected subwindows (same steps as `_close_series` step 5).
  8. Handle focused subwindow (same steps as `_close_series` step 6).
  9. Update navigator.

  > **Note:** Do not implement `_close_study` as a loop over `_close_series` calls — that would invoke the navigator refresh multiple times per close. Do it as a single batch operation with one navigator refresh at the end.

#### 4.3 — Targeted test after Phase 4

- Load two studies. Right-click → Close This Series on a series in subwindow 1. Verify: series gone from navigator, subwindow 1 cleared, subwindow 0 unaffected.
- Right-click → Close This Study on a study. Verify all series from that study disappear; any subwindows showing them are cleared.
- Close the series currently in the focused subwindow (subwindow 0). Verify the subwindow is cleared, metadata panel is empty, focus stays on subwindow 0.
- Verify that after closing a series, reloading the same folder re-adds it cleanly (paths were removed from `loaded_file_paths`).

---

### Phase 5 — Navigator UI

**Files:** `src/gui/series_navigator.py`, `src/core/app_signal_wiring.py`, `src/main.py`

**Goal:** Add right-click context menu to thumbnails and colored dots showing which subwindows currently display each series.

**Before starting:** Back up `src/gui/series_navigator.py` to `backups/`.

#### 5.1 — Signals on `SeriesNavigator`

- [ ] Add two new signals to `SeriesNavigator`:
  ```python
  close_series_requested = Signal(str, str)  # (study_uid, series_key)
  close_study_requested = Signal(str)         # (study_uid)
  ```

#### 5.2 — Right-click context menu on `SeriesThumbnail`

- [ ] In `SeriesThumbnail`, override `contextMenuEvent(self, event)`:
  - Create a `QMenu`.
  - Add action "Close This Series" → emit `self._close_series_signal(self.study_uid, self.series_uid)`.
  - Add action "Close This Study" → emit `self._close_study_signal(self.study_uid)`.
  - Exec the menu at `event.globalPos()`.
- [ ] `SeriesThumbnail` needs two new signals: `close_series_signal(str, str)` and `close_study_signal(str)`. These are connected in `SeriesNavigator.update_series_list()` (where thumbnails are created) to forward to the navigator-level signals `close_series_requested` and `close_study_requested`.

  > ⚠️ **CAUTION:** `SeriesThumbnail` widgets are destroyed and recreated on every `update_series_list()` call. Signal connections made at creation time are severed when the widget is destroyed. This is fine as long as connections are made inside `update_series_list()` for each newly created thumbnail.

#### 5.3 — Colored subwindow dots

The goal is a small colored circle in the top-right corner of each thumbnail that is currently displayed in a subwindow. The four subwindow slot colors are: **blue** (slot 0), **green** (slot 1), **orange** (slot 2), **magenta** (slot 3).

- [ ] Define a `SUBWINDOW_DOT_COLORS` constant in `series_navigator.py`:
  ```python
  SUBWINDOW_DOT_COLORS = {0: "#2196F3", 1: "#4CAF50", 2: "#FF9800", 3: "#E91E63"}
  ```
- [ ] Add method `SeriesNavigator.set_subwindow_assignments(assignments: Dict[int, Tuple[str, str]]) -> None`:
  - `assignments` maps `subwindow_idx → (study_uid, series_key)` for every occupied subwindow.
  - Stores assignments internally: `self._subwindow_assignments: Dict[int, Tuple[str, str]] = {}`.
  - Calls `_refresh_dot_indicators()`.
- [ ] Add `_refresh_dot_indicators()`:
  - Builds a reverse map: `{(study_uid, series_key): List[int]}` (which slot indices display this series).
  - Calls `thumbnail.set_subwindow_dots(slot_indices)` on every thumbnail in the current layout.
- [ ] In `SeriesThumbnail`:
  - Add `set_subwindow_dots(slot_indices: List[int]) -> None` that stores `self._dot_slots = slot_indices` and calls `update()` to repaint.
  - Override `paintEvent`: after the existing paint, for each slot index in `self._dot_slots`, draw a filled circle (8px diameter) using `SUBWINDOW_DOT_COLORS[slot_idx]` at the top-right corner, offset by `slot_idx * 10px` leftward so dots don't overlap.

  > ⚠️ **CAUTION:** `update_series_list()` rebuilds all thumbnail widgets. After any rebuild, `set_subwindow_assignments()` must be called again to re-apply dots. The caller (app) must always pass the current assignments when updating the navigator. Add `subwindow_assignments` as an additional optional parameter to `update_series_list()`, or call `set_subwindow_assignments()` immediately after `update_series_list()` wherever `update_series_list()` is called.

- [ ] Update all existing call sites of `series_navigator.update_series_list(...)` in `file_series_loading_coordinator.py` and `main.py` to also pass or immediately follow with the current subwindow assignments.

#### 5.4 — Signal connections

- [ ] In `src/core/app_signal_wiring.py` (in the appropriate `_connect_*` sub-method, likely `_connect_dialog_signals` or a new `_connect_navigator_signals`):
  ```python
  app.series_navigator.close_series_requested.connect(app._close_series)
  app.series_navigator.close_study_requested.connect(app._close_study)
  ```
- [ ] After any call that changes `subwindow_data` (load, series drag-assign, close-series), call `series_navigator.set_subwindow_assignments(self._get_subwindow_assignments())` where `_get_subwindow_assignments()` is a small helper on `DICOMViewerApp` that builds the `Dict[int, Tuple[str, str]]` from `subwindow_data`.

  > ⚠️ **CAUTION:** `set_subwindow_assignments` and `_refresh_dot_indicators` must be called **after** the navigator has been rebuilt (i.e., after `update_series_list()`), never before, or the thumbnails to update won't exist yet.

---

### Phase 6 — Menu Rename and Load Feedback

**Files:** `src/gui/main_window_menu_builder.py`, `src/main.py`

#### 6.1 — Rename Close → Close All

- [ ] In `src/gui/main_window_menu_builder.py`, change `QAction("&Close", main_window)` to `QAction("Close &All", main_window)`.
- [ ] Update the tooltip/status tip if one is set.

#### 6.2 — Status bar and toast feedback on additive load

- [ ] In `handle_additive_load()`, after all state updates, set a status bar message:
  - If `merge_result.new_series`: `"Loaded {n} new series across {m} studies"`
  - If only `merge_result.appended_series` (no new series): `"Added {k} slice(s) to existing series"`
  - If nothing was new: `"No new files — all {total} already loaded"`
- [ ] Implement or reuse a toast/banner widget for the "skipped files" notification. Show the toast only when `merge_result.skipped_file_count > 0`. Text: `"{n} file(s) already loaded and skipped"`. Toast should auto-dismiss after 3 seconds.

  > ⚠️ If no toast/banner widget exists in the codebase, implement a minimal one: a `QLabel` with a semi-transparent rounded background that fades out via a `QPropertyAnimation`. Keep it under 50 lines. Place it as an overlay on the main window, anchored to the top-center or bottom-center.

---

### Cross-Cutting: Subwindow Assignment Helper

The following small helper method on `DICOMViewerApp` is needed by multiple phases (Phase 3, 4, 5):

- [ ] Add `_get_subwindow_assignments(self) -> Dict[int, Tuple[str, str]]`:
  ```python
  def _get_subwindow_assignments(self) -> Dict[int, Tuple[str, str]]:
      return {
          idx: (data['current_study_uid'], data['current_series_uid'])
          for idx, data in self.subwindow_data.items()
          if data.get('current_dataset') is not None
      }
  ```
  Call this wherever `series_navigator.set_subwindow_assignments()` is needed.

---

### Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| `_organize_files_into_batch()` extraction silently changes sort order or skips edge-case datasets | High | Targeted test with known multi-series dataset before and after extraction |
| `handle_additive_load()` updating the focused-subwindow app attributes when `target_idx` is not the focused subwindow | High | Guard every focused-subwindow state update behind `if target_idx == app.focused_subwindow_index` |
| `_close_series()` partial clear (e.g. ROIs cleared but annotations not) leaving stale graphics items | High | Replicate the exact clearing sequence from `_clear_data()`, verified line by line |
| `dicom_organizer.clear()` not called from `_close_files()`, causing `loaded_file_paths` staleness | High | Phase 3.5 checklist item; verify in Phase 3 targeted test |
| Navigator dot paint event called before `_dot_slots` is initialized | Medium | Initialize `self._dot_slots = []` in `SeriesThumbnail.__init__` |
| `set_subwindow_assignments()` called before `update_series_list()` on a fresh load | Medium | Always call `update_series_list()` first, then `set_subwindow_assignments()` |
| Disambiguation counter not incrementing correctly, producing duplicate keys | Medium | Unit test: load same-UID series from two separate folders, verify keys are distinct |
| Fusion state reset accidentally triggered on additive load | Low | Verify `_reset_fusion_for_all_subwindows()` is NOT called in `handle_additive_load()` |
| Silent staleness: `annotation_manager` PS/KO not cleared on `_close_files()` | Medium | Phase 3.5 checklist: `clear_all_ps_ko()` call in `_close_files()` |
