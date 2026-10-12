# Plan: Navigator series thumbnail fallback (skip an empty / near-flat first slice)

**Created:** 2026-10-08 (split out 2026-10-09)
**Status:** **Not started.** Planning only; no product code for this item exists yet.
**Priority:** P2
**Tracks:** [`TO_DO.md`](../../TO_DO.md) — SR browsing & MPR workspace (navigator thumbnail item).

This was the second half of the former combined plan. Its MPR half (multiple
sessions, duplicates and linked scrolling) is implemented and archived in
[`MPR_MULTI_SESSION_AND_LINKED_VIEWS_PLAN.md`](../completed/MPR_MULTI_SESSION_AND_LINKED_VIEWS_PLAN.md).
The two are independent: this work touches series thumbnails (`series_navigator`
thumbnail generation), not MPR tiles.

<a id="navigator-thumbnail-fallback"></a>

## 1. Approach

### 1.1 Current behavior

- `SeriesNavigator.update_series_list` builds `series_list` entries with `first_dataset = datasets[0]` (first element of the per-series list after organizer ordering) and passes that to `_generate_thumbnail(first_dataset, study_series[series_uid])` (`src/gui/series_navigator.py`).
- `_generate_thumbnail` applies W/L via `_resolve_thumbnail_window_level` and `DICOMProcessor.dataset_to_image` (same philosophy as slice display). There is **no** check for “image is all black / flat” after rendering.
- `regenerate_series_thumbnail` similarly assumes a single representative dataset (callers pass “first slice” semantics today).

### 1.2 Proposed heuristic (configurable)

After obtaining a **candidate** PIL image (post W/L) and/or the **rescaled float** pixel array used for display:

1. **Compute contrast metrics** on the grayscale or luminance channel, e.g.:
   - `p_low`, `p_high` = 2nd and 98th percentile (robust to outliers), or min/max;
   - `contrast_ratio = (p_high - p_low) / max(mean_abs, eps)` or simple `(max - min)`;
   - Optional: fraction of pixels outside a narrow mid-gray band.
2. **Treat as “bad thumbnail”** if:
   - `(max - min)` below a small epsilon (true flat), or
   - `contrast_ratio` below threshold **T** (tune starting ~0.001 of full dynamic range or empirically from black-first-slice CT scouts), or
   - mean luminance within **extreme** narrow band (optional guard for “all near zero”).
3. If bad, **retry** with `datasets[len(datasets)//2]` (middle instance in current list order), then optionally **quarter** indices, then fall back to first.
4. **Cache key** today is `(study_uid, series_uid)` only—if the chosen slice index changes, either:
   - include `chosen_instance_index` in the cache key, or
   - invalidate cache when heuristic path is used, or
   - compute heuristic before caching so cache key remains per series (simplest: store “thumbnail_source_index” in a side map keyed by `(study_uid, series_uid)` for diagnostics).

### 1.3 Edge cases

- **Single-slice series:** Middle == first; no change.
- **Multi-frame single dataset:** `datasets` may be one element with many frames—middle should mean **frame index**, not file index. May require using `NumberOfFrames` / per-frame pixel access (align with `MultiFrameSeriesInfo` in the same module).
- **Compressed / lazy failures:** Existing compression-error placeholder path must remain; do not loop heavy decode on dozens of instances without a **cap** (e.g. try at most 3 candidates).
- **Privacy / empty pixel data:** Do not treat SR/no-pixel as “low contrast”; keep existing placeholders.

### 1.4 Implementation phases

- [ ] **Phase 1 — Helper:** Add `_pick_series_thumbnail_dataset(datasets: list[Dataset]) -> Dataset` in `series_navigator.py` (or a small `core/` helper if reused) with unit tests on synthetic arrays (zeros; noise with amplitude 1e-6).
- [ ] **Phase 2 — Wire `update_series_list`:** Replace bare `datasets[0]` for the **main** series thumbnail path; keep tooltips/SeriesNumber from first instance unless product prefers “display series” metadata from chosen file.
- [ ] **Phase 3 — Instance mode:** When “show instances separately” builds per-instance thumbnails, apply the same heuristic **per instance** (first frame of that instance, then middle frame if needed).
- [ ] **Phase 4 — `regenerate_series_thumbnail`:** Caller currently passes one dataset; either pass the series list and reuse picker, or document that regeneration is for W/L refresh only and re-pick slice.
- [ ] **Phase 5 — Optional config:** Settings toggle “Navigator: prefer middle slice when first is flat” or advanced numeric threshold (default on).

### 1.5 Open questions

- Should ordering follow **Instance Number** / **Slice Location** rather than raw list order so “middle” is anatomically meaningful?
- Is 0.1% contrast the right order of magnitude for CT, MRI, and CR/DR without per-modality thresholds?
---

## 2. Verification (when implemented)

- **Thumbnails:** a series with an intentional black first slice shows recognizable anatomy in the navigator; multiframe series still correct; cache invalidation does not regress performance on large studies.

---

## 3. Primary code touchpoints (reference)

| Area | Files |
|------|--------|
| Series thumbnail generation | `src/gui/series_navigator.py` (`update_series_list`, `_generate_thumbnail`, `regenerate_series_thumbnail`) |
| Thumbnail ordering / specs helpers | `src/gui/series_navigator_model.py` |

---

*Document version: 2026-10-09 — planning only; no product code changes.*
