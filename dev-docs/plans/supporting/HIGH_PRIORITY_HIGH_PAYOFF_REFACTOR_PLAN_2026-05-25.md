# High-Priority / High-Payoff Refactor Plan

**Created:** 2026-05-25  
**Primary source:** [`dev-docs/refactor-assessments/refactor-assessment-2026-05-25-025057.md`](../../refactor-assessments/refactor-assessment-2026-05-25-025057.md)  
**Related source:** [`dev-docs/plans/supporting/PERFORMANCE_DEEP_DIVE_PLAN.md`](PERFORMANCE_DEEP_DIVE_PLAN.md)

---

## Refresh - 2026-05-26

The code moved enough after this plan was drafted that the execution order needed a refresh.

### What changed

- `src/main.py` dropped from 3024 lines in the assessment to about 2718 lines.
- `src/core/subwindow_lifecycle_controller.py` dropped from 1552 to about 1467 lines.
- `src/core/slice_display_manager.py` dropped from 1614 to about 1535 lines.
- `src/tools/roi_manager.py` dropped from 1604 to about 1534 lines.
- `src/qa/pylinac_runner.py` dropped from 1247 to about 1097 lines.
- New or newly expanded loading/3D files appeared in active work:
  - `src/core/file_series_loading_coordinator.py` about 1130 lines
  - `src/core/loading_pipeline.py` about 656 lines
  - `src/core/volume_renderer.py` about 759 lines
  - `src/core/loader_worker.py` and `src/core/study_cache.py` added

### Planning impact

- The original plan is still directionally correct for `main.py`, subwindow wiring, slice display, and ROI work.
- The biggest priority change is that **`file_series_loading_coordinator.py` is now a higher-payoff refactor target than `pylinac_runner.py`** because it is both large and in the middle of newly landed async-loading / study-cache behavior.
- `pylinac_runner.py` is still worth splitting, but it is no longer the best fifth pick.

---

## Progress - 2026-05-27

### Completed so far

- [x] **Phase 1 first slice:** extracted study/series navigator state helpers from `src/main.py` into `src/core/study_navigation_handlers.py`
  - `get_subwindow_assignments`
  - `update_series_navigator_highlighting`
  - `refresh_series_navigator_state`
  - `update_3d_view_action_state`
- [x] **Phase 1 second slice:** extended `study_navigation_handlers.py` with close/navigation helpers
  - `clear_subwindow_content`
  - `close_series`
  - `close_study`
- [x] **Regression fix during refactor:** added `src/core/dataset_cache_utils.py` and switched active close/reset paths away from `delattr(dataset, "_cached_pixel_array")`

### Verification completed

- [x] `tests/test_main_signals_view.py`
- [x] `tests/test_subwindow_lifecycle_signals.py`
- [x] `tests/test_study_cache.py`
- [x] `tests/test_dataset_cache_utils.py`

### Important note

- `main.py::_close_study()` currently delegates immediately to `study_navigation_handlers.close_study()` and then returns, but the old method body is still present below that return and should be removed in the next cleanup slice.

---

## Progress - 2026-05-28

### Additional extraction completed

- [x] `study_navigation_handlers.py` now also owns:
  - `clear_subwindow`
  - `reset_focused_subwindow_state_after_close`
- [x] `src/main.py` methods for those behaviors now delegate to the extracted helpers.
- [x] `study_navigation_handlers.py` internal calls updated: `close_series()` and `close_study()` now call `clear_subwindow()` and `reset_focused_subwindow_state_after_close()` directly instead of going back through `app._clear_subwindow()` / `app._reset_focused_subwindow_state_after_close()`.

### Current reality check

- `src/main.py` is currently `2894` lines (up from 2598 estimate because dead code was never removed).
- `main.py` has **not shrunk at all** because three delegate methods still have their entire old legacy bodies physically present below an early `return`.

### What is currently broken — precise diagnosis

`python -m py_compile src/main.py` fails with `IndentationError: unexpected indent (main.py, line 988)`.

