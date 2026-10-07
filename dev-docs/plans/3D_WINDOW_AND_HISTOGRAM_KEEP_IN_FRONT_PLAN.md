# 3D Window and Histogram Keep-in-Front Plan

**Status:** Active (not started)
**Last updated:** 2026-10-07
**TO_DO refs:** Next up item 5 ("3D window: minimize, keep in front,
show/hide"); the two 3D viewer sub-items "3D viewer minimize button" and
"3D viewer visibility and pinning"; the manual smoke check "Histogram stacking
and minimization".
**Branch:** `feature/3d-window-and-histogram-keep-in-front`. It starts from
PR #182's branch, because that PR adds the Next up item. Rebase onto `main`
after #182 merges.

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
- It installs an event filter on its parent and calls `raise_()` on the main
  window's `WindowActivate` (`histogram_dialog.py:164`).
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
- It sets no window flags, so it has no minimize button on some platforms
  and no keep-in-front behavior. It is `WA_DeleteOnClose`.
- `VolumeRenderFacade.launch_3d_view` focuses an existing dialog for the same
  series only when `isVisible()` is true. A hidden dialog is dropped and the
  volume is **rebuilt**. A minimized dialog is raised but not restored.
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
  still change which `QWindow` receives activation. Probe: log `QGuiApplication.focusWindowChanged` and
  `QApplication.activeWindow()` for clicks in each region.
- **H3 — the image viewer path raises the histogram on its own.** For
  example, a focus or slice change might call a refresh that shows or raises
  the dialog. That would make the viewer case work by accident. Probe: trace
  every `raise_`, `show`, and `activateWindow` on the dialog.

## Phase 0 — Diagnose on native macOS and Windows

- [ ] Add a `DEBUG_WINDOW_STACKING` flag in `utils/debug_flags.py` (default
  `False`). Gate tracing of the main window's activation events,
  `focusWindowChanged`, and the histogram's raise calls behind it.
- [ ] Ask the user to reproduce on macOS with the flag on: click the viewer,
  the metadata pane, and the statistics pane. Record which hypothesis holds.
- [ ] Repeat the same check on Windows under Parallels.
- [ ] Record the finding in this plan before Phase 1.

## Phase 1 — Shared keep-in-front helper

Build one Qt helper in `gui/window_stacking.py` that both windows use, and
pick the mechanism from Phase 0's finding:

- **Option A — deferred re-raise (H1).** Keep today's design, but raise on
  `QTimer.singleShot(0, ...)` after `WindowActivate`. Also raise on
  `focusWindowChanged` when the new focus window belongs to this app and is
  not the tool window itself. This is cheap, but it may still flicker.
- **Option B — application-scoped stay-on-top.** Set `WindowStaysOnTopHint`
  while the app is active, and clear it when
  `QGuiApplication.applicationStateChanged` reports the app inactive. This
  meets goals 1 and 3 on every platform. Changing that flag on a visible
  window re-creates the native window, so the helper must restore geometry
  and the minimized state, and must not steal focus. Spike it before
  committing to it.
- **Option C — native child window (macOS only).** Attach the tool window as
  an `NSWindow` child of the main window, which macOS then keeps above its
  parent. This needs PyObjC or a ctypes bridge and a new dependency review
  (`security/security-tool-inventory.json`). Use it only if A and B both
  fail.

Recommendation: try A first, because it is the smallest change and H1 is the
most likely cause. Move to B if native testing still shows the window falling
behind. Keep C as a last resort.

- [ ] Implement the helper with an `install_keep_in_front(tool_window,
  main_window, *, enabled: Callable[[], bool])` entry point. It returns an
  object that can be removed when the window closes.
- [ ] Use it for the histogram in place of the current event filter. Keep the
  minimize behavior. A minimized window is never restored by a re-raise.
- [ ] Tests: unit-test the helper's decision logic, such as when to raise and
  when to skip because the window is minimized, hidden, or the app is
  inactive. Use a fake clock or `qtbot.wait`-free event posting. Native
  ordering stays a manual smoke check.

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
  the visibility of the 3D window the user used most recently (reuse
  `VolumeRenderFacade.target_dialog`). It is disabled when no 3D window
  exists. Hiding keeps the dialog and its volume alive.
- [ ] **Reopen without rebuilding.** In `launch_3d_view`, an existing dialog
  for the same series that is hidden or minimized must be restored with
  `showNormal()`, raised, and activated. It must not be dropped and rebuilt.
  Only a closed (deleted) dialog is rebuilt.
- [ ] **Line caps.** `volume_viewer_widget.py` and `main_window.py` are at
  their caps. Keep new logic in `gui/window_stacking.py`,
  `volume_render_facade.py`, and the menu builder.
- [ ] Tests:
  - flags include minimize;
  - the setting persists and toggling it updates live dialogs;
  - show/hide keeps the same dialog object and never starts a new build;
  - reopen after hide or minimize reuses the dialog;
  - the menu action's enablement follows open dialogs.

## Phase 3 — Docs, smoke, and closeout

- [ ] User docs: the 3D guide covers minimize, keep in front, and View → Show
  3D Viewer. The histogram section notes the same in-front behavior.
- [ ] Replace the manual smoke item "Histogram stacking and minimization"
  with one combined check covering the histogram and the 3D window on native
  macOS and Windows: click every region of the main window, minimize and
  restore, switch to another app, and toggle the setting.
- [ ] `CHANGELOG.md`: a **Fixed** entry for the histogram falling behind the
  side panes (patch), and an **Added** entry for the 3D window controls
  (minor).
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
- **PHI.** The debug tracing must log only window class names and event
  types. It must never log window titles, because 3D titles include the
  series description.
