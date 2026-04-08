# Orchestration state

**Canonical run state for multi-agent workflows.** The **orchestrator** edits *Goal* through *Next action* and *Iteration guard*. Other subagents **append** dated entries under **Handoff log** only—they do not rewrite the sections above the log.

## Goal and success criteria

- (orchestrator) Restate the user objective and measurable “done.”

## Phase

One of: `idle` | `planning` | `implementation` | `verify` | `ship` | `blocked` | `complete`

Current: `idle`

## Assignments

| Agent   | Task (one line) | Expected artifact / output        |
|---------|-----------------|-----------------------------------|
| —       | —               | —                                 |

## Git / worktree

| Field        | Value |
|--------------|-------|
| Branch       | (e.g. `main` or feature branch) |
| Worktree path| `none` or absolute path to linked worktree |
| Proposals    | (optional) pending branch/worktree requests from planner/coder |

**Naming (defaults):** `feature/<slug>`, `agent/<run-id>/<slug>` for isolated experiments.

## Cloud

| Field   | Value |
|---------|-------|
| Status  | `none` \| `requested` \| `approved` \| `n/a` |
| Packet  | When approved: paste the **Cloud Task Packet** (objective, branch/commit, constraints, acceptance checks) for copy into a cloud agent. |

## Blockers and escalations

- None.

## Next action

- **Invoke:** `/orchestrator` — (one concrete next step for the parent session.)

## Iteration guard

- **Cycles** (reviewer/tester ↔ coder on the same defect): `0` — orchestrator increments each loop; **soft cap** `5` then escalate or reassess.

## Handoff log (newest first)

### 2026-04-05 — orchestrator

- Initialized `orchestration-state.md` structure for long-horizon delegation.
