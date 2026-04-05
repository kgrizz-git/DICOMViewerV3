---
name: plans-folder-authoring
description: >Writes implementation plans under a plans subfolder using markdown checklists, phased breakdowns, and explicit open questions—no product code. Use when planning features, comparing specs to codebase, or producing [ ] task lists for orchestrator and coder.
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

## Checklists

- Use `- [ ]` / `- [x]` consistently.
- Each task should be **one clear outcome**, assignable to a single role.
- For large work, use **multi-phase** plans with checkpoints between phases.

## Modularity

- Flag plans that would create **very large files or functions**; propose splits, modules, and boundaries up front.
- Prefer **small, composable** units and explicit interfaces.

## Handoff

- When the plan is ready for implementation, state explicitly: **ready for orchestrator to assign coder** (and ux if UI work).
