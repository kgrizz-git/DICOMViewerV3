# S1c merge_batch profile

**Date:** 2026-07-12

## Scope

Profiled `DICOMOrganizer.merge_batch()` internals for large single-file multi-frame objects after the large-file prompt is auto-confirmed. The runs used `DICOM_PERF_LOG=1` and the existing Qt app harness with `confirm_large_files` monkeypatched to return `True`, so popup decision time is excluded.

## Logs

- `/tmp/dv3-first-paint-s1c-xa-241mb.log`
- `/tmp/dv3-first-paint-s1c-ct-182mb.log`

## Samples

### XA, 241 MB, 450 frames

Source: local 241 MB XA multi-frame sample (450 frames).

Measured timings:

- Loader/decode: 347.5 ms
- `merge_batch` total from worker marker: 4770.8 ms
- Dedup filter: 0.0 ms
- `organize_batch`: 4519.3 ms
- `scan_and_split`: 4517.4 ms
- `create_frame_wrappers`: 4516.6 ms for 450 wrappers
- `sort_and_map`: 1.8 ms
- `apply_batch`: 0.9 ms
- UI handoff: 102.4 ms
- First additive `display_slice`: 53.7 ms
- Thumbnail generation: 138.5 ms

### Enhanced CT, 182 MB, 364 frames

Source: local 182 MB enhanced CT multi-frame sample (364 frames).

Measured timings:

- Loader/decode: 937.1 ms
- `merge_batch` total from worker marker: 26377.2 ms
- Dedup filter: 0.0 ms
- `organize_batch`: 26347.8 ms
- `scan_and_split`: 26346.2 ms
- `create_frame_wrappers`: 26345.7 ms for 364 wrappers
- `sort_and_map`: 1.6 ms
- `apply_batch`: 29.3 ms
- UI handoff: 225.5 ms
- First additive `display_slice`: 87.2 ms
- Thumbnail generation: 13.4 ms

## Interpretation

The post-Continue delay for these large single-file multi-frame samples is dominated by `create_frame_dataset()` / `FrameDatasetWrapper.__init__()` during organizer ingestion. Sorting, deduplication, applying the organized batch, and UI handoff are negligible by comparison.

`FrameDatasetWrapper.__init__()` currently iterates every non-pixel element in the original dataset and performs `copy.deepcopy(original_dataset[tag.tag])` for every frame wrapper. For enhanced CT, this means hundreds of repeated deep copies of a metadata-heavy dataset, which explains the 26.3 second pre-handoff delay. The XA object has more frames but appears less metadata-heavy, so the same path costs 4.5 seconds.

## Recommended next implementation target

Do not spend the next slice on first-paint event-loop scheduling for the XA/CT large-file symptom. The first visible image happens quickly once UI handoff occurs.

Instead, optimize multi-frame wrapper construction before the UI handoff. Candidate approaches:

- Make `FrameDatasetWrapper` lazy/proxy more metadata instead of deep-copying the whole non-pixel dataset for every frame.
- Copy only the small per-frame/display-critical tags needed for sorting, geometry, rescale, window/level, and display metadata, while delegating all other tags to `_original_dataset`.
- Cache shared extracted metadata once per original dataset when creating all frame wrappers, then apply only per-frame overrides.

Any optimization needs regression coverage for sorting, geometry, rescale/window-level, metadata display, and pixel access for enhanced CT/XA/MG multi-frame samples.
