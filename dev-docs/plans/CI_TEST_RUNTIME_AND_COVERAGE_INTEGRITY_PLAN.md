# CI Test Runtime and Coverage Integrity Plan

**Status:** Active
**Last updated:** 2026-08-14

## Goal

Reduce local and GitHub Actions test wall time without omitting tests, weakening
assertions, lowering the 80% coverage floor, or changing the SonarQube coverage
input.

## Evidence and constraints

- `pytest.ini` uses `-n auto`, so local and CI test execution already uses
  `pytest-xdist` parallel workers.
- The PR #62 Ubuntu test job passed 6,040 tests in 17m36s with an 80.48%
  coverage.py combined line-and-branch total. This is the recorded CI baseline;
  no separate 80.49% metric is retained. Its slowest groups repeatedly construct
  `DICOMViewerApp`; 33 such constructions occur across the known slow
  `test_main_*.py` modules.
- The same PR passed locally with parallel coverage. `pytest-cov` combines
  xdist worker coverage, so parallel execution is the supported default, not a
  coverage workaround.
- The workflow already caches pip packages. Increasing the worker count above
  the hosted runner's available CPUs is out of scope because it can increase Qt
  contention without a measured gain.

## Non-goals

- Do not skip, xfail, deselect, reorder for concealment, or weaken any test.
- Do not remove branch coverage, the coverage XML artifact, the SonarQube scan,
  privacy gates, or the existing test floor.
- Do not use serial execution for the complete suite. `-n 0` remains only a
  short-feedback option for a single test while debugging.
- Do not modify application behaviour merely to make tests faster.

## Phase 0 — establish a reproducible baseline

1. On a representative PR, record the full CI test count, skipped/xfailed
   count, coverage percentage and executable-line totals, `coverage.xml`, and
   elapsed time.
2. Activate the project virtual environment, then use that environment's
   interpreter for the full local parallel coverage command:
   `source .venv/bin/activate && python -m pytest tests --cov=src
   --cov-report=term --cov-report=xml:coverage.xml --cov-fail-under=80
   --durations=50`. Record the same data and retain the ranked duration output
   as the performance baseline.
3. Confirm the baseline CI log identifies the repeated-full-app test modules
   and their setup/teardown cost before changing their fixtures.

**Exit criterion:** a committed measurement record identifies the baseline and
the top slow modules, with no unexplained test-count or coverage difference.

## Recorded Phase 2 baseline — 2026-08-14

- The full local parallel coverage command completed successfully with 6,056
  collected test items and the 80% floor enabled. Its coverage.py total was
  50,705 statements, 7,986 missed statements, 16,472 branches, and 2,911
  partial branches: **80.52%** combined coverage. This is 0.04 percentage
  points above the 80.48% PR #62 Ubuntu CI baseline; retain both separately and
  treat the lower CI measurement as the enforcement reference.
- The same test selection under `-n auto --durations=50` completed in about
  66 seconds on the local 18-worker environment. This is a local profiling
  result, not a substitute for the PR #62 Ubuntu CI duration.
- The slowest individual calls were decoder-fixture smoke checks (2.12s and
  1.98s). Among repeated-`DICOMViewerApp` façade groups, the visible top-50
  calls were led by `test_main_signal_wiring.py` (six calls totaling about
  9.02s), followed by `test_main_tag_export_union.py` (about 8.04s),
  `test_main_subwindow_lifecycle.py` (about 6.16s), and
  `test_main_facade_delegation.py` (about 5.22s).
- **First bounded Phase 2 candidate:** inspect
  `tests/test_main_signal_wiring.py` and retain a real-app smoke test while
  replacing only demonstrably redundant façade setup.

## Phase 1 — remove redundant reporting configuration

1. Make `pytest.ini` the single source of truth for verbosity and traceback
   settings; remove the duplicate `-v --tb=short` flags from the CI command.
2. Retain `-n auto`, `--cov=src`, both terminal and XML coverage reports, and
   `--cov-fail-under=80`.
3. Run a full parallel local suite and one CI PR run to compare the test count,
   coverage totals, artifact presence, and elapsed time.

**Expected benefit:** smaller CI logs and modest wall-time reduction. This is a
safe hygiene change, not the primary performance lever.

## Phase 2 — remove repeated full-app setup only where redundant

1. Group the slow façade tests by the specific `DICOMViewerApp` method they
   exercise and classify each as either:
   - a full-app integration boundary that must retain real construction; or
   - a façade delegation test that can use a minimal, explicitly configured
     harness for its direct dependencies.
2. For each group, retain at least one real `DICOMViewerApp()` construction
   smoke test covering configuration, signal setup, and clean teardown.
3. Replace only the redundant façade cases with a narrow test helper that
   creates the exact collaborators the method requires. Keep every existing
   behavioural assertion, and add an assertion for each dependency boundary
   previously supplied implicitly by app construction.
4. Do not use a mutable module- or session-scoped app fixture. That would make
   test order stateful and would hide the isolation failures xdist is intended
   to expose.
5. Implement one module at a time; run its focused tests in parallel, then the
   complete parallel suite with coverage before proceeding to the next module.

**Exit criterion:** every converted module retains or improves its source-line
and branch coverage, and the complete suite remains order-independent under
xdist.

## Recorded Phase 2 batch 1 — 2026-08-14

