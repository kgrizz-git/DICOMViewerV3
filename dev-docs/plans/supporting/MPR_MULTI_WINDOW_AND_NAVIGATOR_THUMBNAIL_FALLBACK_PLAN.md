# Plan: MPR in multiple windows / multiple detached sessions + navigator thumbnail fallback

Supporting plan for two UX backlog items in `dev-docs/TO_DO.md` (UX / Workflow).

**Last updated:** 2026-10-09

## Pre-implementation review (2026-10-08)

Code inspection confirms the single detached slot and activation-time discard
still exist. This review covers the P1 MPR work only; the P2 thumbnail heuristic
below remains separate. Detached means an in-memory session represented in the
navigator, not a separate OS window or a session persisted across app restarts.

### Agreed baseline (2026-10-08)

- Support independent builds, multiple detached sessions, duplicate views sharing
  one result, and optional linked scrolling between duplicate views.
- Use stable session and view IDs independent of pane assignment. Negative IDs
  may remain a navigator adapter for detached views; pane indices are not
  session identity. Every attach/clear resolves the exact view; stale IDs are
  harmless no-ops.
- Preserve detached sessions when building a new MPR, including another build
  from the same source series. Re-detaching preserves its view identity;
  detaching an already empty/non-MPR pane creates nothing.
- Show one tile per view after its source series in creation order, with an
  orientation/session label to distinguish same-source sessions. Sorting negative
  IDs numerically would reverse creation order; specify ordering explicitly.
- Preserve a destination MPR as a detached session on a successful replacement.
  Failed moves/attachments must preserve both sessions and the destination's
  prior 2-D state. Do not discard a session as a side effect of a drop.

### Bug risks and required plan additions

1. **Transactional transfer:** `relocate_mpr_subwindow` tears down the source
   and clears the destination before checking installation success.
   `_install_mpr_payload_at_subwindow` mutates pane fields before display can
   fail. Existing attach rollback covers a prior MPR, but not all partial state
   or a prior ordinary image. Validate targets/payloads first; snapshot and
   restore state on failure; publish thumbnail changes only after success.
2. **Build races:** worker callbacks unconditionally pop the pane worker and
   activate their result. Check worker identity or a pane generation token so
   a late canceled/replaced build cannot overwrite a newly attached session or
   remove a newer worker. Cancel destination builds before transfers.
3. **Session display state:** the captured payload includes slice/combine state
   but omits W/L, raw/rescaled mode, inversion, LUT, zoom and pan. Detached
   thumbnails borrow focused-pane settings, and attached thumbnails also read
   W/L from the focused controls. Decide and
   test which settings travel with the session; at minimum make thumbnail
   rendering independent of whichever unrelated pane currently has focus.
4. **Source lifetime:** define close-series, close-study, close-all and app-exit
   cleanup explicitly. Detached payloads retain source datasets/volume arrays;
   closing a source must remove its attached/detached sessions and invalidate
   pending builds so hidden references do not keep closed data alive.
5. **Memory admission:** a detach moves existing array ownership, while a new
   build allocates additional arrays. A detach-only limit cannot bound RAM.
   Count unique source/result arrays across attached, detached and pending
   builds. Admission limits apply to growth, not detach/reattach; never evict
   older sessions silently.
6. **Public API and UI refresh:** replace private payload reads with per-session
   metadata/pixel accessors. Refresh/remove all relevant session tiles on
   source closure and navigator rebuild; width accounting and same-source
   grouping must handle every ID. Existing integer MIME can carry negative IDs;
   the app dispatcher currently discards their identity and must change.

### Confirmed decisions and implementation defaults

The user approved duplicate/linked views, display-state preservation and the
proposed admission policy. Preserve an occupied destination MPR as detached.
Preserve slice/combine, W/L, rescale mode, inversion and LUT per view. Fit to the
new viewport on attachment; zoom/pan restoration is deferred.

