# Plan: Remediate Important Local SonarQube Major Findings

**Last updated:** 2026-07-18
**Status:** Active (staged on `fix/sonarqube-major-findings-20260718`)
**Source analysis:** `2026-07-18T17:12:01+0000`, revision `9484958196fcd183a88407f5f312d77bb521f8df`

## Goal and scope

The local reporter (`scripts/report_local_sonarqube_issues.py`) was extended to
surface MAJOR findings (all types), not only BLOCKER and CRITICAL
BUG/VULNERABILITY. The refreshed scan returned **140** DICOM-Viewer-scoped
findings: 0 BLOCKER, 0 CRITICAL, 25 MAJOR BUG, 1 MAJOR VULNERABILITY, and 114
MAJOR CODE_SMELL.

This plan fixes only the **substantive** findings — the vulnerability and the
genuine logic bugs — in a staged, low-risk way. The 114 CODE_SMELL items and the
lower-risk float-equality duplicates are explicitly out of scope for this pass to
keep the change reviewable and the behavior stable.

## Triage summary

| Rule | Severity / Type | Count | Disposition |
|------|-----------------|-------|-------------|
| `python:S2245` | MAJOR VULNERABILITY | 1 | **Fix — Phase 1 (security)** |
| `python:S3923` | MAJOR BUG (duplicate/identical branch) | 6 | **Fix — Phase 2 (logic bugs)** |
| `python:S1244` | MAJOR BUG (float `==`) | 19 | **Fix core only — Phase 3**; GUI duplicates deferred |
| `python:S*` CODE_SMELL | MAJOR CODE_SMELL | 114 | Deferred (separate cleanup pass) |

## Phase 1 — Security: insecure randomness in the anonymizer

- [ ] `src/utils/deep_anonymizer.py:281` (`python:S2245`): date-shift jitter is
      drawn from the non-cryptographic `random.randint`. Replace with
      `secrets.randbelow(DATE_JITTER_MAX_DAYS + 1)` (or `os.urandom`-based) so the
      batch-wide jitter that hides the real date baseline is not predictable.
- [ ] Keep `random` out of any de-identification path; confirm the module still
      imports and the date-offset unit tests pass.

## Phase 2 — Logic bugs: identical if/else branches (`python:S3923`)

Six sites where both branches of a conditional do the same work, indicating a
copy/paste leftover that drops the intended alternate behavior:

- [ ] `src/core/slice_sync_coordinator.py:195`
- [ ] `src/gui/dialogs/annotation_options_dialog.py:455`
- [ ] `src/gui/dialogs/annotation_options_dialog.py:483`
- [ ] `src/gui/image_viewer_view.py:1295`
- [ ] `src/gui/measurement_coordinator.py:383`
- [ ] `src/gui/measurement_coordinator.py:417`

For each: inspect both branches, restore the intended distinct behavior (or
collapse the redundant `if/else` to a single path), and add/adjust a unit test
that would have caught the dead branch.

## Phase 3 — Numeric correctness: float equality in core imaging math (`python:S1244`)

Scoped to the modules that affect pixel/rescale correctness. Replace exact
`== 0.0` / `!= 0.0` slope/intercept/scale guards with a tolerance check
(`math.isclose(..., abs_tol=...)` or an explicit near-zero sentinel) where a true
divide/slope is involved:

- [ ] `src/core/dicom_window_level.py:113, 174, 381`
- [ ] `src/core/slice_display_lut.py:36`
- [ ] `src/core/volume_renderer.py:129, 1002, 1046`
- [ ] `src/core/window_level_preset_handler.py:42`
- [ ] `src/core/wl_preset_catalog.py:148`

**Deferred (GUI/tooling layer, follow-up pass):** the remaining S1244 sites in
`src/gui/image_viewer_view.py:177, 1078`, `src/gui/view_state_manager.py:443,
492, 693, 762`, `src/gui/volume_viewer_widget.py:1446`,
`src/gui/dialogs/export_dialog.py:697`, `src/tools/angle_measurement_items.py:63`.
Same tolerance pattern, lower risk because they are view-state comparisons rather
than pixel math.

## Explicitly out of scope

- The 114 MAJOR CODE_SMELL findings (e.g. `python:S107`, `python:S1854`,
  `python:S3358`). Track separately; do not mix into this fix branch.
- Re-running the scanner with `--with-coverage` is a verification step, not a
  code change.

## Verification (after each phase)

- [ ] `python -m pytest tests/ -q` green (focus: anonymizer, slice sync, window/level, volume).
- [ ] `ruff` and `basedpyright` clean for touched modules.
- [ ] `python scripts/git_hook_privacy_checks.py --staged` passes (privacy-relevant: Phase 1 touches de-identification).
- [ ] Re-run `python scripts/report_local_sonarqube_issues.py --output tmp/sonar-current-findings.md`
      and confirm the addressed rules no longer appear for the fixed paths.

## Files changed on this branch

- `scripts/report_local_sonarqube_issues.py` — reporter now also fetches MAJOR findings.
- `tests/test_report_local_sonarqube_issues.py` — updated policy-class assertion.
- `dev-docs/plans/SONARQUBE_MAJOR_FINDINGS_REMEDIATION_PLAN_20260718.md` — this plan.
