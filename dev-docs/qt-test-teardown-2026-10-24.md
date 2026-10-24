# Qt test teardown investigation — 2026-10-24

## Outcome and limits

The export module had a reproducible lifetime defect: its final test retained a
parentless `QPushButton` and `VolumeRenderSurface` until interpreter shutdown.
A scoped-widget fixture now releases both after each export test.

That fix alone was insufficient. Crash reports confirm that both the baseline
full-suite run and the export-only patched coverage run crashed workers in
PySide cleanup even though the pytest controllers returned zero. xdist sends
`workerfinished` from its session-finish hook, before interpreter finalization;
its green summary did not establish clean worker exit.

A diagnostic two-worker run found 947 surviving top-level widgets at session
finish (713 and 234), spanning many test modules. Explicit deletion while Python
and QApplication were still active let both workers finish PySide cleanup.
The shared test configuration now performs that deletion at session finish,
including a second sweep for auxiliary windows created by close callbacks.
Per-test scopes remain necessary to avoid stale windows affecting later tests.
The configuration also retains an existing QApplication when a plugin creates
it first, so session cleanup covers both creation paths. No production
application behavior or dependency versions change.

The precise native invalid-pointer cause is not established. The change fixes
the observed test lifetime problem and moves destruction before interpreter
finalization; clean worker exit must be verified independently of pytest's
controller summary.

## Incident evidence

User report: October 22, 2026, 16:23:29 EDT, Python PID 63155, parent Python
PID 63146, responsible application Paseo. Incident:
`F862B41D-7BC6-40B1-88AD-2FC4F7E67774`.

The local matching report is
`~/Library/Logs/DiagnosticReports/Retired/python3.12-2026-10-22-162331.ips`.
Its main-thread path is Python `Py_FinalizeEx` / `atexit`, PySide module
shutdown, `destroyQCoreApplication`, then `QPushButtonWrapper`, `QWidget`, and
`QObject` destruction, ending in EXC_BAD_ACCESS / SIGSEGV. That establishes
failure during interpreter cleanup, not a failed Python assertion or a kernel
panic. The VM summary is virtual address accounting, not evidence of RAM
exhaustion.

The local Claude session record for DICOMViewerV3 contains a command at
20:22:48 UTC (16:22:48 EDT):

```text
python scripts/run_local_sonarqube.py --with-coverage
```

The crashed process launched at 16:22:50. `run_coverage()` launches pytest as a
child of that Python wrapper, and the process loads QtTest and the offscreen Qt
plugin. This strongly supports attribution to the coverage test run, though
the redacted executable paths and lack of a historical command line prevent
absolute PID-to-test attribution. The Sonar scan itself subsequently reported
success; that alone is not a clean bill of health for child-process shutdown.

A census of the retired Python reports for October 22–23 found 51 distinct
incident IDs. All had `Py_FinalizeEx` in the crashing stack; leading frames
included QObject/QPushButton destruction and Shiboken recursive invalidation.
This census does not establish that every report came from this repository.

## Reproduction and mechanism

Installed environment: Python 3.12.10, PySide6 6.12.0, pytest 9.1.1,
pytest-xdist 3.8.0. Tests use the project virtual environment and offscreen Qt.

Running only
`test_button_recovers_after_failed_first_capture` with a session-finish widget
census produced one passing test but two surviving top-level widgets:

```text
VolumeRenderSurface
QPushButton (Save Image…)
```

The full 43-test export module produced the same survivors. The test connects
`surface.image_captured` to a lambda retaining `widget`; `widget` references
both `surface` and the parentless button. The surface fixture calls
`surf.cleanup()`, which releases rendering resources but does not delete the
Qt widget or disconnect that signal. That leaves a reference chain spanning
Qt and Python after the fixture finishes.

Previously, the shared session `qapp` fixture returned a process-wide
QApplication without explicit widget cleanup. Leaked widgets therefore reached
PySide's late interpreter cleanup. Several GUI modules already use scoped
widget cleanup, but the full suite still leaves hundreds of other widgets alive.

## Change and regression

