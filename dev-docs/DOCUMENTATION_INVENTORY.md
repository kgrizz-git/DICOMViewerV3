# Documentation inventory and review register

**Last updated:** 2026-09-04  
**Status:** Living register — update it in the pull request that changes a
listed product surface, or record an explicit deferral in
[`DOCUMENTATION_TRIAGE.md`](DOCUMENTATION_TRIAGE.md).

## Purpose and operating rules

This is the current-state index for documentation that describes the shipped
application or its maintenance contracts. It answers four questions without
reconstructing Git history: which source is canonical, which copies can drift,
what code or product change triggers review, and what evidence establishes the
current claim is accurate.

- **Canonical** means the source that must be updated first. A mirror is never
  silently treated as independent documentation.
- **Steward** is the PR author plus the maintainer reviewing the affected code
  area; it is a role, not a claim that one person permanently owns every page.
- **Accuracy evidence** is required when a claim or behavior changes. Automated
  checks detect limited structural regressions; code, tests, and the running UI
  remain the authority for factual accuracy.
- **Review state** is updated only after the stated evidence has been checked.
  `Baseline` means inventoried, not certified accurate. `Assessed` means the
  listed surface was reviewed against its evidence during the named assessment.
- **Cadence** is event-based: review a row whenever its listed trigger changes,
  and sample all relevant rows at each minor/major-release or substantial
  UI/Help assessment. A row with an unresolved `pending-triage` or `deferred`
  item must be revisited at the next relevant assessment.
- Historical snapshots live in [`doc-assessments/`](doc-assessments/). Git
  history records the precise revision and change history of this register and
  its sources; do not edit old assessment records to rewrite their conclusions.

## Current inventory

