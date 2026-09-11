# User docs platform pilot and sync harness plan

**Created:** 2026-09-11  
**Last updated:** 2026-09-11  
**Status:** Not started (DeepSeek plan review applied 2026-09-11)  
**Priority:** P2 (Next up slot 3)  
**Parent plan:** [Documentation workflow and freshness](DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md) — implements Phase 3 pilot, one enforcement gap, and the platform decision record for Phase 4–5.  
**TO_DO ref:** Next up slot 3; Documentation section in [`TO_DO.md`](../../TO_DO.md).

**Review:** OpenCode Nvidia DeepSeek V4 Pro 0813 (2026-09-11) — verdict **ready-with-fixes**; M1–M2 / S1–S3 applied below before Phase A.

---

## Goal

Deliver **professional, navigable end-user documentation** without weakening the
repository's accuracy controls. Canonical sources stay in-repo Markdown and
in-app HTML; any site generator is **generated output only**.

This plan bundles three related workstreams that were discussed together:

1. **MkDocs Material proof of concept** — local static site from existing
   `user-docs/` with search, sidebar nav, and offline preview.
2. **Docs-impact sync harness** — advisory automation so UI/help changes surface
   missing documentation updates before merge.
3. **Platform decision record** — written adopt/defer/reject outcome after the
   pilot (MkDocs vs Mintlify vs status quo), including privacy and offline
   bundle implications.

Human review remains authoritative for user-facing claims. No third-party
documentation GitHub App on this application repository.

---

## Constraints (non-negotiable)

1. **Do not migrate or delete** canonical Markdown under `user-docs/` during the
   pilot; generated `site/` output is disposable until adoption.
2. **Privacy:** no connection of this repo to hosted doc builders (Mintlify,
   GitBook, etc.) until scope, permissions, retention, and data handling are
   reviewed and explicitly approved. If Mintlify is piloted later, use a
   **documentation-only mirror repository** per the parent plan's Mintlify scope
   rule.
3. **Existing gates stay:** `check_user_docs_links.py` remains blocking CI;
   new checks start **advisory** until false-positive rates are reviewed.
4. **In-app Help parity:** `resources/help/quick_start_guide.html` and
   `doc_urls.py` remain first-class mirrors; the pilot must not orphan them.
5. **URL alignment:** MkDocs `repo_url` / `edit_uri` must target the **same**
   `main` + `user-docs/` paths as `USER_DOCS_GITHUB_PREFIX` in
   [`src/utils/doc_urls.py`](../../../src/utils/doc_urls.py)
   (`https://github.com/kgrizz-git/DICOMViewerV3/blob/main/user-docs`).

---

## Current baseline

| Asset | Role |
|-------|------|
| `user-docs/*.md` (12 topic guides) | Canonical end-user Markdown |
| `resources/help/quick_start_guide.html` | Canonical in-app Quick Start (DOC-03) |
| `scripts/check_user_docs_links.py` | Blocking link + `src/` path check (CI) |
| `scripts/check_doc_feature_coverage.py` | QAction → doc mention heuristic (report-only) |
| `scripts/check_documentation_freshness.py` | Inventory/triage/assessment age (advisory CI) |
| `tests/test_doc_urls_resolve.py` | Help filenames + Quick Start `{doc_*}` placeholders |

Feature-coverage report: **99.1%** (only **Exit** intentionally omitted).
Phase 2 slice **2a** (eight user-facing inventory rows needing a running UI)
remains open in the parent plan — complete in parallel, not blocked by this
pilot.

**Known MkDocs gap (M1):** `user-docs/` is **not** self-contained. Four
cross-boundary links point at `../dev-docs/info/` (see
[`TO_DO.md`](../../TO_DO.md) P2 “Make `user-docs/` fully self-contained”):

