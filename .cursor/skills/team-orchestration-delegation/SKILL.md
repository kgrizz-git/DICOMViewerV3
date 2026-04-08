---
name: team-orchestration-delegation
description: "Defines safe multi-agent orchestration: delegation, sequencing, branch/worktree isolation, and release hygiene."
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
| `tester` | Runs tests; maintains `logs/test-ledger.md`; **no code edits** |
| `docreviewer` | Doc accuracy; timestamped `docs_log-*.md`; no direct code edits |
| `docwriter` | Updates documentation; hands off to docreviewer when done |

## Canonical state: `plans/orchestration-state.md`

- **Orchestrator** is the only role that should edit the sections from **Goal** through **Iteration guard** (assignments, phase, git/cloud fields, blockers, next action, cycle counter).
- **All other subagents** append a dated subsection under **Handoff log (newest first)** only. They do not change assignments or phase unless the user explicitly overrides this convention.
- **Every orchestrator turn:** read `plans/orchestration-state.md` first (if it exists). If missing, create it from the template in that file or from the **State template** below.
- **Parent session loop:** Cursor does not auto-schedule subagents. For long runs, end **Next action** with an explicit follow-up (e.g. “invoke `/coder` with …” then “invoke `/orchestrator` to merge handoffs”). Optionally add a **user rule**: for multi-step tasks, keep invoking `/orchestrator` until phase is `complete` or `blocked`.

### State template (orchestrator may paste into `plans/orchestration-state.md`)

Use the same section headings as the checked-in `plans/orchestration-state.md`: Goal, Phase, Assignments table, Git/worktree, Cloud, Blockers, Next action, Iteration guard, Handoff log.

## Structured handoff (all subagents → orchestrator)

Every specialist response must end with a block **exactly** like this (orchestrator parses it from chat or from pasted content into the Handoff log):

```text
HANDOFF → orchestrator:
- Status: done | blocked | needs_user
- Artifacts: <paths or "none">
- Plan deltas: <checkbox ids or task lines touched, or "none">
- Risks: <short or "none">
- Recommended next: <single primary agent + task> | optional parallel: <agent + task>
- Git: clean | dirty | conflict; branch: <name>; worktree: <path|none>
- Git proposal: <none | BRANCH: name + reason + paths> | <none | WORKTREE: path + reason>
- Cloud: <none | REQUEST: objective + branch/commit + constraints + acceptance + timeout hint>
- Merge recommendation: <n/a | yes | no | yes_with_followups>  # reviewer primarily
```

- **Git proposal:** planner or coder may propose a branch or worktree; **orchestrator approves** (records under Git/worktree, may rename or reject). If the user has forbidden branching without confirmation, set `needs_user` and do not create the branch.
- **Cloud REQUEST:** tester (long suites), secops (heavy scans), or coder (large batch refactors) may request a cloud run. **Orchestrator approves** and fills **Cloud Task Packet** in state (see below). Never put secrets or credentials in the packet or logs.

## Cloud Task Packet (orchestrator writes into `plans/orchestration-state.md` under Cloud)

When approving a cloud agent, record a copy-paste block:

```text
CLOUD TASK PACKET
- Objective: <one paragraph>
- Repo state: branch <name>, commit <sha or HEAD>
- Constraints: no secrets; read-only where applicable; resource limits if known
- Commands / scope: <ordered list>
- Definition of done: <acceptance checks>
- Rollback / safety: <what to revert or avoid>
- Hand back: update Handoff log + plan checkboxes; file paths for artifacts
```

## Parallel vs sequential

- **Parallel** when tasks touch disjoint paths, no shared mutable state, and no ordering dependency (e.g. secops scan + tester run on clean tree, or explorer-style reads).
- **Sequential** when the same files, same migrations, same `package-lock`/`requirements.txt`, or git state would race; when one output is input to the next (planner → coder → reviewer).
- **Conflict signals**: same file/dir, same dependency manifest, overlapping API surface, shared DB migrations. Prefer **separate git branches** or **git worktrees** when two streams could stomp each other.

## Git branches and worktrees (decision table)

| Situation | Prefer |
|-----------|--------|
| Unrelated feature or experiment | New **branch** from agreed base (`main` / `develop`) |
| Parallel implementation, same repo, need two working trees | **Git worktree** |
| Generated artifacts or lockfiles that conflict | Separate branch or worktree + record in state |
| Single linear task, one coder | Stay on current branch unless policy requires feature branches |

- Use a **fresh branch** per feature or isolated experiment; avoid mixing unrelated WIP.
- **Worktrees** when two checkouts need different build outputs or long-running local states side by side.
- Record branch name, base, and any worktree path in `plans/orchestration-state.md`.

## Autonomy and escalation (when to stop without the user)

**Hard stops** (`Status: needs_user` in HANDOFF; set phase `blocked` if severe):

- Ambiguous requirements that change product behavior
- Secrets, credentials, production access, or policy ambiguity
- Destructive or irreversible ops (e.g. mass deletes, prod migrations) without explicit approval

**Soft stops** (orchestrator loops **coder ↔ reviewer ↔ tester** with **Iteration guard**):

- Lint debt, test flakes, minor gaps — increment **Cycles** in state; at **soft cap** (default 5), orchestrator reassesses or escalates.

## Local vs cloud agents

- Prefer **local** for tight edit/run/debug loops, secrets-sensitive work, or large binary assets.
- Prefer **cloud** for long batch jobs, heavy CI-like suites, or when local machine is unavailable—only when the user or policy allows and **secrets are not exposed**.

## Semver and changelog (orchestrator-only code touch)

- Orchestrator updates **`VERSION`** (semver), **`CHANGELOG.md`** (Keep a Changelog style), and release notes when appropriate—**no other product code** unless the user explicitly expands that role.
- Bump semver per user/project policy; default **patch** for fixes/docs, **minor** for backward-compatible features, **major** for breaking changes.

## Reporting

- End each orchestration turn with: current goal, phase, assigned subagents, parallel/sequential rationale, blockers, **next** delegation step (match **Next action** in state), and iteration count if in a verify loop.

## Tool availability and failure reporting

- **Subagents**: if any required tool (package, MCP server, skill, API endpoint, command, program) is not available or fails, report by name, error/reason, and task impact to **orchestrator** before continuing. Do not silently skip or substitute.
- **Orchestrator**: when receiving a tool unavailability or failure report from any subagent, relay immediately to the **user**: tool name, failure reason, affected task, and suggested remediation if known. Do not absorb these silently.
