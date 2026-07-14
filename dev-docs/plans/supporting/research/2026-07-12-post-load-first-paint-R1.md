# Post-Load First Paint Call Sequence Map (R1)

**Date:** 2026-07-12
**Task:** (R1) Map the post-load call sequence from loader completion through first `display_slice()`, app/subwindow state updates, metadata/cine/history refresh, `series_navigator.update_series_list()`, thumbnail creation, and `_refresh_series_navigator_state()`; report exact function names and file/line anchors.

## Complete Call Sequence

### 1. Loader Completion → Load First Slice Callback

**Entry Point:** Async loading pipeline completion in `src/core/loading_pipeline.py`

- **Line 340:** `load_first_slice_callback(merge_result)`
  - File: `src/core/loading_pipeline.py`
  - This callback is set to `app._file_series_coordinator.handle_additive_load` (see `src/gui/app_handler_bootstrap.py:95`)

### 2. Additive Load Handler (Main Entry)

**Function:** `handle_additive_load()` in `src/gui/file_series_loading_coordinator.py`

- **Line 400-414:** `def handle_additive_load(self, merge_result: Any) -> None:`
  - File: `src/gui/file_series_loading_coordinator.py`
  - Called by loading pipeline after `merge_batch()` completes
  - Updates `app.current_studies` with organizer studies (line 417)
  - Handles LRU study cache eviction (lines 419-445)
  - Processes study index auto-add (lines 447-468)
  - Shows toast for duplicate skips (lines 470-476)
  - Calls `handle_load_first_slice()` for initial loads (line 491)

### 3. Load First Slice Handler (Core Display Logic)

**Function:** `handle_load_first_slice()` in `src/gui/file_series_loading_coordinator.py`

- **Line 188-398:** `def handle_load_first_slice(self, studies: dict[str, dict[str, list[Dataset]]]) -> None:`
  - File: `src/gui/file_series_loading_coordinator.py`
  - **Key operations in sequence:**

#### 3.1 Clear State (Lines 201-235)
- **Line 202:** `app._reset_fusion_for_all_subwindows()` - Disables fusion for all subwindows
- **Line 205-206:** Clear edited tags for previous dataset via `tag_edit_history.clear_edited_tags()`
- **Line 208-213:** Clear all subwindows: `image_viewer.scene.clear()`, set `image_item = None`, `viewport().update()`
- **Line 216-225:** Clear overlay items for all subwindows via overlay managers
- **Line 228:** `app.slice_display_manager.reset_projection_state()` - Reset projection state
- **Line 229-231:** Reset intensity projection controls widget
- **Line 233-234:** Clear tag viewer filter via dialog coordinator

#### 3.2 Load First Slice Info (Lines 236-243)
- **Line 236:** `first_slice_info = app.file_operations_handler.load_first_slice(studies)`
  - Calls `src/gui/file_operations_handler.py:508-535` `load_first_slice()`
  - Returns dict with `study_uid`, `series_uid`, `slice_index`, `dataset`, `total_slices`
- **Line 238-242:** Update app state: `current_studies`, `current_study_uid`, `current_series_uid`, `current_slice_index`

#### 3.3 Fusion Controls Update (Lines 244-251)
- **Line 244-251:** Update fusion controls series list for focused subwindow

#### 3.4 Clear Stale Subwindow Data (Lines 253-273)
- **Line 254-269:** Clear subwindow_data for series not in current_studies
- **Line 270-273:** Debug logging for stale data clearance

#### 3.5 Load Presentation States and Key Objects (Lines 275-288)
- **Line 276-284:** Iterate through studies, get presentation states and key objects from organizer
- **Line 285-288:** Load into annotation manager

#### 3.6 Set Up Subwindow 0 (Lines 290-305)
- **Line 291-294:** Set subwindow 0 as focused
- **Line 296-297:** Ensure subwindow 0 has managers
- **Line 299-305:** Get slice_display_manager_0 and view_state_manager_0
- **Line 304-305:** Reset window level state and series tracking

