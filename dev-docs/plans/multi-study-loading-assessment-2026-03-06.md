# Multi-Study / Additive Loading — Assessment & Approach Options
**Date:** 2026-03-06  
**Status:** Assessment — awaiting approach decision before detailed planning

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

## 3. Key Design Challenges

### 3.1 Accumulating `DICOMOrganizer.studies` Across Multiple Loads

`DICOMOrganizer.organize()` currently overwrites `self.studies` entirely. We need a merge path. The key identity is `(StudyInstanceUID, composite_series_key)` — if the same series is dragged in twice, it should not be duplicated.

`file_paths` would also need to be merged, not replaced.

**Complication:** If the same `StudyInstanceUID` already exists (e.g., user adds more slices from the same study), we need to decide whether to merge at the series level or detect conflicts.

### 3.2 Deciding What to Display After an Additive Load

Currently the first series from the new load always goes to subwindow 0. With additive loading:

- If subwindow 0 (or the focused subwindow) is empty, the new series goes there — natural.
- If all subwindows are occupied, **what do we do?**
  - Option A: Fill empty subwindows, then do nothing (user assigns via drag-from-navigator).
  - Option B: Fill empty subwindows, then show a "Study/Series added" status message.
  - Option C: Always display the first series of the newest study in the focused subwindow, replacing what was there (but not purging it from the data store).

### 3.3 `_clear_data()` / Scene Clearing

`_clear_data()` currently clears **all** subwindows' ROIs, measurements, annotations, and scene state. For additive loading, it should **not** be called at all (ROIs/annotations for the currently displayed series should be preserved).

`handle_load_first_slice()` also clears all image viewer scenes and overlay items before displaying the new series. For additive loading, scenes for subwindows that still have valid, unchanged assignments should **not** be cleared.

### 3.4 Presentation States and Key Objects

Currently loaded into the annotation manager wholesale. With additive loading, the new batch's PS/KO data needs to be **added** to the annotation manager, not replace it.

### 3.5 Tag Edit History

Currently cleared on every load. With multiple studies loaded, the edit history for previously loaded studies should be preserved.

### 3.6 Memory / Pixel Cache Management

`_close_files()` explicitly frees cached pixel arrays from datasets before clearing `current_studies`. A per-series close path needs to do the same for only the closed series' datasets.

### 3.7 `reset_slot_to_view_default()` on Load

`_open_files`, `_open_folder`, and `_open_recent_file` all call this before opening. For additive loading, resetting the multi-window layout when adding a new study may be jarring and should probably be skipped or made optional.

---

## 4. Approach Options

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

## 5. Recommended Approach

**Start with Approach A (flag-based), with the data merge logic modeled on Approach B's structure** — specifically:

- In `DICOMOrganizer`, expose a `merge_batch(new_studies, new_file_paths, new_ps, new_ko)` method alongside the existing `organize()` path, so the merge is in one place rather than at the call site.
- Thread a `keep_existing` flag through the four `FileOperationsHandler` entry points and `handle_load_first_slice()`.
- Default today's behavior unchanged (flag defaults to `False`).

This gives the clean merge ownership of Approach B without introducing a new class, keeps risk low, and leaves the door open to extracting a `StudyRegistry` later.

For the **close-series / close-study** paths, introduce a dedicated `_close_series(study_uid, series_uid)` and `_close_study(study_uid)` method on `DICOMViewerApp` (or on a new `StudyCloseController`). These are new code paths with no regression risk on the existing load flow.

---

## 6. Scope of Changes by File

| File | Change Needed |
|---|---|
| `src/gui/main_window_menu_builder.py` | Rename "Close" → "Close All" |
| `src/gui/series_navigator.py` | Add right-click context menu to `SeriesThumbnail`; add `close_series_requested` / `close_study_requested` signals |
| `src/core/dicom_organizer.py` | Add `merge_batch()` method |
| `src/core/file_operations_handler.py` | Conditionally skip `clear_data_callback()` on additive load; call `merge_batch()` instead of `organize()` |
| `src/core/file_series_loading_coordinator.py` | Add `keep_existing` path in `handle_load_first_slice()`: skip scene clearing, skip tag-history clear, merge PS/KO, only assign to empty subwindows |
| `src/main.py` | Add `_close_series()` / `_close_study()` methods; connect new navigator signals; pass `keep_existing=True` from open entry points (after confirming with user if any preference setting is wanted) |
| `src/core/app_signal_wiring.py` | Connect new `close_series_requested` / `close_study_requested` signals |
| `src/core/subwindow_lifecycle_controller.py` | Update focused-subwindow signal logic for the case where the displayed series is removed mid-session |

---

## 7. Open Questions for User

1. **Default open behavior**: Should all four open entry points (Open Files, Open Folder, Recents, Drag-and-Drop) be additive by default, or should there be a user preference toggle (e.g., `File → Always add to current session`)? Or should drag-and-drop be additive while menu opens are still "replace"?

2. **New-series subwindow placement**: When a new study is loaded additively, which subwindow should it appear in? Options:
   - Auto-fill any empty subwindow (then stop if all are full)
   - Always use the focused subwindow (replacing the displayed series but keeping both in the data store)
   - Show nothing automatically; user assigns from navigator by dragging

3. **Duplicate detection**: If the user opens the same folder twice (same `StudyInstanceUID` and `SeriesInstanceUID`), should we silently ignore it, replace the existing series' data, or warn the user?

4. **Tag edit history across studies**: Should undo/redo history be scoped per-study (so closing a study removes its undo entries) or global (one undo stack for all edits regardless of study)?

5. **ROI/annotations on close-series**: Should ROIs, measurements, and annotations be deleted when the series they belong to is removed, or persisted in a recoverable undo state?

6. **Presentation State / Key Objects**: If multiple loaded studies each have their own PS, they all need to coexist in `annotation_manager`. Is that already supported, or does `annotation_manager` assume a single study's PS at a time?
