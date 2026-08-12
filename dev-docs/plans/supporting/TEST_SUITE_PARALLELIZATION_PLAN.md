# Plan: Parallelize the CI test suite (pytest-xdist)

**Last updated:** 2026-08-12
**Status:** Supporting — **Phases 1 and 2 complete, 20/20 gate passed**; Phase 3 docs/config remain
**Area:** CI / test harness

---

## Current state: push blocker cleared

Commit `4558a53` put `-n auto` into
[`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) on branch
`perf/parallelize-tests` while the suite still crashed 3 of 3 at `-n 4`. That
was a red-CI hazard.

**Resolved 2026-08-12.** The Phase 2 fix is implemented and passed the full
gate: **20 consecutive `-n 4` runs, 4887 passed / 15 skipped every time, zero
failures or worker crashes** (205.5–233.7s, mean ~211s). The Phase 2 changes are
uncommitted in the working tree and must be committed **on the same branch,
before pushing**, or CI will still see the pre-fix state.

---

## Goal and success criteria

The full suite takes **~8m41s** serially. Parallel execution removes most of
that, but `pytest-xdist` currently aborts Qt workers. The abort is now fully
diagnosed and a fix is validated.

**Success criteria:**

- The CI `pytest` job runs with `-n auto` and is green across **20 consecutive
  runs** at the worker count CI actually uses (`ubuntu-latest` = 4 cores).
- No test is marked `xfail`, skipped, or serialized to achieve that.
- `--cov-fail-under=65` still gates, and `coverage.xml` is still complete.
- Local and CI invocations stay documented in sync.

---

## Context and links

- CI test job: [`.github/workflows/ci.yml:117-128`](../../../.github/workflows/ci.yml)
- Session `qapp` fixture: [`tests/conftest.py:30-40`](../../../tests/conftest.py)
- **The offending test:** [`tests/core/test_subwindow_lifecycle_controller_slice.py:339-341`](../../../tests/core/test_subwindow_lifecycle_controller_slice.py)
- Validation plugin (gitignored, temporary): `tmp/qapp_probe.py`
- Dev-env sync stamp: [`scripts/sync_dev_environment.py`](../../../scripts/sync_dev_environment.py)
- PHI artifact gate: [`scripts/check_no_phi_artifacts.py`](../../../scripts/check_no_phi_artifacts.py),
  [`.github/workflows/privacy-gates.yml:170-189`](../../../.github/workflows/privacy-gates.yml),
  [`.githooks/pre-push:32`](../../../.githooks/pre-push)
- Docs mirroring the CI pytest command:
  [`dev-docs/DEVELOPER_SETUP.md:277,299`](../../DEVELOPER_SETUP.md),
  [`dev-docs/HARNESS.md:75`](../../HARNESS.md)

---

## Root cause (confirmed)

**`QWidget: Cannot create a QWidget without QApplication`** → `qFatal` →
`abort()`. It is a **SIGABRT, not a segfault**, and it happens during widget
*construction*, not during teardown or garbage collection.

Native backtrace from the crash report
(`~/Library/Logs/DiagnosticReports/python3.12-2026-08-12-145017.ips`):

```
libsystem_c.dylib        abort
QtCore                   QMessageLogger::fatal(char const*, ...) const
QtWidgets                QWidgetPrivate::init(QWidget*, QFlags<Qt::WindowType>)
QtWidgets                QGraphicsView::QGraphicsView(QWidget*)
QtWidgets.abi3.so        Sbk_QGraphicsView_Init
  → src/gui/image_viewer.py:148 in __init__   (super().__init__(parent))
  → tests/core/test_subwindow_right_click_focus.py:49
```

### The mechanism

1. [`tests/core/test_subwindow_lifecycle_controller_slice.py:339-341`](../../../tests/core/test_subwindow_lifecycle_controller_slice.py)
   creates a **bare `QCoreApplication`** when no instance exists:

   ```python
   # Initialize QCoreApplication if not exists to support QTimer.singleShot
   if not QCoreApplication.instance():
       QCoreApplication([])
   ```

2. `QCoreApplication` is a **non-GUI** application object. Widgets cannot be
   created under it.

3. [`tests/conftest.py:37-39`](../../../tests/conftest.py) guards only on
   *existence*, not on *type*:

   ```python
   app = QApplication.instance()
   if app is None:
       app = QApplication(sys.argv)
   ```

   `QApplication.instance()` returns the `QCoreApplication` (non-`None`), so the
   session fixture **declines to create a real `QApplication`**.

4. The next widget-constructing test in that worker aborts the process.

### Why it only shows up under xdist

Serially, some test that needs a real `QApplication` almost always runs before
`test_on_main_window_layout_changed`, so the `QCoreApplication` branch never
fires. Sharding assigns tests to workers in a different order, so a worker can
receive the `QCoreApplication` test **first** — poisoning that worker for every
widget test it is subsequently handed.

This explains every observed symptom: the nondeterminism, the moving victim
(any widget test scheduled after it in that worker), why `--dist loadfile`
didn't help (the poisoning is cross-file), and why serial runs are always clean.

### Minimal reproduction (0.3 seconds, no xdist required)

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest \
  "tests/core/test_subwindow_lifecycle_controller_slice.py::test_on_main_window_layout_changed" \
  tests/core/test_subwindow_right_click_focus.py -s
# QWidget: Cannot create a QWidget without QApplication
# Fatal Python error: Aborted
```

### Hypotheses this replaces

Two earlier diagnoses were wrong and are recorded here so they are not
re-litigated:

- **Not** window-focus stealing between workers (`offscreen` has no display
  server; the assertion never executed).
- **Not** GC-timing-dependent teardown of the session-scoped `qapp` fixture.
  That was this plan's previous root cause and it is incorrect — the abort is at
  construction. **No `deleteLater` drain or teardown surgery is needed.**

---

## Measurements

All on macOS, 18 logical cores (6 performance), `QT_QPA_PLATFORM=offscreen`.

| Config | Time | Result |
|---|---|---|
| serial | 521.98s | 4887 passed, clean |
| `-n 4` **+ fix** | 212s / 215s / 237s | **3 of 3 clean** |
| `-n auto` (18 workers) **+ fix** | 38.38s / 38.28s | **2 of 2 clean** |
| `-n auto` **+ fix + `--cov`** | 48.14s | clean, TOTAL 71.01% |
| `-n 4` pre-fix | 70–75s | crash, 3 of 3 |
| `-n auto` pre-fix | 22–51s | crash, 3 of 5 |

**Read the pre-fix rows with suspicion.** They come from runs that aborted a
worker, and a 7x wall-clock speedup on 4 workers is superlinear — not physically
possible for the same workload. Treat only the post-fix rows as real.

**What CI will actually see:** `ubuntu-latest` has **4 cores**, so CI's `-n auto`
behaves like the `-n 4` row: roughly **8m42s → ~3m30s, a ~2.5x improvement**.
The 38s figure requires an 18-core machine and is not the CI outcome. The
earlier "7–20x" claim in this plan was an artifact of the contaminated numbers.

**Open measurement question:** pre-fix `-n 4` (70s) was ~3x *faster* than
post-fix `-n 4` (212s) for the same test count. Unexplained. The leading
hypothesis is that a real `QApplication` in every worker makes GUI tests take
their full code path where poisoned workers short-circuited. Worth a
`--durations=20` comparison during Phase 2, but it does not affect the go/no-go:
the pre-fix state crashes and is not shippable.

---

## Phase 1 — Safe changes — COMPLETE

All three items are done (items 2 and 3 completed 2026-08-12, uncommitted).

1. **PHI live-repo test.** `test_this_repository_is_clean` is genuinely
   redundant — it runs `check_paths`/`check_contents` over `tracked_files`,
   exactly what `scripts/check_no_phi_artifacts.py` does, and that script is
   already the required `privacy-gates / No PHI artifacts tracked` check *and*
   runs in `pre-push`. **No security coverage is lost.**

   **Measured cost (resolves an earlier open question): ~65s, not ~91s** —
   `check_contents` over 1411 tracked files is 64.7s; `tracked_files` and
   `check_paths` are 0.07s combined. It is ~12% of the serial suite.

   **Done:** converted from unconditional `@pytest.mark.skip` to
   `@pytest.mark.skipif(not os.environ.get("PHI_LIVE_SCAN"), ...)` so it stays
   runnable instead of rotting into dead code. Both paths verified — skipped by
   default (0.06s, reason names both redundant gates), and
   `PHI_LIVE_SCAN=1` runs it green in 65.49s, which independently confirms the
   ~65s measurement and that the live tree is clean.

2. **Refresh the dev-env sync stamp — done.**
   `python scripts/sync_dev_environment.py` recorded the new hash;
   `--check` now exits 0. No packages actually changed (every requirement was
   already satisfied) — only the stamp, which lives in `.venv/` and is not
   tracked.

3. **`MAINTENANCE_LOG.md` entry — done.** Added under a new 2026-08-12 heading
   covering the xdist enablement, the root cause and fix, the measured numbers,
   and the PHI test change, per [`AGENTS.md:71`](../../../AGENTS.md).

---

## Phase 2 — Guarantee one real QApplication per worker (blocks Phase 3)

Small and validated. Phase 2.1 of the previous plan (capture a crash log) is
**done**; its finding is the Root cause section above.

1. **Create the `QApplication` at session start in
   [`tests/conftest.py`](../../../tests/conftest.py)**, before any test can
   create a `QCoreApplication`, holding a module-level reference so it can never
   be collected:

   ```python
   _QAPP = None

   def pytest_configure(config):
       global _QAPP
       from PySide6.QtWidgets import QApplication
       if QApplication.instance() is None:
           _QAPP = QApplication(sys.argv[:1])
   ```

2. **Harden the `qapp` fixture** to check the instance is a real `QApplication`,
   not merely non-`None` — so a stray `QCoreApplication` can never silently
   satisfy the guard again.

3. **Fix the offending test.** In
   [`test_subwindow_lifecycle_controller_slice.py:339-341`](../../../tests/core/test_subwindow_lifecycle_controller_slice.py),
   drop the `QCoreApplication([])` construction and depend on the session
   `qapp` instead. `QTimer.singleShot` works fine under a full `QApplication`.

4. **Optional cleanup:** five modules shadow the session fixture with their own
   module-scoped `qapp` — `test_window_level_controls.py:21`,
   `test_wl_preset_menu_access.py:25`, `test_main_window_fullscreen.py:37`,
   `test_main_window_toast.py:29`, `test_multi_window_layout.py:17`, plus
   class-level `cls._app` in `test_measurement_items.py` and
   `test_arrow_annotation_selection_bounds.py`. These are harmless once step 1
   is in place, but they are duplication that invites the same class of bug.

### Status: implemented 2026-08-12

Steps 1–3 are done in the working tree; step 4 (cleanup) is deferred.

- [`tests/conftest.py`](../../../tests/conftest.py) — `pytest_configure` now
  creates the `QApplication` and holds it in a module-level `_QAPP`; the `qapp`
  fixture checks `isinstance(app, QApplication)` and raises a diagnostic
  `RuntimeError` if a non-GUI application already owns the process.
- [`tests/core/test_subwindow_lifecycle_controller_slice.py`](../../../tests/core/test_subwindow_lifecycle_controller_slice.py)
  — `test_on_main_window_layout_changed` takes the `qapp` fixture; the
  `QCoreApplication([])` construction is gone. The `QCoreApplication` import
  stays, still used for `processEvents()`.

A repo-wide grep confirms **no other bare `QCoreApplication` construction**
exists in `tests/`, `src/`, or `scripts/`, so the landmine is removed rather
than relocated.

**Verified after the fix** (no prototype plugin loaded):

- the 0.3s two-file repro passes (4 passed);
- `tests/core/test_subwindow_lifecycle_controller_slice.py` passes (18 passed);
- full suite at `-n auto`: **4887 passed in 37.95s**;
- `ruff` clean on both edited files.

Prototype `tmp/qapp_probe.py` has been deleted.

**Exit criteria — MET.** `-n 4` clean **20 of 20** consecutive runs:
4887 passed / 15 skipped every run, no failures, no worker crashes,
205.52–233.66s (mean ~211s). Identical pass counts across all 20 runs confirm
no tests were silently lost.

---

## Phase 3 — Enable `-n auto` in CI

`-n auto` is already in `ci.yml` from `4558a53`; this phase is about verifying
it rather than adding it.

1. **Coverage under xdist — verified, no action needed.** A green `-n auto`
   run with `--cov=src --cov-fail-under=65` reports:

   ```
   TOTAL   50705  12473  16472  2770   71%
   Required test coverage of 65% reached. Total coverage: 71.01%
   4887 passed, 15 skipped in 48.14s
   ```

   Coverage combining across workers works correctly and the floor passes with
   room to spare. Note the [`ci.yml:119`](../../../.github/workflows/ci.yml)
   comment claims "local measured TOTAL is ~67%" — the actual figure is **71%**,
   so that comment is stale and worth correcting while editing the file.

   The original concern still holds as a *failure-mode* caveat: a crashed worker
   can drop its collected coverage and stack a spurious `--cov-fail-under`
   failure on top of the real crash. That is a reason to fix crashes rather than
   tolerate them, not a reason to distrust the gate on green runs.

2. **Close the CI-only-flakiness gap.** Add `-n auto` to `pytest.ini`
   `addopts` so local runs match CI. The obvious objection — that this slows
   single-test iteration — is handled: **`-n 0` overrides it** and runs
   in-process (verified: 3 tests in 0.25s with no worker spawn). Document
   `pytest -n 0 path/to/test.py` for quick iteration.

3. **Single source of truth for the pytest command.** This repo has **no
   `Makefile` and no `pyproject.toml`**, so the vehicle is `pytest.ini`
   `addopts` plus [`tests/run_tests.py`](../../../tests/run_tests.py), which
   already forwards extra argv. Putting `-n auto` in `addopts` means CI,
   `run_tests.py`, and bare `pytest` all agree, and the docs describe one
   command instead of three.

4. **Sync the docs.** [`DEVELOPER_SETUP.md:277,299`](../../DEVELOPER_SETUP.md)
   and [`HARNESS.md:75`](../../HARNESS.md) mirror the CI invocation.

5. **Set expectations in the commit message:** ~2.5x on CI's 4 cores, not the
   headline local number.

**Exit criteria:** 20 consecutive green CI runs; coverage TOTAL unchanged.

---

## Phase 4 — Reassessed: premise was wrong, mostly already solved

**Do not implement the module-scoped app fixture.** Profiling disproved the
assumption behind it.

The five slowest tests in
[`tests/test_main_tag_export_union.py`](../../../tests/test_main_tag_export_union.py)
measured 8.95–9.43s each in the serial full-suite run, and this plan attributed
that to constructing `main_module.DICOMViewerApp()`. Direct measurement:

| Context | Cost |
|---|---|
| `DICOMViewerApp()` in isolation | **0.23s** (0.89s first, warm 0.23s) |
| whole file run alone | **3.19s total**, slowest test 0.92s |
| same file after ~1,940 other tests | 4.62–4.75s per test |
| same file after ~4,800 other tests (serial suite) | 8.95–9.43s per test |

The cost is **not** construction — it scales with how many tests already ran in
the process. `cProfile` shows the dominant frame is
`QApplication.setStyleSheet()` inside `main_window._apply_theme` (0.21s of a
0.34s construction), and `setStyleSheet` restyles *every* live widget in the
process. Widgets leak across the session, so each successive
`DICOMViewerApp()` gets more expensive.

Consequences:

- A module-scoped fixture would have delivered far less than the projected ~46s
  while introducing shared mutable state across five tests that monkeypatch the
  app's internals — the exact coupling that produced the Phase 2 crash.
- **Parallelism already fixes most of it.** Spreading tests across workers caps
  per-worker accumulation, which is part of why `-n auto` beats a linear
  speedup prediction.
- The residual lever is widget cleanup between tests (an autouse fixture
  disposing top-level widgets), which would speed up the serial path and reduce
  memory pressure. Worth doing on its own merits; not required for
  parallelization. Measure before committing to it.

---

## Risks and non-goals

- **Non-goal:** masking the crash with `--dist loadgroup` / `xdist_group` /
  rerun plugins. The defect is a real one-line test bug; serializing around it
  would leave the `QCoreApplication` landmine in place for the next person.
- **Risk (now low):** the fix is validated across 5 clean parallel runs, but the
  20-run gate stands — Qt process crashes are exactly the class of bug that
  hides at low sample counts.
- **Risk:** the unexplained pre-fix/post-fix `-n 4` timing gap could mean the
  fix makes some tests genuinely slower. Even at 212s the change is a 2.5x CI
  win, so this is a follow-up, not a blocker.

- **A second, pre-existing ordering bug — found and FIXED 2026-08-12.**
  Running `tests/gui/test_image_viewer_context_menu.py` before
  `tests/test_main_tag_export_union.py` made all five of the latter fail with
  `AttributeError: '_FakeMenu' object has no attribute 'aboutToShow'` at
  [`src/gui/wl_preset_menu.py:111`](../../../src/gui/wl_preset_menu.py).

  **Root cause.** `_install_fake_menu_patches` patched the *global*
  `PySide6.QtWidgets.QMenu` with a `_FakeMenu` stand-in, and then — while that
  patch was live — patched an attribute on `gui.wl_preset_menu`, triggering
  that module's **first** import. Its module-level
  `from PySide6.QtWidgets import QMenu` therefore bound `_FakeMenu`
  permanently: `monkeypatch` restores the attribute on the PySide6 module but
  cannot undo a copy another module already took. `wl_preset_menu.py:127` then
  built a `_FakeMenu` for every later test in the process. The module is
  imported lazily (`main_app_initialization.py:459`,
  `main_window_toolbar_builder.py:437`), which is why the patch window could
  win the race.

  Confirmed by a probe scanning `sys.modules` for non-real `QMenu` bindings:
  `gui.wl_preset_menu.QMenu -> _FakeMenu`.

  **Fix.** Dropped the global `PySide6.QtWidgets.QMenu` patch; the module-local
  patch on `image_viewer_context_menu` is sufficient. Verified: the
  context-menu tests still pass (5 passed), the two-file repro passes
  (10 passed), the 1,947-test subset that previously failed passes, and the
  probe reports no leaked bindings. A comment at the patch site explains why
  the global patch must not come back.

  Verified pre-existing rather than a Phase 2 regression: reverting
  `tests/conftest.py` and the lifecycle test to `4558a53` reproduced it
  identically (5 failed / 1942 passed both ways).