Default to a configurable cap of **8 constructed MPR sessions**, including
attached, detached and pending builds. A session is one independently built
result; duplicates are views of that session and consume no new session slot.
Reserve admission before volume construction/cache loading, release reservations
on cancellation/failure/closure, and never evict automatically. Estimate unique
array memory for visibility; defer a hard RAM budget. Eight is a UX limit, not a
RAM guarantee. The user accepted **16 total views** as plenty. Keep this
configurable default to limit navigator clutter; duplicates share session arrays,
so lowering the view cap is not an effective volume-memory control. Count
attached, detached and reserved views; moves/detach/reattach consume no additional
slot. Duplication into an occupied pane is +1 view because the displaced view is
retained. Validate `view_cap >= session_cap >= 1`; defaults are 16/8 but the knobs
are separate. Do not silently evict to repair config or lower limits. Admission
messages identify the limiting cap and show current/limit counts.

Opus recommended 32 views to allow four duplicates per each of eight sessions;
retain 16 because the user considers it sufficient and the cap is configurable.
The proposed sync rule below now treats linked views as one scrolling unit,
including incoming global sync, removing the earlier asymmetric exclusion rule.

### Independent review

MiMo V2.6 Flash Free and Claude Opus 5.5 Low reviewed the plan against code; both
supported the design after refinements, and all three scratch bug reproductions
passed (also independently rerun by the primary agent).

### Required verification additions

Controller tests must cover two same-source sessions, selective attach/clear,
new-build preservation, repeated detach/reattach, occupied-target preservation,
invalid/stale IDs, installation exceptions with rollback, source closure and
late worker completion. GUI tests must exercise a second negative drag ID,
individual context-menu deletion, tile order/width and navigator rebuild.
Manual smoke must include independent attached MPRs, both detached tiles,
display-state restoration, occupied-target drop and close-source cleanup.

### Current code map (supersedes historical paths below)

- Lifecycle/build callbacks: `src/gui/mpr_controller.py`.
- Thumbnail orchestration: `src/core/mpr_navigator_thumbnail.py`.
- App dispatch: `MPRNavigationMixin` in `src/main_app_subwindow_management.py`.
- Clear Window/source closure: `src/core/study_navigation_handlers.py`.
- Navigator layout/width: `src/gui/series_navigator.py`,
  `src/gui/series_navigator_view.py`, `src/gui/series_navigator_model.py`.
- Drag source/target: `src/gui/mpr_thumbnail_widget.py`,
  `src/gui/sub_window_container.py`.

The implementation phases below incorporate these lifecycle and rollback cases.
Automated drag/dispatch coverage and manual smoke are required.

| Item | Priority | Summary |
|------|----------|---------|
| Multiple MPR windows + detached/duplicate/linked views | P1 | Introduce session/view ownership, multiple detach, shared-result duplicates and explicit linked scrolling. |
| Series thumbnail when first slice is empty / flat | P2 | If the representative slice for the navigator is visually empty or extremely low contrast, pick a better slice (e.g. middle of stack). |

---

## 1. Investigation summary (current behavior)

### 1.1 In-pane MPR (per subwindow)

- `MprController` documents that **each subwindow may independently be in MPR mode** via `subwindow_data[idx]["is_mpr"]` and related keys (`mpr_result`, `mpr_slice_index`, …). See module docstring and `is_mpr()` in `src/gui/mpr_controller.py`.
- `open_mpr_dialog(target_subwindow_idx)` always targets the pane that requested the dialog; there is **no** global guard that prevents a second pane from building its own MPR while another pane already shows MPR.
- The series navigator can show **several** MPR tiles: `SeriesNavigator._mpr_thumbnail_specs` / `_mpr_thumbnails` are keyed by **subwindow index** (`set_mpr_thumbnail` / `clear_mpr_thumbnail` in `src/gui/series_navigator.py`).

**Implication:** “Load MPR into multiple windows” is largely **already supported** for **attached** sessions, provided the user opens **Create MPR** from each pane (or relocates via drag-drop). If users still report inability to do this, the gap is likely **workflow discoverability**, a **specific interaction bug**, or a request for **duplicate linked views** (same MPR rendered in two panes simultaneously)—that last case is **not** implemented today (one `MprResult` per pane; relocate moves rather than clones).

### 1.2 Detached (“floating”) MPR — single session only

- Detached state is stored as a **single** optional payload: `_detached_mpr_payload` on `MprController` (`src/gui/mpr_controller.py`).
- `detach_mpr_from_subwindow(idx)` **always overwrites** that slot: a second detach **drops** the previous floating session from the controller (no stack, no LRU).
- The navigator uses a **single** sentinel subwindow index **`-1`** for the detached thumbnail (`_update_floating_mpr_navigator_thumbnail` in `src/main_app_subwindow_management.py`; `MprThumbnailWidget` treats `< 0` specially).
- Starting a **new** in-pane MPR clears any detached session: `_activate_mpr` sets `_detached_mpr_payload = None` so a new build does not leave stale floaters (`mpr_controller.py`).