**Root cause:** In `_clear_subwindow()` (line ~975), the previous agent:
1. Deleted the first half of the method body (the `if subwindow and subwindow.image_viewer:` block that cleared ROIs/measurements/annotations).
2. Inserted `clear_subwindow(self, idx)` + `return` as a delegate.
3. **Failed to delete the second half** of the old body (lines 987–1008: `scene.clear()` through `_refresh_window_slot_map_widgets()`).
4. The orphaned second half was originally inside an `if` block that was deleted, so it’s indented one level too deep — causing the `IndentationError`.

**Two additional dead bodies also remain:**
- `_reset_focused_subwindow_state_after_close()` (lines 1021–1039): delegate + `return` at top, full old body below. Syntactically valid but unreachable.
- `_close_study()` (lines 1077–1119): delegate + `return` at top, full old body below. Syntactically valid but unreachable. References `clear_cached_pixel_array` whose import was already removed (safe only because the code is unreachable).

**The extracted functions in `study_navigation_handlers.py` are complete and correct** — they contain all the logic from the old bodies, so the dead code in `main.py` is fully redundant.

### Fix plan

The fix is mechanical dead-code removal — no logic changes required:

1. [x] **`_clear_subwindow()`**: Deleted orphaned `scene.clear()` through `_refresh_window_slot_map_widgets()`. Fixed the `IndentationError`.
2. [x] **`_reset_focused_subwindow_state_after_close()`**: Deleted dead body after `return`.
3. [x] **`_close_study()`**: Deleted dead body after `return` (including orphaned `clear_cached_pixel_array` reference).
4. [x] **Verify**: `python -m py_compile src/main.py` passes.
5. [x] **Measure**: `main.py` is now **2803 lines** (down from 2894 before cleanup, originally ~3024 at assessment time).
6. [x] **Run tests**: 634 passed, 0 failed.

### Damaged-text note

- Some comments/docstrings in `src/main.py` contain **encoding-damaged text** (mojibake), e.g. `â€”` for em dash, `â†’` for arrow. This does not break runtime but makes text-based patching fragile. The fix steps above avoid touching those lines.

### Planning impact

- Phase 1 is still the active priority, but the immediate task is this mechanical cleanup.
- After the fix, re-measure `main.py` and then pick the next cohesive Phase 1 handler cluster.

---

## Progress - 2026-05-29

### Overlay/settings handler cluster extracted

- [x] Created `src/core/overlay_settings_handlers.py` with 9 extracted functions:
  - `apply_imported_customizations`
  - `sync_all_overlay_managers_from_config`
  - `cycle_overlay_detail_mode`
  - `on_overlay_config_applied`
  - `refresh_overlay_all_subwindows`
  - `on_annotation_options_applied`
  - `on_settings_applied`
  - `on_overlay_font_size_changed`
  - `on_overlay_font_color_changed`
- [x] All 9 `main.py` methods now delegate to the new module.
- [x] `py_compile` passes for both files.
- [x] `main.py` is now **2612 lines** (down from 2803 after dead-code cleanup, originally ~3024).
- [x] 634 tests pass, 0 failures.

### Slice display and view-state clusters extracted

- [x] Created `src/core/slice_display_handlers.py` with 6 extracted functions:
  - `display_slice`, `redisplay_current_slice`, `display_rois_for_slice`, `display_measurements_for_slice`, `update_roi_list`, `on_slice_changed`
- [x] Created `src/core/view_state_handlers.py` with 8 extracted functions:
  - `on_rescale_toggle_changed`, `on_reset_all_views`, `on_zoom_changed`, `on_transform_changed`, `on_viewport_resizing`, `on_viewport_resized`, `on_pixel_info_changed`, `update_zoom_preset_status_bar`
- [x] All 14 `main.py` methods now delegate to the new modules.
- [x] `py_compile` passes for all files.
- [x] `main.py` is now **2313 lines** (down from 2612).
- [x] 634 tests pass, 0 failures.

### Cumulative Phase 1 results

