# Maintenance Log

**Last updated:** 2026-08-29

This file records development and repository-maintenance history that is useful to contributors and agents but is not necessarily user-facing release history.

## 2026-08-29

- **Pylinac ACR full-metrics export + MRI batch — Phases 1–5 complete (docs/strings):** Closed the documentation and in-app-string slice of [PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md](plans/supporting/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md). **P5-D1** user-docs: `USER_GUIDE_QA_PYLINAC.md` now has a dedicated `### ACR MRI batch` section (was a paragraph under `### ACR CT`); single-run CSV/XLSX documented as full flatten (Summary vs Detail); **Embed module images in XLSX** option documented (default on, PDF parity, uncheck skips Images sheet); JSON still carries full `raw_pylinac` (no `metrics_flat`); compare mode unchanged. Hub `USER_GUIDE.md` bullet updated; `CONFIGURATION.md` ACR/pylinac row expanded with the embed-toggle description. **P5-D2** dev-docs: `PYLINAC_INTEGRATION_OVERVIEW.md` ACR CT CNR/batch/XLSX row updated to document canonical flatten (`qa_result_flatten.py`, metrics-overlay-wins, path denylist), wide batch CSV vs single-run metric/value, XLSX Summary/Detail/Images + embed toggle, `ACRMBatchResult` + `QAMRIBatchWorker` (not compare-mode `MRIBatchResult`), MRI batch menu + export; stale "batch for other modalities remain future work" corrected to "shipped for ACR CT and ACR MRI"; Phase 6 SNR kept **not shipped**. Plan appendix P5-D1/D2/D3/D4 marked `[x]` with honest landed notes; plan status header updated to "Phases 1–5 shipped; Phase 6 (viewer-computed MRI SNR) still open". **P5-D3** in-app strings: audited against the plan's **Documentation updates** table — all strings already landed from P3/P4; **zero Python changed**. **P5-D4** CHANGELOG: existing Unreleased **Added** (minor) + **Fixed** P2-X4 (patch) already cover the ship; no new entry needed. **P5-D5** partial: link checker OK; plan not moved to `completed/` while Phase 6 remains; `TO_DO.md` Next-up retargeted to MRI SNR. Phase 6 (MRI SNR) remains open in the plan.

## 2026-08-28

- **Privacy hardening plan disposition:** Marked G6 closed (**2026-07-13**
  snapshot root on `origin/main`; development from **2026-07-14** on this
  lineage). PRIV-V1–V3 satisfied by routine CI/hooks; demoted Phase 8 tail to
  P2 optional. Review is maintainer + agents only.
- **Backlog — Manual Smoke Checks section:** Added a dedicated [`TO_DO.md`](TO_DO.md)
  section for human verification after merged implementation work, with workflow
  guidance, a single **Next up** pointer, and a rule that slot 1 stays manual
  smokes while any remain open. Consolidated volume-render, post-load first-paint,
  and W/L preset smokes; removed duplicate 3D sub-bullets and closed the
  refactor-extraction smoke block (all confirmed 2026-06).
- **Pylinac ACR export slice plan:** Added
  [`PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md`](plans/supporting/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md)
  (full metrics CSV/XLSX, batch CT CSV, multi-series MRI batch); linked from
  `TO_DO.md` Next up.