**Implication:** “More than one MPR constructed and **detached**” is **not** supported; it is the main technical gap behind the P1 backlog line.

### 1.3 Drag / drop and “-1”

- MIME type `application/x-dv3-mpr-assign` and `SubWindowContainer` treat source index **-1** as “attach floating MPR” (`src/main.py` `_on_mpr_assign_requested`).
- Only one floating session exists, so the UI model **implicitly** assumes at most one `-1` thumbnail.

---

<a id="mpr-multi-window-detached"></a>

## 2. Plan: multiple MPR sessions, duplicate views and linked scrolling (P1)

### 2.1 Session / view model and ownership

- A session owns a stable session ID, immutable shared `MprResult`, source
  identity and build metadata. NumPy result/source arrays are shared by
  references, not copied for duplication; rendering/rescale/combine must not
  mutate shared arrays. No manual reference counter is needed for ordinary
  Python ownership, but registry lifetime must be explicit.
- A view owns a stable view ID, session ID, optional pane assignment, slice
  index, combine settings and display state. Detached views retain this state.
  Multiple views of one session can be attached or detached independently.
- Pane-to-view mapping and view-to-session mapping are authoritative. Keep
  existing `subwindow_data` fields as adapters for display/export/tools while
  migrating; avoid two mutable sources of truth. Define all controller APIs in
  terms of view/session IDs, with public navigator metadata accessors.
- `MprController` owns the registry; navigator specs are keyed by stable view
  ID with pane display number stored separately. Each view has an immutable
  creation sequence used for sorting across moves, detach and reattach.
- One tile per view, grouped after the source series, ordered by creation.
  Labels identify session, orientation, attached pane or detached state and
  linked membership without patient-identifying text.
- Clear MPR removes only that view; Clear Window detaches it. The session is
  released after its last view is discarded. Close All releases every session,
  view and pending reservation. Closing the source series/study
  removes every dependent session/view and pending build; closing the app
  releases all. No persistence across application restarts.

### 2.2 Duplicate and link UX

- Preserve ordinary drag as move/attach. Add explicit navigator actions
  **Duplicate into Window…** and **Duplicate Linked into Window…**, choosing
  an existing visible target pane. Disable the current source pane as a target.
  Duplication copies view state, shares the result and fits the target viewport.
- Preserve an occupied destination as detached atomically, including at the
  admission limits: replacement moves its view, rather than allocating one.
  Do not modify either source/destination until target validation succeeds.
- Plain duplication starts unlinked. Linked duplication joins the source's
  session-local link group, or creates one with source and duplicate. Add a
  **Unlink View** action and visible link indicator. Detached source tiles can
  also be duplicated; a detached member is dormant until attached again.
- Initial linking synchronizes **slice position only**, bidirectionally for
  views of the exact same result. W/L, inversion, LUT, zoom/pan and combine
  settings stay independent. Initial linked duplication copies the source's
  current slice. On reattachment, linked views adopt the group canonical slice;
  unlinked views retain their own slice.
- User scrolling, slider, keyboard navigation and cine all update the group's
  canonical slice once through a controller-owned slice setter called from
  `core/slice_display_handlers.on_slice_changed`. It redraws attached peers
  through `display_mpr_slice`; that rendering method never initiates link
  propagation, since overlay/W/L/combine refreshes also call it.
  Detached members retain/adopt that canonical slice without rendering.
  Suppress recursive propagation and redundant redraws. Reuse the existing
  single app-level cine player bound to the focused pane; its navigation uses
  the same slice setter. Test focus changes during playback.
- This session-local link is explicit and independent of the global anatomic
  slice-sync toggle. Treat a linked group as one scrolling unit: any slice
  update reaching a member, from user input or incoming global sync, updates
  the whole group through `MprController.set_view_slice`. With A/B duplicate
  views and native series C in global sync, scrolling A moves B and C; scrolling
  C anatomically selects an MPR slice and moves A/B together. Existing geometric
  overlap/tolerance rules still apply; no change when no valid match exists.