| Source | Target |
|--------|--------|
| `USER_GUIDE.md` | `../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` |
| `USER_GUIDE_3D.md` | `../dev-docs/info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md` |
| `USER_GUIDE_QA_PYLINAC.md` | `../dev-docs/info/PYLINAC_CATPHAN_AND_NUCLEAR_MODULES.md` |
| `USER_GUIDE_QA_PYLINAC.md` | `../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` |

With `docs_dir: user-docs`, MkDocs will **not** copy those targets into `site/`,
so the generated site has dead links. `check_user_docs_links.py` still passes
because it resolves against the repo source tree. Phase A must **record** this
as a known adoption blocker (do not “fix” by rewriting guides in the PoC);
closing it is a separate TO_DO / Phase C precondition, not a Phase A rewrite.

---

## Phase A — MkDocs Material proof of concept

**Implements:** parent plan [Phase 3 — Local static documentation pilot](DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#phase-3--local-static-documentation-pilot).

Work on the current docs branch (or an isolated worktree); do not rewrite source
guides until navigation structure is approved.

**Intentional omission vs parent Phase 3:** no `mkdocstrings` sample in this
pilot (API reference is out of scope for end-user docs). Parent Phase 3’s
`mkdocstrings` checkbox remains deferred, not silently claimed done.

### A1. Scaffold (read-only pilot)

- [ ] Confirm `site/` is gitignored (`/site` already in `.gitignore`). Do **not**
  stage generated output. Add `docs/site/` only if a nested config is used.
- [ ] Pin doc-build dependencies in `requirements-dev.txt` only (`mkdocs`,
  `mkdocs-material`); document local preview in Verification below.
- [ ] Add `mkdocs.yml` at repo root with:
  - `docs_dir: user-docs`
  - `site_name` matching the product name
  - `repo_url: https://github.com/kgrizz-git/DICOMViewerV3`
  - `edit_uri: edit/main/user-docs/` (same repo/branch/path family as
    `USER_DOCS_GITHUB_PREFIX` / `doc_urls.py` — Constraint 5)
  - **Navigation** from the hub Topics table in `USER_GUIDE.md`:
    - **Home / hub** → `USER_GUIDE.md` (this is “Getting started” for the PoC;
      in-app Quick Start HTML is out-of-tree and is **not** a MkDocs page —
      mention it in the hub prose only)
    - Configuration, Layouts, Annotations, Export, Tags, Shortcuts,
      Anonymization, MPR, 3D, QA/pylinac, Fusion technical doc
  - MkDocs Material theme: search, dark mode, table of contents depth
- [ ] After scaffold: run `python scripts/check_user_docs_links.py` (source-tree
  links). Separately, after `mkdocs build`, **list** dead `../dev-docs/` (and
  `../CHANGELOG.md`) links in the generated site and record them in A3 — do not
  treat source-link CI as proof that the site is clean.

### A2. Evaluate pilot quality

- [ ] Local preview (`mkdocs serve`): sidebar discoverability, full-text search,
  mobile width, code blocks, heading hierarchy vs flat GitHub rendering.
- [ ] **Offline bundle:** `mkdocs build` → static `site/`. Open `index.html`
  via **`file://`** and confirm (1) pages render and (2) **client-side search
  works** (Material’s `search_index.json` can fail under `file://` CORS — treat
  that as a measured finding for the offline/installer argument). Also try a
  local static server for comparison.
- [ ] Accessibility spot-check (heading order, contrast in dark mode, keyboard
  nav to search).
- [ ] Estimate maintainer cost: edit workflow, build time, release packaging
  hook (feeds TO_DO offline-bundle item).

### A3. Pilot exit artifact

- [ ] Write a short **Pilot result (Phase A)** section at the bottom of this
  plan (or a dated note in `dev-docs/doc-assessments/`) with screenshot paths
  under `tmp/` only — **never commit PHI screenshots**. Cross-ref
  [`PHI_PII_REPOSITORY_GUARDRAILS.md`](../../PHI_PII_REPOSITORY_GUARDRAILS.md)
  before any future README/media admit.
- [ ] Explicitly list cross-boundary / out-of-tree link findings from A1.
- [ ] **Provisional** recommendation only: lean **adopt MkDocs locally**,
  **defer**, or **needs different presentation** (Mintlify). Config may be
  **retained provisionally** or removed; the binding adopt/defer/reject
  decision is **Phase C**, not A3.

**Exit:** pilot builds reproducibly; provisional recommendation + known-gap
list recorded; config retained provisionally or removed pending Phase C.

---

## Phase B — Docs-impact sync harness

**Implements:** parent plan [Enforcement gaps — docs-impact report](DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#enforcement-gaps-to-build) and feature-coverage PR surfacing.

### B1. `scripts/check_docs_impact.py` (new)

- [ ] Inspect `git diff` (staged or `origin/main...HEAD`) for paths that imply
  user-visible documentation risk, for example:
  - `src/gui/`, `src/main_app_*.py`, `main_window_menu_builder.py`
  - `src/utils/config/`, shortcut registration, export/privacy dialogs
  - `resources/help/`, `src/utils/doc_urls.py`
- [ ] Path matching is intentionally coarse (comment-only edits under `src/gui/`
  may warn). That is acceptable while advisory.
- [ ] When matched, **warn and request** (do **not** hard-require until
  promoted) **either**:
  - a change under `user-docs/`, `resources/help/`, or `CHANGELOG.md`
    (user-visible), **or**
  - an explicit declaration: `docs-impact: not needed — <reason>`
    - Prefer parsing from `--pr-body-file` or `GITHUB_PR_BODY` in CI
    - Document that **local/pre-push runs without a PR body** should pass the
      same line via `--pr-body-file` or a commit/topic note; without it the
      check only **warns** (exit 0) unless `--strict`
- [ ] Exit **0** with warnings by default; optional `--strict` for local/pre-push
  use after false-positive review.
- [ ] Add `tests/test_check_docs_impact.py` with synthetic diffs.

### B2. Feature-coverage on UI changes

- [ ] When Phase B1 triggers on UI paths, also run
  `check_doc_feature_coverage.py` and print uncovered action labels (no blanket
  `--fail-under` threshold).
- [ ] Wire into CI as a **non-blocking** step (or PR comment when available);
  mirror pattern of advisory `check_documentation_freshness.py`.

### B3. Harness documentation

- [ ] Document commands in [`HARNESS.md`](../../HARNESS.md) and
  [`dev-docs/README.md`](../../README.md#quality-checks-documentation).
- [ ] Add PR template reminder cross-link if not already satisfied by B1's
  `docs-impact` convention.
- [ ] Add tool to `security/security-tool-inventory.json` only if the check
  invokes external services (it should not).

### B4. Optional follow-up (not required for this plan's exit)

- [ ] Shortcut parity script: compare `USER_GUIDE_SHORTCUTS.md` tables to
  registered shortcuts in code.
- [ ] Promote `check_documentation_freshness.py --strict` after parent plan
  Phase 2 clears unowned `Baseline` rows.

**Exit:** advisory docs-impact check runs in CI on relevant diffs; tests green;
maintainers know the `docs-impact:` escape hatch (PR body **or** local
`--pr-body-file`).

---

## Phase C — Platform decision record

**Implements:** parent plan [Phase 4–5 adoption gate](DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md#phase-4--conditional-externalgenerative-tool-evaluation) in minimal form.

After Phase A pilot and Phase B harness land, record an evidence-backed decision.

**Phase 5 gate inheritance:** a provisional “lean adopt” from A3 is **not**
sufficient to adopt. C2 must explicitly check parent Phase 5 preconditions
(inventory assessed or bounded deferred, high-priority accuracy findings owned,
canonical vs generated/rollback documented, privacy/licensing review, build/link
checks preserved, maintainer owner/cadence). Slice **2a** still open means any
MkDocs “adopt” stays **contingent** on that gate — pilot look-and-feel alone
cannot clear it.

### C1. Decision matrix

| Criterion | MkDocs Material (local) | Mintlify (hosted, docs-only repo) | Status quo (Markdown + in-app HTML) |
|-----------|-------------------------|-----------------------------------|-------------------------------------|
| Professional appearance | Good | Excellent | Adequate in GitHub / plain files |
| Offline / bundled in installer | Strong (verify `file://` search) | Weaker; export-dependent | Strong for HTML; weak for full guide set |
| Privacy / repo access | No external access | Requires review + separate repo | No external access |
| Maintainer cost | Low (pip, local build) | Medium (sync + hosted pipeline) | Lowest |
| Search / nav | Strong | Strong | Weak without a viewer |
| Self-contained `user-docs/` | Gap until TO_DO P2 closed | Same content gap | Source links OK in-repo |

### C2. Record outcome

- [ ] Add a **Platform decision** section to this plan (or a subsection in the
  parent plan) with: **adopt / defer / reject** per candidate, owner, and next
  action — and a checkbox that **parent Phase 5 preconditions** are met or
  explicitly waived with reason.
- [ ] If **MkDocs adopted:** add offline bundle step to release docs
  (`BUILDING_EXECUTABLES.md`); keep generated `site/` gitignored; address or
  schedule the cross-boundary link gap before shipping a bundled site as
  “complete.”
- [ ] If **Mintlify deferred:** document trigger to re-evaluate (e.g. after
  first public release or when a docs-only mirror repo is approved).
- [ ] Update Next up slot 3 and parent plan Phase 3/4 checkboxes accordingly.

**Exit:** written decision linked from `TO_DO.md` and parent workflow plan; no
ambiguous "still evaluating" state.

---

## Sequencing

```mermaid
flowchart LR
  A[Phase A MkDocs PoC] --> C[Phase C Decision record]
  B[Phase B Sync harness] --> C
  P[Parent Phase 2 slice 2a] -.-> C
```

- **Phase A and B can proceed in parallel** (different files; no conflict).
- **Phase C** requires A's pilot artifact and B's harness at least at advisory
  CI wiring; parent Phase 2 slice 2a can continue in parallel but should be
  noted in the decision if accuracy gaps remain.

---

## Verification

```bash
# After any user-docs or harness change
python scripts/check_user_docs_links.py
python scripts/check_doc_feature_coverage.py
python -m pytest tests/test_user_docs_links.py tests/test_doc_urls_resolve.py -q

# Phase A (from repo root, after pip install -r requirements-dev.txt)
mkdocs serve    # local preview
mkdocs build    # offline site/ artifact (gitignored)
# Then open site/index.html via file:// and confirm search

# Phase B
python scripts/check_docs_impact.py
python scripts/check_docs_impact.py --pr-body-file /path/to/body.txt
python -m pytest tests/test_check_docs_impact.py -q
```

Before adopting MkDocs in CI or release packaging: update
`security/security-tool-inventory.json` if required and run
`python scripts/check_security_tool_inventory.py`.

---

## Completion criteria

- [ ] Phase A pilot result recorded; MkDocs builds from current `user-docs/`
      without moving canonical sources; known dead-link list captured.
- [ ] Phase B `check_docs_impact.py` merged with tests and advisory CI step.
- [ ] Phase C platform decision recorded (MkDocs / Mintlify / status quo),
      including Phase 5 gate status.
- [ ] `HARNESS.md`, `dev-docs/README.md`, and parent workflow plan cross-links
      updated.
- [ ] Next up slot 3 in `TO_DO.md` updated to point at this plan's status.

When all criteria are met, archive or narrow this plan per
[`TO_DO.md`](../../TO_DO.md) tracking rules and continue standing freshness
practice in the parent plan.

---

## Pilot result (Phase A)

*(Filled when Phase A exits.)*