- **pytest-xdist parallelization — closed:** Fifteen consecutive green CI runs on
  `main` (PRs #79–#92, 2026-08-23 through 2026-08-28) with `-n auto` and the
  80% coverage floor. Archived
  [`TEST_SUITE_PARALLELIZATION_PLAN.md`](plans/completed/TEST_SUITE_PARALLELIZATION_PLAN.md)
  and removed the long Maintenance follow-up from `TO_DO.md`. Optional future
  runtime work stays under [CI test runtime and coverage integrity](plans/CI_TEST_RUNTIME_AND_COVERAGE_INTEGRITY_PLAN.md).

## 2026-08-26

- **3D volume fallback and memory hardening:** Replaced the blank-frame
  boolean with a transfer-function/occupancy-aware three-way outcome, keeping
  legitimately blank CT Bone views on GPU while retaining real CPU fallback.
  Expected-blank probes are transfer-function-dirty rather than reading back
  the framebuffer every render. Eliminated calibration and VTK deep copies,
  retained the shallow VTK NumPy backing safely, and added a pre-allocation
  uniform downsampling guard based on available RAM (20%, capped at 2.5 GiB).
  It preserves patient-space geometry and visibly reports its factor. Synthetic
  512×512×800 measurement with smoothing: 1438 MiB peak RSS (baseline
  3274–3276 MiB). The focused 68-test suite and the serial non-native pytest
  scope both passed (the latter exited 0). A basic native-macOS 3D-view smoke
  was user-confirmed; Windows/Parallels GPU-fallback checks remain in
  [`TO_DO.md`](TO_DO.md) → **Manual Smoke Checks** (plan archived to
  [`completed/VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md`](plans/completed/VOLUME_RENDER_FALLBACK_AND_MEMORY_HARDENING_PLAN.md)).

## 2026-08-25

- **README feature gallery + approved-media update:** Expanded root `README.md`
  Highlights and added a constrained-width gallery (ROI/MPR hero, 3D,
  annotation customization, histogram, tag editor, tag export, automated QA
  menu). Resized PNGs under `resources/readme-screenshots/` and refreshed their
  SHA-256 pins in `security/approved-media-sha256.json`. Fusion and slab/MIP
  screenshot follow-up tracked in `TO_DO.md`.

## 2026-08-24

- **Approved-media manifest hardening:** The artifact gate now validates the
  complete approved-media schema before exempting it from generic content
  scanning: object root, allowed top-level fields, exact purpose, file and
  image-tree paths, SHA-256 digests, and media-entry keys. Malformed manifests
  fail closed without crashing; regression tests cover PHI-like content in
  unknown fields and nested image-tree entries.

- **First-run visual defaults and README showcase:** New installations now use
  larger overlay/annotation text, medium overlay weight, violet accent,
  visible red scale markers and direction labels, and compact icon-plus-label
  toolbar buttons. Stored preferences continue to win without a config-file
  rewrite. The main splitter has an explicit 8 px Qt hit target while keeping
  a 1 px rest-state hairline; the labelled toolbar has a 1348 px uncompressed
  Qt size hint and remains one row at the 1280 px target, protected by a Qt
  regression test. The README now shows two human-approved synthetic-demo
  workflows; their final PNG hashes are pinned in the approved-media manifest.
  The artifact gate now avoids generic text scanning of arbitrary manifest
  hashes while retaining its structured path-and-digest validation, fixing a
  pre-existing false positive on a previously approved media filename.

- **pytest CI hang fixed:** Two manually cancelled PR #82 `pytest` attempts reached 98–99% and then made no progress for 32–40 minutes. Debug logs placed `test_main_privacy_lifecycle.py::test_main_installs_privacy_boundary_before_application_construction` on the same xdist worker 85 seconds before `test_main_window_fullscreen.py::test_fullscreen_chrome_hide_and_restore_splitter` stalled. The former deliberately calls `main()`, which installs the process-global `sys.excepthook`, but did not restore it. A later Qt timer exception during scoped-widget cleanup was consequently routed to `main.exception_hook`; its modal `QMessageBox.critical()` cannot be dismissed in an offscreen worker and nested its event loop indefinitely. The test now scopes and verifies restoration of `sys.excepthook`. The exact CI-style native macOS command (`QT_QPA_PLATFORM=offscreen`, `-n 4`, coverage XML, 80% floor) completed in 54.53s: 6365 passed, 15 skipped, 81.88% coverage. Await the replacement GitHub run before closing the active xdist follow-up.

## 2026-08-23

- **Modeless dialog lifetime:** The Structured Report browser is modeless and uncached, so without `WA_DeleteOnClose` the Qt parent kept every browser alive after the user closed it — one leaked per SR opened, for the life of the session. Fixed in `dialog_coordinator.open_structured_report_browser`, with a regression test that uses a real `QDialog` subclass (a mock would accept `setAttribute` and prove nothing).
- **Correction to the 2026-08-23 dialog-accumulation claim:** the same report also asserted that the ~13 **modal** `dialog.exec()` dialogs leak, citing "20 live `OverlaySettingsDialog` children, +24 MB after 20 opens". That measurement was wrong: the probe constructed and dropped dialogs without ever showing or closing them, which is not the application's path. Exercised through `DialogCoordinator` with a real `exec()` that is then dismissed, the census stays empty — modal dialogs do **not** accumulate. No change was made to those call sites.
- **Qt widget lifetime in tests:** Test suite leaked ~30 top-level widgets per `DICOMViewerApp()` and ~22 per direct `MainWindow(...)`, reaching 902 live windows / 633 MB across 8 modules. Root cause of the intermittent CI `worker 'gwN' crashed` flake. Added `tests/qt_widget_scope.py`; full suite `-n auto` dropped 25-37s to 15.6s.
- **Completed the direct-`MainWindow` cleanup sweep:** Added the existing scoped Qt cleanup fixture to the four remaining real-`MainWindow` test modules (`test_main_window_recent_files.py`, `test_main_window_overlay_options.py`, `test_main_window_toast.py`, and `gui/test_slider_menu_grouping.py`), covering all 25 direct constructions. `widget_scope()` now retains pre-scope widget wrappers so Python cannot reuse an old wrapper's identity for a new widget, and it also covers the parentless QWidget test doubles in `test_pylinac_nuclear_e2e.py` and `gui/test_main_window_layout_helper.py`. The combined 63-test set passed under the crash-prone `-n 2` configuration. A full `-n 2` run then stopped at a VTK native crash: `tests/gui/test_volume_interactor_bridge.py` segfaulted serially in isolation at `vtkGenericRenderWindowInteractor.Initialize()` before its first surface-level assertion. Focused reproduction resolved it as a sandbox limitation: the macOS VTK Cocoa window cannot create an OpenGL context there (no usable EGL/OSMesa fallback), including in standalone VTK without pytest or Qt. With native macOS graphics access, the bridge module passed three times each at `-n 0`, `-n 1`, and `-n 2`; the 58-test real-VTK GUI batch also passed at `-n 0` and `-n 2`. It is independent of the Qt-lifetime sweep and xdist; run real VTK rendering tests outside the sandbox or on a Linux EGL/OSMesa-capable runner.

## 2026-08-22

- **UI-triggered releases — Step 0 evidence (macOS slim flag saves 0 MB; D1 chosen).**
  Recorded for `dev-docs/plans/completed/UI_TRIGGERED_RELEASES_PLAN.md` Step 0. Same-commit
  local A/B on macOS (arm64): standard `PYINSTALLER_MACOS_SLIM` unset vs `=1`
  (`tmp/build_test.sh`, gitignored). `du -sk` measured **1,178,268 KB for both**
  `DICOMViewerV3_standard.app` and `DICOMViewerV3_slim.app` — byte-identical,
  **0 MB saved**. The PyInstaller analysis logs differ only by hook ordering.
  Environment: PyInstaller **6.22.2**, pyinstaller-hooks-contrib **2026.6**,
  PySide6 **6.11.2**, Python **3.12.10** (security floor `pyinstaller>=6.22.1`).
  Why zero: the app imports only QtCore/QtGui/QtWidgets/QtOpenGL + matplotlib
  qtagg; modern PyInstaller traces the import graph, so the
  `MACOS_PYSIDE6_MODULE_EXCLUDES` modules (WebEngine, 3D, Quick, Multimedia, …)
  were never collected in either build. The 200–500 MB figures in
  `completed/pyinstaller-bundle-size-macos-2026-04-09.md` and the baseline doc are
  conditional upper bounds *if* analysis would pull them in — falsified for this
  dependency graph. **Conditionality:** property of the *current* dependency
  graph; a future pylinac/PySide6 bump that imports an excluded module reverses
  it (post-D1 detection relies on a human reading `du` logs vs the baseline
  table — no CI tripwire). **Maintainer sign-off: D1 (full deletion)** chosen —
  remove flag, list, test, job, docs. `git tag` → **(none)**; `gh release list` →
  **(none)** (Assumption 1 verified; zero tags/releases exist). Baseline table in
  `PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md` filled with the same evidence numbers.

- **Dependency-license exceptions: SPDX / hooks-contrib scope correction.**
  Updated `accepted_exceptions` for `pyinstaller` to
  `GPL-2.0-or-later WITH Bootloader-exception` (upstream COPYING SPDX; replaces
  the non-standard `PyInstaller-Bootloader-CPE` label). Split
  `pyinstaller-hooks-contrib` rationale into GPL-2.0-or-later standard hooks
  (build-time) vs Apache-2.0 `_pyinstaller_hooks_contrib/rthooks` (may embed in
  frozen builds); removed the blanket “not bundled / not shipped” claim.
  Documented freeze-graph candidates for this app (`hook-pydicom`,
  `hook-imageio*`, `hook-cryptography`; likely contrib rthook
  `pyi_rth_cryptography_openssl` when cryptography is collected). Synced
  `DEPENDENCY_LICENSE_POLICY.md` table + guidance note. Validation (project
  `.venv`): JSON load ok; `python scripts/check_dependency_licenses.py` → OK
  (both packages still accepted).

## 2026-08-21

- **Dependency-license policy: accepted build-only PyInstaller exceptions.**
  The pre-commit license gate (`scripts/check_dependency_licenses.py`) flagged
  `pyinstaller` (GPLv2) and `pyinstaller-hooks-contrib` (GPLv2 + Apache) as
  `FORBIDDEN` because `accepted_exceptions` in
  `dev-docs/info/dependency_license_policy.json` was empty. These are
  **build-only** tools in `requirements-build.txt` (not `requirements.txt`)
  with security floor `pyinstaller>=6.22.1` (GHSA-9fxf-4qw3-ghmr; was
  `>=6.21.0`) and are never imported as runtime libraries.
  `pyinstaller-hooks-contrib` is additionally a hard transitive dependency of
  `pyinstaller`. PyInstaller's GPL carries a bootloader exception permitting
  proprietary/frozen builds for the embedded bootloader/loader. Added both to
  `accepted_exceptions` with `reason` + `review_by: 2026-12-31`, and synced the
  "Current accepted exceptions" table in `DEPENDENCY_LICENSE_POLICY.md`. This
  does not undermine the policy's intent (rejecting future strong-copyleft
  *runtime decoder* dependencies); the gate still fails on any new copyleft
  runtime dep. (SPDX label and hooks-contrib embed scope refined 2026-08-22.)
  Validation (project `.venv`, 2026-08-21):
  `python -c "import json; json.load(open('dev-docs/info/dependency_license_policy.json'))"`
  → ok; `python scripts/check_dependency_licenses.py` → OK (158 dists;
  `pyinstaller` 6.22.2 and `pyinstaller-hooks-contrib` 2026.6 accepted);
  `pip show pyinstaller` → Version: 6.22.2 (≥ 6.22.1 floor).

