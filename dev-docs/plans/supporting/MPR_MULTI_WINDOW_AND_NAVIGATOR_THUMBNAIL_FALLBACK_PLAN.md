# Plan: MPR in multiple windows / multiple detached sessions + navigator thumbnail fallback

Supporting plan for two UX backlog items in `dev-docs/TO_DO.md` (UX / Workflow).

| Item | Priority | Summary |
|------|----------|---------|
| Multiple MPR windows + multiple detached MPRs | P1 | Extend controller + navigator so more than one MPR can live off-pane without losing prior sessions, and clarify or extend in-pane multi-MPR workflows. |
| Series thumbnail when first slice is empty / flat | P2 | If the representative slice for the navigator is visually empty or extremely low contrast, pick a better slice (e.g. middle of stack). |

---

## 1. Investigation summary (current behavior)

### 1.1 In-pane MPR (per subwindow)

- `MprController` documents that **each subwindow may independently be in MPR mode** via `subwindow_data[idx]["is_mpr"]` and related keys (`mpr_result`, `mpr_slice_index`, …). See module docstring and `is_mpr()` in `src/core/mpr_controller.py`.
- `open_mpr_dialog(target_subwindow_idx)` always targets the pane that requested the dialog; there is **no** global guard that prevents a second pane from building its own MPR while another pane already shows MPR.
- The series navigator can show **several** MPR tiles: `SeriesNavigator._mpr_thumbnail_specs` / `_mpr_thumbnails` are keyed by **subwindow index** (`set_mpr_thumbnail` / `clear_mpr_thumbnail` in `src/gui/series_navigator.py`).

**Implication:** “Load MPR into multiple windows” is largely **already supported** for **attached** sessions, provided the user opens **Create MPR** from each pane (or relocates via drag-drop). If users still report inability to do this, the gap is likely **workflow discoverability**, a **specific interaction bug**, or a request for **duplicate linked views** (same MPR rendered in two panes simultaneously)—that last case is **not** implemented today (one `MprResult` per pane; relocate moves rather than clones).

### 1.2 Detached (“floating”) MPR — single session only

- Detached state is stored as a **single** optional payload: `_detached_mpr_payload` on `MprController` (`src/core/mpr_controller.py`).
- `detach_mpr_from_subwindow(idx)` **always overwrites** that slot: a second detach **drops** the previous floating session from the controller (no stack, no LRU).
- The navigator uses a **single** sentinel subwindow index **`-1`** for the detached thumbnail (`_update_floating_mpr_navigator_thumbnail` in `src/main.py`; `MprThumbnailWidget` treats `< 0` specially).
- Starting a **new** in-pane MPR clears any detached session: `_activate_mpr` sets `_detached_mpr_payload = None` so a new build does not leave stale floaters (`mpr_controller.py`).

**Implication:** “More than one MPR constructed and **detached**” is **not** supported; it is the main technical gap behind the P1 backlog line.

### 1.3 Drag / drop and “-1”

- MIME type `application/x-dv3-mpr-assign` and `SubWindowContainer` treat source index **-1** as “attach floating MPR” (`src/main.py` `_on_mpr_assign_requested`).
- Only one floating session exists, so the UI model **implicitly** assumes at most one `-1` thumbnail.

---

<a id="mpr-multi-window-detached"></a>

## 2. Plan: MPR — multiple windows + multiple detached sessions (P1)

### 2.1 Goals

1. **Multiple detached MPR sessions** can coexist without silently discarding earlier ones.
2. **Navigator** shows one thumbnail per detached session (ordering TBD—see open questions).
3. **Drag-drop** can target a specific detached session or attach the correct session to a pane.
4. **Clear / discard** remains explicit (per-session context menu or equivalent).
5. **Memory / UX guardrails:** cap the number of floaters or total estimated RAM; surface a message when the cap is hit instead of silent loss.

### 2.2 Design directions (pick one in implementation)

**Option A — Stable floating IDs (recommended baseline)**

- Replace `_detached_mpr_payload: Optional[dict]` with `_detached_mpr_sessions: dict[int, dict]` (or a small list of named payloads with monotonic IDs).
- Navigator keys MPR thumbnails not only by `0..3` for in-pane but by **opaque ids** for floaters (e.g. `-1`, `-2`, … internally, or positive ids with an enum `kind=in_pane|detached`).
- `MprThumbnailWidget` / `SeriesNavigator.set_mpr_thumbnail` signatures evolve from `subwindow_index: int` to **`mpr_thumbnail_id: int`** (or a tiny dataclass) with documented ranges.
- `attach_floating_mpr(to_idx, session_id)` selects which floater attaches.
- MIME payload for drags encodes **session id** (not only `-1`).

**Option B — Queue of floaters with single UI row**

- Keep one visible “floating” tile but maintain a **stack** or queue in the controller; “cycle” or submenu to choose which to attach. Lower UI churn, worse discoverability.

**Option C — Clone view (same volume, two panes)**

- If product intent is “same MPR in two windows” without duplicating heavy arrays, hold **one** `MprResult` with refcount or shared pointer and two display states (`mpr_slice_index`, W/L) per pane. This is a **different** feature from multiple independent volumes; scope separately.

### 2.3 Implementation phases