#### 3.7 Update Slice Navigator (Lines 307-308)
- **Line 307-308:** Set total slices and current slice on slice navigator

#### 3.8 **FIRST DISPLAY SLICE CALL** (Lines 310-317)
- **Line 310-317:** `slice_display_manager_0.display_slice(first_slice_info['dataset'], ...)`
  - File: `src/gui/slice_display_manager.py:858-995`
  - **This is the critical first image display call**

#### 3.9 Update App Dataset State (Lines 319-351)
- **Line 319:** `app.current_dataset = first_slice_info['dataset']`
- **Line 321-351:** Update subwindow_data for focused window (index 0)
- **Line 338-341:** Set current dataset, slice index, series UID, study UID in subwindow_data
- **Line 343-344:** Sync app current_series_uid and current_study_uid
- **Line 346-351:** Update current_datasets in subwindow_data

#### 3.10 Set Data Context (Lines 353-363)
- **Line 353-359:** `slice_display_manager_0.set_current_data_context(...)`
- **Line 361-363:** Set view_state_manager_0 current_dataset
- **Line 364-365:** Set app view_state_manager alias

#### 3.11 ROI Coordinator Setup (Lines 366-368)
- **Line 366-368:** Set app.roi_coordinator from subwindow 0 managers

#### 3.12 Signal Connection (Lines 370-371)
- **Line 370-371:** Disconnect and reconnect focused subwindow signals

#### 3.13 Metadata and Cine Update (Lines 373-374)
- **Line 373:** `app.metadata_panel.clear_filter()`
- **Line 374:** `app.cine_app_facade.update_cine_player_context()`

#### 3.14 Tag Edit History and Undo/Redo (Lines 376-378)
- **Line 376-378:** Clear tag edit history and update undo/redo state

#### 3.15 Deferred View State Store (Line 380)
- **Line 380:** `QTimer.singleShot(100, app.view_state_manager.store_initial_view_state)`

#### 3.16 **SERIES NAVIGATOR UPDATE** (Lines 382-388)
- **Line 382-386:** `app.series_navigator.update_series_list(app.current_studies, app.current_study_uid, app.current_series_uid)`
  - File: `src/gui/series_navigator.py:332-630`
  - **This is the navigator rebuild call**
- **Line 387:** `app._refresh_series_navigator_state()`
  - File: `src/main.py:1373-1375` → `src/core/study_navigation_handlers.py:66-92`
- **Line 388:** `app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())`

#### 3.17 Navigator Visibility and Fit (Lines 390-394)
- **Line 390-392:** Show series navigator if it was hidden
- **Line 393-394:** `QTimer.singleShot(50, lambda: app.image_viewer.fit_to_view(center_image=True))`

#### 3.18 Slice Location Lines (Lines 396-398)
- **Line 397:** `app._slice_sync_coordinator.invalidate_cache()`
- **Line 398:** `QTimer.singleShot(100, app._slice_location_line_coordinator.refresh_all)`

### 4. Display Slice Implementation (First Image Display)

**Function:** `display_slice()` in `src/gui/slice_display_manager.py`

- **Line 858-995:** `def display_slice(self, dataset, current_studies, current_study_uid, current_series_uid, current_slice_index, ...)`
  - File: `src/gui/slice_display_manager.py`
  - **Key operations:**

#### 4.1 Dataset Resolution (Lines 891-898)
- **Line 892-898:** `_resolve_canonical_dataset_for_slice()` - Get canonical dataset for slice

#### 4.2 Context Update (Lines 899-905)
- **Line 899-905:** `_update_current_context()` - Update current context managers

#### 4.3 Rescale Context Sync (Line 906)
- **Line 906:** `_sync_view_state_rescale_context(dataset)` - Sync rescale slope/intercept/type