## 2026-08-16

- **W/L presets bit-depth awareness + MONOCHROME1 on-screen inversion:**
  Implemented the full plan at `plans/completed/WL_PRESETS_BIT_DEPTH_AND_MONOCHROME1_PLAN.md`.
  Core render layer (`render_grayscale_image`) now owns MONOCHROME1 inversion;
  export/cine no longer re-invert (single-inversion ownership). Export-render
  ownership moved from `export_rendering.process_image_by_photometric_interpretation`
  to `core.dicom_image_render.render_grayscale_image`. Built-in presets for
  CR/DX/MG/NM/RF/XA/US/ANY derive from the dataset's stored pixel range via a
  new tag-only helper (`core.dicom_pixel_range`). CR/DX HU presets gated behind
  real rescale. An inversion-specific migration key in `ViewStateManager` discards
  pre-upgrade MONOCHROME1 stored inversion state. Status bar shows `(MI)` marker.

## 2026-08-15

- **Test-discovered strict-xfail remediation:** Corrected two production defects
  characterized during coverage work. Recent-list multi-selection moves now
  preserve relative order when moving upward; derived projection exports now
  use DICOM CS-valid `ImageType` values (`MIP`, `AIP`, `MINIP`) while retaining
  descriptive metadata. Both tests are ordinary passing regressions. Full
  parallel coverage verification: 6,193 passed, 15 skipped, 81.52%, with
  `coverage.xml` produced. **Completed plan:** [Test-discovered strict-xfail
  remediation](plans/completed/TEST_DISCOVERED_XFAIL_REMEDIATION_PLAN.md).

## 2026-08-12

- **Parallel test execution (pytest-xdist) and the Qt worker abort:** Added
  `pytest-xdist>=3.8.0` to `requirements-dev.txt` and `-n auto` to the CI
  `pytest` job. Enabling it exposed a nondeterministic worker abort that only
  appeared under sharding.

  **Root cause:** `tests/core/test_subwindow_lifecycle_controller_slice.py`
  constructed a bare `QCoreApplication` when no instance existed, and
  `tests/conftest.py` guarded the session `qapp` fixture on *existence*
  (`instance() is None`) rather than *type*. A worker that received that test
  first ended up owned by a non-GUI application, so the next widget
  construction died with `QWidget: Cannot create a QWidget without
  QApplication` (SIGABRT inside `QWidgetPrivate::init`, not a segfault).
  Serial ordering hid the bug because a GUI test almost always ran first.

  **Fix:** `tests/conftest.py` now creates the `QApplication` in
  `pytest_configure` and holds it in a module-level reference; the `qapp`
  fixture checks `isinstance(app, QApplication)` and raises a diagnostic
  `RuntimeError` if a non-GUI application owns the process; the offending test
  depends on `qapp` instead of building its own. No other bare
  `QCoreApplication` construction remains in `tests/`, `src/`, or `scripts/`.

  **Measured:** serial 8m42s → `-n auto` 37.95s on an 18-core host and ~3m30s
  on CI's 4 cores (~2.5x). Coverage combining across workers verified intact
  (TOTAL 71.01%, above the 65% floor). Note the `ci.yml` comment claiming
  "~67%" is stale.

- **PHI live-repository test made opt-in:** `test_this_repository_is_clean` is
  redundant with the required `privacy-gates / No PHI artifacts tracked` job
  and the `pre-push` hook, which run the same `scripts/check_no_phi_artifacts.py`
  scan over the same tracked files. It now uses `skipif` on `PHI_LIVE_SCAN`
  rather than an unconditional `skip`, so it stays runnable on demand. Measured
  cost ~65s (`check_contents` over 1411 tracked files), ~12% of serial suite
  runtime. No security coverage was removed.

- **`_FakeMenu` monkeypatch leak fixed (pre-existing, found while profiling):**
  `tests/gui/test_image_viewer_context_menu.py` patched the *global*
  `PySide6.QtWidgets.QMenu`, then patched an attribute on `gui.wl_preset_menu`
  while that patch was live — triggering that module's first import so its
  module-level `from PySide6.QtWidgets import QMenu` captured `_FakeMenu`
  permanently. `monkeypatch` cannot undo a copy another module already took, so
  `wl_preset_menu.py:127` built a `_FakeMenu` for every subsequent test,
  failing with `'_FakeMenu' object has no attribute 'aboutToShow'`. Any subset
  run pairing those files broke (5 failed / 1942 passed); the full suite passed
  only because its ordering avoided the pair. Fixed by dropping the global
  patch — the module-local patch suffices — with a comment at the patch site.
  Reproduced identically at `4558a53`, confirming it predated the xdist work.

- **Test-suite profiling correction:** the five `test_main_tag_export_union.py`
  tests were believed to cost ~9s each constructing `DICOMViewerApp()`.
  Measured, construction is ~0.23s; the ~9s only appears after thousands of
  tests have run in the same process, because `QApplication.setStyleSheet()`
  in `main_window._apply_theme` restyles every live widget and widgets
  accumulate across the session. Parallel execution caps that accumulation. The
  planned module-scoped app fixture was therefore dropped as both ineffective
  and a shared-state hazard.

  **Plan:** [Parallelize the CI test suite](plans/completed/TEST_SUITE_PARALLELIZATION_PLAN.md) (closed 2026-08-27).

## 2026-08-10

- **3D first-paint responsiveness:** Added a VTK-free Auto Detail policy,
  cancellable Fast-preview/refinement timers, elapsed-time gating of automatic
  refinement, Fast GPU→CPU blank-frame fallback, visible non-modal progress,
  and idempotent timer-safe cleanup. Added focused widget, renderer, and pure
  policy regressions; manual hardware timing remains required by the active
  responsiveness plan.

## 2026-08-09

- **MainWindow refactor extractions #1–#6:** Split `main_window.py` (~1777 →
  ~1076 lines) into `dialogs/about_dialog.py`, `main_window_toast_controller.py`,
  in-place mouse-mode action maps, `main_window_recent_files_manager.py` (owns
  recent-menu `eventFilter`), `main_window_fullscreen_manager.py`, and
  `main_window_overlay_options.py` mixin. Public contracts retained
  (`show_toast_message`, `set_fullscreen`, `update_recent_menu`, overlay
  `set_*_checked`, etc.). Plan moved to
  `dev-docs/plans/completed/MAIN_WINDOW_REFACTOR_PLAN.md`. Branch:
  `bugfix/post-review-cleanup`.

- **MainWindow refactor Phase 0 (characterization):** Added required regression
  nets before extractions — about dialog, recent-files menu/context menu,
  mouse-mode map, overlay option sync/emit contract, contract `hasattr` suite,
  and fullscreen close/exit cases. Full suite green (4596 passed). Gate
  checklist marked complete in
  `dev-docs/plans/completed/MAIN_WINDOW_REFACTOR_PLAN.md`. Branch:
  `bugfix/post-review-cleanup`.

## 2026-08-08

