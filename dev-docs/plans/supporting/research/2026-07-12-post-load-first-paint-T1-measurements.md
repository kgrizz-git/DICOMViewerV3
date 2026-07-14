# Post-Load First Paint Measurements (T1)

**Date:** 2026-07-12
**Task:** (T1) Run timing on at least one large single file and one large multi-file folder; capture before measurements.

## Harness

Perf logging was enabled with `DICOM_PERF_LOG=1`. The app was launched programmatically and opened bounded sample paths with `app._open_files_from_paths([target])`; each run auto-quit after 45-60 seconds.

The large single-file XA, CT, and MG samples triggered the large-file confirmation popup in normal interactive use. The timings below start after the app reaches `handle_additive_load.start`; they do not include the user decision time in the popup, nor the loader/merge interval after clicking **Continue** and before `handle_additive_load.start`.

Logs are in `/tmp/`:

- `/tmp/dv3-first-paint-auto-open.log`
- `/tmp/dv3-first-paint-single-xa-241mb.log`
- `/tmp/dv3-first-paint-single-ct-182mb.log`
- `/tmp/dv3-first-paint-single-mg-tomo-57mb.log`
- `/tmp/dv3-first-paint-folder-petct-838files.log`

## Samples

| Sample | Shape | Handoff | First display | Metadata/cine | Navigator structure | Thumbnail jobs |
|---|---:|---|---:|---:|---:|---:|
| WH Ascend SR-inclusive folder | 478 files, 17 series | `new_series=17`, `added_files=478` | 32.2 ms | 24.7 ms | 1.2 ms | 17 jobs, 1000.1 ms total, 830.1 ms max |
| XA single-file multiframe | 241 MB, 450 frames | `new_series=1`, `added_files=1` | 38.9 ms | 14.9 ms | 0.2 ms | 1 job, 230.0 ms |
| Enhanced CT single-file multiframe | 182 MB, 364 frames | `new_series=1`, `added_files=1` | 83.4 ms | 47.7 ms | 0.3 ms | 1 job, 13.3 ms |
| Breast tomo single-file multiframe | 57 MB, 14 frames | `new_series=1`, `added_files=1` | 47.3 ms | 17.2 ms | 0.3 ms | 1 job, 16.7 ms |
| PET/CT folder | 838 files on disk, app reported 1677 added files, 5 series | `new_series=5`, `added_files=1677` | 39.3 ms | 25.0 ms | 0.5 ms | 5 jobs, 53.0 ms total, 21.3 ms max |

## Observations

- In these samples, post-handoff first display was not the dominant delay; it stayed under 100 ms after `handle_additive_load.start`.
- Navigator structure rebuild was also small after handoff, staying near 0-1 ms in these runs.
- Deferred thumbnail generation can still occupy the UI thread after navigator structure creation. The largest observed job was 830.1 ms in the 478-file WH Ascend folder; the 241 MB XA single-file thumbnail took 230.0 ms.
- The enhanced CT single-file run took noticeably longer before reaching `handle_additive_load.start`; current S1 instrumentation starts after loader/merge handoff, so pre-handoff loader timing needs separate instrumentation if that delay is in scope.
- User observation: the XA and CT large-file cases especially took a long time after clicking **Continue** in the large-file warning. That delay is pre-handoff and is not explained by the sub-100 ms post-handoff first-display timings in this note.
- The PET/CT run auto-quit with `QThread: Destroyed while thread '' is still running`; treat that run as invalid and exclude it from comparative timing claims. Worker shutdown needs separate investigation before it is used for a benchmark.

## Implications

- T3/T4 should verify whether the first deferred thumbnail can run before the first paint actually reaches screen; current `first_paint.additive.event_loop_returned` logged after the first thumbnail in the 478-file and XA samples.
- T6/T7 should prioritize thumbnail job cost and scheduling, especially for large multi-frame first datasets and folders with mixed series.
- Add loader/merge timing before `handle_additive_load.start` for file/folder opens that pass through the large-file confirmation, with explicit markers for: large-file check complete, user continued, pipeline start, loader complete, merge complete, and additive handoff.