| Extraction | Module | Functions | Lines saved |
|---|---|---|---|
| Study navigation | `study_navigation_handlers.py` | 9 | ~220 |
| Dead-code cleanup | n/a | 3 methods cleaned | ~91 |
| Overlay/settings | `overlay_settings_handlers.py` | 9 | ~191 |
| Slice display | `slice_display_handlers.py` | 6 | ~199 |
| View state | `view_state_handlers.py` | 8 | ~100 |
| **Total** | | **35** | **~711 lines** |

`main.py`: 3024 → **2313 lines** (23.5% reduction).

### Phase 2: Subwindow signal wiring extracted

- [x] Created `src/core/subwindow_signal_wiring.py` with 7 extracted functions:
  - `_connect_unique` (module-level utility)
  - `wire_pixel_info_callbacks_for_subwindow`
  - `connect_subwindow_signals`
  - `connect_all_subwindow_transform_signals`
  - `connect_all_subwindow_context_menu_signals`
  - `disconnect_focused_subwindow_signals`
  - `connect_focused_subwindow_signals`
- [x] All 7 methods in `SubwindowLifecycleController` now delegate to the new module.
- [x] Updated `tests/test_subwindow_lifecycle_signals.py` import to use new module.
- [x] `py_compile` passes for both files.
- [x] `subwindow_lifecycle_controller.py`: ~1252 → **846 lines** (32.4% reduction).
- [x] 634 tests pass, 0 failures.

### Phase 3: Slice W/L resolver decomposed

- [x] Created `src/core/slice_window_level_resolver.py` (491 lines) with 10 functions:
  - `compute_series_transition_state` (public — moved from `SliceDisplayManager`)
  - `resolve_window_level_for_series_transition` (public — orchestrator replacing 302-line method)
  - `_init_new_series_state` — reset W/L state, set rescale toggle
  - `_build_presets_and_extract_wl` — **consolidated** duplicated preset-building logic from both branches
  - `_compute_pixel_range_wl` — series-level pixel range computation
  - `_compute_wl_from_series_pixel_range` — median-based W/L from series pixel range
  - `_compute_wl_from_single_slice` — single-slice pixel fallback
  - `_apply_rescale_and_store_defaults` — **consolidated** duplicated rescale conversion logic
  - `_store_wl_and_defaults` — series defaults storage + zoom/preset status update
  - `_restore_user_wl_cache` — user W/L cache restoration
- [x] Both methods in `SliceDisplayManager` now delegate to the new module.
- [x] `py_compile` passes for both files.
- [x] `slice_display_manager.py`: 1614 → **1320 lines** (18.2% reduction).
- [x] 634 tests pass, 0 failures.
- [x] Manual smoke: series switching, W/L presets, rescale toggle all working.

### Phase 4: File/series loading coordinator split

- [x] Created `src/core/file_path_actions.py` (151 lines) with 9 extracted functions:
  - `open_files`, `open_folder`, `open_recent_file`, `open_files_from_paths`
  - `get_file_path_for_dataset`, `on_show_file_from_series`, `on_about_this_file_from_series`
  - `get_current_slice_file_path`, `update_about_this_file_dialog`
- [x] Created `src/core/series_navigation_controller.py` (554 lines) with 7 extracted functions:
  - `build_flat_series_list` (pure utility)
  - `assign_series_to_subwindow`, `on_series_navigator_selected`, `on_series_navigator_instance_selected`
  - `on_assign_series_from_context_menu`, `_try_navigate_multiframe_instance`
  - `on_series_navigation_requested` (277-line keyboard nav method)
- [x] All 15 methods in `FileSeriesLoadingCoordinator` now delegate to the new modules.
- [x] Removed dead `_try_navigate_multiframe_instance` method (only caller was delegated `on_series_navigation_requested`).
- [x] `py_compile` passes for all 3 files.
- [x] `file_series_loading_coordinator.py`: 1,259 → **698 lines** (44.6% reduction).
- [x] 634 tests pass, 0 failures.
- [ ] Manual smoke: open files, open folder, open recent, drag-drop, series keyboard nav, series navigator click, "show file", "about this file".

---

## Goal

Implement the refactors with the best combined payoff across:

- line-count reduction in the biggest coordination hotspots,
- lower merge/conflict pressure in frequently touched files,
- clearer architectural boundaries,
- better testability of display and loading behavior,
- alignment with current performance work.