- **`main.py` mixin split — gate remediation:** Fixed `DICOM_PERF_LOG=1`
  startup `NameError` by moving emit to `DICOMViewerApp._log_startup_perf`.
  Cleared basedpyright (0 errors) using ImageViewer-style mixin pragmas
  (plan’s `self: DICOMViewerApp` is invalid under basedpyright). Ruff clean.
  Consolidated `StudiesNestedDict` on `gui.tag_export_union_host`. Restored
  `main_app_ui_and_files.py` after accidental truncation during re-review
  probes (re-extracted from phase-4 `main.py` backup). Backlog: lift
  `.coveragerc` omit for `main_app_*.py` (`TO_DO.md`).

- **`main.py` mixin split (Phases 6–7):** Removed 114 stale imports from
  `src/main.py` (506 → 334 lines). Regenerated
  `scripts/line_complexity_grandfather.json` for the new file sizes (no new
  `functions` entries for `main_app_*.py`). Updated `SOURCE_LAYOUT.md`,
  `ARCHITECTURE.md` mixin section (verified), `CHANGELOG.md` [Unreleased], and
  plan progress ledger. Branch: `refactor/main-split`.

## 2026-08-07

- **Tag export UX:** extracted preset persistence and Select All / count helpers
  from `tag_export_dialog.py` into `tag_export_dialog_presets.py`,
  `tag_export_dialog_selection.py`, and `tag_export_dialog_helpers.py` so the
  dialog stays within its existing line-count grandfather (1415).

