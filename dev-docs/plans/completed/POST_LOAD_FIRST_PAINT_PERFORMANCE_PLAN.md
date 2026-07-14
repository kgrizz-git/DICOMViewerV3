# Plan: Slow Post-Load First Paint Investigation and Fixes

**Status:** **Complete and archived.** The remaining human visual smoke is tracked in `dev-docs/TO_DO.md`.

Last updated: 2026-07-12

## Goal and success criteria

After the user confirms opening large DICOM objects, the first image and series navigator should appear promptly, especially for single-file multi-frame XA/CT/MG objects and large multi-file folders. Initial investigation showed the largest user-visible delay for the reported large-file symptom occurs before UI handoff, while `DICOMOrganizer.merge_batch()` creates per-frame wrappers for multi-frame datasets.

Success criteria:

- Instrumentation captures timing from large-file confirmation through loader/decode, organizer merge, UI handoff, first image display, and first navigator update.
- The dominant pre-handoff blocker for single-file multi-frame XA/CT is reduced with before/after measurements.
- Multi-frame display semantics remain correct: frame ordering, per-frame geometry, rescale/window-level metadata, metadata display, and pixel access still work.
- Smaller post-handoff UI wins, such as thumbnail/navigator deferral, are kept only if measurements show they still matter after the primary fix.
- The UI remains responsive during first-paint work and cancellation/close behavior is safe.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` Bugs / Correctness, "Slow post-load first paint".
- Existing broader performance plan: `dev-docs/plans/supporting/PERFORMANCE_DEEP_DIVE_PLAN.md`.
- Primary code paths:
  - `src/core/file_series_loading_coordinator.py`, especially `handle_load_first_slice()`.
  - `src/core/file_operations_handler.py` and loader completion handoff.
  - `src/core/slice_display_manager.py`, especially first `display_slice()` after load.
  - `src/gui/series_navigator.py`, `src/gui/series_navigator_model.py`, and thumbnail generation/update paths.
  - `src/core/study_cache.py` for memory/caching interactions during additive loads.
- Current sequence observed from code: large-file confirmation returns, the loader decodes the dataset, `DICOMOrganizer.merge_batch()` organizes it, then the UI handoff displays the first slice and updates metadata/navigator state. S1c found that the worst XA/CT samples spend almost all post-Continue time inside `create_frame_dataset()` / `FrameDatasetWrapper.__init__()`, where the wrapper deep-copies every non-pixel DICOM element once per frame.

## Task graph and gates

### Ordering

- S1 -> T1 -> S1b -> T1b -> S1c -> Gate 1.
- S2/T3/S3/T4 are the primary fix path for the reported large-file symptom.
- S4 decides whether remaining post-handoff first-paint/navigator work is worth keeping in this plan or should move to backlog.
- T2 follows the final instrumentation decision.

### Verification gates

- Gate 1: Timing log identifies where the delay lives. Current result: single-file multi-frame XA/CT is dominated by wrapper creation in organizer merge, not first display or navigator work.
- Gate 2: The representative XA and enhanced CT samples show materially improved post-Continue time without changing displayed frame behavior.
- Gate 3: Existing loading, navigator, and display tests still pass.

### File / area ownership

- `src/core/file_series_loading_coordinator.py` -> coder.
- `src/core/slice_display_manager.py` -> coder for first image display timing.
- `src/core/dicom_organizer.py` and `src/core/multiframe_handler.py` -> coder for primary multi-frame wrapper optimization.
- `src/gui/series_navigator*.py` -> coder for navigator and thumbnail deferral/chunking.
- `tests/` loading/navigator/display tests -> tester/coder.

### Cheap-model / low-risk preliminary research

These tasks are read-only or artifact-only and can be handed to a smaller/cheaper `researcher` model before code changes. They should not edit product code, change tests, or decide the final implementation. Each research task should write its findings to a dated note under `dev-docs/plans/supporting/research/` named `YYYY-MM-DD-post-load-first-paint-<task-id>.md` and add only a one-line link under this plan's Completion notes. If the researcher cannot create files, paste the same note content into the handoff and leave this plan unchanged.

- [x] (R1) Map the post-load call sequence from loader completion through first `display_slice()`, app/subwindow state updates, metadata/cine/history refresh, `series_navigator.update_series_list()`, thumbnail creation, and `_refresh_series_navigator_state()`; report exact function names and file/line anchors (owner: researcher, parallel-safe: yes, stream: R, after: none).
- [x] (R2) Inventory existing diagnostics relevant to this work, especially `DEBUG_LOADING`, `DEBUG_NAV`, `PERF_LOG`, and any existing timing helpers; recommend whether S1 can reuse them or needs a new `DEBUG_LOADING_FIRST_PAINT` flag, but leave the decision to the coder in T2 (owner: researcher, parallel-safe: yes, stream: R, after: none).
- [x] (R3) Inventory existing tests that touch loading handoff, first display, navigator rebuild, thumbnail cache/regeneration, stale/canceled loads, and current-series highlighting; identify likely files to extend for T10/T11 (owner: researcher, parallel-safe: yes, stream: R, after: none).
- [x] (R4) Draft a measurement protocol for T1/T6/T12: datasets needed, app command to run, timing fields to capture, expected log format, and how to distinguish first image visible vs navigator usable. Keep it implementation-neutral (owner: researcher, parallel-safe: yes, stream: R, after: none).
- [x] (R5) Timing-log analysis completed through S1c/T4 measurement notes; no separate researcher pass was needed (owner: researcher, parallel-safe: yes, stream: R, after: S1).

Keep with a stronger coder/reviewer: S1/T2 instrumentation edits, T3-T5 event-loop/deferred-work changes, T7-T9 navigator behavior changes, and T10/T11 regression tests. Those tasks touch UI ordering, stale-load safety, or selection correctness and should not be treated as cheap-model implementation work.

## Phases

### Phase 1 - Instrument and classify the delay

- [x] (S1) Add temporary or debug-flag-gated timing around key milestones: loader completion, `load_first_slice()`, first `display_slice()`, viewer pixmap/image item update, metadata panel refresh, navigator `update_series_list()`, thumbnail generation, `_refresh_series_navigator_state()`, and first event-loop return (owner: coder, parallel-safe: no, stream: none, after: none).
- [x] (T1) Run the timing on at least one large single file and one large multi-file folder; capture before measurements in the plan completion notes or a linked investigation note (owner: tester, parallel-safe: no, stream: none, after: S1).
- [x] (S1b) Add `DICOM_PERF_LOG=1`-gated pre-handoff timing for large-file-confirmed opens: large-file check complete, user clicked Continue, load pipeline start, loader complete, merge complete, and `handle_additive_load()` handoff. This is needed because XA/CT/MG large single files can feel slow after the Continue popup before current S1 markers start (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T1b) Re-run the large single-file XA and CT samples with S1b instrumentation to separate popup/user wait, loader/decode, merge/indexing, and post-handoff first-paint timing (owner: tester, parallel-safe: no, stream: none, after: S1b).
- [x] (S1c) Profile `DICOMOrganizer.merge_batch` internals for single-file multi-frame objects, especially enhanced CT and XA, to identify why merge/organize dominates post-Continue delay before UI handoff (owner: coder, parallel-safe: no, stream: none, after: T1b).
- [x] (T2) Retain the existing `DICOM_PERF_LOG=1`-gated instrumentation for future measurements; do not add a second debug flag (owner: coder, parallel-safe: no, stream: none, after: T1).

### Phase 2 - Primary fix: multi-frame wrapper creation

- [x] (S2) Design the smallest safe `FrameDatasetWrapper` optimization: avoid deep-copying the full non-pixel dataset for every frame, while preserving direct access to required per-frame/display tags and delegating other metadata to `_original_dataset` (owner: coder, parallel-safe: no, stream: A, after: S1c).
- [x] (T3) Add focused regression tests for multi-frame wrapper behavior before changing it: frame count/order, per-frame `ImagePositionPatient`, shared/per-frame `ImageOrientationPatient`, pixel spacing/slice thickness, rescale slope/intercept/type, window center/width, delegated metadata access, and per-frame `pixel_array` access where practical (owner: coder/tester, parallel-safe: no, stream: A, after: S2).
- [x] (S3) Implement the optimized wrapper construction and update organizer usage only as needed; keep DICOM interpretation behavior unchanged (owner: coder, parallel-safe: no, stream: A, after: T3).
- [x] (T4) Re-run XA and enhanced CT measurements with `DICOM_PERF_LOG=1`; compare post-Continue loader/decode, merge, UI handoff, first display, and thumbnail times against T1b/S1c baselines (owner: tester, parallel-safe: no, stream: A, after: S3).
- [x] (T5) Focused automated checks and real GUI benchmark loads pass; the remaining human visual smoke is tracked in `dev-docs/TO_DO.md` (owner: tester, parallel-safe: no, stream: A, after: S3).

### Phase 3 - Secondary post-handoff wins, only if still justified

- [x] (S4) After T4, decide whether post-handoff UI work remains material. If first image is prompt but thumbnails/navigator still have small delays, either keep one measured task here or move the small/complicated wins to `dev-docs/TO_DO.md` as deferred P2/P3 follow-ups (owner: coder/reviewer, parallel-safe: no, stream: B, after: T4).
- [x] (T6) Not applicable: S4 found navigator work was not materially visible after the wrapper fix (owner: tester, parallel-safe: yes, stream: B, after: S4).
- [x] (T7) Deferred by S4; do not add navigator scheduling complexity without a new measurement or user report (owner: coder, parallel-safe: no, stream: B, after: T6).
- [x] (T8) Deferred with T7 (owner: coder, parallel-safe: no, stream: B, after: T6).
- [x] (T9) Deferred with T7 (owner: coder, parallel-safe: no, stream: B, after: T7).

### Phase 4 - Regression coverage and benchmarks

- [x] (T10) Deferred with T7-T9; no staged-work behavior was introduced (owner: tester, parallel-safe: no, stream: none, after: T9).
- [x] (T11) Deferred with T7-T9; thumbnail generation behavior is unchanged (owner: tester, parallel-safe: no, stream: none, after: T9).
- [x] (T12) Record before/after timings for representative datasets, with XA/enhanced CT post-Continue time as the required benchmark and navigator-visible timing as secondary (owner: tester, parallel-safe: no, stream: none, after: T4).

## Risks and mitigations

- Risk: Deferring navigator work can leave stale thumbnails or wrong current-series highlighting. Mitigation: use a load-generation token and re-check current study/series before applying deferred updates.
- Risk: Forcing event processing inside a load handler can introduce reentrancy bugs. Mitigation: prefer staged `QTimer.singleShot(0, ...)` callbacks over direct nested event processing unless there is a measured reason.
- Risk: Moving DICOM pixel extraction off-thread can cross thread-safety boundaries. Mitigation: this plan first targets post-load UI work; deeper loader threading belongs in the broader performance plan.
- Risk: Debug timing can become noisy release output. Mitigation: gate with `src/utils/debug_flags.py` and keep defaults false.
- Risk: Making `FrameDatasetWrapper` lazy can break callers that expect copied tags to be present directly on the wrapper. Mitigation: add focused tests for direct tag access, delegated tag access, display-critical per-frame overrides, sorting, rescale/window-level, and pixel access before optimizing.

## Modularity and file-size guardrails

Avoid expanding `FileSeriesLoadingCoordinator` with a large scheduler unless post-handoff work remains material after the wrapper fix. The primary fix should stay in `multiframe_handler`/organizer boundaries. If multiple staged UI callbacks are later needed, introduce a small helper such as a post-load UI update queue with a narrow API and generation-token checks.

## Testing strategy

- Run focused loading/navigator tests after implementation.
- Run `.\.venv\Scripts\python.exe -m pytest tests/test_loading_and_shell_helpers.py tests/test_series_navigator_tooltips.py -q` where applicable.
- Run relevant GUI smoke manually with a large single file and a large folder.
- If debug instrumentation remains, confirm all `DEBUG_*` flags default to `False`.

## Questions for user

None blocking. If multiple user datasets reproduce the delay differently, prioritize the scenario with the worst first-visible-image latency.

## Completion notes

- [R1] Complete: See [2026-07-12-post-load-first-paint-R1.md](../supporting/research/2026-07-12-post-load-first-paint-R1.md) for detailed call sequence map with exact function names and file/line anchors.
- [R2] Complete: See [2026-07-12-post-load-first-paint-R2.md](../supporting/research/2026-07-12-post-load-first-paint-R2.md) for diagnostics inventory (`DEBUG_LOADING`/`DEBUG_NAV`/`DEBUG_SERIES`/`PERF_LOG`/`perf_timer`) and reuse-vs-new-flag assessment (T2 decision left to coder).
- [R3] Complete: See [2026-07-12-post-load-first-paint-R3.md](../supporting/research/2026-07-12-post-load-first-paint-R3.md) for existing test inventory by concern, coverage gaps, and files to extend for T10/T11.
- [R4] Complete: See [2026-07-12-post-load-first-paint-R4.md](../supporting/research/2026-07-12-post-load-first-paint-R4.md) for the implementation-neutral T1/T6/T12 measurement protocol (datasets, run command, timing fields, log/CSV format, first-image-visible vs navigator-usable).
- [S1] Complete: Added `DICOM_PERF_LOG=1`-gated `[PERF]` timing/mark instrumentation via `utils.perf_timer` around pre-first-slice reset, `load_first_slice()`, first `display_slice()`, slice render sub-stages, metadata/cine/history refresh, `series_navigator.update_series_list()`, `_refresh_series_navigator_state()`, subwindow assignment refresh, deferred thumbnail generation/application, and first event-loop return. Follow-up app run showed additive folder opens use `handle_additive_load()`, so S1 now also instruments additive-load start, first display, metadata/cine refresh, navigator refresh, and first event-loop return. `main.py` configures logging when `DICOM_PERF_LOG=1` so startup and first-paint `[PERF]` lines are emitted during GUI runs.
- [T1] Complete: See [2026-07-12-post-load-first-paint-T1-measurements.md](../supporting/research/2026-07-12-post-load-first-paint-T1-measurements.md) for baseline runs across a 478-file folder, an 838-file PET/CT folder, and large single-file multiframe XA/CT/MG datasets. Post-handoff first display was under 100 ms in these samples; deferred thumbnail generation was the largest post-load UI-thread work observed (up to 830.1 ms for one folder thumbnail job and 230.0 ms for a 241 MB XA single-file thumbnail). User-observed slowness after clicking **Continue** in the large-file popup for XA/CT/MG occurs before current post-handoff markers; S1b/T1b added to time that pre-handoff path.
- [S1b/T1b] Complete: See [2026-07-12-post-load-first-paint-T1b-prehandoff-measurements.md](../supporting/research/2026-07-12-post-load-first-paint-T1b-prehandoff-measurements.md). With an auto-confirmed large-file prompt, XA spent 329.2 ms in loader/decode and 4933.8 ms in merge/organize before UI handoff; enhanced CT spent 939.8 ms in loader/decode and 26272.7 ms in merge/organize. Added S1c to profile `DICOMOrganizer.merge_batch` internals before assuming the remaining user-visible delay is a first-paint UI scheduling problem.
- [S1c] Complete: See [2026-07-12-post-load-first-paint-S1c-merge-batch-profile.md](../supporting/research/2026-07-12-post-load-first-paint-S1c-merge-batch-profile.md). The remaining post-Continue delay is dominated by `create_frame_dataset()` / `FrameDatasetWrapper.__init__()` during multi-frame wrapper creation: 4516.6 ms for the 450-frame XA sample and 26345.7 ms for the 364-frame enhanced CT sample. Dedup, sorting, merge application, UI handoff, and first `display_slice()` are not the bottleneck for these samples.
- [S2/T3/S3/T4/T12] Complete: `FrameDatasetWrapper` is now a metadata view that stores only local frame-specific overrides and delegates other metadata to its original dataset. Focused tests cover delegated attributes and mapping access, per-frame geometry, shared display metadata, frame count/order via organizer coverage, and frame pixel access. See [2026-07-12-post-load-first-paint-T4-wrapper-optimization-measurements.md](../supporting/research/2026-07-12-post-load-first-paint-T4-wrapper-optimization-measurements.md): wrapper creation fell from 4516.6 ms to 14.5 ms for XA and from 26345.7 ms to 44.0 ms for enhanced CT; full merge fell from 4770.8 ms to 562.5 ms and from 26377.2 ms to 1159.4 ms, respectively.
- [S4] Complete: First display is now prompt after UI handoff (49.5 ms XA, 178.1 ms enhanced CT), while XA thumbnail work runs after event-loop return and CT thumbnail work is 13.5 ms. Do not implement navigator deferral/chunking as part of this P1 fix. The residual enhanced-CT multiframe-info update is deferred to the P3 backlog only if future measurements show it matters.
- [T2] Complete: Retained the existing `DICOM_PERF_LOG=1` timing path; it is opt-in and avoids adding a second debug flag.
- [T5] Complete for automated verification: focused tests, harness checks, basedpyright, and real XA/enhanced-CT GUI benchmark loads pass. The human visual smoke was moved to `dev-docs/TO_DO.md`.
