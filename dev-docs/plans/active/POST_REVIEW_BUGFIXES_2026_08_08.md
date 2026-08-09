# Post-Review Bugfixes and Architectural Improvements

**Date:** 2026-08-08
**Status:** Implemented on `bugfix/post-review-cleanup` (ready for PR)
**Last reviewed:** 2026-08-09 (PR scope tagged; implementation landed)

## Overview
This plan tracks bugs, edge-case flaws, and architectural improvements identified by subagent code reviews during the test coverage expansion effort. Per project policy, these findings were isolated rather than fixed in-flight during the test-writing phase.

## Implementation notes (2026-08-09)

- Execute only the **[PR]** items below in this branch; leave deferred items alone.
- Prefer TDD against existing strict `@pytest.mark.xfail` tests; remove the
  marker once the fix lands (do not leave green xfails).
- When a current test encodes buggy behavior (e.g. crosshair
  `_move_batch_timer` identity replacement for **17B**, tag-export drain
  patching `time.time` for **3**), update the test to the intended contract
  in the same commit as the fix.
- For **18B**, prefer removing or documenting the unused
  `handle_settings_applied` stub rather than double-invoking settings
  callbacks (see review table).
- Land this PR before MainWindow extractions; Phase 0 characterization for
  `MAIN_WINDOW_REFACTOR_PLAN.md` remains a separate required gate.

## PR scope (planned)

The following items are selected for a single bug-fix + cleanup PR.

**Bug fixes:**
- 3 — `TagExportUnionHost`: `time.time()` → `time.monotonic()`
- 4A/4B — `SliceLocationLineCoordinator`: manager init guard + pending refresh drain
- 5A — `TextAnnotationCoordinator`: pop stale move-tracking on deletion
- 14A — `CineControlsWidget`: `set_speed` float formatting mismatch
- 14B — `CineControlsWidget`: refresh tooltip on zero frames
- 15A — `CinePlayer`: allow single multi-frame DICOM into cine path
- 17B — `CrosshairCoordinator`: reuse QTimer instead of allocating per-move
- 21A — `study_index_config`: deduplicate column-order normalization

**Cleanups:**
- 6A — `LayoutWindowSlotController`: extract hardcoded max slot constant
- 6B — `LayoutWindowSlotController`: `app.config_manager` consistency
- 12A — `MainWindowLayoutHelper`: log instead of silently swallowing exceptions
- 17A — `CrosshairCoordinator`: remove dead `if commands:` branch
- 18A — `DialogCoordinator`: remove unreachable dead code in `open_histogram`
- 18B — `DialogCoordinator`: wire or remove unused `handle_settings_applied` stub

## Review recommendations (2026-08-09)

The coverage review validated the following priority and scope. “Do not pursue”
means the reported behavior is either the explicit production contract, an
unsupported partial-test fixture, or a future feature request rather than a
current defect.

