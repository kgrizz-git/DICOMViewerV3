# Pre-Handoff Large-File Timing Measurements (T1b)

**Date:** 2026-07-12
**Task:** (T1b) Re-run large single-file XA and CT samples with S1b instrumentation to separate popup/user wait, loader/decode, merge/indexing, and post-handoff first-paint timing.

## Harness

Perf logging was enabled with `DICOM_PERF_LOG=1`. The app was launched programmatically with `app._open_files_from_paths([target])`. The large-file confirmation was auto-confirmed by replacing `app.file_dialog.confirm_large_files` with a lambda returning `True`, so `large_file_confirm.wait` excludes human decision time and represents a simulated immediate **Continue** click.

Logs:

- `/tmp/dv3-first-paint-t1b-xa-241mb.log`
- `/tmp/dv3-first-paint-t1b-ct-182mb.log`

## Results

| Sample | Large-file check | Loader/decode | Merge/organize | UI handoff | First display | Thumbnail |
|---|---:|---:|---:|---:|---:|---:|
| XA single-file multiframe, 241 MB / 450 frames | 1 large file, auto-continued | 329.2 ms | 4933.8 ms | 92.6 ms | 44.2 ms | 273.9 ms |
| Enhanced CT single-file multiframe, 182 MB / 364 frames | 1 large file, auto-continued | 939.8 ms | 26272.7 ms | 227.1 ms | 88.7 ms | 13.5 ms |

## Interpretation

- The user-observed delay after clicking **Continue** is primarily pre-handoff `merge_batch` / organize time, not first display.
- The enhanced CT case is the clearest outlier: about 0.94 s loading/decode, then about 26.3 s merge/organize before the UI handoff starts.
- XA also spends most of the post-Continue delay in merge/organize: about 4.9 s merge vs 0.33 s load and 0.09 s UI handoff.
- Post-handoff first display remains comparatively small in both runs: under 100 ms for the first `display_slice()` block.
- Thumbnail generation is still relevant after handoff for XA (273.9 ms), but it does not explain the long post-Continue pause.

## Implications

- This baseline recommendation was superseded by S1c/T4. `FrameDatasetWrapper` metadata copying was identified as the dominant merge cost and fixed; see [T4 wrapper optimization measurements](2026-07-12-post-load-first-paint-T4-wrapper-optimization-measurements.md).
- Residual thumbnail/navigator work did not justify added scheduling complexity after the fix. The archived plan records the decision and the only residual P3 measurement follow-up.
