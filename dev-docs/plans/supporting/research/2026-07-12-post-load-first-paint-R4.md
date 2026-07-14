# Post-Load First Paint Measurement Protocol (R4)

**Date:** 2026-07-12
**Task:** (R4) Draft a measurement protocol for T1/T6/T12: datasets needed, app command to run, timing fields to capture, expected log format, and how to distinguish first image visible vs navigator usable. Keep it implementation-neutral.

> Research-only, implementation-neutral. This does not choose the instrumentation mechanism (that is S1/T2, informed by R2). It defines *what* to measure and *how to run/record* so T1, T6, and T12 produce comparable before/after numbers. Where it says "log line," the concrete flag/logger is the coder's choice in S1/T2.

## Scope of each task using this protocol

- **T1** — baseline capture on representative datasets after S1 instrumentation exists (identifies where the delay lives).
- **T6** — focused capture to attribute delay between `update_series_list()` vs thumbnail creation.
- **T12** — before/after capture proving the fix improved first-image and navigator-visible timings.

## Datasets needed

Pick datasets that stress the two blockers found in R1 (synchronous `display_slice` render, synchronous `update_series_list` rebuild). Record exact identity of each so runs are comparable.

| ID | Description | Stresses | Required for |
|----|-------------|----------|--------------|
| D1 | **Large single file** (large multi-frame or large-pixel-matrix single DICOM) | First `display_slice()` render/pixel extraction | T1, T12 |
| D2 | **Large multi-file folder** (many instances, one or few series) | Loader handoff + first display + navigator/thumbnail volume | T1, T6, T12 |
| D3 | **Multi-study / many-series folder** (several studies, many series) | `update_series_list()` widget/layout rebuild + thumbnail count | T6, T12 |
| D4 (optional) | **Small baseline** (single small series) | Control — near-zero post-load cost | Sanity/regression |
| D5 (optional) | **Additive load** (open D4, then open an unrelated study) | Thumbnail cache reuse (T8), additive `handle_additive_load` path | T6, T12 |

For each dataset record: file/folder path (or a non-PHI descriptor), file count, series count, study count, largest single-instance size, and total bytes. Do **not** commit PHI; use descriptors (e.g. "CT chest, 480 instances, 1 series, 512×512").

## App command to run

- Activate the venv, then launch from project root: `python src/main.py` (see AGENTS.md; on Windows use the venv `python.exe`).
- Load via the normal **Open File / Open Folder** UI action for the chosen dataset. There is currently **no startup CLI flag to auto-load a path**, so loading is an operator action; note the operator step in the run record.
- Enable whatever S1 instrumentation surface is chosen (per R2 this is likely env-gated `DICOM_PERF_LOG=1` and/or a debug flag — the coder decides in T2). Capture stdout/stderr to a file for parsing.
- Precedent for automated capture and CSV aggregation: `scripts/benchmark_startup.py` (launches with `DICOM_PERF_LOG=1`, parses `[PERF]` lines, writes `dev-docs/perf-baselines/`). T1/T6/T12 tooling can mirror this pattern; a `dev-docs/perf-baselines/post-load-first-paint.csv` sibling would keep history.
- Repeat each dataset **N ≥ 5** runs; report **median, min, max** (drop the first "cold" run or record it separately, since OS/file cache warms it).

## Timing fields to capture

Anchor pre-handoff timestamps to pipeline start and post-handoff timestamps to UI handoff. Do not subtract a post-handoff origin from an earlier pipeline marker; capture each segment explicitly.

Define **`t_pipeline_start`** as the start of loading after the user confirms the large-file prompt. Define **`t_handoff`** as the loader callback/UI handoff, and use it as the zero point for post-handoff UI milestones.
All fields after `t_handoff` in the record example are elapsed from handoff; `t_handoff` itself is elapsed from pipeline start.

| Field | Milestone (R1 anchor) | Meaning |
|-------|-----------------------|---------|
| `t_handoff` | loader callback → `handle_additive_load` (`loading_pipeline.py:340` → coordinator `:400`) | Loader-to-UI handoff; post-handoff zero point |
| `t_first_slice_info` | `load_first_slice()` returns (`:236`) | First-slice info resolved |
| `t_display_start` | before `display_slice()` (`:310`) | Render begins |
| `t_display_end` | after `display_slice()` returns (`:318`) | **First image rendered into the scene** |
| `t_display_render` | inside `display_slice` `_render_base_image_pipeline` (`slice_display_manager.py:944-959`) | Pixel/W-L/convert cost |
| `t_metadata_cine` | after metadata/cine update (`:373-374`) | Panel/cine refresh cost |
| `t_nav_start` | before `update_series_list()` (`:382`) | Navigator rebuild begins |
| `t_nav_end` | after `update_series_list()` returns (`:386`) | Navigator widgets/layout built |
| `t_nav_refresh` | after `_refresh_series_navigator_state()` (`:387-388`) | Navigator state refresh |
| `t_handler_return` | exit `handle_load_first_slice()` (`:398`) | Synchronous work done |
| `t_event_loop_return` | first event-loop turn after handler returns | **When the UI can actually paint** |
| `t_first_paint` | first viewer `paintEvent` / pixmap visible after t0 | **First image visible to user** |
| `t_thumbs_done` | last `_process_next_thumbnail` drains queue (`series_navigator.py:636-655`) | All thumbnails generated |