| ID | Audience / subject | Canonical source | Mirrors or coupled sources | Change trigger and steward | Accuracy evidence / required checks | Review state |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-01 | New users: project overview, install, first launch | [`README.md`](../README.md) | `USER_GUIDE.md`; release/install guidance | Launch, packaging, supported-platform, onboarding, or prominent-feature change; relevant feature PR author | Run instructions against the supported launch path; verify release/version links; `check_user_docs_links.py` | Baseline 2026-09-04 |
| DOC-02 | Users: guide hub, topic discovery, core workflows | [`user-docs/USER_GUIDE.md`](../user-docs/USER_GUIDE.md) | README; Quick Start HTML; Help → Documentation route | New/changed user workflow, menu, shortcut, or topic; UI-feature PR author | Exercise the UI path and compare labels/shortcuts; confirm all topic links; link check | Baseline 2026-09-04 |
| DOC-03 | Users: Quick Start | [`user-docs/USER_GUIDE.md`](../user-docs/USER_GUIDE.md) section and linked topics | [`resources/help/quick_start_guide.html`](../resources/help/quick_start_guide.html); [`src/utils/doc_urls.py`](../src/utils/doc_urls.py) | Onboarding, loading, layout, Help HTML, or URL-routing change; UI/help PR author | Open the in-app Quick Start and every linked topic; compare steps with UI; link check | Baseline 2026-09-04 |
| DOC-04 | Users: settings, preferences, import/export customizations | [`user-docs/CONFIGURATION.md`](../user-docs/CONFIGURATION.md) | settings dialogs; configuration defaults/persistence code | New/changed setting, default, persistence, reset, import, or export; settings-feature PR author | Compare labels, default, persistence, and error behavior with code/tests and running UI; link check | Baseline 2026-09-04 |
| DOC-05 | Users: navigation, panes, layouts | [`user-docs/USER_GUIDE_LAYOUTS.md`](../user-docs/USER_GUIDE_LAYOUTS.md) | `USER_GUIDE.md`; menus/toolbars; Quick Start HTML; related [`USER_GUIDE_SHORTCUTS.md`](../user-docs/USER_GUIDE_SHORTCUTS.md) (see DOC-16) | Pane, layout, navigation, toolbar, or context-menu change; UI-feature PR author | Exercise each changed command; compare visible label/path; coverage report + link check | Baseline 2026-09-04 |
| DOC-06 | Users: annotations and measurements | [`user-docs/USER_GUIDE_ANNOTATIONS.md`](../user-docs/USER_GUIDE_ANNOTATIONS.md) | `USER_GUIDE.md`; annotation dialogs/toolbars | Annotation/measurement behavior, units, export, persistence, or shortcut change; annotation-feature PR author | Exercise the workflow with representative data; verify units, save/export behavior, and UI labels; link check | Baseline 2026-09-04 |
| DOC-07 | Users: MPR, cine, projections | [`user-docs/USER_GUIDE_MPR.md`](../user-docs/USER_GUIDE_MPR.md) | `USER_GUIDE.md`; MPR dialogs/controllers | MPR, cine, projection, slab, orientation, or sync change; MPR-feature PR author | Exercise changed workflow and verify menu/dialog labels, defaults, units, and output; coverage report + link check | Baseline 2026-09-04 |
| DOC-08 | Users: 3D viewing | [`user-docs/USER_GUIDE_3D.md`](../user-docs/USER_GUIDE_3D.md) | `USER_GUIDE.md`; 3D Help action/dialogs | 3D controls, rendering mode, supported input, or 3D Help change; 3D-feature PR author | Exercise affected controls with a safe fixture; compare Help route and labels; link check | Baseline 2026-09-04 |
| DOC-09 | Users: fusion | [`user-docs/IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md`](../user-docs/IMAGE_FUSION_TECHNICAL_DOCUMENTATION.md) | [`resources/help/fusion_technical_doc.html`](../resources/help/fusion_technical_doc.html); fusion Help route | Fusion alignment, opacity, supported modalities, resampling, output, or Help change; fusion-feature PR author | Exercise the changed workflow; compare technical claims with code/tests; check HTML/Markdown parity manually | Baseline 2026-09-04 |
| DOC-10 | Users: anonymization | [`user-docs/USER_GUIDE_ANONYMIZATION.md`](../user-docs/USER_GUIDE_ANONYMIZATION.md) | `USER_GUIDE.md`; privacy/anonymization dialogs and export code | Privacy/anonymization workflow or format change; privacy-feature PR author | Use synthetic/de-identified fixtures; verify warnings, defaults, and privacy claims against code/tests; link check | Baseline 2026-09-04 |
| DOC-11 | Users: in-app documentation routing | [`src/utils/doc_urls.py`](../src/utils/doc_urls.py) | Help actions, `resources/help/`, `user-docs/` URLs | Any Help action, hosted-prefix, anchor, or offline-doc change; help/release PR author | Exercise every changed action; verify resolved URL/path and anchor; link check where Markdown applies | Baseline 2026-09-04 |
| DOC-12 | Users: About, disclaimer, support/product identity | [`src/gui/dialogs/about_dialog.py`](../src/gui/dialogs/about_dialog.py) | README; release metadata; Help disclaimer action | Version, copyright, support, safety/disclaimer, or product-link change; release/UI PR author | Open About and Disclaimer; compare version/links with `src/version.py` and release guidance | Baseline 2026-09-04 |
| DOC-13 | Contributors: contribution workflow | [`dev-docs/CONTRIBUTING.md`](CONTRIBUTING.md) | `AGENTS.md`; CI scripts; test commands; related setup/harness docs (see DOC-20, DOC-21) | Contributor, CI, dependency, or PR-workflow change; maintenance PR author | Execute changed command/path in the project venv; `check_repo_harness.py`; applicable link check | Baseline 2026-09-04 |
| DOC-14 | Developers: architecture map | [`ARCHITECTURE.md`](../ARCHITECTURE.md) | module tree; public/high-risk docstrings; related source/code-doc indexes (see DOC-22, DOC-23) | Module move, boundary, public contract, mixin/facade, or architectural refactor; code-area PR author | Compare imports/call paths and tests; `check_architecture_boundaries.py`; targeted docstring review | Baseline 2026-09-04 |
| DOC-15 | Maintainers: release checklist | [`dev-docs/RELEASING.md`](RELEASING.md) | this inventory; [`DOCUMENTATION_TRIAGE.md`](DOCUMENTATION_TRIAGE.md); PR template; assessment records; workflow plan | Release policy, docs process, docs checks, or assessment cadence change; release/maintenance PR author | Follow the release checklist; verify inventory/triage updates and assessment reference; harness/link checks as applicable | Baseline 2026-09-04 |
| DOC-16 | Users: keyboard shortcuts | [`user-docs/USER_GUIDE_SHORTCUTS.md`](../user-docs/USER_GUIDE_SHORTCUTS.md) | `USER_GUIDE.md`; menus/toolbars; Quick Start HTML; related [`USER_GUIDE_LAYOUTS.md`](../user-docs/USER_GUIDE_LAYOUTS.md) (see DOC-05) | Shortcut, keybinding, or shortcut-doc change; UI-feature PR author | Exercise each changed shortcut; compare visible label/path; coverage report + link check | Baseline 2026-09-04 |
| DOC-17 | Users: DICOM tags | [`user-docs/USER_GUIDE_TAGS.md`](../user-docs/USER_GUIDE_TAGS.md) | `USER_GUIDE.md`; tag dialogs and preset import/export code | Tag viewer, tag-preset, or tag-export workflow change; tag-feature PR author | Exercise changed tag workflow; verify labels, presets, and export/import behavior; link check | Baseline 2026-09-04 |
| DOC-18 | Users: export and structured reports | [`user-docs/USER_GUIDE_EXPORT.md`](../user-docs/USER_GUIDE_EXPORT.md) | `USER_GUIDE.md`; export/SR dialogs and export code | Export, SR, or output-format workflow change; export-feature PR author | Exercise changed export/SR path with synthetic fixtures; verify files, warnings, and defaults; link check | Baseline 2026-09-04 |
| DOC-19 | Users: pylinac QA | [`user-docs/USER_GUIDE_QA_PYLINAC.md`](../user-docs/USER_GUIDE_QA_PYLINAC.md) | `USER_GUIDE.md`; QA dialogs and QA code | QA workflow, metrics, or export format change; QA-feature PR author | Exercise changed QA path with synthetic/de-identified fixtures; verify outputs and warnings; link check | Baseline 2026-09-04 |
| DOC-20 | Contributors: developer setup | [`dev-docs/DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md) | [`dev-docs/CONTRIBUTING.md`](CONTRIBUTING.md); `AGENTS.md`; install/venv scripts | Environment, install, hook, or local-tooling setup change; maintenance PR author | Execute changed setup command/path in the project venv; applicable link check | Baseline 2026-09-04 |
| DOC-21 | Contributors: agent harness | [`dev-docs/HARNESS.md`](HARNESS.md) | [`dev-docs/CONTRIBUTING.md`](CONTRIBUTING.md); `AGENTS.md`; harness scripts | Harness script, smoke, or agent-workflow change; maintenance PR author | Run `check_repo_harness.py` and any changed harness command; applicable link check | Baseline 2026-09-04 |
| DOC-22 | Developers: source layout | [`dev-docs/SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) | [`ARCHITECTURE.md`](../ARCHITECTURE.md); [`dev-docs/CODE_DOCUMENTATION.md`](CODE_DOCUMENTATION.md) | Module move, controller/signal wiring, or source-tree documentation change; code-area PR author | Compare documented tree/wiring with imports and tests | Baseline 2026-09-04 |
| DOC-23 | Developers: code documentation index | [`dev-docs/CODE_DOCUMENTATION.md`](CODE_DOCUMENTATION.md) | [`ARCHITECTURE.md`](../ARCHITECTURE.md); [`dev-docs/SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md); public/high-risk docstrings | Module index, dialog/help pointer, or code-doc map change; code-area PR author | Compare listed modules/paths with the tree; targeted docstring review where contracts change | Baseline 2026-09-04 |

## Required review protocol

For a changed inventory row, the PR must do one of the following:

1. Update the canonical source and each listed mirror in the same PR, then
   record the evidence in the PR description; or
2. Add a row to the triage ledger with an approved disposition, rationale,
   bounded follow-up, and target inventory ID.

For behavior claims, the reviewer must compare the documentation with the
relevant code and tests and, where a user can observe the behavior, exercise
the UI or a documented smoke path. A green link or docstring-coverage check is
necessary evidence when applicable but is never sufficient evidence of
accuracy.

## Historical record

Each minor/major release and substantial UI/Help change creates a new,
timestamped assessment under [`doc-assessments/`](doc-assessments/) **before**
tagging (or before merging the substantial UI/Help change). It must
cite the inventory IDs sampled, commands run, revision assessed, findings,
triage IDs opened/closed, and any waiver. Git history supplies the immutable
revision trail; the assessment is the human-readable decision record.
