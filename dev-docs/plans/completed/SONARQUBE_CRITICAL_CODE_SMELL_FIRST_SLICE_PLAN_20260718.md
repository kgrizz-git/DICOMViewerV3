# Plan: First Slice of Local SonarQube Critical Code-Smell Remediation

**Last updated:** 2026-07-18
**Status:** Implemented (first slice complete; remaining backlog deferred)
**Source analysis:** `2026-07-18T20:10:53+0000`, revision
`b2e58c6f6ff0e48011191351223e0660e84ce51a`
**Post-fix analysis:** local scanner submission after Phase 2–3; scoped
reporter returned **472** active priority findings (was 476). Confirmed
`python:S5727` = 0 open and the two targeted `ROICommand` `python:S3776`
findings closed (`S3776` open count 295 → 293).

## Goal

Correct the local reporter's scope and resolve a small, behavior-preserving set
of the highest-impact open SonarQube findings. This is intentionally a first
slice, not an attempt to clear the dashboard in one branch.

## Baseline and scope

The dashboard records 368 CRITICAL code smells (364 open, 4 closed). The 364
open findings are:

| Rule | Count | Disposition in this plan |
|------|------:|--------------------------|
| `python:S3776` cognitive complexity | 295 | Fix two related ROI-command methods only |
| `python:S1192` duplicated strings | 67 | Deferred |
| `python:S5727` constant `None` comparisons | 2 | Fix both |

The widened local reporter now reports all active BLOCKER, CRITICAL, and MAJOR
findings regardless of type. At the source analysis revision this is 476
findings: 364 CRITICAL and 112 MAJOR. The dashboard also has 77 lower-impact
open code smells, which remain out of reporter scope and out of this plan.

This first implementation batch targets four open CRITICAL findings in two
related, testable areas. It does not change product behavior or add a new
complexity gate.

## Phase 1 — Keep priority reporting aligned with the dashboard

- [x] Update `scripts/report_local_sonarqube_issues.py` so its CRITICAL query
      includes all issue types, rather than only BUG/VULNERABILITY. The prior
      filter omitted the dashboard's CRITICAL CODE_SMELL findings.
- [x] Update `tests/test_report_local_sonarqube_issues.py` to assert the all-types
      query, then confirm the live reporter returns 476 active priority findings
      for the source revision.
- [x] Update the local SonarQube setup guidance and maintenance record to state
      the widened scope.

## Phase 2 — Remove two redundant fusion guards (`python:S5727`)

- [x] `src/gui/fusion_coordinator.py:964` contains two findings on
      `stored_scale is not None and stored_offset is not None`. Both variables
      are initialized before the spatial-alignment branches and every reachable
      branch assigns a tuple before the cache write. Remove the redundant
      identity checks and retain the unconditional `set_alignment(...)` call.
- [x] Preserve the early return for an existing cached alignment; it is a
      separate path and must not be changed by this cleanup.
- [x] Add a focused coordinator regression under `tests/gui/` using fake fusion
      handler and controls. Cover both missing pixel spacing and missing image
      position so the cache receives `(1.0, 1.0)` / `(0.0, 0.0)` respectively,
      while user-modified offsets are still not overwritten.

## Phase 3 — Reduce ROI command complexity without changing undo semantics

- [x] `src/utils/undo_redo.py:167` and `:196` (`ROICommand.execute()` and
      `ROICommand.undo()`) each trigger `python:S3776`. Extract private helpers
      for the shared add-to-scene and remove-from-scene operations; keep action
      dispatch in `execute()` / `undo()` explicit.
- [x] Preserve all existing contracts: the ROI list has no duplicate item, the
      graphics item is added or removed only when necessary, resize-handle and
      selected-ROI state are cleared before removal, the statistics overlay is
      removed with the graphics item, and undo restores the saved overlay-visible
      flag before recalculating statistics.
- [x] Extend `tests/test_roi_delete_resize_handles.py` (or add a focused
      `tests/test_undo_redo_roi_commands.py`) to characterize add → undo,
      remove → undo, and redo after removal, including resize handles, selection,
      scene membership, and overlay visibility.

## Explicitly deferred

- The remaining `python:S3776` findings, including MPR, fusion, measurement,
  loading, and multi-window controller flows. Refactor only one behavior domain
  at a time after characterizing it with tests.
- All 67 `python:S1192` findings. In particular, the clustered bundled-font
  registry strings are data definitions, not a reason to reshape the registry
  in this branch.
- The 112 active MAJOR findings and lower-impact code-smell backlog. Track and
  re-triage them after this slice in `dev-docs/TO_DO.md`.
- Any behavioral redesign, complexity threshold, CI gate, or dashboard quality
  profile change.

## Verification and close-out

1. Run the focused reporter, fusion, and ROI command tests, then the relevant
   broader ROI/fusion test modules.
2. Run `python scripts/agent_smoke_harness.py` because this slice touches fusion
   controls and ROI interaction state.
3. Run `python scripts/check_architecture_boundaries.py` and
   `python scripts/check_repo_harness.py`.
4. Submit a fresh local analysis with `python scripts/run_local_sonarqube.py`,
   then run `python scripts/report_local_sonarqube_issues.py
   --expected-revision "$(git rev-parse HEAD)"`. Confirm the two S5727 and two
   selected S3776 findings are no longer open; report the remaining total
   without treating a changed count as a failure of the scoped pass.
5. Record the implementation result in `dev-docs/MAINTENANCE_LOG.md`; keep the
   remaining backlog item below open until a later dedicated slice is complete.
