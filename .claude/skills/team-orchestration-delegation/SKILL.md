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
| `ux` | UX/UI assessment: **desktop/Qt/native** workflows by default in Qt apps; **web** flows via Playwright/Chrome when the product is browser-based | no |
| `reviewer` | Spec vs implementation; lints; plan checklist updates | no |
| `secops` | Security scans; timestamped reports | yes (default) |
| `tester` | Runs tests; maintains `logs/test-ledger.md`; **no code edits** | yes |
| `docreviewer` | Doc accuracy; timestamped `docs_log-*.md`; no direct code edits | yes |
| `docwriter` | Updates documentation; hands off to docreviewer when done | no |

## Canonical state: `plans/orchestration-state.md`

- **`## Chain mode`** (orchestrator-owned): **`autonomous`** (default) | **`step`**. **Default is `autonomous`:** use **`step`** only when the user or run packet explicitly sets **`CHAIN_MODE: step`** or edits state. If the section is missing, orchestrator and parent treat the run as **`autonomous`**. In **`autonomous`**, the **parent session** must call **`Task(orchestrator)`** again after **every** non-orchestrator specialist completes (unless HANDOFF is `needs_user` / `blocked`). In **`step`**, the parent chains only immediately after an orchestrator turn (one specialist per user-visible cycle unless the user asks to continue). See **`.cursor/rules/orchestration-auto-chain.mdc`**.
- **Orchestrator** is the only role that should edit the sections from **Goal** through **Global orchestration guard** and **Iteration guard** (assignments, phase, git/cloud fields, blockers, next action, per-task cycle counter, chain mode, orchestration hop limits).
- **All other subagents** **must** append a dated subsection under **Handoff log (newest first)** when **`plans/orchestration-state.md`** exists—copy the full **`HANDOFF → orchestrator:`** block into that file (same content as chat). This keeps **autonomous** chains reliable if chat context is trimmed. They do not change assignments, **Global orchestration guard**, or phase unless the user explicitly overrides this convention.
- **Every orchestrator turn:** read `plans/orchestration-state.md` first (if it exists). If missing, create it from the template in that file or from the **State template** below.
- **Parent session loop:** Cursor does not auto-schedule subagents by itself. **Primary agent (parent) with the `Task` tool:** default **`CHAIN_MODE: autonomous`** (see **`.cursor/rules/orchestration-auto-chain.mdc`**): after **`Task(orchestrator)`**, chain **`NEXT_TASK_TOOL`** / **`NEXT_TASK_TOOL_SECOND`** when safe; after **each** non-orchestrator specialist, **`Task(orchestrator)`** again unless **`## Chain mode`** is **`step`** or the user opted out. **`NEXT_TASK_TOOL_SECOND`** parallel dispatch only if the skill’s **orchestrator checklist** passes.

### State template (orchestrator may paste into `plans/orchestration-state.md`)

Use the same section headings as the checked-in `plans/orchestration-state.md`: Goal, Phase, **Chain mode**, **Global orchestration guard**, Streams, Assignments table, Git/worktree, Cloud, Blockers, Next action, Session checkpoint, Iteration guard, Handoff log.

**Chain mode** (short section — default **`autonomous`**):
```markdown
## Chain mode

`autonomous` | `step`
```

**Global orchestration guard** (cost and runaway protection; orchestrator increments and enforces):

```markdown
## Global orchestration guard

| Field | Value |
|-------|-------|
| Orchestrator cycles (this run) | 0 |
| Max orchestrator cycles | 40 |
| Specialist completions (this run) | 0 |
| Max specialist completions | 120 |

```

- **Orchestrator cycles:** increment by **1** on **every** orchestrator turn (including resume). If **Orchestrator cycles ≥ Max orchestrator cycles**, set **Phase** to **`blocked`**, explain in **Blockers** (“orchestration hop limit—raise **Max** in state or start a fresh run”), and emit **`NEXT_TASK_TOOL: none`**.
- **Specialist completions:** optional; increment when a non-orchestrator specialist finishes a `Task` in an autonomous chain. If **≥ Max specialist completions**, same **blocked** behavior. Omit the specialist row if unused.
- User may raise limits via **run packet** (see **`dev-docs/orchestration/RUN_PACKET_TEMPLATE.md`**) or by editing state before continuing.

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

## Specialist start-of-turn (all non-orchestrator subagents)

Apply at the **beginning** of every specialist turn (before substantive work).

1. **Read state first:** If **`plans/orchestration-state.md`** exists, **read it** (at minimum **Goal**, **Assignments** rows for your task, **Next action**, **Execution mode**, **Risk tier**, **Phase**, **Chain mode**, **Session checkpoint**). Do not rely on chat alone.
2. **Context survival:** If prior user/orchestrator instructions are **missing, unclear, or trimmed**, or this is a **cold/resumed** `Task`, **proactively** re-read **`plans/orchestration-state.md`** and the **newest 8** subsections under **Handoff log (newest first)** before proceeding—even when you “already have” a short prompt from the parent.
3. **Execution mode + Risk tier → output scale:** Read **`## Execution mode`** and **`## Risk tier`** (or equivalent bullets under Goal/Phase in your repo’s state file). Align with orchestrator **Handoff size policy** (~**≤250 tokens** in the **`HANDOFF → orchestrator:`** block for **`fast`** or **`low`** risk unless `Status` is **`blocked`** / **`needs_user`**). For **`full`** execution or **`medium`/`high`** risk, put depth in **Artifacts** (files, ledgers, reports); keep the HANDOFF bullet list tight unless escalation requires detail.
4. **Token discipline:** Specialists enforce the above scaling themselves; orchestrator still sets mode/risk in state when absent.

## Tool failure recovery (specialists)

- **Substantive** operations (file read/write, patch apply, test run, package install, scanner invocation): allow **one** targeted retry if the failure looks **transient** (timeout, file lock, flaky network).
- After **two failures** on the **same** operation **or** two consecutive failures that **block** the assigned task, set **`Status: blocked`** in **`HANDOFF → orchestrator:`** and include **tool/command name** and **reason** for **each** failure—**never** silently skip or pretend success.
- **Exploratory** zero-result (e.g. grep no matches on a hypothesis) is not automatically a “failure”; if the assignment **requires** a finding and none is possible after reasonable alternatives, use **`blocked`** or **`needs_user`** with explanation.

## `NEXT_TASK_TOOL_SECOND` — orchestrator checklist (before emitting non-`none`)

Set **`NEXT_TASK_TOOL_SECOND:`** only if **all** are true; otherwise **`none`**:

1. **Streams / assignments:** **`## Streams`** lists the two specialists on **distinct streams** with a **fan-in gate**, **or** **Assignments** + linked plan show **disjoint path sets** (no overlap on files, dirs, lockfiles, or shared mutable artifacts).
2. **Ordering:** No plan or **Next action** dependency requires one specialist’s output before the other starts.
3. **Plan graph:** Where the plan uses **`parallel-safe: yes`**, both parallel tasks are marked accordingly (or risk is low and paths are provably disjoint).
4. **Git:** No branch/worktree collision—use **separate branches or worktrees** if both would write the working tree.
5. **Parent rule:** The primary agent may only `Task(...)` **both** in parallel per **`.cursor/rules/orchestration-auto-chain.mdc`** when this checklist passes.

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