| ID | Review conclusion | Recommendation |
| --- | --- | --- |
| 1 | Plausible smooth-scroll UX problem; threshold selection changes normal wheel behavior. | Validate with a physical smooth-scrolling device, then implement an accumulator with focused interaction tests. |
| 2 | First-seen is a valid tag-catalog policy; value aggregation is a product decision. | Do not change without a tag-export UX requirement. |
| 3 | Valid timeout robustness issue. | **[PR]** Use `time.monotonic()` and test elapsed-time behavior. |
| 4A–4B | Valid coordinator invariants; public single-view refresh can lose work. | **[PR]** Fix manager creation and drain the pending refresh in the single-view `finally` path. |
| 5A | Valid stale-reference issue after annotation deletion. | **[PR]** Remove tracking entries on deletion; cover direct and undo/redo deletion. |
| 5B | No concurrent pointer drag exists in the normal Qt interaction model. | Do not add per-item timers unless an actual lost-move reproduction appears. |
| 6A | The application currently supports exactly four slots. | **[PR]** Extract hardcoded constant; future layout-expansion work deferred. |
| 6B | Consistency improvement only; production main window owns the config manager. | **[PR]** Align to `app.config_manager`. |
| 7A–7B | Possible cursor-state hardening, but no user-visible stale-cursor reproduction. | Defer until reproduced; test against real cursor objects rather than mocks. |
| 8A | A harmless startup/teardown guard would improve resilience. | Add the layout guard if lifecycle work touches this module. |
| 8B | `privacy_view_enabled` is an application initialization contract. | Do not add a fallback solely for partial mocks. |
| 9 | Omitting incomplete W/L is explicitly documented behavior. | Do not change. |
| 10A | Helpers receive trusted preset colors only. | Do not add validation without an untrusted color input path. |
| 10B | Plausible frozen-build resilience improvement, unverified. | Reproduce in a frozen-build test before changing resource lookup. |
| 11A–11B | Fallback immediately raises a clear error; undo/redo callbacks require a fully initialized app. | Do not change for artificial partial-app fixtures. |
| 12A | Silent exception handling is observability debt. | **[PR]** Add sanitized logging in a focused cleanup. |
| 12B | `rescale_toggle_changed` is a required MainWindow signal. | Do not add a fallback. |
| 13 | Signal wiring is intentionally called only after complete app construction. | Do not weaken wiring with broad `hasattr` guards. |
| 14A–14B | Both are reproducible cine-control defects. | **[PR]** Fix `set_speed` formatting and refresh the bounds tooltip on zero frames. |
| 15A | Single multi-frame DICOM files are incorrectly rejected. | **[PR]** Fix and add a real multi-frame regression test. |
| 16A | Cine playback itself is forward-only and normalizes bounds. | Do not introduce reverse export without a full reverse-playback feature. |
| 16B | Internal rasterization flattens RGBA before PNG output. | Do not change absent an external RGBA-path contract. |
| 17A | Dead branch only. | **[PR]** Remove during cleanup. |
| 17B | Replacing the unparented Python-owned timer does not establish a Qt memory leak. | **[PR]** Reuse timer in `__init__` to avoid per-move allocation. |
| 18A | Harmless defensive branch. | **[PR]** Remove dead code. |
| 18B | Settings callbacks are wired directly when dialogs are opened; the stub is unused. | **[PR]** Remove or document the stub rather than invoking callbacks twice. |
| 19A | Normal hide paths reset opacity before the next reveal. | Do not change unless an external caller reproduces it. |
| 19B | The single-shot timer is inactive once it fires. | Do not change. |

## Identified Issues

### 1. `SliceNavigator` (`src/gui/slice_navigator.py`)
*   **Issue:** No Debounce on Wheel Events. Smooth-scrolling mice (like Apple Magic Mouse) can emit hundreds of tiny `delta` events. The current logic moves one slice per event as long as `delta != 0`.
*   **Proposed Fix:** Add an accumulator that only ticks over after accumulating a threshold (e.g., `delta >= 120`).

### 2. `TagExportUnionWorker` (`src/gui/dialogs/tag_export_union_worker.py`)
*   **Issue:** First-Seen Tag Policy. The dictionary merge uses a "first-seen" policy (`if tag_str not in merged: merged[tag_str] = tag_data`). If this is intended as a strict tag catalog (which tags exist), this is fine. If it should aggregate variations, this architecture would overwrite/ignore them.
*   **Proposed Fix:** Clarify intent. If intended to show distinct values, transition from `Dict[str, Any]` to `Dict[str, Set[Any]]` (or similar) to capture value variation.

### 3. `TagExportUnionHost` (`src/gui/tag_export_union_host.py`)
*   **Issue:** Susceptible to System Clock Jumps. The timeout calculation in `drain_worker` uses `time.time()`. If the system clock resets or jumps (e.g., NTP sync) during execution, the loop could end instantly or hang for hours.
*   **Proposed Fix:** Switch from `time.time()` to `time.monotonic()` for robust internal timeout calculations.