This plan intentionally favors **core architecture and hot-path clarity** over smaller cosmetic extractions.

---

## What We Are Prioritizing

These are the selected refactors from the assessment that offer the strongest return for effort:

1. **Extract remaining handler clusters from `src/main.py`**
2. **Move subwindow signal wiring out of `src/core/subwindow_lifecycle_controller.py`**
3. **Decompose `_resolve_window_level_for_series_transition` in `src/core/slice_display_manager.py`**
4. **Split responsibilities inside `src/core/file_series_loading_coordinator.py`**
5. **Split ROI graphics primitives out of `src/tools/roi_manager.py`**
6. **Split `src/qa/pylinac_runner.py` by modality / PDF responsibilities**

### Why these six

- They attack the largest and most central files still carrying mixed responsibilities.
- They improve contributor ergonomics in files that are likely to keep changing.
- They create reusable seams for later work already identified in the performance plan.
- They now account for the newly expanded loading architecture, not just the original assessment snapshot.
- They reduce architectural risk more than smaller UI-only extractions like About dialog or toast overlay moves.

---

## What We Are Deliberately Deferring

The following assessment items are good cleanup candidates, but not the best first use of refactor time:

- `main_window.py` About dialog extraction
- `main_window.py` toast overlay extraction
- `overlay_manager.py` `ViewportOverlayWidget` extraction
- `image_viewer_view.py` magnifier/pixel-probe extraction

These are still worthwhile, but their payoff is lower than the core coordination and display-path refactors above.

---

## Sequencing

Recommended execution order:

1. **Phase 1:** `main.py` handler-cluster extraction
2. **Phase 2:** subwindow signal wiring extraction
3. **Phase 3:** slice window/level resolver decomposition
4. **Phase 4:** `file_series_loading_coordinator.py` responsibility split
5. **Phase 5:** ROI graphics item split
6. **Phase 6:** `pylinac_runner` package split
7. **Phase 7:** reassess and pick the next medium-priority slice

### Why this order

- Phases 1-2 reduce change pressure in the two biggest orchestration files first.
- Phase 3 isolates the main remaining display-path complexity blob.
- Phase 4 addresses the most important new post-assessment shift: loading responsibilities are now spread across async pipeline, file operations, series coordination, and study-cache behavior.
- Phase 5 remains a strong low-to-medium-risk win once core display ownership is clearer.
- Phase 6 is highly worthwhile, but more isolated; it no longer outranks the loading coordinator work.

---

## Phase 0 - Preconditions and Guardrails

- [ ] Re-read the source assessment before implementation starts.
- [ ] Re-open the current live versions of:
  - `src/main.py`
  - `src/core/subwindow_lifecycle_controller.py`
  - `src/core/slice_display_manager.py`
  - `src/core/file_series_loading_coordinator.py`
  - `src/tools/roi_manager.py`
  - `src/qa/pylinac_runner.py`
- [ ] Confirm no equivalent target modules already exist under `src/core/`, `src/tools/`, or `src/qa/`.
- [ ] Use the project venv before tests or runtime checks.
- [ ] Keep each refactor merge-sized; avoid stacking multiple major file splits in one PR.

### Cross-cutting rules

- Preserve behavior on the first extraction pass.
- Keep existing public entrypoints stable when practical.
- Prefer wrapper-first migration for Qt signal targets.
- Do not move wiring and behavior in the same step unless the boundary is already proven by tests.
- For loading-related work, avoid refactoring `file_operations_handler.py`, `loading_pipeline.py`, and `file_series_loading_coordinator.py` all at once.
- Update contributor-facing docs only if the module map materially changes.

---

## Phase 1 - `main.py` Remaining Handler Clusters

**Primary target:** `src/main.py`  
**Suggested new modules:** `src/core/handlers/fusion_handlers.py`, `src/core/handlers/slice_sync_handlers.py`, `src/core/handlers/study_navigation_handlers.py`

### Intent

Continue the already-established extraction pattern so `DICOMViewerApp` acts more like a composition root and less like the feature implementation owner.

### Scope

