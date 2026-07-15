# Maintenance Log

**Last updated:** 2026-07-14

This file records development and repository-maintenance history that is useful to contributors and agents but is not necessarily user-facing release history.

Use this log for CI, static analysis, harness changes, dependency-verification passes, repo hygiene, doc-garden cleanup, and other maintainer workflow notes. Use [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible product/release changes. Use [`TO_DO.md`](TO_DO.md) only for active backlog items and near-term follow-ups.

## 2026-07-14

- **Optional local SonarQube Community Build runner:** Added `scripts/run_local_sonarqube.py` plus isolated `tools/sonarqube/sonar-project.properties` for opt-in local analysis while preserving SonarQube Cloud Automatic Analysis. The runner uses `SONAR_TOKEN`, preflights the service, selects a native or Docker scanner, records the last successful submission in ignored `.sonar-local/last-analysis.json`, and offers opt-in pytest coverage. It is intentionally excluded from Git hooks and CI because a local scan may be slow.

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
