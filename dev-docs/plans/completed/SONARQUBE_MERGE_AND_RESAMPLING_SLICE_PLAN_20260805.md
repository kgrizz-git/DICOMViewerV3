# Plan: Local SonarQube Merge and Resampling Slice

**Last updated:** 2026-08-05
**Status:** Implemented
**Branch:** `refactor/sonar-top-complexity-rendering-export`
**Scope:** Extend the existing, unpushed PR with two behavior-preserving
`python:S3776` refactors in two production files.

## Goal

Reduce cognitive complexity in the two highest-ranked remaining, distinct-file
findings without changing DICOM load, series merge, fusion, cache, or pixel
resampling behavior. Keep the first five-function refactor slice closed in its
archived plan; this is a separately reviewable follow-on slice in the same PR.

## Baseline and selection

The local SonarQube report submitted for source revision
`9a08fcd4b6930343a771fce5c6c63429c254e08d` contains 238 active
BLOCKER/CRITICAL/MAJOR findings. A direct ranking of open `python:S3776`
findings selected these top two distinct files:

| File | Method | Sonar complexity | Why selected |
|---|---|---:|---|
| `src/core/dicom_organizer.py` | `merge_batch` | 65 | Highest remaining finding; central additive-load and deduplication path. |
| `src/core/image_resampler.py` | `get_resampled_slice` | 63 | Second-highest remaining file; central 3D fusion resampling and cache path. |

Neither selected source file changed between that ranked scan and the start of
this extension. The remaining 62-point `ExportManager` finding is deferred so
this slice remains two files and two functions.

## Guardrails

- Preserve public method signatures, returned values, cache keys, path keys,
  side effects, error behavior, and performance-timing labels.
- Keep helpers private to their current modules. Do not add a new dependency
  edge, persistent state, DICOM fixture, or binary asset.
- Retain the existing synthetic-data-only testing policy. Do not log DICOM
  tag values or local file paths.
- Do not alter unrelated remaining Sonar findings in either selected file.
- Avoid creating `S107` findings: group closely related private helper inputs
  where a helper would otherwise require a long parameter list.

## Stream A — additive study/series merging

### Target

`DICOMOrganizer.merge_batch()` — cognitive complexity 65.

### Refactor shape

Keep `merge_batch` as the transactional orchestration method. Extract small
private helpers for:

1. normalizing and filtering duplicate incoming paths while preserving the
   existing no-path behavior;
2. building existing/new `(dataset, path)` tuples for a series;
3. adding batch file-path mappings for a destination series key;
4. appending and re-sorting an existing same-source series, including its
   multiframe metadata update and result recording; and
5. creating a new or source-disambiguated series, including the `_vN` key,
   source-directory map, multiframe metadata, and result recording.

Do not move the outer timing spans or change when PS/KO sidecars and normalized
loaded paths are applied. Helpers must preserve the literal timing labels used
by the privacy-aware performance instrumentation.

### Contracts to characterize and preserve

- Empty input returns an empty `MergeResult` without mutating organizer state.
- Canonically duplicate paths are skipped and counted; missing input paths do
  not fabricate a file-path mapping or loaded-path entry.
- Same-source incoming slices append, re-sort, preserve old path mappings, add
  new path mappings, refresh multiframe metadata, and report `appended_series`.
- A new base series reports `new_series`; a different source directory creates
  the next `_vN` series key and maps its path entries to that effective key.
- `added_file_count` counts only normalized incoming paths, while PS/KO sidecars
  continue merging by study.

### Tests

Extend `tests/test_dicom_organizer.py` with independently asserted paths for
dedupe, appends, new series, source disambiguation, partial/no paths, and
multiframe instance identifiers. Keep `tests/test_sr_organizer_and_metadata.py`,
`tests/test_loading_pipeline_sonar_slice.py`, and
`tests/test_canceled_load_behavior.py` green.

## Stream B — cached 3D fusion-slice resampling

### Target

`ImageResampler.get_resampled_slice()` — cognitive complexity 63.

### Refactor shape

Keep the public method as a short sequence of validation, reference-index
resolution, volume lookup/resampling, NumPy conversion, and final slice
extraction. Extract private helpers for:

1. resolving/caching the sorted, duplicate-filtered reference dataset list;
2. mapping an unsorted requested dataset to its sorted index, including the
   duplicate-location tolerance fallback;
