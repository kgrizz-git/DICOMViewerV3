# Post-Load First Paint Test Inventory (R3)

**Date:** 2026-07-12
**Task:** (R3) Inventory existing tests that touch loading handoff, first display, navigator rebuild, thumbnail cache/regeneration, stale/canceled loads, and current-series highlighting; identify likely files to extend for T10/T11.

> Research-only note. No product code or test edits here. Identifies coverage and gaps to inform T10 (staged/deferred stale-load tests) and T11 (navigator highlighting with deferred thumbnails).

## Coverage by concern

### 1. Loading handoff (loader completion → coordinator)

| Test file | What it covers | Notes |
|-----------|----------------|-------|
| `tests/test_canceled_load_behavior.py` | `run_load_pipeline` cancel path, `format_cancelled_partial_status`, `schedule_index_after_load` skip-on-cancel; patches `core.loading_pipeline.QTimer.singleShot` (`:51`) | Closest existing analogue to deferred/stale handling; tests the pipeline layer, not `handle_load_first_slice`. |
| `tests/test_loading_and_shell_helpers.py` | Folder-loading junk-basename skip; Windows reveal command | Named in the plan's testing strategy; currently thin, only 2 helper tests. |
| `tests/test_large_file_warning.py` | Large-file warning path (references `singleShot`) | Tangential. |

**Gap:** No test drives `handle_additive_load()` / `handle_load_first_slice()` in `src/gui/file_series_loading_coordinator.py` directly. The coordinator is only referenced by `tests/test_file_path_actions.py` (path helpers), not its first-slice display sequence.

### 2. First display (`display_slice`)

| Test file | What it covers |
|-----------|----------------|
| `tests/core/test_slice_display_handlers.py` | `slice_display_handlers.display_slice(app, ...)` wrapper: happy path stores initial view, MemoryError/RuntimeError handling, MPR routing, redisplay of current dataset, ROI/statistics sync, subwindow-state update path (`display_slice.assert_called_once_with(...)`). Uses `MagicMock` slice manager. |
| `tests/core/test_slice_display_lut.py`, `test_slice_display_pixels_projection_raw.py` | Rendering/LUT/pixel internals of the display manager. |
| `tests/core/test_slice_window_level_resolver.py` | W/L resolution during series transition. |

**Note:** These mock `slice_display_manager.display_slice`; they verify call wiring, not first-paint ordering. Suitable to assert "display before deferred work" if T3/T4 introduce staging at the handler level.

### 3. Navigator rebuild (`update_series_list`) and current-series highlighting

| Test file | What it covers |
|-----------|----------------|
| `tests/test_series_navigation_controller.py` | Heaviest coverage: `_build_flat_series_list`, `_assign_series_to_subwindow`, focused vs non-focused updates, and highlighting via `app._update_series_navigator_highlighting` (mock at `:58`, asserted `:226`) and `series_navigator.set_current_series(...)` (`:230`). Selection/instance-selection handlers. |
| `tests/gui/test_series_navigator_view.py` | Widget-level: `SeriesThumbnail.set_current(True/False)` badge/state (`:103-107`), `update_thumbnail_image` (`:100`), `_thumbnail_to_qimage` conversions, click/drag/context-menu emissions, study divider/label. Real `qapp`. |
| `tests/test_series_navigator_tooltips.py` | Tooltip/label builders, privacy masking, instance dedupe. Named in plan testing strategy. |

**Gap:** No test exercises `update_series_list()`'s full rebuild path or `set_current_position()`, nor the deferred `QTimer.singleShot(0, _process_next_thumbnail)` kickoff (`series_navigator.py:630`).

### 4. Thumbnail cache / regeneration

| Test file | What it covers |
|-----------|----------------|
| `tests/gui/test_series_navigator_view.py` | `SeriesThumbnail` image mutators and QImage conversion (widget level). |
| `tests/core/test_mpr_navigator_thumbnail.py` | MPR thumbnail pixel-array generation, rescale on/off, `set_mpr_thumbnail`/`clear_mpr_thumbnail`, middle-slice selection, error handling. |
| `tests/config/test_display_config.py` | Thumbnail-related display config. |

