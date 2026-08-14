# CI Test Runtime and Coverage Integrity Plan

**Status:** Active
**Last updated:** 2026-08-14

## Goal

Reduce local and GitHub Actions test wall time without omitting tests, weakening
assertions, lowering the 65% coverage floor, or changing the SonarQube coverage
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
   --cov-report=term --cov-report=xml:coverage.xml --cov-fail-under=65
   --durations=50`. Record the same data and retain the ranked duration output
   as the performance baseline.
3. Confirm the baseline CI log identifies the repeated-full-app test modules
   and their setup/teardown cost before changing their fixtures.

**Exit criterion:** a committed measurement record identifies the baseline and
the top slow modules, with no unexplained test-count or coverage difference.

## Phase 1 — remove redundant reporting configuration

1. Make `pytest.ini` the single source of truth for verbosity and traceback
   settings; remove the duplicate `-v --tb=short` flags from the CI command.
2. Retain `-n auto`, `--cov=src`, both terminal and XML coverage reports, and
   `--cov-fail-under=65`.
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