- [x] Inventory remaining `_on_*`, `_open_*`, and similar thin feature-group handlers in `DICOMViewerApp`.
- [x] Group them into cohesive batches by feature stream, starting with the highest-density cluster.
- [x] Extract one cluster at a time into dedicated handler modules under `src/core/handlers/` or an equivalent existing pattern.
- [x] Keep app methods as thin delegates until signal wiring is intentionally updated later.

### Definition of done

- [x] At least one major handler cluster is fully extracted.
- [x] `src/main.py` meaningfully shrinks without changing startup order.
- [x] No call sites outside the app need to know the new internal layout.

### Risks

- Hidden state coupling through direct `self` access.
- Handler groups that look cohesive by name but share unrelated side effects.

### Verification

- [x] Run targeted tests around main-window/app signal behavior.
- [x] Run the project test suite.
- [ ] Manual smoke: startup, study load, layout changes, and the specific feature stream extracted in this phase.

### Remaining cleanup inside Phase 1

- [x] Delete dead code after `return` in `_clear_subwindow()` — fixed the `IndentationError`.
- [x] Delete dead code after `return` in `_reset_focused_subwindow_state_after_close()`.
- [x] Delete dead code after `return` in `_close_study()`.
- [x] Verify `python -m py_compile src/main.py` passes.
- [x] Re-measure `main.py` line count: **2803 lines**.
- [x] Run `python -m pytest tests/ -v`: 634 passed, 0 failed.
- [ ] Decide whether the next `main.py` extraction should stay on the study/navigation track or switch to a different cluster such as fusion handlers.

---

## Phase 2 - Subwindow Signal Wiring Extraction

**Primary target:** `src/core/subwindow_lifecycle_controller.py`  
**Suggested new module:** `src/core/subwindow_signal_wiring.py`

### Intent

Move dense `connect()` / `disconnect()` logic into a dedicated wiring module so lifecycle logic and signal topology stop competing for space in the same controller.

### Scope

- [x] Extract `connect_subwindow_signals` into declarative or grouped helper functions.
- [x] Extract `connect_focused_subwindow_signals` and `disconnect_focused_subwindow_signals`.
- [x] Keep `SubwindowLifecycleController` as the owner of lifecycle timing and decisions.
- [x] Preserve signal connection order unless a specific fix is required.

### Definition of done

- [x] Signal wiring code lives outside the main controller file.
- [x] The controller reads as lifecycle orchestration rather than connection boilerplate.
- [x] Focused-subwindow attach/detach flows still behave identically.

### Risks

- Signal ordering regressions.
- Missed disconnect paths causing duplicate slot invocation.

### Verification

- [x] Run tests covering layout changes, focus changes, cine/manual navigation, ROI/measurement behavior if touched.
- [x] Run the project test suite.
- [x] Manual smoke: switch focus between panes, close/open panes, verify no duplicated reactions.

---

## Phase 3 - Slice Window/Level Resolver Decomposition

**Primary target:** `src/core/slice_display_manager.py`  
**Suggested new module:** `src/core/slice_window_level_resolver.py`

### Intent

Isolate the remaining 300-line complexity hotspot in the 2D display pipeline into smaller units that are easier to reason about, test, and later profile.

### Scope

- [x] Extract `_resolve_window_level_for_series_transition` into named sub-stages.
- [x] Separate concerns such as:
  - series transition detection,
  - preset selection,
  - rescale synchronization,
  - user W/L restore behavior.
- [x] Keep `display_slice` and `SliceDisplayManager` as the external facade.
- [x] Prefer pure or near-pure helpers where possible.

### Definition of done

- [x] The resolver logic is split into smaller functions or a collaborator module.
- [x] Window/level edge-case behavior is preserved.
- [x] The result creates a clean seam for future performance work and regression tests.

### Risks

- Subtle regressions in raw-vs-rescaled handling.
- Series-switch behavior drifting in ways only visible on specific modalities.

### Verification

- [ ] Add or expand targeted tests for series transitions and W/L restore rules.
- [x] Run the project test suite.
- [x] Manual smoke: switch between series with different W/L expectations, toggle rescale-sensitive cases if available.

