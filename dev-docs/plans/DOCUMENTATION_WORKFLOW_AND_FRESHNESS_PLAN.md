# Documentation workflow, freshness, and publication plan

**Created:** 2026-09-04
**Status:** Phase 0 complete; Phase 1 first slice in progress (assessment + High remediation batch on branch `docs/documentation-phase1-accuracy-audit`) — no documentation platform selected or installed
**Priority:** P2 evaluation; ongoing user-documentation completeness remains P1

## Goal

Make documentation accurate, findable, and sustainable as the application keeps
changing. Establish evidence and review controls before selecting a documentation
publisher or generator. Human review remains the authority for user-facing claims
and code-docstring correctness.

This extends the completed [Documentation structure and completeness
plan](completed/DOCUMENTATION_STRUCTURE_AND_COMPLETENESS_PLAN.md) and implements
the active `TO_DO.md` documentation-generation workflow item.

## Decisions and constraints

1. **Source of truth remains in-repository Markdown/HTML and code.** A rendered
   site is generated output, never the only editable source.
2. **Documentation accuracy is not a coverage percentage.** `interrogate` can
   guard against docstring-coverage regression, but code/test review must verify
   behavior, parameters, returns, side effects, and error conditions.
3. **No feature is fully documented merely because an AI generator produced a
   page.** Generated material needs an identified owner and normal pull-request
   review.
4. **Privacy controls apply to source, generated output, screenshots, and
   external integrations.** Do not upload or connect the application repository
   to a third-party documentation service until scope, permissions, retention,
   and data handling have been reviewed and explicitly approved.
5. **Keep user and developer audiences distinct.** End users need workflows and
   feature guidance; developers need architecture, contribution, and selected
   API/contract material. This standalone application does not need exhaustive
   library-style API documentation.

## Scope

Included:

- `README.md`, `user-docs/`, `dev-docs/`, relevant release/build guidance, and
  in-app help under `resources/help/`.
- Public-code docstrings and high-risk internal contracts (configuration,
  persistence, privacy boundaries, loading, rendering, export, QA, and cross-
  mixin orchestration).
- Link validation, feature-to-doc coverage, ownership, update triggers, and
  evaluation of MkDocs Material, `mkdocstrings`, Sphinx, Mintlify, and
  DeepWiki-RS/Litho.

Excluded until a later approved decision:

- Publishing a hosted documentation site, granting an external GitHub App
  repository access, or adding a new dependency/tool to CI.
- Mass-rewriting docstrings solely to raise a metric.
- Treating generated architecture prose or diagrams as evidence of current
  behavior.

## Tooling position to validate

| Candidate | Proposed role | Evaluation position |
|---|---|---|
| MkDocs Material + `mkdocstrings` | Local static-site pilot for Markdown user/developer docs; curated Python reference where useful | Preferred starting point |
| Sphinx | Alternative for a future library-like, exhaustive Python API reference | Do not adopt unless that audience becomes primary |
| Mintlify | Optional hosted presentation of a deliberately publishable user-doc subset | Evaluate only after the local workflow is proven and external scope is approved |
| DeepWiki-RS / Litho | One-off, local review aid for architecture discovery | Never a source of truth or unattended documentation writer |

### Mintlify scope rule

A Mintlify source **subdirectory** can limit which docs are published, but it
does not by itself create a repository-permission boundary. If Mintlify is ever
piloted, use a dedicated documentation-only repository containing only approved
publishable material. Do not install its GitHub App on this application
repository merely to select `user-docs/`. Record the exact app permissions,
hosting/retention terms, generated-site review steps, and rollback before any
connection.

## Phase 0 — Establish the baseline and ownership map

- [x] Inventory the active user-facing, developer-facing, and in-app help
  surfaces in [`DOCUMENTATION_INVENTORY.md`](../DOCUMENTATION_INVENTORY.md),
  including audience, canonical source, mirrors, stewardship role, change
  trigger, evidence, and review state. Historical plans, investigations, and
  generated output are not canonical product documentation unless an inventory
  row explicitly adds them.
- [x] Run and preserve the existing `scripts/check_user_docs_links.py` and
  `scripts/check_doc_feature_coverage.py` reports as a dated baseline in
  [`doc-assessment-2026-09-04-164808.md`](../doc-assessments/doc-assessment-2026-09-04-164808.md).
