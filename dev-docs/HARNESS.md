# Agent harness

**Last updated:** 2026-07-12
**Reference:** [OpenAI — Harness engineering](https://openai.com/index/harness-engineering/) (environment design, progressive disclosure, mechanical checks).

This project uses a **human-led, agent-assisted** workflow—not a fully agent-generated codebase. The harness below makes repository knowledge legible and verifiable for Cursor/Codex-style agents.

---

## Layer 1 — Table of contents (`AGENTS.md`)

[`AGENTS.md`](../AGENTS.md) stays short (~100 lines): venv, run/test, orchestration, links. **Do not** paste the full `src/` tree into `AGENTS.md`; use [`ARCHITECTURE.md`](../ARCHITECTURE.md) and [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md).

---

## Layer 2 — Architecture map

| File | Role |
|------|------|
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Domains, dependency rules, “where to change what” |
| [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) | Full `src/` tree, controllers, init order, signal wiring |
| [`DESIGN.md`](../DESIGN.md) | UI tokens and interaction spec |
| [`dev-docs/README.md`](README.md) | Index of developer documentation |
| [`dev-docs/plans/`](plans/) | Active, supporting, and completed implementation plans |
| [`dev-docs/TO_DO.md`](TO_DO.md) | Active product/engineering backlog |
| [`dev-docs/MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md) | Developer-maintenance history for CI, harness, repo hygiene, and similar work |

---

## Layer 3 — Mechanical checks (CI + local)

| Script | What it validates |
|--------|-------------------|
| [`scripts/check_user_docs_links.py`](../scripts/check_user_docs_links.py) | Relative links in `user-docs/` and `dev-docs/README.md` |
| [`scripts/check_repo_harness.py`](../scripts/check_repo_harness.py) | Harness files present, `AGENTS.md` not bloated, `TO_DO.md` freshness, plan paths in `TO_DO.md`, links in harness docs, required **user-docs** topic guides linked from `USER_GUIDE.md` hub |
| [`scripts/check_architecture_boundaries.py`](../scripts/check_architecture_boundaries.py) | AST import-boundary checks for the highest-risk edges in `ARCHITECTURE.md`; existing legacy edges are listed in [`architecture_boundary_baseline.txt`](architecture_boundary_baseline.txt) |
| [`scripts/agent_smoke_harness.py`](../scripts/agent_smoke_harness.py) | Python path, core imports, committed DICOM fixture read; optional Qt headless smoke |
| [`scripts/check_doc_feature_coverage.py`](../scripts/check_doc_feature_coverage.py) | Report-only: maps `QAction` labels in `src/` to mentions in `user-docs/` and lists candidate documentation gaps (heuristic; exit 0 unless `--fail-under RATIO`) |

**CI:** [`.github/workflows/user-docs-links.yml`](../.github/workflows/user-docs-links.yml), [`.github/workflows/repo-harness.yml`](../.github/workflows/repo-harness.yml).

**Pytest:** `tests/test_user_docs_links.py`, `tests/test_repo_harness.py`, `tests/test_architecture_boundaries.py`, `tests/test_agent_smoke_harness.py`, `tests/test_doc_feature_coverage.py`.

**Doc garden:** `python scripts/check_repo_harness.py --doc-garden` prints a non-blocking report for stale harness dates, open TO_DO count, and duplicate `[Unreleased]` changelog headings. Treat it as a triage aid, not a merge gate.

**Feature → doc coverage:** `python scripts/check_doc_feature_coverage.py` lists menu/`QAction` labels not yet mentioned anywhere under `user-docs/` — a heuristic worklist for the documentation audit (some labels are trivial or documented under different wording). Add `--show-covered` to see what is matched, or `--fail-under 0.5` to gate in CI.

**Tracking split / plan archive:** keep [`TO_DO.md`](TO_DO.md) limited to active and near-term backlog items. Remove fully completed rows after the outcome is captured in the right durable place: [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible release changes, [`MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md) for CI / harness / static-analysis / dependency-verification / repo-maintenance history, and `plans/completed/`, `plans/supporting/`, `info/`, or `bug-investigations/` for detailed implementation or investigation records. Move finished implementation plans to `plans/completed/`; leave plans in `plans/supporting/` only when they remain active as dependencies, reference material, or future-scope support for open backlog work.

**Doc dates:** keep `**Last updated:**` dates on living guidance documents when the edit changes policy, workflow, user-facing behavior, or canonical instructions. Do not bump dates for typo-only edits. Completed plans, one-off investigations, changelogs, and dated maintenance-log entries do not need separate date churn unless they already use a living-document date.

---

## Debugging (console traces)

All optional diagnostic **`print`** paths are gated by **`DEBUG_*`** constants in **[`src/utils/debug_flags.py`](../src/utils/debug_flags.py)** (not environment variables). Open that file first when investigating layout, loading, W/L, fusion, MPR, 3D volume, pylinac, or navigation issues — each flag lists the modules it affects.

- Set the relevant flag to **`True`** locally, reproduce, then set back to **`False`** before commit.
- CI workflow **debug-flags-check** (see [`.github/workflows/security-checks.yml`](../.github/workflows/security-checks.yml)) rejects any `DEBUG_*: bool = True` in that file.
- Human policy: [`CONTRIBUTING.md`](CONTRIBUTING.md) (debug flags section).

Agents: also listed in [`AGENTS.md`](../AGENTS.md) repository map and conventions.

---

## Layer 4 — Agent runtime smoke

For UI or integration validation after changes:

1. Activate venv: `.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate`.
2. Run automated smoke: `python scripts/agent_smoke_harness.py --write-report`
3. Optional Qt import smoke: `python scripts/agent_smoke_harness.py --qt-smoke`
4. Launch app: `python src/main.py` or `launch.bat` → option 1.
5. Manual checklist: [`orchestration/AGENT_SMOKE.md`](orchestration/AGENT_SMOKE.md)
6. Full regression: `python -m pytest tests/ -v` (allow several minutes).

Agents with browser MCP can drive the running app per project UX skills; logs and version come from `src/version.py` and test output.

---

## Layer 5 — Multi-agent orchestration

Optional team workflow: `.claude/agents/`, `.claude/skills/team-orchestration-delegation/`, [`plans/orchestration-state.md`](../plans/orchestration-state.md), [`.cursor/rules/orchestration-auto-chain.mdc`](../.cursor/rules/orchestration-auto-chain.mdc) (see [`.cursor/rules/README.md`](../.cursor/rules/README.md)).

Skill: [`.claude/skills/agent-smoke-harness/SKILL.md`](../.claude/skills/agent-smoke-harness/SKILL.md).

---

## Maintaining the harness

When you add a major domain or change bootstrap/signal rules:

1. Update [`ARCHITECTURE.md`](../ARCHITECTURE.md) (domains / where-to-change).
2. Update [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) if files or wiring moved.
3. Bump **Last updated** on edited harness docs when the edit changes policy, workflow, user-facing behavior, or canonical guidance; skip date churn for typo-only edits.
4. Run `python scripts/check_repo_harness.py` and `python scripts/check_architecture_boundaries.py`; fix new failures before merge.
5. When a baseline violation is intentionally refactored away, run `python scripts/check_architecture_boundaries.py --refresh-baseline` and review the removed line.

Future improvements (not required today): autonomous doc-gardening bot, per-worktree launch script with observability hooks.