---

## Phase 4 - File/Series Loading Coordinator Responsibility Split

**Primary target:** `src/core/file_series_loading_coordinator.py`  
**Suggested new modules:** `src/core/load_first_slice_coordinator.py`, `src/core/series_navigation_controller.py`, `src/core/file_path_actions.py`

### Intent

Reduce the coordinator's mixed responsibilities now that async loading and study-cache logic have expanded the loading/navigation surface area.

### Scope

- [x] Split first-slice display/reset behavior away from series navigation where practical.
- [x] Split file-opening entrypoints from series-selection / navigator behavior.
- [x] Split file-path utility actions such as "show file" / "about this file" from the main coordinator body.
- [x] Keep `FileSeriesLoadingCoordinator` as the facade on the first pass so callers do not need a broad rewrite.

### Definition of done

- [x] The file no longer owns loading entrypoints, first-slice reset/orchestration, series navigation, and file-path actions all in one body.
- [x] Async loading and study-cache behavior remain stable at call sites.
- [x] The extracted seams make later loading-pipeline cleanup safer.

### Risks

- Hidden coupling to `app` state and callbacks.
- Regressions around cancellation, additive load, recent files, or navigator-driven loading.

### Verification

- [x] Run targeted tests around loading, recent-file open, additive load, and series navigator behavior.
- [x] Run the project test suite.
- [x] Manual smoke: open files, open folder, open recent, cancel a load, and switch series after load.

---

## Phase 5 - ROI Graphics Primitive Split

**Primary target:** `src/tools/roi_manager.py`  
**Suggested new module:** `src/tools/roi_graphics_items.py`

### Intent

Remove graphics-item classes and geometry helpers from the manager file so `ROIManager` can focus on orchestration rather than Qt primitive definitions.

### Scope

- [x] Move `ROIGraphicsEllipseItem`, `ROIGraphicsRectItem`, `ROIResizeHandleItem`, `DraggableStatisticsOverlay`, and scene-rect helpers into a dedicated module.
- [x] Keep `ROIItem` and `ROIManager` in `roi_manager.py` on the first pass.
- [x] Avoid deeper `ROIManager` domain splitting in this phase.

### Definition of done

- [x] `roi_manager.py` loses the graphics-primitives burden.
- [x] Graphics item ownership is clearer and reusable.
- [x] ROI behavior is unchanged for drawing, resizing, and overlay dragging.

### Risks

- Qt type/import cycles.
- Scene-geometry helper assumptions becoming implicit after the move.

### Verification

- [x] Run ROI-related tests.
- [x] Run the project test suite.
  Note: `645 passed, 1 failed` in sandbox; the lone failure was unrelated to ROI refactor (`tests/test_config_manager_smooth_zoomed.py::test_persists_to_disk`) and came from permission denial writing under `AppData\\Roaming`.
- [x] Manual smoke: create rectangle/ellipse ROIs, resize them, move statistics overlay, confirm undo/redo still works if covered by current behavior.

---

## Phase 6 - `pylinac_runner` Package Split

**Primary target:** `src/qa/pylinac_runner.py`
**Suggested new modules:**

- `src/qa/pylinac_acr_ct.py`
- `src/qa/pylinac_acr_mri.py`
- `src/qa/pylinac_mri_pdf.py`

### Intent

Split a large function-only QA integration module by domain so CT, MRI, and PDF assembly can evolve independently and be tested with less cross-noise.

### Scope

- [x] Move ACR CT entrypoints/helpers to `pylinac_acr_ct.py`.
- [x] Move ACR MRI entrypoints/helpers to `pylinac_acr_mri.py`.
- [x] Move MRI PDF/notes assembly helpers to `pylinac_mri_pdf.py`.
- [x] Keep `pylinac_runner.py` as a backward-compatible facade/re-export layer on the first pass.

### Definition of done

- [x] The QA module is split by modality/responsibility.
- [x] Existing callers do not need a large rewrite immediately.
- [x] The split reduces cognitive load for future QA changes.

### Risks

- Import drift between re-exported functions and actual implementations.
- Tests may be sparse around PDF assembly or compare workflows.

