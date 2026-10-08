# 3D Window and Histogram Keep-in-Front Plan

**Status:** Active. Phase 0 is done on macOS, and Option B is chosen.
**Last updated:** 2026-10-07
**TO_DO refs:** Next up item 5 ("3D window: minimize, keep in front,
show/hide"); the two 3D viewer sub-items "3D viewer minimize button" and
"3D viewer visibility and pinning"; the manual smoke check "Histogram stacking
and minimization".
**Branch:** `feature/3d-window-and-histogram-keep-in-front`, based on `main`
after PR #182 merged.

## Goal

Make the histogram and 3D windows behave like tool windows of the viewer:

1. Each stays in front of the main window while the app is in use, whichever
   part of the main window you click.
2. Each can be minimized, and stays minimized until you restore it.
3. Neither stays above other applications.
4. The 3D window can be hidden and shown from the View menu without
   rebuilding its volume.

## Current state (verified 2026-10-07)

### Histogram

- `HistogramDialog` (`gui/dialogs/histogram_dialog.py:117`) is parented to the
  main window. It sets `Dialog | WindowMinimizeButtonHint | ...` flags and no
  stay-on-top flag.
- It installs an event filter on its parent. When the main window receives
  `WindowActivate`, the filter raises the histogram dialog
  (`histogram_dialog.py:164`).
- **Native bug (macOS, reported by the user 2026-10-07):** the histogram stays
  in front when you click the image viewer. It falls behind the main window
  when you click the left metadata pane or the right statistics pane.
- The raise and the event filter have automated tests
  (`tests/gui/test_histogram_dialog.py`). Those tests send synthetic events,
  so they cannot see window-manager ordering.

### 3D window

- `VolumeRenderDialog` is **parentless** on purpose
  (`volume_render_dialog.py:173`). The legacy VTK interactor needs a true
  top-level host. The default offscreen surface does not, but the legacy
  escape hatch still exists.
- It sets no explicit window flags, so whether it shows a minimize button
  depends on the platform's defaults. It has no keep-in-front behavior. It is
  `WA_DeleteOnClose`.
- `VolumeRenderFacade.launch_3d_view` focuses an existing dialog for the same
  series only when `isVisible()` is true. A hidden dialog is dropped and the
  volume is **rebuilt**. A minimized dialog still reports `isVisible()` as
  true, so it takes the raise path, and it is raised but not restored.
- `VolumeRenderFacade.target_dialog()` and `has_open_dialog()` consider only
  visible dialogs. A hidden 3D window would therefore be unreachable from the
  menu.
- PR #182 added `VolumeRenderFacade._last_active` tracking and File → Save 3D
  View…, which this plan reuses.

## Root-cause hypotheses for the histogram bug

Phase 0 must confirm one of these before any fix. Each comes with a probe.

- **H1 — the raise races the window manager.** `raise_()` runs while
  `WindowActivate` is being delivered. macOS then finishes bringing the
  clicked window forward and covers the histogram. Clicking the image viewer
  may trigger later work, such as a slice refresh that repaints or raises,
  which happens to restore the order. Probe: log event order and window
  stacking with `DEBUG_*` tracing, and try a deferred raise
  (`QTimer.singleShot(0, ...)`).
- **H2 — some clicks never deliver `WindowActivate` to the main window.**
  This is unlikely: the side panes are children of the main window's
  `QSplitter` (`main_window.py:427`), not dock widgets or separate native
  windows. A native child widget (`WA_NativeWindow`) inside a pane could
  still change which `QWindow` receives activation, and the image viewer may
  host one too. Probe: log `QGuiApplication.focusWindowChanged`,
  `QGuiApplication.focusWindow()`, and `QApplication.activeWindow()` for
  clicks in all three regions (viewer, metadata pane, statistics pane).
- **H3 — the image viewer path raises the histogram on its own.** For
  example, a focus or slice change might call a refresh that shows or raises
  the dialog. That would make the viewer case work by accident. Probe: trace
  every `raise_`, `show`, and `activateWindow` on the dialog.

## Phase 0 — Diagnose on native macOS and Windows

- [x] Add a `DEBUG_WINDOW_STACKING` flag in `utils/debug_flags.py` (default
  `False`). Gate tracing of the main window's activation events,
  `focusWindowChanged`, and the histogram's raise calls behind it.
- [x] Ask the user to reproduce on macOS with the flag on: click the viewer,
  the metadata pane, and the statistics pane. Record which hypothesis holds.
- [ ] Repeat the same check on Windows under Parallels.
- [x] Record the finding in this plan before Phase 1.

### Phase 0 findings (native macOS, 2026-10-07)

- **Run 1 (current code).** Within the app, every click on the main window,
  including both side panes, delivered `WindowActivate` and raised the
  histogram, and it stayed in front. The user's original report was narrower
  than first described. The histogram fell behind **only** after Mission
  Control ("show all windows") or an app switch, followed by a click on the
  viewer. The raise ran at `WindowActivate`, about 50–70 ms **before**
  `ApplicationActive`, and macOS then ordered the clicked window above it.
  This confirms H1 for the app-activation path. H2 and H3 are ruled out.
- **Run 2 (Option A, deferred raise).** Raising on `QTimer.singleShot(0)`
  after `WindowActivate`, and again after `ApplicationActive`, made it
  **worse**. Every deferred raise ran, 25–70 ms later, and the histogram still
  ended up behind more often. A timed re-raise loses the race with the macOS
  window manager, so **Option A is rejected**.
- **Run 3 (Option B, app-scoped stay-on-top).** `gui/window_stacking.py`
  (`AppScopedStayOnTop`) sets `WindowStaysOnTopHint` on the native `QWindow`
  when the app becomes active and clears it when the app goes inactive. The
  log shows each toggle within ~5 ms of the state change. The user confirmed
  that it passes:
  - The histogram stayed in front after Mission Control and after app
    switches.
  - It stayed in front when each main-window region was clicked.
  - It stayed minimized across app switches.
  - It never floated above another app, and there was no flicker.
- **Decision.** Use Option B for Phase 1. Setting the flag on
  `windowHandle()` rather than `QWidget.setWindowFlags` avoids the hide and
  re-create that the reviews warned about. Windows under Parallels is still
  unverified.

## Phase 1 — Shared keep-in-front helper

Build one Qt helper in `gui/window_stacking.py` that both windows use, and
pick the mechanism from Phase 0's finding:

- **Option A — deferred re-raise (H1, experimental).** Keep today's design,
  but raise on `QTimer.singleShot(0, ...)` after the main window's
  `WindowActivate`. A zero timer does not guarantee the raise runs after
  native stacking finishes, so treat this as an experiment. When the callback
  runs, recheck that the window is still visible, not minimized, and that the
  app is still active. Trigger only from the main-window anchor, not from
  every focus change in the app. Skip the raise while a modal dialog or popup
  is open (`QApplication.activeModalWidget()` / `activePopupWidget()`), so a
  tool window never covers a modal prompt. On Windows the foreground lock can
  turn a raise into a taskbar flash; check that in the spike.
- **Option B — application-scoped stay-on-top.** Set `WindowStaysOnTopHint`
  while the app is active, and clear it when
  `QGuiApplication.applicationStateChanged` reports the app inactive.
  `WindowStaysOnTopHint` is system-wide topmost, so goal 3 holds only if the
  flag is cleared promptly on every deactivation. That must be verified per
  platform rather than assumed. Changing the flag hides the widget and can
  re-create its native window, which can invalidate native handles used by
  the legacy VTK surface. The spike must therefore:
  - preserve visibility and the full window state (minimized, maximized,
    fullscreen) and geometry;
  - avoid activation loops and focus stealing;
  - measure flicker on every app switch, and z-order loss on Windows;
  - run against both the offscreen and the legacy 3D surfaces.
- **Option C — native child window (macOS only).** Attach the tool window as
  an `NSWindow` child of the main window, which macOS then keeps above its
  parent. This needs PyObjC or a ctypes bridge and a new dependency review
  (`security/security-tool-inventory.json`). A child window moves with its
  parent, and ordering it out detaches it. The design must therefore define
  who owns the bridge and when to detach and reattach (hide/show, minimize).
  Smoke checks must cover independent minimization, moving the parent, and
  Spaces and fullscreen. Use it only if A and B both fail.

Decision (from Phase 0): **Option B.** Option A was tried and rejected. Keep
C as a last resort if Windows testing fails.

- [ ] Promote `AppScopedStayOnTop` in `gui/window_stacking.py` from the spike
  to the real helper. It takes the tool window and an `enabled` callback, and
  it sets `WindowStaysOnTopHint` through `windowHandle()` only. Never use
  `QWidget.setWindowFlags`, which hides and re-creates the window.
- [ ] **Modal dialogs.** A stay-on-top tool window can cover the app's own
  modal dialogs (message boxes, file pickers, progress dialogs), which are not
  stay-on-top. Clear the flag while `QApplication.activeModalWidget()` is set,
  and restore it when the modal closes, by watching `focusWindowChanged`.
  The spike did not test this.
- [ ] Use it for the histogram in `gui/dialogs/histogram_dialog.py`. Keep the
  existing `WindowActivate` raise for the in-app case, and keep the minimize
  behavior. Remove the spike's debug flags
  (`DEBUG_WINDOW_STACKING_DEFERRED_RAISE`, `DEBUG_WINDOW_STACKING_APP_TOPMOST`)
  and the deferred-raise code. Keep `DEBUG_WINDOW_STACKING` tracing for future
  diagnosis.
- [ ] Tests: the flag follows the application state (active, then inactive,
  then active). It is skipped before the window has a native handle, and
  re-applied on show. It is off while a modal dialog is open. The `enabled`
  callback turns it off. Changing the flag never hides the window, and never
  clears the minimized state. A histogram and a 3D window can both be
  stay-on-top at once. Update the event-filter tests in
  `tests/gui/test_histogram_dialog.py`. Native ordering stays a manual smoke
  check.

## Phase 2 — 3D window behavior

- [ ] **Minimize.** Add `WindowMinimizeButtonHint` (with title, system-menu,
  and close hints) to the 3D dialog's flags. On Windows it must minimize to
  the taskbar. On macOS it must minimize to the Dock.
- [ ] **Keep in front.** Apply the Phase 1 helper with the main window as the
  anchor. The dialog stays parentless, so the helper must not rely on Qt
  parenting.
- [ ] **Setting.** Add a "Keep 3D Viewer in Front" checkable action under
  **View**. It defaults to **on** and is persisted through `display_config`
  using the existing getter/setter pattern. Turning it off removes the
  helper's effect immediately.
- [ ] **Show/hide.** Add a View-menu action, **Show 3D Viewer**, that toggles
  the visibility of the 3D window the user used most recently. Hiding keeps
  the dialog and its volume alive. Split the facade's targeting into
  "existing" (any live, not-deleted dialog, visible or hidden) and "visible"
  sets. The show/hide action and File → Save 3D View… enablement use the
  existing set, so hiding the last 3D window leaves it recoverable. Test
  target selection with several dialogs, some hidden.
- [ ] **Reopen without rebuilding.** In `launch_3d_view`, an existing dialog
  for the same series that is hidden or minimized must be reused, raised, and
  activated. It must not be dropped and rebuilt. Check `isMinimized()`
  explicitly, because a minimized window still reports `isVisible()`. Restore
  by clearing only the minimized bit of `windowState()`, and unhide with
  `show()`, so a maximized or fullscreen window keeps that state. Only a
  closed (deleted) dialog is rebuilt.
- [ ] **Line caps.** `volume_viewer_widget.py` and `main_window.py` are at
  their caps. Keep new logic in `gui/window_stacking.py`,
  `volume_render_facade.py`, `gui/dialogs/volume_render_dialog.py` (flags),
  `gui/dialogs/histogram_dialog.py`, and the menu builder.
- [ ] Tests:
  - flags include minimize;
  - the setting persists and toggling it updates live dialogs;
  - show/hide keeps the same dialog object and never starts a new build;
  - reopen after hide or minimize reuses the dialog and keeps a maximized or
    fullscreen state;
  - the menu action's enablement follows open dialogs.

## Phase 3 — Docs, smoke, and closeout

- [ ] User docs: the 3D guide covers minimize, keep in front, and View → Show
  3D Viewer. The histogram section notes the same in-front behavior.
- [ ] Replace the manual smoke item "Histogram stacking and minimization"
  with one combined check covering the histogram and the 3D window on native
  macOS and Windows: click every region of the main window, minimize and
  restore, minimize and restore the main window, switch to another app and
  back, open a modal dialog (for example File → Open) while a tool window is up and
  check the modal stays on top, and toggle the
  setting.
- [ ] `CHANGELOG.md`: a **Fixed** entry for the histogram falling behind the
  side panes (patch), and an **Added** entry for the 3D window controls
  (minor). Follow the repo's current convention for unreleased changes: add
  the SemVer note, and bump `src/version.py` only if a release is being cut
  (`dev-docs/RELEASING.md`).
- [ ] Verify: `python -m pytest tests/ -v`, `python scripts/check_user_docs_links.py`,
  `python scripts/check_repo_harness.py`,
  `python scripts/check_architecture_boundaries.py`, and
  `python scripts/agent_smoke_harness.py`.
- [ ] Remove Next up item 5 and the two 3D sub-items from `TO_DO.md`, and
  archive this plan.

## Out of scope

- Making other dialogs (tag viewer, About This File, QA dialogs) keep in
  front. Revisit if the shared helper proves reliable.
- Re-parenting the 3D dialog to the main window. Retire the legacy VTK
  surface first, under its own TO_DO item.

## Risks

- **Native behavior differs from tests.** Window ordering cannot be asserted
  in CI. Phase 0 tracing and the combined manual smoke check are the real
  verification.
- **Option B flicker and focus stealing.** Re-creating the native window when
  the flag changes can flash it or steal focus. The spike must check both
  before Option B is chosen.
- **Regressions in today's working cases.** The histogram must still stay up
  when you click the image viewer, when the main window is minimized and
  restored, and when the app regains focus from another application.
- **PHI.** The debug tracing must log only window class names and event
  types. It must never log window titles, because 3D titles include the
  series description.
