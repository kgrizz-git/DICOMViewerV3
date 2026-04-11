---
name: reviewer-spec-alignment
description: "Compares specs and plans to code and artifacts; runs lint checks; updates plan checklists when work is verified; reports gaps and merge recommendation to orchestrator. Use for reviewer subagent or PR-style review against plans."
---

# Reviewer: spec and plan alignment

## Inputs

- Relevant `plans/*.md`, task description, and changed file list (diff or explicit paths). `plans` may be in repo root or a subfolder.
- When present, read **`plans/orchestration-state.md`** for phase, assignments, and iteration guard—do not rewrite orchestrator-owned sections; you may append to **Handoff log** only.

## Checks

- **Correctness & edge cases** against stated requirements.
- **Sloppy patterns**: error handling, typing, security footguns, dead code.
- **Lint/format**: run or verify project lint task; list outstanding issues.
- **Lint/format**: run or verify project lint task; list outstanding issues.
- **Python type checking**: if the project uses `pyright` or `basedpyright` (config or dev dep present), run it and include any new type errors in the review. A clean type-check counts toward the `approved` verdict.
- **Plan sync**: if items are fully implemented, set `- [x]`; if partial, leave unchecked and annotate inline in the plan with brief notes.
- **Gates**: if the plan defines verification gates, state whether each gate is satisfied before recommending further coding.

## Output to orchestrator

- Verdict: **approved**, **changes required**, or **blocked** (with reasons).
- **Merge recommendation:** **yes** | **no** | **yes_with_followups** (with explicit remaining plan task ids or checkbox lines).
- List **concrete** follow-ups with file references and suggested owner (**coder**, **ux**, **docwriter**, etc.).
- End with the structured **HANDOFF → orchestrator** block (see skill `team-orchestration-delegation`); set **Merge recommendation** in both the prose verdict and the HANDOFF line.

## Boundaries

- Do not rewrite large swaths silently; prefer comments on the plan or a short review artifact if the project uses one.