The export module now has an autouse scoped-widget fixture depending on
`qapp`. It establishes the scope before normal test fixtures and cleans up
after the surface fixture has released its render resources. The existing
helper closes and schedules deletion of newly created top-level widgets and
delivers DeferredDelete events while the application is still available.

`tests/test_qt_export_teardown.py` runs the formerly leaking test in a separate
Python process and uses a session-finish probe to fail if any top-level widget
survives. It verifies both the object census and successful process exit. It
failed before the fix despite the inner test passing, and passes after the
fix. It does not assert that the native SIGSEGV reproduces deterministically.

A second subprocess regression intentionally retains a parent QWidget, its
child QPushButton with a Python signal callback, and a parentless QPushButton
past test teardown. A session-finish hook wrapper checks their native wrappers
are invalid after the shared cleanup, and the subprocess must exit successfully. This regression is parametrized
for both the normal application creation path and an earlier plugin-owned
QApplication. The latter reproduced a skipped-cleanup defect: `_QAPP` stayed
None when the application already existed, so the shared hook returned early.
Assigning the existing instance to `_QAPP` fixes that path. An independent
scratch probe failed before the fix with a surviving QPushButton (exit 1);
the focused batch after the fix passes all 46 cases.

Verification:

- Baseline isolated export module: 43 passed, normal process exit, but two
  surviving widgets measured by a separate probe.
- Baseline full suite, two workers: 8,365 passed, 15 skipped, 107.75 seconds,
  controller exit 0; worker PID 70892 crashed at shutdown.
- Regression before fix: failed with the surface and button still alive.
- Fixed focused regression/export/menu batch: 60 passed, 3.18 seconds.
- Fixed full suite, four workers with coverage: 8,366 passed, 15 skipped,
  84% coverage, 57.59 seconds, controller exit 0; workers 74404 and
  74405 crashed at shutdown.
- Ruff on the two changed test files, repository harness, architecture
  boundaries, and agent smoke: passed.
- Shared-cleanup diagnostic full run, two workers: 8,366 passed, 15 skipped,
  89.77 seconds; controller and both workers reached the observer registered
  before PySide import (and therefore executed after its atexit handler). No
  matching crash reports were found.
- Shared-cleanup focused regression/export batch: 45 passed, 1.88 seconds.
- Final shared-cleanup full suite, four workers with coverage: 8,367 passed,
  15 skipped, 84% coverage, 54.81 seconds. Controller PID 93752 and workers
  93753–93756 all reached the observer registered before PySide import. No
  matching native crash reports were found.
- Final Ruff, repository harness, architecture boundaries, agent smoke, and
  `git diff --check`: passed.
- Local baseline/fixed logs and coverage are ignored under `tmp/qt-teardown/`.

## Confirmed full-suite shutdown crashes

The October 24 13:04:59 EDT report (incident
`ACED00E8-94EB-4698-8ECA-2ECB55B86471`, PID 70892) matches the baseline
log creation at 13:03:11 and completion at 13:04:59. Its stack is the same
QPushButton destruction during PySide interpreter cleanup. The coverage run
started at 13:05:31 and produced two further reports at 13:06:28: PID 74405
(incident `AF324632-A715-421D-965B-EF1FCEFE2430`, QPushButton destruction)
and PID 74404 (`8BBF2691-D98E-4276-ADB5-55E2FAEAE173`, Shiboken recursive
invalidation). Earlier claims of normal process exit described only the
controller and were incorrect for its workers.

## Follow-up if a native crash recurs

Keep the new report and the exact pytest command/worker information. Determine
which worker and test shard leaves objects alive, then isolate that shard's
last widget creators and ownership transfers. QObject or Shiboken destruction
at exit may still expose a separate PySide defect or earlier corruption; a
version comparison should use an isolated environment and the project's locked
dependency workflow, not an unreviewed global upgrade.

References:

- [Qt object ownership in Shiboken](https://doc.qt.io/qtforpython-6/shiboken6_generator/typesystem_ownership.html)
- [QObject deferred deletion](https://doc.qt.io/qt-6/qobject.html#deleteLater)

Documentation impact (2026-10-24): reviewed DOC-13, DOC-20, and DOC-21.
Updated testing guidance and maintenance history; no application setup, UI,
Help, release, or user workflow changes require a separate assessment.