#### 4.4 Series Transition State (Lines 907-909)
- **Line 907-909:** `_compute_series_transition_state()` - Detect series transitions

#### 4.5 JPEG-LS Warning (Lines 911-926)
- **Line 911-926:** Check for JPEG-LS transfer syntax and show warning if new series

#### 4.6 Window/Level Resolution (Lines 932-942)
- **Line 932-942:** `_resolve_window_level_for_series_transition()` - Compute W/L for transition

#### 4.7 **Base Image Rendering** (Lines 944-959)
- **Line 944-959:** `_render_base_image_pipeline()` - **This renders the actual image**
  - Includes pixel extraction, W/L application, image conversion
  - Updates image_viewer.image_item with the rendered pixmap

#### 4.8 Controls and Metadata Sync (Lines 961-973)
- **Line 961-973:** `_sync_controls_and_metadata()` - Update controls and metadata panel

#### 4.9 Scene Overlays and Annotations (Lines 974-981)
- **Line 974-981:** `_render_scene_overlays_annotations()` - Render overlays and annotations

### 5. Series Navigator Update (Navigator Rebuild)

**Function:** `update_series_list()` in `src/gui/series_navigator.py`

- **Line 332-630:** `def update_series_list(self, studies, current_study_uid, current_series_uid)`
  - File: `src/gui/series_navigator.py`
  - **Key operations:**

#### 5.1 State Initialization (Lines 346-348)
- **Line 346-348:** Set current_study_uid, current_series_uid, _last_studies

#### 5.2 Clear Existing Layout (Lines 350-369)
- **Line 350-358:** Clear existing widgets from main layout
- **Line 361-369:** Clear tracking lists and cancel pending thumbnail jobs

#### 5.3 Study Iteration (Lines 374-623)
- **Line 376:** Iterate through all studies
- **Line 382-385:** Add study dividers (except first study)
- **Line 387-398:** Get study label from first dataset
- **Line 400-413:** Build and sort series list by SeriesNumber
- **Line 415-445:** Calculate section width including thumbnails and MPRs
- **Line 447-473:** Create study section with label
- **Line 475-594:** **Create thumbnails for each series**
  - **Line 489-496:** Check thumbnail cache, queue cache misses for deferred generation
  - **Line 498-545:** Create SeriesThumbnail widgets
  - **Line 547-592:** Create instance thumbnails if show_instances_separately
  - **Line 596-615:** Create MPR thumbnail widgets
- **Line 617-621:** Add study section to main layout

#### 5.4 Current Position Update (Line 625)
- **Line 625:** `self.set_current_position(current_series_uid, current_study_uid, self.current_slice_index)`

#### 5.5 **Deferred Thumbnail Generation Kickoff** (Lines 627-630)
- **Line 629-630:** `QTimer.singleShot(0, self._process_next_thumbnail)` if pending jobs exist
  - **This is already deferred - thumbnails are generated one-at-a-time on event loop**

### 6. Deferred Thumbnail Generation

**Function:** `_process_next_thumbnail()` in `src/gui/series_navigator.py`

- **Line 636-655:** `def _process_next_thumbnail(self)`
  - File: `src/gui/series_navigator.py`
  - **Line 639-641:** Pop one pending thumbnail job
  - **Line 642:** `_generate_thumbnail(first_dataset, series_datasets)` - Generate thumbnail image
  - **Line 644-645:** Cache thumbnail image
  - **Line 647-649:** Update thumbnail widget with new image
  - **Line 652-655:** Schedule next thumbnail via `QTimer.singleShot(0, ...)`

**Function:** `_process_next_instance_thumbnail()` in `src/gui/series_navigator.py`

- **Line 657-674:** `def _process_next_instance_thumbnail(self)`
  - File: `src/gui/series_navigator.py`
  - Similar pattern for instance thumbnails

### 7. Refresh Series Navigator State

**Function:** `refresh_series_navigator_state()` in `src/core/study_navigation_handlers.py`