### 4. `SliceLocationLineCoordinator` (`src/gui/slice_location_line_coordinator.py`)
*   **Issue 4A:** Missing Manager Initialization in `refresh_for_subwindow`. Calling `refresh_for_subwindow(target_idx)` without prior registration (via `ensure_manager`) causes the method to silently return `None` without creating the manager or displaying slice lines for that subwindow.
*   **Proposed Fix:** Ensure `ensure_manager(target_idx)` is called before fetching `_managers.get(target_idx)` in the `refresh_for_subwindow` method.
*   **Issue 4B:** Re-entrant Pending Flag Stranding. In `refresh_for_subwindow`, if `self._refreshing` is True, it sets `self._pending_refresh_all = True` and returns. However, the `finally` block in `refresh_for_subwindow` sets `self._refreshing = False` but *never* checks or executes `self._pending_refresh_all` (unlike `refresh_all`'s finally block).
*   **Proposed Fix:** Add the missing check in `refresh_for_subwindow`'s `finally` block to execute a queued refresh if `self._pending_refresh_all` is True.

### 5. `TextAnnotationCoordinator` (`src/gui/text_annotation_coordinator.py`)
*   **Issue 5A:** Uncleaned Move Tracking on Deletion. When an annotation is deleted via `handle_text_annotation_delete_requested` or cleared from other slices, `self._text_move_tracking` is NOT cleaned up, leaving dead references in the dictionary.
*   **Proposed Fix:** Add `self._text_move_tracking.pop(annotation, None)` to the deletion and clear pathways.
*   **Issue 5B:** Batch Timer Collision Across Multiple Items. `self._text_move_batch_timer` is a single instance variable. If multiple text annotation items are dragged concurrently (or rapidly within 200ms), calling `.stop()` overwrites the previous item's timer, dropping its move history recording.
*   **Proposed Fix:** Replace the single timer variable with a dictionary of timers keyed by the annotation item `Dict[TextAnnotationItem, QTimer]` to handle concurrent drags independently.

### 6. `LayoutWindowSlotController` (`src/gui/layout_window_slot_controller.py`)
*   **Issue 6A:** Hardcoded Max View Index. In `on_swap_view_requested`, `other_index >= 4` is hardcoded. If the application adds layouts with > 4 views, swapping will break.
*   **Proposed Fix:** Replace `4` with a dynamic query of the layout engine's available slots or a configurable constant.
*   **Issue 6B:** Config Manager Access Inconsistency. In `setup_popup_callback`, `app.main_window.config_manager.get_accent` is used. If `main_window` lacks `config_manager`, an `AttributeError` is raised. Other places use `app.config_manager`.
*   **Proposed Fix:** Change `app.main_window.config_manager.get_accent` to `app.config_manager.get_accent`.

### 7. `MouseModeHandler` (`src/gui/mouse_mode_handler.py`)
*   **Issue 7A:** Layout-Level Cursor Override Leak. When switching back to `"select"`, if subwindow image viewers do not reset their cursor state, the tool cursor override persists over non-viewer layout gutters and margins because the layout widget's cursor is overridden.
*   **Proposed Fix:** Add a fallback cursor reset for the `layout` and `layout.layout_widget` when mode is "select" or standard.
*   **Issue 7B:** Missing Cursor Reset for Null Viewers. If a subwindow container is visible but its `image_viewer` property is `None`, the cursor reset is skipped.
*   **Proposed Fix:** Reset the container's cursor even if `image_viewer` is `None`.

### 8. `SubwindowImageViewerSync` (`src/gui/subwindow_image_viewer_sync.py`)
*   **Issue 8A:** Missing Defensive Guard on `app.multi_window_layout`. Iterating over `app.multi_window_layout.get_all_subwindows()` raises an `AttributeError` if `multi_window_layout` is `None` (e.g., during early startup or teardown).
*   **Proposed Fix:** Add an explicit guard `if app.multi_window_layout is None: return` in `_iter_image_viewers(app)`.
*   **Issue 8B:** Missing Attribute Fallback on `app.privacy_view_enabled`. `apply_initial_image_viewer_display_state` unconditionally reads `app.privacy_view_enabled`. If the attribute is missing, it raises an `AttributeError`.
*   **Proposed Fix:** Add a safe fallback, e.g., `getattr(app, 'privacy_view_enabled', False)`.

### 9. `MainWindowStatusController` (`src/gui/main_window_status_controller.py`)
*   **Issue 9A:** Asymmetric Incomplete W/L Parameter Handling. In `format_zoom_preset_status`, if either `window_center` or `window_width` is `None` (but not both), it silently ignores the provided value without warning or partial formatting.
*   **Proposed Fix:** Either explicitly validate that both are provided or both are None, or provide partial formatting.

### 10. `MainWindowTheme` (`src/gui/main_window_theme.py`)
*   **Issue 10A:** Unchecked Hex Color String Parsing. `_blend_hex_colors` and `_boost_hex_saturation` slice fixed indices `(1, 3, 5)` assuming a `#rrggbb` format. Passing invalid/short strings or non-hex characters raises an unhandled `ValueError`.
*   **Proposed Fix:** Add basic length/regex validation before slicing and integer conversion.
*   **Issue 10B:** PyInstaller `_MEIPASS` Fallthrough. In `_themes_dir`, if `sys.frozen` is true but `_MEIPASS` is missing/None, it falls back to the development directory path, which may fail or locate non-existent files in production.
*   **Proposed Fix:** If `sys.frozen` is true, handle missing `_MEIPASS` robustly (e.g., using `os.path.dirname(sys.executable)` as a fallback).

### 11. `AppHandlerBootstrap` (`src/gui/app_handler_bootstrap.py`)
*   **Issue 11A:** Fallback Subwindow Null Image Viewer Bypass. In fallback initialization, if `subwindows[0]` exists but its `image_viewer` property is `None`, `app.image_viewer` remains `None` and crashes with a `RuntimeError` downstream.
*   **Proposed Fix:** Add an explicit fallback assignment or validation that `app.image_viewer` cannot be `None`.
*   **Issue 11B:** Hardcoded Un-guarded Lambda Calls. Undo/redo callbacks (`lambda: app._on_undo_requested()`) do not verify if `app._on_undo_requested` exists, unlike other methods which guard against missing attributes.
*   **Proposed Fix:** Guard lambda execution or verify method presence before assignment.

### 12. `MainWindowLayoutHelper` (`src/gui/main_window_layout_helper.py`)
*   **Issue 12A:** Silent Swallowing of Exceptions. In window-slot map callback setup, a bare `try...except Exception: pass` block swallows all errors silently. If callback binding fails, the map remains un-wired with no warning or logs.
*   **Proposed Fix:** Log the exception instead of swallowing it silently.
*   **Issue 12B:** Unconditional Signal Binding Assumption. `rescale_cb.toggled.connect(main_window.rescale_toggle_changed.emit)` assumes `rescale_toggle_changed` exists on `main_window`, raising an `AttributeError` if it doesn't.
*   **Proposed Fix:** Ensure the attribute exists before attempting to connect to it.

### 13. `AppSignalWiring` (`src/gui/app_signal_wiring.py`)
*   **Issue 13A:** Coupled Rigid Signal Expectations. The module connects over 60 specific signal names across various widgets without defensive `hasattr` guards. If any sub-widget is missing a signal definition (e.g., during partial layout builds), `wire_all_signals` raises an unhandled `AttributeError`.
*   **Proposed Fix:** Add `hasattr` checks before attempting to `.connect()` signals, or wrap the connections in a `try...except AttributeError` block.

### 14. `CineControlsWidget` (`src/gui/cine_controls_widget.py`)
*   **Issue 14A:** Float Formatting Mismatch in `set_speed`. When `set_speed` formats floats like `1.0` or `2.0`, it yields `"1.0x"` and `"2.0x"`. This fails the subsequent text check `if speed_text in ["0.25x", "0.5x", "1x", "2x", "4x"]:`, leaving the combo box text unchanged.
*   **Proposed Fix:** Format floats dynamically without `.0` (e.g., `f"{speed_multiplier:g}x"`) or strictly match the mapped values.
*   **Issue 14B:** Missing Tooltip Update in `update_frame_position`. When `total_frames <= 0`, it returns early without calling `self._update_loop_bounds_display()`. If cine bounds were set previously, the tooltip retains stale bounds text instead of clearing.
*   **Proposed Fix:** Call `self._update_loop_bounds_display()` before returning when `total_frames <= 0`.

### 15. `CinePlayer` (`src/gui/cine_player.py`)
*   **Issue 15A:** Single Multi-Frame File Rejection. In `is_cine_capable`, the logic checks `if not datasets or len(datasets) < 2: return False` early. This causes valid single multi-frame DICOM series (`len(datasets) == 1` with `NumberOfFrames > 1`) to be incorrectly evaluated as incapable of cine playback, as it exits before reaching the `is_multiframe` check.
*   **Proposed Fix:** Allow `len(datasets) == 1` to proceed to the `is_multiframe(first_dataset)` check before rejecting.

### 16. `CineVideoExport` (`src/gui/cine_video_export.py`)
*   **Issue 16A:** Implicit Reversal of Inverted Loop Bounds. In `build_cine_export_frame_indices`, if `loop_start_frame > loop_end_frame`, they are silently swapped (`ls, le = le, ls`). This prevents exporting a reverse-playback cine loop, forcing it to export forwards instead.
*   **Proposed Fix:** Maintain the order if the user intends a reverse export, generating a descending range.
*   **Issue 16B:** Missing RGBA Channel Flattening in Stream Encoder. In `encode_cine_video_from_png_paths`, 4-channel RGBA arrays are passed directly to `imageio`'s FFmpeg writer without alpha-flattening, causing errors in formats expecting YUV 4:2:0 3-channel input.
*   **Proposed Fix:** Extract RGB channels (`arr[..., :3]`) and blend with a background before appending to the video.

### 17. `CrosshairCoordinator` (`src/gui/crosshair_coordinator.py`)
*   **Issue 17A:** Unreachable Branch in `handle_clear_crosshairs`. Line 217 guarantees `crosshairs_to_delete` is non-empty. The loop builds `commands`, making `if commands:` on line 235 unconditionally `True`. The `False` branch (`235->exit`) is dead code.
*   **Proposed Fix:** Remove the unnecessary `if commands:` check, or handle the extremely unlikely edge case gracefully.
*   **Issue 17B:** QTimer Memory Leak in Drag Move Batching. In `_on_crosshair_moved`, a new `QTimer` is instantiated (`self._move_batch_timer = QTimer()`) on every move without deleting or re-using the existing timer object. This leads to un-garbage-collected `QTimer` allocations during continuous crosshair dragging.
*   **Proposed Fix:** Instantiate the timer once in `__init__` and reuse it, calling `.start()` and `.stop()` as needed.

### 18. `DialogCoordinator` (`src/gui/dialog_coordinator.py`)
*   **Issue 18A:** Unreachable Dead Code in `open_histogram`. Line 381 checks `if dialog is None: return` immediately after instantiating `HistogramDialog` into `self.histogram_dialogs[idx]`. This is structurally unreachable because the constructor always returns an object.
*   **Proposed Fix:** Remove the dead code check or place it correctly if it was meant to guard against a failed allocation.
*   **Issue 18B:** Disconnected `handle_settings_applied` Callback. Line 324 defines `handle_settings_applied(self)` as an empty stub (`pass`). Although `settings_applied_callback` is injected via `__init__`, calling `handle_settings_applied` does not invoke it.
*   **Proposed Fix:** Have `handle_settings_applied` explicitly call `self.settings_applied_callback()` if it exists.

### 19. `EdgeRevealSliderOverlay` (`src/gui/edge_reveal_slider_overlay.py`)
*   **Issue 19A:** Hidden Widget Animation Skip Defect in `reveal`. If `current_opacity >= 0.99`, `reveal` returns early. If `setVisible(False)` was previously called while `current_opacity` remained 1.0, calling `reveal` sets `setVisible(True)` but skips triggering any fade-in animation or opacity reset.
*   **Proposed Fix:** Explicitly reset opacity and ensure animation triggers if the widget was hidden, regardless of `current_opacity`.
*   **Issue 19B:** Orphaned `_hide_timer` State on Animation Completion. When `_start_fade_out` finishes, it sets `_fading_out = False` and `setVisible(False)`, but `_hide_timer` remains active until its timeout fires, triggering a redundant `_start_fade_out` call on an already hidden widget.
*   **Proposed Fix:** Stop `_hide_timer` when fade-out starts or completes.

## Coverage-Effort Findings (2026-08-09)

### 21. `set_study_index_browser_column_order` (`src/utils/config/study_index_config.py`)
*   **Issue 21A (genuine bug): [PR]** Non-deduplicating column-order normalization.
    In `set_study_index_browser_column_order`, `cleaned` is built by keeping only
    known ids (`[str(x) for x in column_ids if x in known]`), then if
    `len(cleaned) != len(known)` the loop appends every missing default id. If
    `column_ids` contains duplicate known ids (e.g. 12 copies of `"patient_name"`),
    `cleaned` already has `len == len(known)` so the "append missing" branch is
    skipped and the duplicates are stored verbatim, while all other columns are
    dropped from the saved order. `get_study_index_browser_column_order` has the
    same normalization gap for already-persisted duplicate ids. The intent is a
    deduplicated permutation of the known ids.
*   **Tests:** `tests/test_study_index_config.py::TestBrowserColumnOrder::test_set_duplicate_ids_are_deduplicated`
    and `test_get_duplicate_ids_are_deduplicated` specify the intended behavior
    as strict expected failures until the separate fix branch implements it.
*   **Proposed Fix:** Deduplicate both setter input and persisted values on read
    (e.g. preserving first occurrence with `dict.fromkeys(...)`) before appending
    missing default ids.



Coverage investigations are isolated from in-flight fixes. Tests for validated,
deferred defects specify the intended contract as strict expected failures;
tests for dismissed reports describe the current supported contract without
labelling it a defect.

### 20. `dispatch_app_key_event` delegation contract (`src/gui/main_app_key_event_filter.py`)
*   **Investigation (no defect):** The module docstring promises `None` only when
    the event is *not* a `QKeyEvent`. For any real `QKeyEvent`, the helper
    intentionally delegates to `keyboard_event_handler` and returns its result
    (the final line returns `app.keyboard_event_handler.handle_key_event(event)`).
    This is by-design: the real `KeyboardEventHandler` returns `False` for a
    `KeyRelease`, so Qt continues event propagation. A review flagged that
    non-handled key events are "consumed" (the helper returns `True`), but that
    only happens if the handler returns `True`; the default handler returns `False`.
    No fix required.
*   **Test:** `tests/test_main_app_key_event_filter.py::TestEscapeFullscreen::test_escape_keyrelease_delegated_to_handler`
    pins the delegation contract (handler result is mocked to verify delegation,
    not the handler's own logic). The prior "latent bug" framing was incorrect and
    has been removed.

## Already Fixed Issues (Pre-Review)

### `SliceNavigator` (`src/gui/slice_navigator.py`)
*   **Zero-Delta Scroll Wheel Event Propagation:** Previously, smooth scrolling that emitted a 0 delta would bypass early checks and propagate incorrectly. Fixed by adding a `delta == 0` early return in `handle_wheel_event`.
*   **Redundant Signal Emission:** Calling `set_current_slice` with the same slice index would emit `slice_changed` multiple times. Fixed by adding an explicit `if self.current_slice_index != index` guard.
*   **Negative Total Slices Edge Case:** Passing negative values to `set_total_slices` could result in invalid application state. Fixed by applying `max(0, total)`.
*   **Stale Reference Bounds Check:** Checking bounds in `set_total_slices` used the un-clamped raw argument instead of the clamped `self.total_slices` property. Fixed.
*   **Missing Keyboard Controls:** Slices could be navigated using arrow keys, but `PageUp` and `PageDown` were omitted. Fixed by expanding the key bindings in `handle_key_event`.
