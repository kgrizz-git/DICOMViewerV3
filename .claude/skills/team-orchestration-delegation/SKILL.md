---
name: team-orchestration-delegation
description: "Defines safe multi-agent orchestration: delegation, sequencing, branch/worktree isolation, and release hygiene."
---

# Team orchestration and delegation

## Subagent roster (invoke explicitly with `/agent-name` or delegate via Agent)

| Subagent | Role | Read-only? |
|----------|------|------------|
| `researcher` | Codebase/API/doc exploration; produces research brief; parallel-safe at start | yes |
| `planner` | Plans only; writes markdown checklists; no product code | no |
| `coder` | Implements plans; modular code; tests when instructed | no |
| `debugger` | Localizes failing tests/errors to root cause; writes debug report; no fixes | yes |
| `ux` | UX/UI/front-end assessment; Playwright; modern web patterns | no |
| `reviewer` | Spec vs implementation; lints; plan checklist updates | no |
| `secops` | Security scans; timestamped reports | yes (default) |
| `tester` | Runs tests; maintains `logs/test-ledger.md`; **no code edits** | yes |
| `docreviewer` | Doc accuracy; timestamped `docs_log-*.md`; no direct code edits | yes |
| `docwriter` | Updates documentation; hands off to docreviewer when done | no |

## Canonical state: `plans/orchestration-state.md`

- **Orchestrator** is the only role that should edit the sections from **Goal** through **Iteration guard** (assignments, phase, git/cloud fields, blockers, next action, cycle counter).
- **All other subagents** append a dated subsection under **Handoff log (newest first)** only. They do not change assignments or phase unless the user explicitly overrides this convention.
- **Every orchestrator turn:** read `plans/orchestration-state.md` first (if it exists). If missing, create it from the template in that file or from the **State template** below.
- **Parent session loop:** Cursor does not auto-schedule subagents. For long runs, end **Next action** with an explicit follow-up (e.g. “invoke `/coder` with …” then “invoke `/orchestrator` to merge handoffs”). Optionally add a **user rule**: for multi-step tasks, keep invoking `/orchestrator` until phase is `complete` or `blocked`.

### State template (orchestrator may paste into `plans/orchestration-state.md`)

Use the same section headings as the checked-in `plans/orchestration-state.md`: Goal, Phase, Streams, Assignments table, Git/worktree, Cloud, Blockers, Next action, Session checkpoint, Iteration guard, Handoff log.

**Streams** (add when using parallel workstreams):
```markdown
## Streams
| Stream | Agents | Status | Fan-in gate |
|--------|--------|--------|-------------|
| A      | coder (module-X) | in-progress | reviewer after A+B done |
| B      | coder (module-Y) | in-progress | reviewer after A+B done |
```

**Session checkpoint** (update on every phase transition for cold-start resumption):
```markdown
## Session checkpoint
- Context summary: <1–3 sentences: state of play, what was last completed>
- Locked decisions: <list of irreversible architectural/tech choices made>
- Canonical files: <list of files that are current sources of truth>
- Last verified ref: <branch + commit SHA or HEAD>
- Last updated: <YYYY-MM-DD by orchestrator>
```

**Iteration guard** (per-task table):
```markdown
## Iteration guard
| Task ID | Cycles | Soft cap | Notes |
|---------|--------|----------|-------|
| T3      | 0      | 5        |       |
```
Orchestrator increments the relevant task row each time reviewer/tester ↔ coder loop on the *same* defect. At soft cap, reassess or escalate to user.

## Structured handoff (all subagents → orchestrator)

Every specialist response must end with a block **exactly** like this (orchestrator parses it from chat or from pasted content into the Handoff log):

