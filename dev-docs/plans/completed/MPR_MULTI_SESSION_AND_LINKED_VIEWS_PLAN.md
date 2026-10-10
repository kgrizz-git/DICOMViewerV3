# Plan (completed): MPR multiple sessions, detached views, duplicates and linked scrolling

**Created:** 2026-10-08
**Completed:** 2026-10-09 (implementation)
**Status:** **Implementation and independent review complete; real-display smoke pending.** All six phases
shipped on the `feature/multiple-mpr-sessions` branch with automated tests and
static gates. **Manual smoke on a real display remains pending** and is tracked in [`TO_DO.md` — Manual Smoke Checks](../../TO_DO.md#manual-smoke-checks).
**Tracks:** [`CHANGELOG.md`](../../../CHANGELOG.md) (Unreleased, MPR entries) and
[`MAINTENANCE_LOG.md`](../../MAINTENANCE_LOG.md) (2026-10-09).
**Split:** this file was the combined "MPR multi-window + navigator thumbnail
fallback" plan. The unfinished navigator-thumbnail work (P2) now lives on its own
in [`NAVIGATOR_THUMBNAIL_FALLBACK_PLAN.md`](../supporting/NAVIGATOR_THUMBNAIL_FALLBACK_PLAN.md).

User-facing behavior: [`user-docs/USER_GUIDE_MPR.md`](../../../user-docs/USER_GUIDE_MPR.md).

## As built

The design below was followed, with these concrete outcomes (and the places the
shipped form differs from the plan text, which is kept as the historical record):

- **Ownership.** `MprSessionRegistry` (`src/core/mpr_session_registry.py`, pure core)
  owns every `MprResult` (sessions), stable view IDs, the one-to-one pane map, link
  groups and admission reservations. `MprController` owns one live registry; a
  pane's `subwindow_data` is the live display adapter of an attached view and is
  flushed into the view before every transfer, detach, read or thumbnail. The
  transfer "payload" is an adapter built on demand, never stored.
- **Admission.** Defaults **8 sessions / 16 views**, configurable in
  **Edit → Settings… → MPR Limits** (atomic pair, `view >= session >= 1`). A
  reservation is taken before volume construction, covers cache hits and direct
  activation, and is released exactly once on cancel, error, closure, close-all or
  activation failure. Moves, detach and reattach consume no admission. Lowering
  limits evicts nothing. A concise "sessions / views / approximate MiB" line is
  shown in refusals and status messages; the estimate (`core/mpr_memory_estimate.py`)
  is **not** a RAM budget.
- **Lifecycle.** Transactional move/attach/duplicate/build replacement with
  snapshot rollback (a render that fails to produce an image counts as failure);
  displaced MPRs are preserved as detached views; worker/source fencing with
  native-thread lifetime retention; source/study close, Close All and a full-replace
  load release dependent sessions and views.
- **Navigator and drag.** Tiles are keyed by **stable view ID** (pane number is a
  separate field), ordered by creation, labelled without patient data
  (`S2`, `S2.1`, `S2.1L`), and reconciled once per controller transaction. The
  negative-ID adapter proposed in the plan was **replaced** by a versioned drag
  payload (`application/x-dv3-mpr-view`: view ID + operation + per-controller
  origin token) that carries no pane index; foreign, stale and malformed drops are
  no-ops. The legacy bare-integer MIME is no longer produced or accepted.
- **Duplicate and link.** **Duplicate into Window…**, **Duplicate Linked into
  Window…** and **Unlink View** on the tile context menu. A duplicate shares the
  session's result (no array copy) and snapshots the source view's state. Linking
  is session-local; one canonical setter (`gui/mpr_view_links.py`) moves a whole
  link group once for wheel, keys, slider, cine and incoming global sync. Redraws
  never propagate. Explicit links work with Slice Sync off; incoming sync moves a
  linked group once and does not cascade into other sync groups. Detached members
  follow the group silently (debounced tile refresh) and adopt the canonical slice
  when reattached.
- **Not changed (by decision).** Detached views are in-memory only (not saved
  across restarts). No new keyboard shortcuts. No hard RAM budget.

## Verification record

- Automated: focused MPR, navigator, signal-wiring, settings, loader and privacy
  suites per chunk; fault-injection checks on the new guards; ruff, basedpyright
  (errors), architecture boundaries, repo harness, line/complexity and privacy
  gates.
- Full suite at `01acdda` (`python -m pytest tests/ -v`): **8126 passed, 15 skipped,
  14 subtests passed, 34 failures — all worker crashes in four native VTK test files**
  (`test_volume_interactor_bridge.py`, `test_volume_render_surface.py`,
  `test_volume_shortcuts.py`, `test_volume_surface_factory.py`) under the sandbox.
  The required narrow native-graphics retry of those four files (`-n0 --no-cov`)
  passed **all 77**. No actual test failures remain. The original sandbox run is
  reported as-is, not replaced by the retry.
- Independent implementation review passed 999 focused tests and found no reproducible
  correctness bug. The final slider/fencing correction (`6e2438c`) passed 104 focused
  tests in the primary review and all 19 new tests in the independent review.
- Automated Qt smoke and 77 documentation/harness tests passed. Real-display smoke
  remains pending (TO_DO): local Computer Use could not access its trusted service.
- Non-blocking review notes: failed moves do not restore focus or show a warning;
  Settings can persist earlier changes before a later privacy-panel failure, following
  its existing save ordering. Neither was changed in this implementation.

---

## Pre-implementation review (2026-10-08, historical)

This review records the starting point and the agreed design. Statements about the single detached slot, negative navigator IDs or behavior that "still exists" describe the code **before** this work.

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

A review suggested 32 views to allow four duplicates per each of eight sessions;
16 was retained because it is sufficient for the intended use and the cap is configurable.
The proposed sync rule below now treats linked views as one scrolling unit,
including incoming global sync, removing the earlier asymmetric exclusion rule.

### Independent review

Two independent reviews checked the plan against the code and supported the design
after refinements; the three scratch bug reproductions were re-run independently.
The finished implementation and final correction received independent review with no
reproducible correctness bug. Approval remains conditional on real-display smoke.

### Required verification additions

Controller tests must cover two same-source sessions, selective attach/clear,
new-build preservation, repeated detach/reattach, occupied-target preservation,
invalid/stale IDs, installation exceptions with rollback, source closure and
late worker completion. GUI tests must exercise a second negative drag ID,
individual context-menu deletion, tile order/width and navigator rebuild.
Manual smoke must include independent attached MPRs, both detached tiles,
display-state restoration, occupied-target drop and close-source cleanup.

---

## Historical baseline (before this work)

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

- [x] **Phase 0 — Contracts:** characterize global C-to-A/B scrolling exactly
  once, A-to-B/C scrolling, and separate-global-group membership; inventory
  every slice-change/cine/export/clear/layout consumer and characterize behavior.
- [x] **Phase 1 — Registry:** session/view types, pane adapters, public metadata,
  display-state snapshot/restore, configurable limits and reservation lifecycle.
  Define lifecycle signal pane/view contracts (`mpr_activated`, `mpr_cleared`,
  `mpr_detached`) and update their wiring/tests with the registry adapters.
- [x] **Phase 2 — Lifecycle:** transactional move/attach/build replacement,
  multiple detach, selective discard, source closure, worker generation guards.
- [x] **Phase 3 — Navigator/DnD:** stable view routing, exact-ID operations,
  deterministic ordering, labels/link indicators, rebuild/width handling.
  Use a versioned structured drag payload with view ID and operation; validate
  malformed/stale/foreign IDs. Legacy pane-index payload support, if retained,
  must resolve at dispatch and never guess a detached view. Update navigator
  click/clear signals, `mpr_assign_requested`, widget MIME and app dispatch
  together; batch tile changes to rebuild once per committed transaction.
- [x] **Phase 4 — Duplicate/link:** target chooser, shared-result duplication,
  session-local slice propagation, unlink/group cleanup, cine arbitration and
  coordination with global slice sync using group target deduplication. Avoid duplicate focused histogram work
  on peer redraws; retain required per-pane overlay/slider correctness.
- [x] **Phase 5 — Regression and closeout:** focused controller/Qt integration
  tests, full suite, automated/manual agent smoke, architecture/harness checks,
  user-doc updates and link checker. Update version/changelog for product code;
  archive this P1 implementation plan at completion while retaining the P2
  supporting work and tracking any remaining manual smoke in TO_DO.
  *Status:* the full automated suite and static gates pass (see
  [Verification record](#verification-record)); manual smoke and the final
  independent review are **pending** and tracked in
  [`TO_DO.md` — Manual Smoke Checks](../../TO_DO.md#manual-smoke-checks).

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

*Archived 2026-10-09. The shipped behavior is documented in the user guide; this file is the design and decision record.*