3. deriving the optional volume-cache key;
4. reading or constructing the resampled volume and maintaining paired LRU
   caches; and
5. reading or constructing the cached NumPy volume before bounds-safe
   float32 slice extraction.

Do not change `dicom_series_to_sitk` ordering, SimpleITK interpolator use,
rescale timing, cache-lock boundaries, LRU capacity, or numpy dtype conversion.

### Contracts to characterize and preserve

- Unavailable SimpleITK, an invalid slice index, or an empty reference list
  returns `None` before any conversion work.
- The original unsorted reference index selects the same image after the
  sorted/deduplicated reference grid is built; duplicate locations use the
  first tolerance-matched sorted slice, otherwise the original index fallback.
- A cache hit avoids DICOM-to-SimpleITK conversion; cache-disabled calls bypass
  volume caching; cache eviction clears the matching NumPy cache entry.
- Any failed conversion/resample/NumPy extraction and an out-of-volume sorted
  index returns `None`.
- Returned slices retain their current values, 2-D shape, and `float32` dtype.

### Tests

Extend `tests/test_image_resampler.py` for sorted-index mapping, duplicate
fallback, cache hit/miss, cache-disabled conversion, paired LRU eviction,
conversion failure, bounds failure, and float32 output. Keep
`tests/core/test_fusion_handler_coverage.py`,
`tests/core/test_fusion_handler_match_slice.py`, and
`tests/fusion_audit_synthetic_2d_vs_3d_test.py` green.

## Commit plan

Continue the current PR with reviewable, independently green commits:

1. `docs: plan merge and resampling complexity slice`
2. `test: characterize batch merge contracts`
3. `refactor: simplify batch merge orchestration`
4. `test: characterize resampled slice contracts`
5. `refactor: simplify resampled slice orchestration`
6. `docs: record merge and resampling remediation`

Do not combine a characterization commit with its corresponding refactor.
No user-visible behavior change is intended, so do not add a CHANGELOG entry
for the refactor itself.

## Implementation outcome

- `c971576` adds merge characterization for retained mappings, missing paths,
  and multi-frame instance identifiers; `c573548` makes `merge_batch` a short
  orchestration method backed by private, timing-preserving helpers.
- `d013709` adds resampling characterization for sorted-index mapping,
  duplicate-location fallback, cache-disabled conversion, and paired LRU
  eviction; `c58a491` makes `get_resampled_slice` an orchestration method with
  private reference-grid and cache helpers.
- The focused combined suite passed **117** tests and the full suite passed
  **3,639** tests. Architecture boundaries, repository harness, automated
  agent-smoke report, and staged privacy checks passed.
- A fresh local SonarQube analysis for source revision `c573548` reported
  **236** priority findings (238 → 236). It has no open `python:S3776`
  finding at either selected target; the highest remaining one is now
  `ExportManager` at 62.
- Contributor manual smoke passed: the additive different-source load retained
  one study with two series thumbnails, and fusion overlay scrolling behaved
  correctly. The implementation plan is ready to archive under
  `plans/completed/`.

## Verification and acceptance criteria

With the project virtual environment active, run:

1. `python -m pytest tests/test_dicom_organizer.py tests/test_sr_organizer_and_metadata.py tests/test_loading_pipeline_sonar_slice.py tests/test_canceled_load_behavior.py -v`
2. `python -m pytest tests/test_image_resampler.py tests/core/test_fusion_handler_coverage.py tests/core/test_fusion_handler_match_slice.py tests/fusion_audit_synthetic_2d_vs_3d_test.py -v`
3. `python -m pytest tests/ -v`
4. `python scripts/check_architecture_boundaries.py`
5. `python scripts/check_repo_harness.py`
6. `python scripts/agent_smoke_harness.py --write-report`
7. `python scripts/git_hook_privacy_checks.py --staged`

Before final analysis, manually smoke an additive same-study load plus a
different-source same-series load using approved non-PHI data, and verify a
fusion overlay while scrolling slices. Finally, run a fresh local SonarQube
analysis and confirm both selected `S3776` locations are absent from the scoped
report for the checked-out source revision.

## Explicitly out of scope

- The remaining `S3776` findings in `dicom_organizer.py` and
  `image_resampler.py`, including organizer grouping/sorting methods.
- `ExportManager` and every other file, even when their ranking is close.
- Changes to load UX, fusion registration, interpolation policy, cache size,
  DICOM parsing, persistence, logging policy, or CI thresholds.