- [x] Capture a scoped `interrogate` baseline for public modules/contracts; do
  not count private boilerplate as a quality goal.
- [x] Define the feature-to-document ownership map through the inventory's
  canonical-source, mirror, stewardship, and trigger fields.

**Exit:** a dated assessment exists under `dev-docs/doc-assessments/`, with
findings only—no content fixes mixed into the assessment.

## Phase 1 — Accuracy and completeness audit

- [x] Use the documentation-assessment template
  ([`templates-generalized/doc-assessment-template.md`](../templates-generalized/doc-assessment-template.md))
  to compare docs with code, UI labels/menu paths, configuration defaults,
  tests, and release behavior.
  First-slice record:
  [`doc-assessment-2026-09-05-111057.md`](../doc-assessments/doc-assessment-2026-09-05-111057.md).
- [ ] Review public docstrings and selected internal contracts for accurate
  signatures, parameters, return values, exceptions, side effects, ownership,
  and initialization/order assumptions.
- [x] Triage each feature→doc candidate gap in
  [`DOCUMENTATION_TRIAGE.md`](../DOCUMENTATION_TRIAGE.md) as: `document`,
  `intentionally-omit`, `duplicate`, `obsolete`, or `deferred`; record the
  rationale, relevant inventory ID, exact canonical destination, and a
  repository-relative follow-up when it is not resolved in the same change.
  `pending-triage` is an intake state, not a resolution.
- [x] When resolving triage rows, replace the shared Phase 0 Follow-up pointer
  (`TO_DO.md#documentation`) with a per-row, discriminating follow-up (exact
  canonical path/section, issue, or bounded batch) so the Follow-up column is
  no longer identical across open rows.
- [x] Revisit inventory **DOC-03** (Quick Start): confirm whether the canonical
  source should remain a `USER_GUIDE.md` section plus linked topics, or whether
  the hub section and
  [`resources/help/quick_start_guide.html`](../../resources/help/quick_start_guide.html)
  roles should be restated (for example, HTML as primary in-app surface with
  the hub as mirror, or a dedicated Markdown canonical). Update the inventory
  row and any mirrors only after that decision.
  **Decision:** canonical = `resources/help/quick_start_guide.html`; mirrors =
  hub orientation + `doc_urls.py`.
- [x] Separate findings by user risk and freshness urgency, then schedule
  documentation edits as bounded follow-up batches.
  High batch applied on this branch; docstring audit remains open.

**Exit:** an approved, prioritized finding list; no claim that all docs are
complete until the listed fixes are reviewed and merged.

## Phase 2 — Freshness controls in normal feature work

- [ ] Add/update contributor guidance requiring a docs-impact decision for
  user-visible behavior, UI labels/shortcuts, configuration, exports, privacy
  workflows, and build/install paths.
- [ ] For each accepted feature batch, update the mapped canonical docs and any
  declared mirror (Quick Guide, in-app HTML, README) in the same pull request,
  update the relevant inventory review state, or record an explicit deferred
  follow-up in the triage ledger.
- [ ] Keep `check_user_docs_links.py` mandatory after user-doc edits; use
  `check_doc_feature_coverage.py` as a triage report rather than an automatic
  truth test.
- [ ] Re-run the full assessment before each minor/major release tag or
  substantial UI/Help merge, as already required by release guidance.

**Exit:** feature changes have a repeatable documentation decision and named
sources, not a best-effort post-release sweep.

### Trigger matrix

| Change | Required review/action | Flag or command |
|---|---|---|
| Any `user-docs/` or `dev-docs/README.md` edit | Check all relative links | `python scripts/check_user_docs_links.py` (already a CI gate) |
| New/changed visible action, toolbar/context-menu item, shortcut, setting, or user workflow | Update the ownership map and canonical docs/mirrors, or record a bounded deferral | `python scripts/check_doc_feature_coverage.py`; review its candidate gaps |
| Public interface or high-risk internal contract change | Verify the docstring against code and tests; update it in the same change when behavior changes | Scoped `interrogate` regression check where a baseline exists; human accuracy review is required |
| Minor/major release or substantial UI/Help change | Create, complete, and link a timestamped assessment before tagging (or before merging a substantial UI/Help change); inventory and audit user, developer, in-app, and relevant code documentation | New timestamped `dev-docs/doc-assessments/doc-assessment-*.md` |