- `SliceSyncCoordinator._update_target` calls the setter for MPR targets instead
  of rendering directly. Before propagation, deduplicate global targets by
  explicit group ID; exclude the source's already-updated explicit group. One
  incoming target update reaches all linked members, even members not assigned
  to that particular pane-based global group. Keep explicit group membership
  in the registry, including detached members. This is intentional: linking
  means those views always share slice position.
- Use a setter-level guard separate from global `_syncing`, equal-index early
  returns and one propagation origin/event. Peer redraws never call
  `on_slice_changed` or start a new global propagation pass. User actions
  initiate global sync once from the initiating pane; incoming global updates
  update their explicit group without cascading into other global groups.
  Test both directions, duplicate targets and links spanning global groups.
- Linking different results/orientations by patient-space geometry continues
  through the existing global sync workflow. New crosshair navigation,
  orthogonal tri-planar reslicing, and linked display parameters are out of
  scope for this batch. Duplication does not generate a different orientation.

### 2.3 Transactions, builds and admission

- Validate source view, target pane and source lifetime before allocation.
  Snapshot destination 2-D/MPR state and managers; defer registry/tile changes
  until install succeeds. Rollback includes all MPR keys/previous-state keys,
  rendered image/context, mouse mode and `_mpr_mode_override`, tool enablement,
  W/L and user-modified flag, rescale parameters/mode, inversion/LUT, banner,
  navigator/slider and focused UI references. Snapshot without copying volume
  arrays. Validate before writing `mpr_previous_state`; no success signals on
  failure. Roll back complete display state on exceptions.
  Failed move/attach/duplicate leaves the source and occupied destination usable.
- Restoration/duplication carries window center/width, W/L user-modified flag,
  rescale mode/slope/intercept/type, inversion and view LUT explicitly. Existing
  views skip the new-build W/L reset. Avoid changing another duplicate through
  a shared series LUT setting. Thumbnails read only their owning view state.
- Existing sessions survive new builds, including builds from the same series.
  Building over an MPR preserves its old view as detached only after success;
  cancel/error retains the old view. A successful build creates a new session.
- Reserve a session slot before building/loading; reserve a view slot for each
  new build or duplicate. Count in-flight reservations to prevent concurrent
  admission overrun. Apply the same admission to cache hits and direct
  activation: activation requires a valid reservation or an existing view.
  Reservation release is idempotent, exactly once even when cancel, closure
  and error callbacks overlap. Same-pane replacement still preserves the old view, so a
  new build needs a new slot. Lowering limits below current usage discards
  nothing and blocks growth until usage falls below the limit.
- Clear Window cancels pending builds even on an empty/non-MPR pane before
  detaching its current view (if any); pending-only clear creates no view.
  All transfer paths cancel destination builds, independent of `is_mpr`.
- Route series/study/Close All and pane teardown through controller cleanup
  before raw subwindow state resets. Clear MPR mouse/tool overrides, purge
  orphan navigator specs and purge `("__mpr__", pane)` geometry-cache entries
  whenever pane view assignments change, as well as on closure, so
  reopening the same source cannot resurrect a stale tile or restriction.
- Invalidate pane/source generations on close, reassignment and cancellation;
  callback closures capture worker identity and pane/source generations and
  compare them before popping worker entries, releasing reservations or
  activating results. Activation never clears detached views.
  Cancellation must retain worker ownership until actual termination; a
  two-second wait is not proof that a native worker has stopped.
- Estimate marginal MPR memory: per-session SimpleITK volume buffers, result
  slices, pending build allocations and thumbnail buffers, deduplicated for
  views sharing the same session/backing storage. Independent same-series
  builds currently construct separate volumes; do not assume shared buffers.
  Already loaded dataset PixelData is not additional MPR memory. Surface the
  estimate during admission without claiming an exact process-RAM measurement.
  Avoid full pixel copies for thumbnails and
  transaction snapshots. Allocation errors roll back state and reservations.

### 2.4 Implementation phases

- [ ] **Phase 0 — Contracts:** characterize global C-to-A/B scrolling exactly
  once, A-to-B/C scrolling, and separate-global-group membership; inventory
  every slice-change/cine/export/clear/layout consumer and characterize behavior.