**Gap:** No test for the navigator's thumbnail cache lookup / cache-miss queue / `_process_next_thumbnail` deferred generation (`series_navigator.py:489-496, 627-655`), nor for cache reuse on additive loads (T8 target).

### 5. Stale / canceled loads

| Test file | What it covers |
|-----------|----------------|
| `tests/test_canceled_load_behavior.py` | Pipeline-level cancel semantics and index-callback skipping. |
| `tests/core/test_session_reset_controller.py` | `clear_data(app)` clears display/annotations/panels/study_cache on reset; skips missing subwindows/tools. |
| `tests/test_study_cache.py` | LRU `mark_accessed`/`remove`/`clear` — relevant to additive-load cache bookkeeping. |

**Gap:** No test for a **load-generation token** guarding deferred `QTimer.singleShot` callbacks (the core T5/T10 safety mechanism). No test that a newer load / cancel / close prevents a stale deferred callback from mutating the UI.

## Likely files to extend

### For T10 (staged/deferred post-load work; stale timers must not update UI after newer load/cancel/close)

1. **New: `tests/test_post_load_first_paint.py`** (recommended) — drive the coordinator's staged post-load queue / generation-token logic directly. Justified because no current test covers `handle_load_first_slice()` staging, and adding it to an existing thin file would blur scope.
   - Pattern to mirror: `tests/test_canceled_load_behavior.py` patching `QTimer.singleShot` to capture/invoke deferred callbacks synchronously; `tests/core/test_slice_display_handlers.py` for `app` `SimpleNamespace`/`MagicMock` scaffolding.
2. **Extend `tests/test_canceled_load_behavior.py`** — if the staging helper lives close to the pipeline, add stale-generation cases beside existing cancel tests.
3. Reference `tests/core/test_session_reset_controller.py` for the "reset invalidates in-flight state" assertion style (close/reset path).

### For T11 (navigator current-series highlighting when thumbnails are deferred)

1. **Extend `tests/test_series_navigation_controller.py`** — already asserts `set_current_series` / `_update_series_navigator_highlighting`; add a case where highlighting is correct while thumbnail generation is still pending (deferred).
2. **Extend `tests/gui/test_series_navigator_view.py`** — real `qapp` widget test; assert `SeriesThumbnail.set_current` reflects the current series before/while `_process_next_thumbnail` fills images (extend existing `set_current` test at `:97-107`).

## Summary of gaps (net-new coverage T10/T11 will need)

- Coordinator `handle_load_first_slice` / `handle_additive_load` first-paint ordering — **no direct tests today.**
- Load-generation token guarding deferred `singleShot` callbacks — **no tests.**
- Navigator `update_series_list` rebuild + `_process_next_thumbnail` deferred kickoff — **no tests.**
- Thumbnail cache hit/miss reuse on additive loads (T8) — **no tests.**
- Highlighting correctness while thumbnails deferred (T11) — **partial**; controller highlighting is tested but not under deferred-thumbnail conditions.

## Key anchors

| Item | File | Line(s) |
|------|------|---------|
| Cancel/pipeline + `singleShot` patch precedent | `tests/test_canceled_load_behavior.py` | 25-72 |
| `display_slice` wrapper behavior | `tests/core/test_slice_display_handlers.py` | 53-118 |
| Highlighting mock + assertions | `tests/test_series_navigation_controller.py` | 58, 216-230 |
| `SeriesThumbnail.set_current` / image mutators | `tests/gui/test_series_navigator_view.py` | 97-107 |
| Tooltip/label builders | `tests/test_series_navigator_tooltips.py` | 22-84 |
| Session reset clears state | `tests/core/test_session_reset_controller.py` | 69-101 |
| Study-cache LRU behavior | `tests/test_study_cache.py` | 33-66 |
| MPR thumbnail generation | `tests/core/test_mpr_navigator_thumbnail.py` | 31-113 |
| Deferred thumbnail kickoff (code under test, untested) | `src/gui/series_navigator.py` | 627-655 |
| Coordinator handler (code under test, no direct tests) | `src/gui/file_series_loading_coordinator.py` | 188-496 |
