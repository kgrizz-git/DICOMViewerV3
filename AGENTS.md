# AGENTS — Cursor team layout

This repository defines a **hub-and-spoke** subagent team for Cursor. Subagents live in `.cursor/agents/`; shared procedures live in `.cursor/skills/`. A **portable mirror** plus a **how-to guide** (creating agents/skills, research extensions, syncing) lives in **[agents_and_skills/README.md](agents_and_skills/README.md)**.

## Quick use

- Invoke explicitly: `/orchestrator …`, `/planner …`, `/coder …`, etc. (see [Cursor Subagents](https://cursor.com/docs/context/subagents)).
- Ask the main Agent to **delegate** using these roles; the **orchestrator** reads **`plans/orchestration-state.md`** first and routes complex work.
- For **long-horizon** work: keep invoking **`/orchestrator`** until `plans/orchestration-state.md` shows phase **`complete`** or **`blocked`** (or add a user rule to that effect). Cursor does not auto-chain subagents; the state file + HANDOFF blocks carry continuity across turns.

## Roles and artifacts

| Role | Primary outputs | Notes |
|------|-----------------|--------|
| orchestrator | **`plans/orchestration-state.md`** (goal → next action), assignments, git/cloud approvals, `VERSION` / `CHANGELOG.md` only | No product code; central coordinator |
| planner | `plans/*.md` | Phases, task graph, gates, questions for user |
| coder | Source, tests when planned | Updates plan checkboxes; may propose branch / cloud batch |
| ux | UX assessment | Playwright, screenshots; HANDOFF to orchestrator |
| reviewer | Review verdict, merge recommendation, plan checkbox updates | Lints; merge gate |
| secops | `assessments/security-assessment-*.md` | Scans, findings; may request cloud for heavy scans |
| tester | `logs/test-ledger.md` | No source/test edits to fix failures; may request cloud for long suites |
| docreviewer | `logs/docs_log-*.md` (or `docs-assessments/` per agent rules) | Does not edit product files |
| docwriter | Docs under `docs/`, `README`, etc. | Then suggest docreviewer |

## Skills map

| Skill folder | Used by |
|--------------|---------|
| `team-orchestration-delegation` | orchestrator; **all agents** (HANDOFF format, state file rules) |
| `plans-folder-authoring` | planner |
| `coder-implementation-standards` | coder |
| `ux-evaluation-web` | ux |
| `reviewer-spec-alignment` | reviewer |
| `security-scanning-secops` | secops |
| `test-ledger-runner` | tester |
| `documentation-review-write-handoff` | docreviewer, docwriter |
| `python-venv-dependencies` | any role running Python tooling |

Subagent files include a **“Load these skills”** section; the Agent should read those skill folders when executing that role.

## Flow (typical)

```mermaid
flowchart TD
  U[User goal] --> O[orchestrator]
  O --> P[planner]
  P --> O
  O --> C[coder]
  C --> O
  O --> T[tester]
  O --> R[reviewer]
  O --> X[ux]
  O --> S[secops]
  O --> DR[docreviewer]
  O --> DW[docwriter]
  DW --> O
  DR --> O
  T --> O
  R --> O
  X --> O
  S --> O
```

Parallel branches (e.g. **tester** + **secops**) are fine when they do not race on the same files or dependency manifests—**orchestrator** decides (see task graph in plans).

## Moving to global Cursor config

Copy to your user directory (same structure):

- `.cursor/agents/*.md` → `~/.cursor/agents/`
- `.cursor/skills/*/` → `~/.cursor/skills/`

Project-level definitions **override** user-level on name conflicts. Keep repo-specific paths (`plans/`, `logs/`, `assessments/`) in plans or orchestration notes when you globalize.

## Related notes in this repo

- [info/agent-orchestration-and-skills-guide.md](info/agent-orchestration-and-skills-guide.md) — broader orchestration and skills ecosystem context.
- [info/agent-orchestration-and-skills-guide.md](info/agent-orchestration-and-skills-guide.md) — broader orchestration and skills ecosystem context.
- [info/agents-skills-tools-collection.md](info/agents-skills-tools-collection.md) — curated collection of agent/skill tool links and local definitions.
- [info/cross-repo-reuse-agents-skills.md](info/cross-repo-reuse-agents-skills.md) — guide for reusing agents and skills across repos and IDEs.
