---
name: plans-folder-authoring
description: "Writes implementation plans under a plans subfolder using markdown checklists, phased breakdowns, explicit open questions, task DAG and verification gates—no product code. Use when planning features, comparing specs to codebase, or producing [ ] task lists for orchestrator and coder."
---

# Plans folder authoring

## Scope

- **Write only** markdown: `.md` under `plans` subfolders. `plans` may be in repo root or within another folder. Do **not** edit application source, tests, or config outside `plans` folders unless the user explicitly overrides.
- **Do not assume**. If requirements are ambiguous, add a **Questions for user** section and tell the orchestrator or user to obtain answers before implementation proceeds.

## Plan structure

Use this shape (adapt headings as needed):

```markdown
# Plan: <title>

## Goal and success criteria
## Context and links (specs, issues, paths)
## Task graph and gates
### Ordering
- After A → B (sequential)
- C ∥ D (parallel — disjoint paths / no shared lockfiles)

### Verification gates
- Gate 1: reviewer approves before merge
- Gate 2: tester green on suite X before ship
### File / area ownership (optional)
- `path/or/tree` → coder | ux | …

## Phases
### Phase 1 — ...
- [ ] Task (owner: coder | ux | …)
### Phase 2 — …
## Risks and mitigations
## Modularity and file-size guardrails
## Testing strategy (what to add/run; suites)
## UX / UI (deferred to ux subagent—do not finalize visual design here)
## Questions for user (blocking if empty before coding)
## Completion notes (filled by reviewer/coder later)
```

## Task graph and gates

- For large or parallel work, add **Task graph and gates**: which tasks are **sequential** (outputs feed inputs), which may run **in parallel** (disjoint files, no shared dependency manifests), and **verification gates** (e.g. “reviewer before coder continues to Phase 2”, “tester after Phase 1”).
- Optionally list **file or directory ownership** so the orchestrator can assign branches/worktrees without overlap.

## Checklists

- Use `- [ ]` / `- [x]` consistently.
- Each task should be **one clear outcome**, assignable to a single role. Use stable task ids in parentheses if helpful for handoffs, e.g. `- [ ] (T3) Implement parser (owner: coder)`.
- **Required task attributes** for any task expected to fan-out or run in parallel:
  - `parallel-safe: yes | no` — `yes` only when the task touches paths fully disjoint from all concurrent tasks and shares no lockfile or mutable state.
  - `stream: <A|B|…|none>` — label matching the Streams table in orchestration-state.
  - `after: <task-id|none>` — explicit upstream dependency.
  - Example: `- [ ] (T4) Write parser tests (owner: coder, parallel-safe: yes, stream: B, after: T2)`
- For large work, use **multi-phase** plans with checkpoints between phases.
- Spikes use `(S1)`, `(S2)` ids; normal tasks use `(T1)`, `(T2)`, etc.

## Spike tasks

Use spikes when technology choice, API behavior, or architectural approach is uncertain *before* implementation. Spikes are always **time-boxed** and always followed by a **gate**.

```markdown
### Spike: evaluate X vs Y (timebox: 2 hours, owner: researcher | coder)
- [ ] (S1) Spike: prototype approach X; document tradeoffs in `spikes/spike-X-vs-Y.md`
  - Outcome: decision recommendation with rationale
  - Gate: reviewer reads spike output → planner updates plan → Phase 2 may start
```

- Spike branches: `spike/<slug>`. Delete or merge after the decision is recorded.
- The plan **must not** advance past the spike gate until the spike output is reviewed.
- If the spike reveals the wrong architecture, escalate to orchestrator to re-plan rather than continuing.

## Modularity

- Flag plans that would create **very large files or functions**; propose splits, modules, and boundaries up front.
- Prefer **small, composable** units and explicit interfaces.

## Coordination with orchestration

- If the repo uses **`plans/orchestration-state.md`**, the planner may append a **Handoff** entry there (or rely on chat HANDOFF) stating **plan ready** and linking the plan path(s).
- Populate the **Streams** table in orchestration-state if the plan has parallel workstreams.
- **Git / cloud:** include a `feature/<slug>` branch recommendation in the plan body for any non-trivial work; name the slug to match the plan filename. Branch creation remains **orchestrator-approved** unless the user pre-authorizes.

## Handoff

- When the plan is ready for implementation, state explicitly: **ready for orchestrator to assign coder** (and ux if UI work).
- End with the standard **HANDOFF → orchestrator** block (see skill `team-orchestration-delegation`).