### Living records and history

- [`DOCUMENTATION_INVENTORY.md`](../DOCUMENTATION_INVENTORY.md) is the
  authoritative current-state ownership and evidence register. Do not duplicate
  its rows in assessments; assessments cite the inventory IDs sampled.
- [`DOCUMENTATION_TRIAGE.md`](../DOCUMENTATION_TRIAGE.md) is the current-state
  decision register for feature-coverage and audit signals. Git history keeps
  the rationale and state-transition history for each stable triage ID.
- `doc-assessments/` is an append-only historical record of assessment scope,
  evidence, findings, and waivers. Keep all snapshots; any exceptional pruning
  needs a dated decision in a later assessment.

### Automation follow-up

- [ ] Keep the link check as the blocking CI gate; it already runs on every CI
  pass and needs no path-based reminder.
- [ ] Add a **warning-only** documentation-impact report to pull requests. It
  should inspect the diff for UI/actions, settings, export, privacy, build, and
  public-contract paths, then require either a related documentation change or
  a concise `docs-impact: not needed — <reason>` declaration in the PR body.
  Start warning-only; do not make it blocking until false positives and the
  ownership map have been reviewed.
- [ ] Surface `check_doc_feature_coverage.py` as a PR artifact/comment when a
  relevant UI path changes. Do not impose a blanket percentage threshold: the
  report is label-based and must be triaged by a reviewer.
- [ ] Add a release-checklist assertion that a documentation assessment exists
  after the previous minor/major release (or record an explicit waiver with a
  reason). This is the reminder for periodic accuracy review, not an automated
  substitute for it.

## Phase 3 — Local static documentation pilot

- [ ] In an isolated branch/worktree, build a read-only proof of concept from
  existing Markdown; do not migrate or delete source documents.
- [ ] Prefer MkDocs Material and assess navigation, search, local preview,
  cross-link preservation, and an offline bundle against the current docs.
- [ ] Add a small `mkdocstrings` sample only for stable, useful Python contracts;
  confirm it neither imports unsafe runtime code nor turns private implementation
  details into a maintenance burden.
- [ ] Review generated output for broken links, duplicated content, external
  assets, offline behavior, PHI/PII exposure, and accessibility.
- [ ] Estimate maintenance cost: author workflow, local/CI build time, release
  packaging, versioning, and reviewer responsibility.

**Exit:** a written pilot result and recommendation; remove the pilot or retain
only reviewed source/configuration with an explicit decision.

## Phase 4 — Conditional external/generative tool evaluation

- [ ] **Sphinx:** compare only if the project decides to serve third-party
  library consumers with broad API reference; assess migration and duplicate-
  source cost against the MkDocs pilot.
- [ ] **Mintlify:** before any connection, assess a docs-only-repository option,
  GitHub App least privilege, data handling/retention, deployment/preview
  review, site export/rollback, price, and failure mode. Obtain explicit
  approval for the external integration.
- [ ] **DeepWiki-RS/Litho:** if useful, run only a locally contained, disposable
  architecture-discovery trial with an approved model/data path. Review every
  generated statement and diagram against code; do not commit output without
  human editing and ownership.

**Exit:** an evidence-backed adopt/defer/reject decision for each candidate.

## Phase 5 — Adoption gate

Adopt a platform only when all of the following are true:

- [ ] The audit’s high-priority accuracy/completeness findings have owners and
  planned remediation.
- [ ] Canonical source, generated output, release/version behavior, and
  rollback are documented.
- [ ] Privacy, licensing, external access, and retention review is complete.
- [ ] Build, link, and offline/output checks run reproducibly without weakening
  the existing documentation guards.
- [ ] A maintainer has approved the recurring maintenance owner and cadence.

## Verification

For planning/documentation-only changes, verify local links and plan references
with `rg`/Markdown review and run:

```bash
python scripts/check_user_docs_links.py
python scripts/check_doc_feature_coverage.py
```

Before a real tool adoption, add the tool to
`security/security-tool-inventory.json` as required, run its inventory check,
and add only scoped, reviewable build validation.