```text
HANDOFF → orchestrator:
- Status: done | blocked | needs_user
- Artifacts: <paths or "none">
- Plan deltas: <checkbox ids or task lines touched, or "none">
- Risks: <short or "none">
- Recommended next: <single primary agent + task> | optional parallel: <agent + task>
- Stream: <stream-id e.g. A | B | none>  # omit if not using Streams
- Git: clean | dirty | conflict; branch: <name>; worktree: <path|none>
- Git proposal: <none | BRANCH: name + reason + paths> | <none | WORKTREE: path + reason>
- PR: <none | OPEN: title + base-branch> | <READY: pr-url or branch>
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

- **Parallel** when tasks touch disjoint paths, no shared mutable state, and no ordering dependency (e.g. `researcher` + `secops` at project start; `tester` + `secops` on a clean tree; explorer-style reads).
- **Sequential** when the same files, same migrations, same `package-lock`/`requirements.txt`, or git state would race; when one output is input to the next (planner → coder → reviewer).
- **Conflict signals**: same file/dir, same dependency manifest, overlapping API surface, shared DB migrations. Prefer **separate git branches** or **git worktrees** when two streams could stomp each other.
- **Streams**: orchestrator may label parallel work as streams (A, B, …) in the Assignments table and the plan. Each subagent reports its `Stream:` in HANDOFF; orchestrator fans in when all streams in a batch are `done`. Streams **must** have a named fan-in gate in the plan.

## Git workflow

### When to branch

| Situation | Action |
|-----------|--------|
| New feature or non-trivial change | New `feature/<slug>` branch from agreed base |
| Bug fix outside an active feature branch | New `fix/<slug>` branch |
| Time-boxed spike or PoC | New `spike/<slug>` branch; delete or merge after decision |
| Parallel agent streams (same repo, disjoint paths) | Separate `feature/<slug>` branches or git worktrees |
| Hotfix on released code | `hotfix/<slug>` from the release tag or `main` |
| Docs-only change | `docs/<slug>` branch (may skip PR if policy allows) |
| Single linear task on a personal/dev branch | Stay on current branch unless project policy requires isolation |

- **Orchestrator approves** all branch creation; coder or planner may *propose* via `Git proposal:` in HANDOFF.
- **No direct pushes to `main`** (or protected default branch) unless user explicitly waives this.
- Branch naming defaults: `feature/<slug>`, `fix/<slug>`, `spike/<slug>`, `docs/<slug>`, `hotfix/<slug>`, `agent/<run-id>/<slug>` for automated runs.

### Commit conventions

Use **Conventional Commits** (`<type>(<scope>): <summary>`):

| Type | When |
|------|------|
| `feat` | New user-visible capability |
| `fix` | Bug or regression correction |
| `refactor` | Code restructure, no behavior change |
| `test` | Add/modify tests only |
| `docs` | Documentation only |
| `chore` | Build, CI, tooling, dependency bumps |
| `perf` | Performance improvement |
| `ci` | CI/CD config changes |

- Keep commits **atomic**: one logical change per commit.
- Body: explain *why*, not *what* (the diff shows what).
- Reference plan task ids in the body when relevant (e.g. `Closes T3`).

### Pull requests

- Open a PR when work on a branch is **ready for reviewer gate** before it merges to the base.
- **PR title**: mirror the branch slug or the primary plan task description.
- **PR description minimum**: what changed, why, how to test, linked plan file/task ids.
- **Orchestrator** approves opening PRs (or delegates to coder via pre-authorization).
- **Reviewer subagent** is the merge gate: verdict `approved` or `yes_with_followups` before orchestrator merges.
- **Merge strategy defaults**: squash-merge feature branches into main (clean history); merge-commit for long-lived release branches; rebase for trivial single-commit fixups.
- After merge: delete the feature branch (and its worktree if one exists).

### Git worktrees

- Use when two parallel streams need **simultaneous checkouts** of the same repo (different build states, different long-running processes).
- Worktree path convention: `../repo-name-<slug>` or a project-agreed location. Record in `plans/orchestration-state.md`.
- **Lifecycle**: create → work → fan-in (reviewer approves) → `git worktree remove <path>` → delete branch.
- Never leave abandoned worktrees; orchestrator tracks and cleans them in the Git/worktree section of state.

### Orchestrator git responsibilities

- Record all active branches, their base, and worktree paths in the `Git / worktree` table in `plans/orchestration-state.md`.
- Approve or reject every `Git proposal:` in HANDOFF before the branch is created.
- Approve PR opens and merges; for human-gated repos, surface the PR URL to the user.
- Update `VERSION` and `CHANGELOG.md` on merge to main (semver per policy).

### Decision table: branches vs worktrees

| Situation | Prefer |
|-----------|--------|
| Single coder, one active task | Feature branch, same working directory |
| Two coders in parallel, disjoint paths | Two feature branches (no worktree needed if no simultaneous build) |
| Two streams need simultaneous local builds | Git worktrees (one per stream) |
| Generated artifacts or lockfiles conflict | Separate branches + worktrees |
| Spike / PoC exploration | `spike/<slug>` branch; worktree optional |

## Autonomy and escalation (when to stop without the user)

**Hard stops** (`Status: needs_user` in HANDOFF; set phase `blocked` if severe):

- Ambiguous requirements that change product behavior
- Secrets, credentials, production access, or policy ambiguity
- Destructive or irreversible ops (e.g. mass deletes, prod migrations) without explicit approval
- Opening PRs or merging to a protected branch when user has not pre-authorized

**Soft stops** (orchestrator loops **coder ↔ reviewer ↔ tester** with **Iteration guard**):

- Lint debt, test flakes, minor gaps — increment **Cycles** for the affected task row in the guard table; at **soft cap** (default 5), orchestrator reassesses or escalates.

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