- **CodeRabbit / LongCat follow-ups (PR #49):** skip grandfather ratchet when
  ``ast.parse`` fails (real lizard does not raise on syntax errors); defensive
  ``int()`` on malformed grandfather caps; surface failed ``git add`` of
  ratcheted JSON; fix DEVELOPER_SETUP hook-order docs; extract shared high-CCN
  test fixture; disambiguate duplicate lizard function names with
  ``<function>@<lineno>`` labels.

- Restored **full-history Gitleaks on local pre-push** (same as CI; ~1s on this
  repo). Push-scoped `--from-pre-push-stdin` remains for optional ad-hoc use.

- **CI basedpyright / pytest:** install ``lizard`` in the pyright and pytest jobs
  so the line-complexity hook script and its tests resolve under CI.

- **Grandfather ratchet:** staged line/CCN improvements automatically lower or
  drop caps in `line_complexity_grandfather.json` and `git add` the file into
  the same commit so ceilings cannot climb back up.

- Added **CI full-history Gitleaks** to `privacy-gates.yml` Detect Secrets
  (pinned 8.30.1 binary + redacted wrapper). Raised CI coverage
  floor from 60% to **65%** (measured TOTAL ~67%).

- Moved the **full pytest** gate off local `pre-push` (too slow)
  onto CI `pytest` via `--cov-fail-under` (now 65%). Pre-push still runs privacy,
  PHI, Gitleaks (full history), basedpyright, and advisory lizard/Sonar checks.

- Added a pre-commit **line-count / lizard CCN** gate
  (`scripts/git_hook_line_complexity.py`, wired from `.githooks/pre-commit`) with
  thresholds warn@600 / block@750 lines and block CCN>20. Existing hotspots are
  grandfathered in `scripts/line_complexity_grandfather.json` (40 files, 67
  functions at initial baseline) at their recorded size/CCN: unchanged or
  smaller → warn only; **increase above baseline → block**. `--all` reads the
  worktree; `--staged` reads the index. Documented in `DEVELOPER_SETUP.md` /
  `CONTRIBUTING.md`.

- Documented local SonarQube Community Build persistence (container vs volume,
  generic shared-server naming, restore-first migration, backups) in
  [`tools/sonarqube/README.md`](../tools/sonarqube/README.md) and linked it from
  [`DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md). Branch
  `chore/local-devtools-hooks-and-docs` is the landing place for related local
  hook/docs follow-ups.

Use this log for CI, static analysis, harness changes, dependency-verification passes, repo hygiene, doc-garden cleanup, and other maintainer workflow notes. Use [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible product/release changes. Use [`TO_DO.md`](TO_DO.md) only for active backlog items and near-term follow-ups.

## 2026-08-05

- **Merge and resampling Sonar slice:** completed the automated implementation
  of the two next highest-ranked distinct-file `python:S3776` targets:
  `DICOMOrganizer.merge_batch` (65) and
  `ImageResampler.get_resampled_slice` (63). Characterization coverage now
  locks down additive path/multiframe bookkeeping and sorted-slice, cache, and
  float32 resampling behavior. The fresh local analysis at `c573548` reported
  **236** priority findings (238 → 236), with both target findings cleared.
  Focused tests (117), the full suite (3,639), architecture boundaries, repo
  harness, automated agent smoke, and staged privacy checks passed. The
  contributor completed the additive-load and fusion-scrolling interactive
  smoke successfully; the plan is archived:
  [Merge and resampling slice](plans/completed/SONARQUBE_MERGE_AND_RESAMPLING_SLICE_PLAN_20260805.md).

- **Portable coverage XML configuration:** enabled `relative_files = True` in
  `.coveragerc`, so coverage XML names `src` rather than a workstation or
  scanner-container path. The staged artifact gate now treats this tracked
  text configuration as content-scanned config rather than an opaque
  extensionless asset; regression coverage confirms it still blocks local-path
  content.

- **Top-complexity Sonar slice** on
  `refactor/sonar-top-complexity-rendering-export`: completed the five selected
  `python:S3776` refactors in tag export, presentation-state annotations,
  graphics overlays, and tag-edit dialog construction, with characterization
  coverage. The final local analysis at `9a08fcd` reported **238** priority
  findings (243 → 238); every selected target is absent. The remaining seven
  `S3776` findings in the four touched files remain intentionally deferred.
  The refactor initially introduced an overlay-helper `S107`; grouping its
  shared inputs in a private `OverlayTextContext` cleared it before closeout.
  Plan: [Top-complexity five-function slice](plans/completed/SONARQUBE_TOP_COMPLEXITY_FIVE_FUNCTION_SLICE_PLAN_20260805.md).

- **Sonar new-code coverage batch** on `test/sonar-new-code-coverage` (PR #46,
  22 commits): reorganized `tests/` into source-mirrored suites
  (`tests/core/`, `tests/gui/`, `tests/tools/`, `tests/utils/`) and added unit
  coverage for DICOM processing/loading, FusionHandler, StudyIndex threads,
  annotation clipboard / ROI serialization, and utility modules; synced
  `tests/README.md` and `dev-docs/SOURCE_LAYOUT.md` to the new layout.
  - **Pre-push privacy hook fix** (`scripts/git_hook_pre_push_privacy.py`):
    initial branch pushes now exclude commits already reachable from the target
    remote's tracking refs (`rev-list <local> --not --remotes=<remote>`), so
    legacy history already upstream no longer trips the author-email policy on
    a first push; the remote name now flows through validation with regression
    coverage.
  - Resolved the CodeRabbit review threads from the run on this branch (7 of 8
    findings fixed; the "US vs HU" rescale comment was closed as stale — the
    hook treats `US` as a display-none placeholder). The PR-scoped docstring
    coverage pre-merge warning was left standing: test suites intentionally
    use module-level docstrings only.

## 2026-08-02

- **Engineering documentation sync:** aligned top-level developer docs with the GDCM decoder productionization and launcher incomplete-venv fix. Updated `README.md` technology stack, `ARCHITECTURE.md` decoder domain, `SOURCE_LAYOUT.md` decoder modules, `DEVELOPER_SETUP.md` troubleshooting (venv + compressed DICOM), `HARNESS.md` decoder fixture smoke command, `BUILDING_EXECUTABLES.md` frozen-build decoder validation, and `CODE_DOCUMENTATION.md` / `dev-docs/README.md` index entries.

## 2026-07-30

- **Unused-symbol / correctness cleanup** on `chore/dead-branch-and-unused-cleanup`:
  basedpyright `reportUnusedImport` + `reportUnusedVariable` +
  `reportUnusedParameter` on `src/` went from **93 → 0** (dead imports/locals
  removed or `_`-prefixed; intentional re-exports and keyword-stable params
  kept with safe markers). Also removed the zoom-release dead pan branch,
  bypassed the OVERLAY empty-coordinates gate, clamped palette LUTs per
  channel, and zeroed flat `normalize_to_uint8` arrays. Overlay LSB no-NumPy
  bit-order was already fixed earlier (`annotation_overlay_bitmap.py`); closed
  the stale TO_DO item. See CHANGELOG `[Unreleased]` Fixed/Changed.

## 2026-07-28

- Landed three pylinac ACR CT features on `feature/pylinac-ct-cnr-batch-xlsx`
  (commits 39dcd7a, 20c8f82, 5a5d3ed), plus the `run.py` `sys.path` launcher
  fix folded into the same branch/PR/CI run. Plan:
  `dev-docs/plans/completed/PYLINAC_CT_CNR_BATCH_XLSX_PLAN.md`.
  - **F1 — CNR intermediates:** `_extract_low_contrast_cnr_details` in
    `src/qa/pylinac_acr_ct.py` harvests object ROI mean, background mean/σ, and
    module CNR from the live `low_contrast_module` (dict-valued `rois` /
    `background_rois`; `cnr()` is a method) into `metrics.low_contrast_cnr`.
    `results_data(as_dict=True)` now feeds a structured `raw_pylinac`, and
    `_jsonable` was hardened for non-`float64` numpy scalars.
  - **F3 — XLSX export:** `src/qa/qa_xlsx_export.build_qa_workbook`
    (Summary/Detail/Images, Qt-free, reuses `qa_export._flatten`); transient
    `QARequest.analyzed_image_out_path` / `QAResult.analyzed_image_path` drive
    `analyzer.save_analyzed_image()` inside the runner with facade-owned
    `TemporaryDirectory` lifecycle. Single-run `schema_version` bumped 1.1 → 1.3.
  - **F2 — batch CT:** `QACTBatchWorker` (serial, per-series error isolation,
    cooperative cancel, worker-owned image temp dir), `CTBatchResult`, selection
    and summary dialogs, and the `acr_ct_batch_requested` signal wiring.
  - F1 built with Opus; F3 and F2 implemented by Sonnet subagents in isolated
    worktrees (F3 first for the shared `build_qa_workbook` dependency, then F2),
    reviewed and re-linted before merge. Pre-merge live-phantom numeric value
    check for F1 (against a real CatPhan dataset) is still open.

## 2026-07-26

- Addressed verified CodeRabbit findings on the S3776 PR (RLE UID, cancel
  animation stop, FrameDatasetWrapper local overrides, first-slice guards,
  overlay recreate context, overlay bitmap LSB/pad, export docstring/sanitize,
  MPR assign disconnect). Skipped speculative nitpick refactors.
- Cleared basedpyright push-gate errors introduced by recent S3776 helper
  extractions: typed bare generics, overlay parser null guard, measurement
  `QPointF` casts, and `importlib` loaders for load-pipeline / ROI-export
  modules so import-cycle errors no longer block pre-push.
- Completed a Sonar `python:S3776` slice on overlay bitmap conversion: moved byte
  extraction, LSB-first unpack, coordinate mapping, OpenCV/scipy path extraction,
  and no-NumPy fallback into `src/tools/annotation_overlay_bitmap.py`;
  `AnnotationManager._convert_overlay_bitmap_to_graphics` now delegates to that
  module. Added `tests/tools/test_annotation_overlay_bitmap_sonar_slice.py`.
  Target finding was cognitive complexity ~85 (radon CCN 34 on the method before
  refactor).
- Completed a Sonar `python:S3776` slice on ROI TXT/CSV export: moved TXT
  area-line formatting, slice/series blocks, and CSV row builders / finalize
  logic into `roi_export_txt` and `roi_export_csv`; `write_txt` and `write_csv`
  in `roi_export_service` are thin wrappers. Added
  `tests/core/test_roi_export_txt_csv_sonar_slice.py`. Target findings were
  cognitive complexity 83 / 81 (radon CCN 26 / 31 on `write_txt` / `write_csv`
  before refactor).
- Completed a Sonar `python:S3776` slice on histogram series-frequency
  computation: moved dataset resolution, rescale parsing, and histogram
  accumulation helpers into `src/gui/dialogs/histogram_frequency.py`;
  `HistogramDialog._compute_series_global_frequency_max` now orchestrates only.
  Added `tests/gui/test_histogram_frequency_sonar_slice.py`. Target finding was
  cognitive complexity ~85 (radon CCN 39 on `_compute_series_global_frequency_max`).
- Completed a Sonar `python:S3776` slice on single-file DICOM loading: moved
  compression-label lookup, defer/multiframe messages, memory-estimate pre-load,
  slow-file timing assembly, and exception message builders into
  `dicom_loader_file`; `DICOMLoader.load_file` now orchestrates module-level
  read/annotate/multiframe helpers. Added
  `tests/core/test_dicom_loader_load_file_sonar_slice.py`. Target finding was
  cognitive complexity 88 (radon CCN 39 on `load_file`).
- Completed a Sonar `python:S3776` slice on first-slice (full replace) load:
  moved pre-reset, stale subwindow cleanup, PS/KO load, subwindow-0 display,
  navigator reveal/fit, and deferred paint side effects into
  `src/gui/file_series_first_slice_load.py`;
  `FileSeriesLoadingCoordinator.handle_load_first_slice` now orchestrates only.
  Added `tests/gui/test_file_series_first_slice_load_sonar_slice.py`. Target finding
  was cognitive complexity 87.
- Completed a Sonar `python:S3776` slice on series-transition window/level
  resolution: extracted new-series stored/fallback/cache helpers in
  `slice_window_level_resolver` so `resolve_window_level_for_series_transition`
  orchestrates only. Added
  `tests/core/test_slice_window_level_resolver_sonar_slice.py`. Target finding
  was cognitive complexity 89.
- Completed a Sonar `python:S3776` slice on measurement itemChange handlers:
  moved handle/group position, selection, geometry sync, and debug logging into
  `src/tools/measurement_item_change.py`; both `itemChange` methods now
  orchestrate that module. Added
  `tests/tools/test_measurement_item_change_sonar_slice.py`. Target findings
  were cognitive complexity 92 and 74.
- Ran a fresh local SonarQube analysis on `349ab6f` after the series-navigator
  list slice. CE task succeeded; `scripts/report_local_sonarqube_issues.py`
  reported **242** priority findings (BLOCKER/CRITICAL/MAJOR). Highest remaining
  open `python:S3776`: `measurement_items.itemChange` (92),
  `resolve_window_level_for_series_transition` (89), `dicom_loader.load_file` (88),
  `handle_load_first_slice` (87).
- Completed a Sonar `python:S3776` slice on series navigator list rebuild:
  moved series sorting, section-width, and display-label helpers into
  `series_navigator_model`; `SeriesNavigator.update_series_list` now
  orchestrates clear/append/schedule helpers. Added
  `tests/gui/test_series_navigator_list_update_sonar_slice.py`. Target finding
  was cognitive complexity 94.
- Completed a Sonar `python:S3776` slice on overlay corner text: lifted
  multiframe label, InstanceNumber/slice, thickness, and timing formatters out
  of `get_corner_text` in `overlay_text_builder`. Added
  `tests/gui/test_overlay_text_builder_sonar_slice.py`. Target finding was
  cognitive complexity 94.
- Completed a Sonar `python:S3776` slice on ROI XLSX export: moved workbook
  assembly, series/slice blocks, ROI stats/area/channel rows, and
  crosshair/measurement writers into `src/core/roi_export_xlsx.py`;
  `roi_export_service.write_xlsx` now orchestrates that module. Added
  `tests/core/test_roi_export_xlsx_sonar_slice.py`. Target finding was
  cognitive complexity 99.
- Completed a Sonar `python:S3776` slice on projection enabled handling:
  extracted state-apply, MPR/non-MPR refresh, and DEBUG_PROJECTION helpers in
  `projection_app_facade` so `on_projection_enabled_changed` orchestrates only.
  Covered by existing `tests/core/test_projection_app_facade.py`. Target finding
  was cognitive complexity 107.
- Completed a Sonar `python:S3776` slice on ROI statistics overlays: moved
  text formatting, font resolution, item ensure/flags, scene position, and
  visibility sync into `src/tools/roi_statistics_overlay.py`;
  `ROIManager.create_statistics_overlay` / position update now orchestrate
  those helpers. Added `tests/tools/test_roi_statistics_overlay_sonar_slice.py`.
  Target finding was cognitive complexity 122.
- Completed a Sonar `python:S3776` slice on subwindow layout signal wiring:
  extracted `_disconnect_ignore_missing` / tracked-slot pop helpers and
  fixed signal-pair tables so `connect_subwindow_signals` orchestrates only.
  Added `tests/core/test_subwindow_signal_wiring_sonar_slice.py`. Target finding
  was cognitive complexity 126.
- Completed a Sonar `python:S3776` slice on additive file load:
  moved eviction, PS/KO load, appended-series refresh, empty-pane auto-assign,
  navigator/fusion/status side effects into
  `src/gui/file_series_additive_load.py`;
  `FileSeriesLoadingCoordinator.handle_additive_load` now orchestrates only.
  Added `tests/gui/test_file_series_additive_load_sonar_slice.py`. Target finding
  was cognitive complexity 127.
- Completed a Sonar `python:S3776` slice on `FrameDatasetWrapper.__init__`:
  extracted nested functional-group helpers for plane geometry, pixel measures,
  rescale, and VOI LUT into focused functions in `multiframe_handler`. Added
  `tests/core/test_frame_dataset_wrapper_sonar_slice.py`. Target finding was
  cognitive complexity 133.
- Completed a Sonar `python:S3776` slice on overlay position updates: moved
  widget geometry sync, viewport corner anchors, max-width cache resolution,
  left/right item placement, and deferred repaint into
  `src/gui/overlay_position_updater.py`; `OverlayManager.update_overlay_positions`
  now orchestrates only. Added
  `tests/gui/test_overlay_position_updater_sonar_slice.py`. Target finding was
  cognitive complexity 142 on `update_overlay_positions`.
- Completed a Sonar `python:S3776` slice on the load pipeline: shared helpers
  for merge paths / empty-load errors / failed-file warnings / post-load
  status / progress UI; sync body split from outer exception wrapper; async
  implementation moved to `src/core/loading_pipeline_async.py` (re-exported
  from `loading_pipeline`). Added `tests/test_loading_pipeline_sonar_slice.py`.
  Fresh analysis: `run_load_pipeline_async` (was 146) cleared; no remaining
  `S3776` under `loading_pipeline*`; priority `S3776` count 253 → 251.
- Completed the non-constructor `python:S107` parameter-object sweep (8 sites:
  layout/load, render pipelines, cine + export request dataclasses) and fixed
  the two follow-on `python:S5806` builtin-shadow findings in
  `export_manager` (`format` → `export_format` locals). Documented the six
  remaining DI `__init__` constructors with `# NOSONAR(S107)` (wiring ctors;
  rule remains active for methods): `dialog_coordinator`, `export_dialog`,
  `histogram_dialog`, `keyboard_event_handler`, `roi_coordinator`,
  `slice_display_manager`. Fresh local analysis target: **0 MAJOR** from
  these S107 sites; CRITICAL volume is still dominated by deferred `S3776`.

## 2026-07-25

- **Superseded by the privacy-gated PR/push configuration below:** enabled the
  initial approved SonarQube Cloud CI analysis of `src/` only after pushes to
  `main`: `.github/workflows/sonarqube-cloud-main.yml` is pinned to the
  official scan action and uses only the repository `SONAR_TOKEN` secret.
  Root `sonar-project.properties` excludes tests, coverage, artifacts, local
  data, and generated/cache paths. The harness now permits only this exact
  main-only workflow; Automatic Analysis must remain disabled in SonarQube
  Cloud to prevent independent PR analysis.
- Completed the privacy structural-schema SonarQube slice: decomposed metric
  normalization and rendered-value revalidation, schema loading, validator
  parsing, and operation parsing into small fail-closed helpers. Added direct
  normalization and invalid-schema regression coverage. A fresh full-suite,
  coverage-backed local analysis cleared all five
  `utils/privacy/structural_schema.py` `S3776` findings; priority findings are
  now **280** (down from 285).
- Completed a targeted local SonarQube cleanup slice: made the RDSR privacy
  projection's `dataclasses.replace` type preservation explicit (`S5886`) and
  moved the lazy 3D-render eligibility import out of the subwindow wiring loop
  (`S1515`), with regression coverage for both. Documented four `S8572`
  suppressions where raw `logging.exception` would violate the PHI/PII sink
  gate; those paths retain structural/sanitized exception reporting. Fresh
  coverage-backed local analysis: **285** priority findings (down from 291).
- Approved a dormant, source-only SonarQube Cloud scope configuration for a
  future explicit CI workflow on `main`. Cloud analysis remains inactive until
  that workflow and its secret are separately enabled; PR, branch, test,
  coverage, artifact, and local-data uploads remain prohibited.

## 2026-07-24

- Local SonarQube freshness is now advisory-stale when a successful submission
  is older than 14 days or more than five commits behind `HEAD`. Submission
  records include their Git revision so the main pre-push reminder can detect
  code drift without contacting SonarQube.
- Every local pre-push now performs metadata-only Docker Hub/SonarSource checks
  for an updated local SonarQube server image and native scanner at most once
  every seven days. It records an ignored local result and never pulls,
  installs, or restarts anything.

## 2026-07-18

- Completed the fusion coordinator Sonar finish slice
  (`plans/completed/SONARQUBE_FUSION_COORDINATOR_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `_finish_overlay_series_load`, `get_fused_image`, and
  `_update_spatial_alignment`. Extended
  `tests/gui/test_fusion_coordinator_sonar_slice.py`. Fresh analysis: **287**
  priority findings (down from 290); `fusion_coordinator` `S3776` → 0.
- Completed the fusion coordinator Sonar first slice
  (`plans/completed/SONARQUBE_FUSION_COORDINATOR_SLICE_PLAN_20260718.md`): extracted
  helpers for `handle_fusion_enabled_changed`, `_update_base_display`,
  `sync_ui_from_handler_state`, `_update_resampling_status`, and
  `_auto_detect_fusion_candidates`. Added
  `tests/gui/test_fusion_coordinator_sonar_slice.py`. Fresh analysis: **290**
  priority findings (down from 295); five targeted `S3776` cleared (3 remaining
  in-file deferred: overlay load, fused image, spatial alignment).
- Completed the ROI coordinator Sonar finish slice
  (`plans/completed/SONARQUBE_ROI_COORDINATOR_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `handle_roi_drawing_finished`, `handle_roi_delete_requested`,
  `delete_all_rois_current_slice`, and `handle_scene_selection_changed`. Added
  `tests/gui/test_roi_coordinator_sonar_finish_slice.py`. Fresh analysis:
  **295** priority findings (down from 299); `roi_coordinator` `S3776` → 0.
- Completed the MPR controller Sonar finish slice
  (`plans/completed/SONARQUBE_MPR_CONTROLLER_FINISH_SLICE_PLAN_20260718.md`): extracted
  helpers for `prompt_save_mpr_as_dicom`, `attach_floating_mpr`,
  `_on_mpr_requested`, and `_reset_window_level_for_mpr`. Extended
  `tests/gui/test_mpr_controller_sonar_slice.py`. Fresh analysis: **299**
  priority findings (down from 303); `mpr_controller` `S3776` → 0.
- Completed the MPR controller Sonar slice
  (`plans/completed/SONARQUBE_MPR_CONTROLLER_SLICE_PLAN_20260718.md`): extracted helpers
  for `display_mpr_slice`, `_activate_mpr`, `_tear_down_mpr_at_subwindow`,
  `_install_mpr_payload_at_subwindow`, and `_build_overlay_dataset`. Added
  `tests/gui/test_mpr_controller_sonar_slice.py`. Fresh analysis: **303**
  priority findings (down from 308); five targeted `S3776` cleared (`mpr_controller`
  `S3776` 9 → 4 remaining out-of-scope methods).
- Finished non-font `python:S1192` cleanup and added a file-scoped ignore for
  `S1192` on `src/utils/bundled_fonts.py` only
  (`tools/sonarqube/sonar-project.properties` multicriteria
  `bundled_fonts_s1192`) so the font catalog stays readable without demoting
  the rule globally. Fresh analysis: **308** priority findings (down from 347);
  `S1192` at 0 (including fonts ignore).
- Cleared all open `python:S108` empty-block findings and started
  `python:S1192` (duplicate string literals): extracted shared UI/status
  constants in dialogs/widgets/loading paths; left `src/utils/bundled_fonts.py`
  deferred as a font data table. Fresh analysis: **347** priority findings
  (down from 399); `S108` at 0; `S1192` remaining **39** (16 in
  `bundled_fonts`).
- Completed the view state manager Sonar slice
  (`plans/completed/SONARQUBE_VIEW_STATE_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `store_initial_view_state`, `reset_view`,
  `handle_window_changed`, `handle_rescale_toggle`, and
  `handle_viewport_resized`. Added
  `tests/gui/test_view_state_manager_sonar_slice.py`. Fresh analysis: **399**
  priority findings (down from 408); five targeted `S3776` cleared.
- Completed the Sonar MAJOR mechanical sweep
  (`plans/completed/SONARQUBE_MAJOR_MECHANICAL_SWEEP_PLAN_20260718.md`): cleared all open
  `python:S125`, `python:S1066`, and `python:S1172` findings (commented-out
  code, collapsible ifs, unused parameters with signature-safe removals or
  `_ = param` retention). Fresh analysis: **408** priority findings (down from
  454); targeted three MAJOR rules at 0.
- Completed the slice display manager Sonar slice
  (`plans/completed/SONARQUBE_SLICE_DISPLAY_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `_render_base_image_pipeline`, `_sync_controls_and_metadata`,
  `_render_scene_overlays_annotations`, `display_rois_for_slice`, and
  `handle_series_navigation`. Added
  `tests/gui/test_slice_display_manager_sonar_slice.py`. Fresh analysis:
  **454** priority findings (down from 461); five targeted `S3776` cleared
  (`python:S3776` 282 → 277).
- Completed the ROI coordinator statistics-path Sonar slice
  (`plans/completed/SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md`): extracted
  projection/spacing/ownership helpers for
  `_get_pixel_array_for_statistics`, `update_roi_statistics`, and
  `update_roi_statistics_overlays`; removed dead closure-debug code. Added
  `tests/gui/test_roi_coordinator_statistics.py`. Fresh analysis: **461**
  priority findings (down from 464); targeted stats-path `S3776` cleared.
- Completed the undo/redo annotation-command Sonar slice
  (`plans/completed/SONARQUBE_UNDO_REDO_ANNOTATION_COMMANDS_SLICE_PLAN_20260718.md`):
  extracted add/remove helpers for `MeasurementCommand`,
  `TextAnnotationCommand`, `ArrowAnnotationCommand`, and `CrosshairCommand`.
  Added `tests/test_undo_redo_annotation_commands.py`. Fresh local analysis +
  scoped reporter: **464** active priority findings (down from 472);
  `undo_redo.py` targeted `S3776` findings cleared (293 → 285 overall).
- Completed the first CRITICAL code-smell remediation slice
  (`plans/completed/SONARQUBE_CRITICAL_CODE_SMELL_FIRST_SLICE_PLAN_20260718.md`):
  - **S5727:** removed redundant `None` guards before
    `FusionCoordinator._update_spatial_alignment` cache writes; every branch
    already assigned `(scale, offset)` tuples. Added
    `tests/gui/test_fusion_coordinator_spatial_alignment.py`.
  - **S3776 (ROICommand only):** extracted add/remove/overlay-restore helpers in
    `utils.undo_redo.ROICommand` without changing undo semantics. Added
    `tests/test_undo_redo_roi_commands.py`.
  - Fresh local analysis + scoped reporter: **472** active priority findings
    (down from 476); remaining CRITICAL/MAJOR backlog stays in `TO_DO.md`.
- Widened the scoped local SonarQube reporter to include all open BLOCKER,
  CRITICAL, and MAJOR issues, regardless of type. The prior CRITICAL query
  filtered to BUG/VULNERABILITY and omitted the dashboard's CRITICAL
  CODE_SMELL findings; regression coverage now locks the all-types scope.
- Local SonarQube runner and scoped reporter now load simple `KEY=VALUE` (or
  `export KEY=VALUE`) entries from the ignored repository-root `.env` file.
  Explicit environment variables still take precedence, the file is parsed
  rather than executed, and token values are never printed. This lets the
  documented `.env` workflow work without a separate shell export.
- Remediated local SonarQube MAJOR findings on branch
  `fix/sonarqube-major-findings-20260718` (analysis
  `2026-07-18T17:12:01+0000` / revision `9484958196fcd183a88407f5f312d77bb521f8df`):
  - **S2245:** `deep_anonymizer` date-shift jitter now uses `secrets.randbelow`.
  - **S3923:** collapsed six identical if/else sites (annotation options colors,
    image-viewer pixel-array ambiguous branch, slice-sync plane lookup via the
    shared dataset→sorted mapper, measurement undo-batch tracking for angle and
    linear items).
  - **S1244:** documented `# NOSONAR(S1244)` suppressions for all 19 float-equality
    findings (DICOM DS-VR RescaleSlope/Intercept guards, VTK empty-scene bounds
    sentinels, flip/zoom/export/angle label sentinels); upgraded the bare
    `# NOSONAR` at `dicom_window_level.py:229` to rule-scoped form. No
    `math.isclose` refactors.
  - Deferred 114 MAJOR CODE_SMELL findings — tracked in `TO_DO.md`.
  - Plan: `plans/SONARQUBE_MAJOR_FINDINGS_REMEDIATION_PLAN_20260718.md`.


- Hardened local SonarQube endpoint handling: `SONAR_HOST_URL` now accepts
  only HTTP(S) loopback hosts, and the Docker-only override accepts only
  `host.docker.internal`. Added regression coverage for `file://`, remote,
  and credential-bearing URL rejection. The two validated `urllib` request
  sinks now have narrow Semgrep suppressions documenting this enforced
  boundary; the targeted security-audit scan returns zero findings.
- Added `scripts/report_local_sonarqube_issues.py`, an opt-in local reporter
  that queries severe SonarQube findings with `componentKeys`, requires every
  returned issue to belong to the requested component, rejects malformed or
  incomplete pagination, and keeps credentials out of command arguments and
  persisted reports. It can assert the latest analysis revision and writes
  detailed metadata only below ignored `tmp/`. Added mocked-HTTP regression
  tests, local-runner documentation, and the inventory entrypoint.
- Corrected a false DICOM Viewer triage report: its ten findings belonged to
  `weekend-digest-free-apis` and `spotibye`. A fresh local analysis processed
  at 2026-07-18 17:12:01 UTC for revision
  `9484958196fcd183a88407f5f312d77bb521f8df` returned zero component-scoped
  BLOCKER or CRITICAL BUG/VULNERABILITY findings. Focused tests (14), Ruff,
  basedpyright, full privacy-output check, security-tool inventory, and repo
  harness passed.

## 2026-07-16

- Added the canonical machine-readable security/privacy tool inventory with
  tested versions, installation scopes, network policies, hook/CI enforcement,
  model hashes, internal control entrypoints, and explicit prohibited external
  services. The repo harness and CI now validate its schema, required coverage,
  and referenced paths. Added a tracked, no-install `.envrc`, safe
  `.env.example`, and privacy-critical ignores/admission blocks for `.env`,
  `.direnv/`, `.scannerwork/`, `.sonar*`, and `.sonarqube*` local state. Direnv
  performs only a network-free requirements-hash check; the explicit
  `scripts/sync_dev_environment.py` command installs changed dependencies and
  stamps the active project venv after success.
- Installed and validated the isolated local PHI review environment
  (`.phi-tools`, approximately 1.7 GB): pinned PhiScan, Presidio plus the pinned English
  spaCy model, DICOM PHI scanner, EasyOCR/PyTorch with environment-local model
  weights, and system Tesseract/ExifTool. Fixed media/DICOM wrappers to resolve
  selected paths before entering protected temporary working directories and
  made the DICOM wrapper fail closed when OCR weights are missing. Added the
  clean private-repository recreation runbook after verifying the 672-commit
  `old-main` archive has no overlap with the 25 commits actually on GitHub. A
  dry-run clean-root export then drove two corrections: force-adding only the
  tracked archive so conservatively ignored packaged icons remain present, and
  allowing reviewed Gitleaks false positives to bind to an exact Git blob,
  rule, and line instead of the root commit identity.
- Added protected-path and conditional local-review enforcement: the blocking
  artifact gate now rejects force-added files under privacy-critical local data,
  screenshot, log, analysis, backup, and temporary roots and validates the
  staged `.gitignore` blob retains every required rule. Pre-commit now invokes
  advisory PhiScan/OCR/Presidio/DICOM wrappers only for matching staged index
  blobs, and successful `main` pre-push flows run local-only Hounddog before the
  existing SonarQube freshness reminder. Optional results remain advisory;
  artifact admission and human hash review remain blocking.

- **Local-first analysis policy:** Removed Codecov coverage upload/configuration
  and SonarQube Cloud repository configuration. CI retains a console-only
  coverage summary. External analysis/telemetry integrations are prohibited by
  the privacy guardrails; the local SonarQube Community Build runner remains
  opt-in.
- **Agent harness simplification:** Removed duplicate project-local general
  skills, specialist role agents, auto-orchestration state/run packets, and the
  test ledger. Retained only the DICOM Viewer-specific agent smoke skill in
  both supported skill locations.
- **Periodic local assurance:** Fixed pre-push ref input reuse so the main-only
  full scanner suite cannot be skipped after the metadata guard consumes
  stdin. Main updates now get a non-blocking reminder when the ignored local
  SonarQube Community Build record is missing or older than 30 days; the check
  never contacts SonarQube or requires a token.

## 2026-07-14

- **Optional local SonarQube Community Build runner:** Added `scripts/run_local_sonarqube.py` plus isolated `tools/sonarqube/sonar-project.properties` for opt-in local analysis. The runner uses `SONAR_TOKEN`, preflights the service, selects a native or Docker scanner, records the last successful submission in ignored `.sonar-local/last-analysis.json`, and offers opt-in pytest coverage. It is intentionally excluded from automatic hook execution and CI because a local scan may be slow. SonarQube Cloud was later removed under the 2026-07-16 local-first policy.

## 2026-07-11

- **Backlog history split:** `TO_DO.md` was converted back to an active-backlog-only checklist: removed the top `Changes:` narrative and removed fully completed `[x]` task rows. Completed user-visible changes belong in `CHANGELOG.md`; maintainer/process changes belong here; detailed implementation records belong in plans, info docs, or bug-investigation notes.

## 2026-06-16

- **Static typing cleanup:** Swept basedpyright back to **0 errors** in `src/` and `scripts/` after the refactor/PS3.15/nuclear work had regressed to 246 errors. Categories included `Tag` to `BaseTag` annotation fixes, `TYPE_CHECKING` app imports, type arguments, Qt builder-pattern directives, and defensive `None` guards. Full pytest at the time: **1008 passed / 17 skipped**.
- **Doc feature coverage tooling:** Added `scripts/check_doc_feature_coverage.py`, a report-only menu/`QAction` label to `user-docs/` coverage heuristic with `--fail-under` support, tests, and HARNESS documentation.
- **Changelog hygiene:** Consolidated duplicate `[Unreleased]` third-level headings in `CHANGELOG.md`; doc-garden duplicate count returned to 0.
- **User-doc coverage:** Added topic guides for de-identified export, measurements/annotations, keyboard shortcuts, multi-window layouts, the general Export dialog, and the DICOM Tag Viewer. Extended repo-harness doc-garden checks to report missing/stale `Last updated:` metadata on required user guides.

## 2026-06-04

- **UX maintenance sweep:** Updated W/L status-bar and preset access notes after status bar center readout changed to numeric W/L, right-pane `Presets...` moved beside `Use rescaled values`, and W/L presets were exposed from the View menu and Quick W/L dialog.
- **Workflow fixes tracked:** Recorded close-out for cut/paste same-slice positioning, ROI resize handle cleanup on delete/cut, large-file cancel-before-load, Edit -> Cut, canceled folder-load index skip/toast, and compact W/L preset labels. User-visible entries remain in `CHANGELOG.md`; implementation details remain in linked plans/tests.