- [ ] **Phase 0 — Product confirmation:** Confirm whether “multiple windows” means (i) independent MPR builds per pane, (ii) multiple floaters, (iii) linked duplicate views, or (iv) all of the above.
- [ ] **Phase 1 — Data model:** Introduce multi-session detached storage on `MprController`; migrate `has_detached_mpr`, `clear_detached_mpr`, `get_detached_mpr_thumbnail_pixels`, `attach_floating_mpr`, `detach_mpr_from_subwindow`, and `_activate_mpr` clearing policy (clear none vs clear all vs clear only “orphaned” — document choice).
- [ ] **Phase 2 — Navigator:** Extend `SeriesNavigator` / `set_mpr_thumbnail` to register **N** detached thumbnails next to the source series (or a dedicated sub-row); update width calculation that currently counts `_mpr_thumbnail_specs` per study/series.
- [ ] **Phase 3 — DnD:** Update `MprThumbnailWidget` and `SubWindowContainer` decode path to pass **session id**; update `_on_mpr_assign_requested` in `main.py`.
- [ ] **Phase 4 — Clear window / lifecycle:** Ensure **Clear Window** on each pane still detaches that pane’s MPR into a **new** session id; define what happens when the same user detaches twice from the same pane without reattach (two entries vs replace).
- [ ] **Phase 5 — Tests:** Unit tests for controller session list + attach/clear; optional GUI smoke for drag of second floater (if harness exists).

### 2.4 Risks

- **Memory:** Each `MprResult` holds large numpy stacks; multiple floaters multiply RAM. A configurable cap (with user-visible warning) is strongly advised.
- **API churn:** Any code reaching into `_detached_mpr_payload` privately (e.g. `main.py` `getattr(self._mpr_controller, "_detached_mpr_payload"`) should be replaced with a **public** accessor returning study/series metadata for thumbnails.

### 2.5 Open questions

- Maximum number of simultaneous detached MPRs (hard cap vs soft warning)?
- Navigator layout when **two** floaters from the **same** source series exist (side-by-side vs overflow menu)?
- Should **new in-pane MPR** still clear **all** floaters, only floaters from the same source series, or never clear floaters?

---

<a id="navigator-thumbnail-fallback"></a>

## 3. Plan: Navigator series thumbnail — skip empty / near-flat first slice (P2)

### 3.1 Current behavior

- `SeriesNavigator.update_series_list` builds `series_list` entries with `first_dataset = datasets[0]` (first element of the per-series list after organizer ordering) and passes that to `_generate_thumbnail(first_dataset, study_series[series_uid])` (`src/gui/series_navigator.py`).
- `_generate_thumbnail` applies W/L via `_resolve_thumbnail_window_level` and `DICOMProcessor.dataset_to_image` (same philosophy as slice display). There is **no** check for “image is all black / flat” after rendering.
- `regenerate_series_thumbnail` similarly assumes a single representative dataset (callers pass “first slice” semantics today).

### 3.2 Proposed heuristic (configurable)

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

### 3.3 Edge cases

- **Single-slice series:** Middle == first; no change.
- **Multi-frame single dataset:** `datasets` may be one element with many frames—middle should mean **frame index**, not file index. May require using `NumberOfFrames` / per-frame pixel access (align with `MultiFrameSeriesInfo` in the same module).
- **Compressed / lazy failures:** Existing compression-error placeholder path must remain; do not loop heavy decode on dozens of instances without a **cap** (e.g. try at most 3 candidates).
- **Privacy / empty pixel data:** Do not treat SR/no-pixel as “low contrast”; keep existing placeholders.

### 3.4 Implementation phases

- [ ] **Phase 1 — Helper:** Add `_pick_series_thumbnail_dataset(datasets: list[Dataset]) -> Dataset` in `series_navigator.py` (or a small `core/` helper if reused) with unit tests on synthetic arrays (zeros; noise with amplitude 1e-6).
- [ ] **Phase 2 — Wire `update_series_list`:** Replace bare `datasets[0]` for the **main** series thumbnail path; keep tooltips/SeriesNumber from first instance unless product prefers “display series” metadata from chosen file.
- [ ] **Phase 3 — Instance mode:** When “show instances separately” builds per-instance thumbnails, apply the same heuristic **per instance** (first frame of that instance, then middle frame if needed).
- [ ] **Phase 4 — `regenerate_series_thumbnail`:** Caller currently passes one dataset; either pass the series list and reuse picker, or document that regeneration is for W/L refresh only and re-pick slice.
- [ ] **Phase 5 — Optional config:** Settings toggle “Navigator: prefer middle slice when first is flat” or advanced numeric threshold (default on).

### 3.5 Open questions

- Should ordering follow **Instance Number** / **Slice Location** rather than raw list order so “middle” is anatomically meaningful?
- Is 0.1% contrast the right order of magnitude for CT, MRI, and CR/DR without per-modality thresholds?

---

## 4. Verification (when implemented)

- **MPR:** Two panes each show different MPR stacks; two floaters visible; attach second floater to empty pane; verify first floater still attachable; verify memory cap message if enabled.
- **Thumbnails:** Series with intentional black first slice shows recognizable anatomy in navigator; multiframe series still correct; cache invalidation does not regress performance on large studies.

---

## 5. Primary code touchpoints (reference)

| Area | Files |
|------|--------|
| MPR lifecycle, detach, attach | `src/core/mpr_controller.py` |
| Floating thumbnail refresh | `src/main.py` (`_update_floating_mpr_navigator_thumbnail`, `_on_mpr_assign_requested`, `_on_mpr_clear_from_navigator_thumbnail`) |
| Navigator MPR tiles | `src/gui/series_navigator.py`, `src/gui/mpr_thumbnail_widget.py` |
| Drop targets | `src/gui/sub_window_container.py` |
| Series thumbnail generation | `src/gui/series_navigator.py` (`update_series_list`, `_generate_thumbnail`, `regenerate_series_thumbnail`) |

---

*Document version: 2026-04-16 — planning only; no product code changes in this commit.*