- **Line 66-92:** `def refresh_series_navigator_state(app: Any)`
  - File: `src/core/study_navigation_handlers.py`
  - **Line 68-70:** `app.series_navigator.set_multiframe_info_map(app.dicom_organizer.series_multiframe_info)`
  - **Line 71-75:** Set show_instances_separately from config
  - **Line 77-82:** Get multiframe_info for current series
  - **Line 84-91:** Enable/disable show_instances_separately based on multiframe info
  - **Line 92:** `update_3d_view_action_state(app)`

## Critical Timing Observations

### Synchronous Blocking Sequence
The main blocking sequence in `handle_load_first_slice()` (lines 188-398) executes **synchronously** before returning to the event loop:

1. **Lines 201-235:** Clear state (subwindows, overlays, fusion) - **synchronous**
2. **Lines 236-243:** Load first slice info - **synchronous**
3. **Lines 310-317:** **First display_slice() call** - **synchronous image rendering**
4. **Lines 319-363:** Update app state and data context - **synchronous**
5. **Lines 370-378:** Signal connection, metadata/cine/history update - **synchronous**
6. **Lines 382-388:** **Series navigator rebuild** - **synchronous layout and widget creation**
7. **Line 387:** **Refresh navigator state** - **synchronous**

### Deferred Operations
Only these operations are already deferred via `QTimer.singleShot()`:

- **Line 380:** View state store (100ms delay)
- **Line 394:** Fit to view (50ms delay, conditional)
- **Line 398:** Slice location lines (100ms delay)
- **Line 630:** Thumbnail generation (0ms delay, but processes one-at-a-time)

### Potential Blockers

1. **First display_slice() (Line 311-317):** Image rendering including pixel extraction, W/L application, PIL conversion
2. **Series navigator rebuild (Line 382-386):** Widget creation, layout calculations, study/series iteration
3. **Metadata panel update (Line 373):** May be expensive for large datasets
4. **Cine player context update (Line 374):** May have overhead
5. **Refresh navigator state (Line 387):** Multiframe info lookup and UI enablement

### Thumbnail Generation Status
**Already deferred:** Thumbnail generation is already chunked via `QTimer.singleShot(0, ...)` in `series_navigator.py:630`. The navigator rebuild creates placeholder widgets and fills thumbnails progressively, which should not block first paint.

## Key File and Line Anchors Summary

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `handle_additive_load()` | `src/gui/file_series_loading_coordinator.py` | 400-496 | Main entry from loader completion |
| `handle_load_first_slice()` | `src/gui/file_series_loading_coordinator.py` | 188-398 | Core display and state update logic |
| `load_first_slice()` | `src/gui/file_operations_handler.py` | 508-535 | Get first slice info from studies |
| `display_slice()` | `src/gui/slice_display_manager.py` | 858-995 | **First image display** |
| `update_series_list()` | `src/gui/series_navigator.py` | 332-630 | **Navigator rebuild** |
| `_process_next_thumbnail()` | `src/gui/series_navigator.py` | 636-655 | Deferred thumbnail generation |
| `refresh_series_navigator_state()` | `src/core/study_navigation_handlers.py` | 66-92 | Navigator state refresh |

## Recommendations for Instrumentation

Based on this call sequence, timing instrumentation should be placed at:

1. **Entry to handle_load_first_slice()** (line 188)
2. **Before display_slice() call** (line 310)
3. **After display_slice() returns** (line 318)
4. **Before update_series_list()** (line 382)
5. **After update_series_list() returns** (line 386)
6. **Before refresh_series_navigator_state()** (line 387)
7. **After refresh_series_navigator_state()** (line 388)
8. **Exit from handle_load_first_slice()** (line 398)
9. **Within display_slice()** at key pipeline stages (render, metadata, overlays)
10. **Within update_series_list()** at layout rebuild start/end
11. **Event loop return** after handle_load_first_slice() completes

This will identify which synchronous operations are blocking first paint.
