# Plan: 3D Volume Render Dialog Lifecycle on App Close

Last updated: 2026-05-31

## Goal and success criteria

Closing or quitting the main application must close every open 3D volume render dialog and release VTK resources so no orphaned 3D window remains on the desktop or keeps the process alive.

Success criteria:

- Main-window close closes all open 3D render dialogs.
- Application quit via `QApplication.aboutToQuit` closes all open 3D render dialogs.
- Active background volume builds are cancelled or joined without hanging the main close path.
- VTK cleanup remains idempotent when close is requested twice.
- A regression test covers the facade close path and the app/main-window close hook that calls it.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` Bugs / Correctness, "3D viewer lifecycle".
- Existing 3D launch/lifecycle owner: `src/gui/volume_render_facade.py`.
- Existing dialog cleanup owner: `src/gui/dialogs/volume_render_dialog.py`.
- Existing app-close hooks:
  - `src/gui/main_window.py` calls `facade.close_all_dialogs()` in `MainWindow.closeEvent()`.
  - `src/core/session_reset_controller.py` calls `app._volume_render_facade.close_all_dialogs()` from app-quit finalization.
  - `src/core/app_signal_wiring.py` connects `QApplication.aboutToQuit` to `app._on_app_about_to_quit`.
- Because current code already contains close hooks, this plan starts with verification and hardening rather than assuming no lifecycle support exists.

## Task graph and gates

### Ordering

- T1 -> T2.
- T3 and T4 can run in parallel after T2 if they touch separate tests.
- T5 follows any failing verification.

### Verification gates

- Gate 1: Tests prove `VolumeRenderFacade.close_all_dialogs()` closes visible dialogs, clears `_alive`, and clears `_open_dialogs`.
- Gate 2: Tests or manual smoke prove main-window close and app quit both invoke the facade cleanup.
- Gate 3: Manual smoke with a real VTK-backed dialog confirms no orphaned window remains.

### File / area ownership

- `src/gui/volume_render_facade.py` -> coder.
- `src/gui/dialogs/volume_render_dialog.py` -> coder if worker/VTK cleanup needs hardening.
- `src/gui/main_window.py`, `src/core/session_reset_controller.py`, `src/core/app_signal_wiring.py` -> coder only if hooks are missing or not ordered correctly.
- `tests/` focused lifecycle tests -> tester/coder.

## Phases

### Phase 1 - Audit current lifecycle behavior

- [ ] (T1) Confirm current close paths from toolbar/menu launch through `VolumeRenderFacade`, `MainWindow.closeEvent()`, and `session_reset_finalize_for_application_quit()` (owner: coder, parallel-safe: no, stream: none, after: none).
- [x] (T2) Add focused tests with fake dialogs to verify `close_all_dialogs()` closes every alive dialog, tolerates already-deleted dialogs, and clears duplicate-dialog tracking (owner: tester, parallel-safe: yes, stream: A, after: T1).
- [ ] (T3) Add or update a main-window/app-quit hook test that asserts the facade cleanup method is called during close/quit finalization (owner: tester, parallel-safe: yes, stream: B, after: T1).

### Phase 2 - Harden only if audit exposes gaps

- [x] (T4) If `close_all_dialogs()` fails to close or clear any tracked dialog, make it idempotent and safe against Qt object deletion races (owner: coder, parallel-safe: no, stream: none, after: T2).
- [ ] (T5) If an active `_VolumeBuilderWorker` can survive shutdown, make `VolumeRenderDialog.closeEvent()` cancel, quit, and wait safely without blocking indefinitely (owner: coder, parallel-safe: no, stream: none, after: T2).
- [ ] (T6) If app quit bypasses `MainWindow.closeEvent()` in any path, keep the `aboutToQuit` cleanup as the canonical fallback and ensure it runs before long-lived object teardown (owner: coder, parallel-safe: no, stream: none, after: T3).

### Phase 3 - Manual VTK smoke

- [ ] (T7) Launch a 3D volume render window from a valid multi-slice series, close the main app, and confirm the 3D window closes immediately (owner: tester, parallel-safe: no, stream: none, after: T4).
- [ ] (T8) Repeat while the 3D dialog is still building the volume; confirm no hang and no orphaned native VTK window (owner: tester, parallel-safe: no, stream: none, after: T5).
- [ ] (T9) Repeat via File/Exit or application quit path if available, not only the title-bar close button (owner: tester, parallel-safe: no, stream: none, after: T6).

## Risks and mitigations

- Risk: Parentless dialogs are intentional because the VTK interactor needs a top-level host on Windows. Mitigation: keep dialogs parentless but tracked by strong references in `VolumeRenderFacade`.
- Risk: Waiting on a worker during shutdown can hang the UI. Mitigation: use bounded waits and tolerate cancellation when the process is exiting.
- Risk: Double cleanup can hit deleted Qt objects. Mitigation: make cleanup idempotent and catch `RuntimeError` from deleted wrappers, as the facade already starts to do.

## Modularity and file-size guardrails

Keep lifecycle ownership in `VolumeRenderFacade` and `VolumeRenderDialog`. Avoid moving VTK cleanup into `MainWindow` beyond calling the facade.

## Testing strategy

- Run focused tests for volume render lifecycle once added.
- Run existing volume render eligibility tests: `.\.venv\Scripts\python.exe -m pytest tests/test_volume_render_eligibility.py -q`.
- Manual smoke requires a local valid multi-slice dataset and VTK installed in the project venv.

## Questions for user

None blocking. If manual smoke discovers platform-specific behavior, record whether it was Windows native, Parallels, or macOS packaging.

## Completion notes

2026-05-31: Added `tests/test_volume_render_facade_lifecycle.py` for tracked facade dialogs and untracked top-level `VolumeRenderDialog` instances. The second test failed before the fix because `close_all_dialogs()` only closed `_alive` dialogs. Hardened `VolumeRenderFacade.close_all_dialogs()` to also sweep live Qt top-level `VolumeRenderDialog` widgets, hide any dialog that refuses close, process close events, and clear tracking dictionaries. Focused test now passes. Manual VTK smoke is still needed before marking the `TO_DO.md` item complete.