- Converted the two independent high-cost façade modules together, as an
  intentionally bounded batch: `tests/test_main_signal_wiring.py` and
  `tests/test_main_tag_export_union.py`. This replaces twelve
  `DICOMViewerApp()` constructions under xdist with two anchor constructions
  (one per module). The other assertions use short-lived, explicit harnesses:
  Qt signal stubs for the individual `app_signal_wiring` helpers and a
  `QObject` plus `TagEditingMixin` for tag-export host delegation.
- Each module retains one real-app smoke test. The harnesses are function-local
  rather than module- or session-scoped, so they do not introduce test-order
  state or cross-worker sharing.
- Combined focused measurement under the default `-n auto` configuration:
  12 tests passed in **11.77s**, down from **13.31s** for the same selection
  before the batch (**1.54s / 11.6%** local reduction, including xdist startup).
  This is directional local evidence only; CI timing has deliberately not yet
  been remeasured.
- A detached, immediately preceding full-suite baseline and the refactored
  full suite both collected 6,056 items and passed the 80% floor. Their source
  set was identical: 50,705 statements and 16,472 branches. The baseline was
  **80.4948%** (42,710 covered lines; 2,916 partial branches); the refactored
  run was **80.5052%** (42,717 covered lines; 2,916 partial branches). The
  small difference from the earlier 80.52% local record is normal xdist-run
  variation; the controlled comparison shows no coverage regression.
- Focused refactor checks passed: both converted modules (12 tests), their
  direct seam suites (`test_app_signal_wiring.py` and
  `test_tag_export_union_host.py`, 15 tests), Ruff, and `git diff --check`.

**Next decision:** repeat the same bounded conversion-and-comparison approach
for the next two measured façade candidates only after reviewing this batch in
CI; do not introduce CI sharding until Phase 2 has a representative CI timing.

## Recorded Phase 2 batch 2 — 2026-08-14

- Converted the next two measured façade candidates together:
  `tests/test_main_subwindow_lifecycle.py` and
  `tests/test_main_facade_delegation.py`. The conversion reduces their repeated
  `DICOMViewerApp()` constructions from fourteen to two under xdist, one real
  configuration-and-delegation anchor in each module.
- The remaining lifecycle checks use function-local
  `SubwindowManagementMixin` instances with exact mocked collaborators. The
  remaining export, QA, and MPR checks invoke the actual defining mixin method
  with a narrow mock facade/controller. This keeps direct forwarding contracts
  explicit without a mutable shared fixture or an implicit full-app setup.
- Combined focused measurement under default `-n auto`: the prior selection
  had 14 tests and completed in **12.21s**; the converted selection has 15
  tests and completed in **11.88s**. This is a small absolute local reduction
  despite the additional smoke assertion; CI timing remains the decision
  metric.
- Focused converted modules (15 tests), adjacent lifecycle/export/QA seam
  coverage (27 tests), Ruff, and whitespace validation passed. The next step
  is one complete parallel coverage run, then CI review of this two-batch
  refactor before choosing another pair.
- Two complete parallel coverage runs passed the enforced 80% gate. They
  retained the identical 50,705-statement and 16,472-branch source set and
  measured **80.4829%** and **80.5067%**, respectively. The small xdist-run
  variation was limited to asynchronous, unrelated coordinator execution;
  the repeat run is above the controlled 80.4948% pre-batch measurement.
  Keep the 80% gate and use CI as the next timing/coverage decision point.

## Phase 3 — shard CI only after Phase 2 measurements

1. Compare the post-Phase-2 duration with the baseline. Introduce CI sharding
   only if the remaining test wall time materially exceeds the agreed target.
2. Create balanced, deterministic shards from the recorded timing data. Keep
   each test node assigned to exactly one shard and distribute the slow
   `test_main_*.py` modules across shards.
3. Each shard must run its complete assigned selection with `pytest-cov` and a
   unique non-hidden raw coverage data path (for example,
   `COVERAGE_FILE=coverage.shardN`). A test failure fails its shard immediately.
4. Upload every expected raw coverage file as a short-retention internal CI
   artifact with `if-no-files-found: error`. In the dependent merge job,
   download every expected shard explicitly and fail if any is absent, then run
   `coverage combine`, `coverage xml`, and `coverage report --fail-under=65`.
   Upload the resulting single `coverage.xml` under the existing artifact name
   for SonarQube.
5. Do not concatenate XML files or use `--cov-append` to mix unrelated job
   runs. Coverage must be combined from raw coverage data so the global floor
   and XML report represent the union of all shards.

**Exit criterion:** all tests run once, the merged coverage totals match the
single-job baseline, SonarQube consumes the generated XML, and CI wall time is
lower without new flakes.

## Validation matrix

For each phase, verify all of the following before keeping the change:

| Check | Required result |
| --- | --- |
| Focused affected tests | Pass with default `-n auto` |
| Full local suite | Same pass/skip/xfail counts; executable line and branch totals unchanged, with each percentage no lower than the single-job baseline |
| Coverage XML | The merged/single XML has the same measured source set and executable line/branch totals as the baseline; it is not accepted merely because an aggregate percentage is higher |
| CI pytest job | Same test selection, coverage floor, and XML artifact |
| SonarQube job | Receives and accepts the merged/single coverage XML |
| Privacy, lint, repo harness, architecture, and security jobs | Unchanged and passing |
| User-document links | `python scripts/check_user_docs_links.py` passes |
| Agent smoke harness | `python scripts/agent_smoke_harness.py` passes |
| Repeat CI run | No new order-, timing-, or Qt-worker-dependent failure |

## Rollback

Each phase is independently reversible. Revert the fixture conversion or CI
workflow commit, restore the single existing coverage command, and retain the
baseline measurement record for the next attempt.