Derived comparisons for reporting:
- `display_ms = t_display_end − t_display_start`
- `nav_build_ms = t_nav_end − t_nav_start`
- `pre_handoff_ms = t_handoff − t_pipeline_start`
- `sync_total_ms = t_handler_return − t_handoff` (post-handoff synchronous blocking span)
- `first_image_visible_ms = t_first_paint − t_handoff`
- `navigator_usable_ms = t_nav_end − t_handoff` (or `t_thumbs_done − t_handoff` if "usable" requires thumbnails; see below)

## Distinguishing "first image visible" vs "navigator usable"

These are two different success signals in the plan (goal + Gate 2) and must be reported separately:

- **First image visible** = the first viewer pixmap is actually painted on screen. Best proxy in-code: the first `paintEvent`/viewport update *after* `t_event_loop_return`, not merely `t_display_end` (the render can finish while the handler still blocks the event loop). If instrumenting the paint is impractical, report `t_event_loop_return` as an upper-bound proxy and label it as such.
- **Navigator usable (shell)** = `update_series_list()` has built the study/series widgets and current-series highlight is applied (`set_current_position`, `series_navigator.py:625`), even if thumbnails are still filling. This is `t_nav_end`.
- **Navigator fully populated** = all thumbnails generated (`t_thumbs_done`). Report this separately because R1 confirms thumbnails are *already* deferred/chunked (`singleShot(0, _process_next_thumbnail)`), so they should not gate first paint; conflating it with "usable" would misattribute delay.

Report all three per dataset so T1 can localize the blocker and T6 can decide whether navigator rebuild or thumbnail generation dominates.

## Expected log/record format

Implementation-neutral shape (concrete flag/logger chosen in S1/T2). One line per milestone or one summary line per load; must include a stable tag for parsing and the dataset ID.

Per-milestone example:
```
[FIRST-PAINT] dataset=D2 pipeline_start=0.0ms handoff=503.1ms first_slice_info=8.4ms display_start=9.0ms display_end=142.7ms nav_start=143.0ms nav_end=511.9ms handler_return=512.3ms event_loop_return=515.0ms first_paint=531.2ms thumbs_done=1840.0ms
```
Summary/derived example:
```
[FIRST-PAINT-SUMMARY] dataset=D2 pre_handoff_ms=503 first_image_visible_ms=531 navigator_usable_ms=512 nav_build_ms=369 display_ms=134 sync_total_ms=512 thumbs_done_ms=1840
```

Aggregate across N runs into a CSV row per (dataset, git_sha), mirroring `benchmark_startup.py`:
```
timestamp,git_sha,dataset,runs,first_image_visible_ms_median,navigator_usable_ms_median,display_ms_median,nav_build_ms_median,sync_total_ms_median,thumbs_done_ms_median
```

## Run record checklist (per T1/T6/T12 session)

1. Machine/OS, git SHA, venv active, instrumentation surface enabled.
2. Dataset descriptors (D1–D5 as used) with counts/sizes, no PHI.
3. N runs; median/min/max for each derived field; note the cold-run separately.
4. First-image-visible, navigator-usable, and thumbs-done reported **separately**.
5. For T12: paired before/after under identical dataset + machine + SHA-delta; state the fix commit.
6. Link results back into this plan's Completion notes (a one-line link per capture), and consider committing aggregated CSV to `dev-docs/perf-baselines/`.

## Key anchors

| Item | File | Line(s) |
|------|------|---------|
| Post-load synchronous handler (t0 → return) | `src/gui/file_series_loading_coordinator.py` | 188-398 |
| Loader handoff callback | `src/core/loading_pipeline.py` | 340 |
| First `display_slice()` call | `src/gui/file_series_loading_coordinator.py` | 310-318 |
| Base image render pipeline | `src/gui/slice_display_manager.py` | 944-959 |
| Navigator rebuild | `src/gui/series_navigator.py` | 332-630 |
| Current-position highlight | `src/gui/series_navigator.py` | 625 |
| Deferred thumbnail drain | `src/gui/series_navigator.py` | 636-655 |
| Benchmark/CSV capture precedent | `scripts/benchmark_startup.py` | 1-92 |
| Timing helper (optional S1 reuse) | `src/utils/perf_timer.py` | 12-21 |
