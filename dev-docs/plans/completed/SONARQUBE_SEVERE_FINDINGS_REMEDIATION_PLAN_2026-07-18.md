# Completed Plan: Correct SonarQube Severe-Finding Scope

**Last updated:** 2026-07-18

## Goal and outcome

Make local SonarQube severe-finding reports trustworthy before changing product
code, then remediate only findings proven to belong to DICOM Viewer V3.

This plan is complete. The reported ten findings were not DICOM Viewer issues:
eight BLOCKER findings and one CRITICAL bug belonged to
`weekend-digest-free-apis`, while the CRITICAL vulnerability belonged to
`spotibye`. None of their reported paths exists in this checkout or its
reachable Git history.

The error was report scoping: on the local server,
`projectKeys=dicom-viewer-v3` did not constrain the result to the requested
component. The correct `componentKeys=dicom-viewer-v3` query returned zero
BLOCKER and zero CRITICAL BUG/VULNERABILITY findings.

## Phase 1 — Component-safe reporter

- [x] Added opt-in `scripts/report_local_sonarqube_issues.py`.
- [x] Queries all BLOCKER findings and CRITICAL BUG/VULNERABILITY findings
  through `componentKeys`, with full pagination.
- [x] Fails closed on foreign components, malformed payloads, changing totals,
  incomplete pages, unsafe paths, and mismatched expected revisions.
- [x] Keeps credentials out of URLs, command arguments, console output, and
  persisted reports. Detailed metadata is limited to an explicitly requested
  file under ignored `tmp/`.
- [x] Added mocked-HTTP tests for filters, both severity/type policies,
  pagination, malformed responses, foreign components, token safety, and
  local-output boundaries.
- [x] Documented the canonical command in `dev-docs/DEVELOPER_SETUP.md` and
  registered the entrypoint in `security/security-tool-inventory.json`.

## Phase 2 — Fresh analysis and triage

- [x] Submitted and processed a fresh local SonarQube analysis from this
  remediation branch.
- [x] The final processed analysis was `2026-07-18T17:12:01+0000` for revision
  `9484958196fcd183a88407f5f312d77bb521f8df`.
- [x] Ran the reporter with `--fail-on-findings` and `--expected-revision`.
  It returned zero scoped severe findings and wrote the ignored local evidence
  report `tmp/sonarqube-severe-findings-20260718.md`.
- [x] No product-code finding required triage or remediation. Do not edit the
  foreign `weekend-digest-free-apis` or `spotibye` paths from this repository.

## Verification

- [x] Focused reporter and local-runner tests: 14 passed.
- [x] Ruff and basedpyright: no findings for the changed script and tests.
- [x] `python scripts/git_hook_privacy_checks.py --all` passed.
- [x] Security-tool inventory validation and repository harness passed.
- [x] Final local analysis and component-safe severe-finding report returned
  zero findings for DICOM Viewer V3.

No `CHANGELOG.md` update was needed because this is maintainer tooling and no
user-visible viewer behavior changed.
