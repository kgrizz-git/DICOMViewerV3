---
name: team-orchestration-delegation
description: >-
  Coordinates multi-subagent software work—delegation, parallel vs sequential
  execution, git branches and worktrees, local vs cloud agents, semver and
  changelog hygiene. Use when acting as orchestrator, routing tasks to planner,
  coder, ux, reviewer, secops, tester, docreviewer, or docwriter, or when the
  user asks for orchestration, work breakdown, or conflict-safe parallelization.
---

# Team orchestration and delegation

## Subagent roster (invoke explicitly with `/agent-name` or delegate via Agent)

| Subagent | Role |
|----------|------|
| `planner` | Plans only; writes markdown checklists; no product code |
| `coder` | Implements plans; modular code; tests when instructed |
| `ux` | UX/UI/front-end assessment; Playwright; modern web patterns |
| `reviewer` | Spec vs implementation; lints; plan checklist updates |
| `secops` | Security scans; timestamped reports |
| `tester` | Runs tests; maintains `tests/test-ledger.md`; **no code edits** |
| `docreviewer` | Doc accuracy; timestamped `docs_log-*.md`; no direct code edits |
| `docwriter` | Updates documentation; hands off to docreviewer when done |

## Parallel vs sequential

- **Parallel** when tasks touch disjoint paths, no shared mutable state, and no ordering dependency (e.g. secops scan + tester run on clean tree, or explorer-style reads).
- **Sequential** when the same files, same migrations, same `package-lock`/`requirements.txt`, or git state would race; when one output is input to the next (planner → coder → reviewer).
- **Conflict signals**: same file/dir, same dependency manifest, overlapping API surface, shared DB migrations. Prefer **separate git branches** or **git worktrees** when two coders (or long-running streams) could stomp each other.

## Git branches and worktrees

- Use a **fresh branch** per feature or per isolated experiment; avoid mixing unrelated work.
- Use **worktrees** when parallel implementation needs separate working directories (e.g. two versions of generated artifacts).
- Orchestrator records branch/worktree assignment in an active plan or orchestration notes in a `plans` folder when multiple streams run. In some repos `plans` may be in a subfolder; check for existing matching subfolders before creating a new `plans/` folder in repo root.

## Local vs cloud agents

- Prefer **local** for tight edit/run/debug loops, secrets-sensitive work, or large binary assets.
- Prefer **cloud** for long batch jobs, heavy CI-like suites, or when local machine is unavailable—only when the user or policy allows it and secrets are not exposed.

## Semver and changelog (orchestrator-only code touch)

- Orchestrator updates **`VERSION`** (semver), **`CHANGELOG.md`** (Keep a Changelog style), and release notes when appropriate—**no other product code** unless the user explicitly expands that role.
- Bump semver per user/project policy; default **patch** for fixes/docs, **minor** for backward-compatible features, **major** for breaking changes.

## Reporting

- End each orchestration turn with: current goal, assigned subagents, parallel/sequential rationale, blockers, and next user-visible decision (if any).

## Tool availability and failure reporting

- **Subagents**: if any required tool (package, MCP server, skill, API endpoint, command, program) is not available or fails, report by name, error/reason, and task impact to **orchestrator** before continuing. Do not silently skip or substitute.
- **Orchestrator**: when receiving a tool unavailability or failure report from any subagent, relay immediately to the **user**: tool name, failure reason, affected task, and suggested remediation if known. Do not absorb these silently.
