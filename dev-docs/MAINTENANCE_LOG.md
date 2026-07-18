# Maintenance Log

**Last updated:** 2026-07-18

This file records development and repository-maintenance history that is useful to contributors and agents but is not necessarily user-facing release history.

Use this log for CI, static analysis, harness changes, dependency-verification passes, repo hygiene, doc-garden cleanup, and other maintainer workflow notes. Use [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible product/release changes. Use [`TO_DO.md`](TO_DO.md) only for active backlog items and near-term follow-ups.

## 2026-07-18

- Completed the view state manager Sonar slice
  (`plans/SONARQUBE_VIEW_STATE_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `store_initial_view_state`, `reset_view`,
  `handle_window_changed`, `handle_rescale_toggle`, and
  `handle_viewport_resized`. Added
  `tests/gui/test_view_state_manager_sonar_slice.py`. Fresh analysis: **399**
  priority findings (down from 408); five targeted `S3776` cleared.
- Completed the Sonar MAJOR mechanical sweep
  (`plans/SONARQUBE_MAJOR_MECHANICAL_SWEEP_PLAN_20260718.md`): cleared all open
  `python:S125`, `python:S1066`, and `python:S1172` findings (commented-out
  code, collapsible ifs, unused parameters with signature-safe removals or
  `_ = param` retention). Fresh analysis: **408** priority findings (down from
  454); targeted three MAJOR rules at 0.
- Completed the slice display manager Sonar slice
  (`plans/SONARQUBE_SLICE_DISPLAY_MANAGER_SLICE_PLAN_20260718.md`): extracted
  helpers for `_render_base_image_pipeline`, `_sync_controls_and_metadata`,
  `_render_scene_overlays_annotations`, `display_rois_for_slice`, and
  `handle_series_navigation`. Added
  `tests/gui/test_slice_display_manager_sonar_slice.py`. Fresh analysis:
  **454** priority findings (down from 461); five targeted `S3776` cleared
  (`python:S3776` 282 → 277).
- Completed the ROI coordinator statistics-path Sonar slice
  (`plans/SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md`): extracted
  projection/spacing/ownership helpers for
  `_get_pixel_array_for_statistics`, `update_roi_statistics`, and
  `update_roi_statistics_overlays`; removed dead closure-debug code. Added
  `tests/gui/test_roi_coordinator_statistics.py`. Fresh analysis: **461**
  priority findings (down from 464); targeted stats-path `S3776` cleared.
- Completed the undo/redo annotation-command Sonar slice
  (`plans/SONARQUBE_UNDO_REDO_ANNOTATION_COMMANDS_SLICE_PLAN_20260718.md`):
  extracted add/remove helpers for `MeasurementCommand`,
  `TextAnnotationCommand`, `ArrowAnnotationCommand`, and `CrosshairCommand`.
  Added `tests/test_undo_redo_annotation_commands.py`. Fresh local analysis +
  scoped reporter: **464** active priority findings (down from 472);
  `undo_redo.py` targeted `S3776` findings cleared (293 → 285 overall).
- Completed the first CRITICAL code-smell remediation slice
  (`plans/SONARQUBE_CRITICAL_CODE_SMELL_FIRST_SLICE_PLAN_20260718.md`):
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