- [ ] **Phase 1 — Registry:** session/view types, pane adapters, public metadata,
  display-state snapshot/restore, configurable limits and reservation lifecycle.
  Define lifecycle signal pane/view contracts (`mpr_activated`, `mpr_cleared`,
  `mpr_detached`) and update their wiring/tests with the registry adapters.
- [ ] **Phase 2 — Lifecycle:** transactional move/attach/build replacement,
  multiple detach, selective discard, source closure, worker generation guards.
- [ ] **Phase 3 — Navigator/DnD:** stable view routing, exact-ID operations,
  deterministic ordering, labels/link indicators, rebuild/width handling.
  Use a versioned structured drag payload with view ID and operation; validate
  malformed/stale/foreign IDs. Legacy pane-index payload support, if retained,
  must resolve at dispatch and never guess a detached view. Update navigator
  click/clear signals, `mpr_assign_requested`, widget MIME and app dispatch
  together; batch tile changes to rebuild once per committed transaction.
- [ ] **Phase 4 — Duplicate/link:** target chooser, shared-result duplication,
  session-local slice propagation, unlink/group cleanup, cine arbitration and
  coordination with global slice sync using group target deduplication. Avoid duplicate focused histogram work
  on peer redraws; retain required per-pane overlay/slider correctness.
- [ ] **Phase 5 — Regression and closeout:** focused controller/Qt integration
  tests, full suite, automated/manual agent smoke, architecture/harness checks,
  user-doc updates and link checker. Update version/changelog for product code;
  archive this P1 implementation plan at completion while retaining the P2
  supporting work and tracking any remaining manual smoke in TO_DO.

### 2.5 Acceptance tests

Existing single-slot characterization tests need deliberate migration:
`tests/test_main_mixin_mpr_and_tag_wiring.py`,
`tests/gui/test_mpr_controller_sonar_slice.py`,
`tests/core/test_mpr_navigator_thumbnail.py`, and
`tests/test_main_mixin_delegation.py`. Update signal-wiring tests during the
relevant implementation phase, alongside slice-sync/cine integration coverage.


- Two independent builds coexist, both detach, second attaches selectively;
  new builds leave earlier sessions available, including same-source sessions.
- Duplicate shares object/array identity and creates independent mutable view
  state. Discarding either view leaves the other usable; last-view removal
  releases session ownership. Detached/attached duplicates count correctly.
- Unlinked duplicate scrolls independently. Linked duplicate synchronizes
  bidirectionally via mouse, slider, keys and cine; W/L/combine remain separate.
  Unlink, detach/reattach, hidden-layout panes and occupied-pane replacement do
  not leave stale memberships or update an unrelated replacement view.
- Global sync on/off, overlapping group membership and cine driver changes
  cannot produce loops, competing updates or incorrect MPR slice indices.
- Cap-boundary builds/duplicates, pending reservations, cancellation, cache hits,
  allocation/install failures and lowering limits preserve all existing views.
- Validate stale/malformed drags, navigator rebuilds, source closure and late
  callbacks. Test rollback to both an ordinary image and an existing MPR.
- Verify export, cine depth, overlay/photometric/rescale correctness, pane
  expand/swap/layout changes and fit behavior for every attached duplicate.

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

- **MPR:** Two independent stacks and two detached views; selective attach; shared-result duplicates; linked/unlinked scrolling and cine; rollback and source cleanup; session/view admission messages.
- **Thumbnails:** Series with intentional black first slice shows recognizable anatomy in navigator; multiframe series still correct; cache invalidation does not regress performance on large studies.

---

## 5. Primary code touchpoints (reference)

| Area | Files |
|------|--------|
| MPR lifecycle, detach, attach | `src/gui/mpr_controller.py` |
| Floating thumbnail refresh | `src/core/mpr_navigator_thumbnail.py`, `src/main_app_subwindow_management.py` (`MPRNavigationMixin`) |
| Navigator MPR tiles | `src/gui/series_navigator.py`, `src/gui/mpr_thumbnail_widget.py` |
| Drop targets | `src/gui/sub_window_container.py` |
| Series thumbnail generation | `src/gui/series_navigator.py` (`update_series_list`, `_generate_thumbnail`, `regenerate_series_thumbnail`) |

---

*Document version: 2026-10-09 — planning only; no product code changes.*