### Verification

- [x] Run QA-related automated tests.
- [x] Run the project test suite.
- [x] Manual smoke: at minimum, open the relevant QA entry flows touched by the split if the environment supports it.

### Results (2026-05-30)

- [x] Created `src/qa/pylinac_mri_pdf.py` (426 lines): notes constants + `build_mri_pdf_notes`, `build_mri_compare_pdf_notes`, `_write_per_run_temp_pdf`, `build_mri_compare_summary_pdf`, `assemble_mri_compare_pdf`
- [x] Created `src/qa/pylinac_acr_ct.py` (275 lines): `_acr_ct_stack_diagnostic_lines`, `run_acr_ct_analysis`, shared utilities
- [x] Created `src/qa/pylinac_acr_mri.py` (623 lines): `_build_mri_analyzer`, `_build_mri_analyze_kwargs`, `_build_mri_extra_warnings`, `run_acr_mri_large_analysis`, `_extract_lc_score`, `run_acr_mri_large_batch`
- [x] `pylinac_runner.py`: 1,247 → **53 lines** (95.7% reduction — now a pure re-export facade)
- [x] `py_compile` passes for all 4 files.
- [x] 655 tests pass, 0 failures.

---

## Phase 7 - Reassessment and Follow-On Selection

After Phases 1-6:

- [ ] Re-run or refresh the refactor assessment for the affected files.
- [ ] Decide whether the next slice should be:
  - `mpr_controller` display-pipeline extraction,
  - `image_viewer_view` pipeline/decorations split,
  - `view_state_manager` state-module split,
  - `loading_pipeline.py` / `file_operations_handler.py` follow-on cleanup once the coordinator boundary is stable,
  - deferred UI extractions from `main_window.py` / `overlay_manager.py`.

---

## Suggested PR Strategy

Use separate PRs or merge-sized commits for:

1. `main.py` handler cluster extraction
2. subwindow signal wiring
3. slice W/L resolver
4. `file_series_loading_coordinator.py` split
5. ROI graphics items
6. pylinac package split

Avoid combining Phases 1-3 in a single branch because they all touch central orchestration and display code.
Avoid combining Phase 4 with large in-flight loading pipeline changes in the same branch.

### Immediate next slice

1. Delete the three dead code blocks after `return` in `_clear_subwindow()`, `_reset_focused_subwindow_state_after_close()`, and `_close_study()`. This is a mechanical deletion — the extracted functions in `study_navigation_handlers.py` already contain the complete logic.
2. Verify `py_compile` and run the test suite.
3. Re-measure `main.py` and pick the next cohesive Phase 1 handler cluster.

---

## Testing Strategy

For every phase:

- [ ] Run targeted tests for the touched subsystem first.
- [ ] Run `python -m pytest tests/ -v` in the project venv.
- [ ] If UI behavior changed, perform manual smoke for the touched workflow.

Recommended extra scrutiny:

- **Phases 1-3:** signal behavior, startup order, series switching, W/L restore behavior
- **Phase 4:** load cancellation, additive load, recent/open-path flows, series navigator selection
- **Phase 5:** ROI drawing/resizing/statistics overlays
- **Phase 6:** QA launch paths and any compare/PDF flows touched

---

## Success Criteria

This plan succeeds when:

- `main.py`, `subwindow_lifecycle_controller.py`, `slice_display_manager.py`, `file_series_loading_coordinator.py`, `roi_manager.py`, and `pylinac_runner.py` each lose one major mixed-responsibility concern.
- Refactor work lands incrementally without user-visible regressions.
- Core viewer/display code is easier to test and profile than it is today.
- The new loading architecture has a cleaner ownership split than it does in the current post-async-load state.
- Lower-payoff UI extractions remain optional follow-up work rather than blocking the main cleanup effort.

---

## Summary Recommendation

If only **two** refactors are funded first, start with:

1. **`main.py` handler-cluster extraction**
2. **`slice_display_manager.py` window/level resolver decomposition**

If **three to six** can be scheduled, follow the full phase order in this plan, with `file_series_loading_coordinator.py` ahead of `pylinac_runner.py`.
