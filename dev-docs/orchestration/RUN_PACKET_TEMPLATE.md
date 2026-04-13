# Orchestration run packet (copy-paste for the primary agent)

Use this template when starting a **multi-agent** run with **`Task(orchestrator)`**. **Default chain mode is `autonomous`** (parent chains orchestrator after each specialist). Set **`CHAIN_MODE: step`** only when you want one hop per user turn.

---

## 1. Mode and stop conditions

- **Chain mode:** **`autonomous`** (default — run until **complete** / **blocked** / guard limit) **or** **`step`** (one orchestrator → specialist hop per user turn; opt-in only).
- **Stop when:** Phase **`complete`**, **`blocked`**, **`needs_user`**, or **Global orchestration guard** fires (see **`plans/orchestration-state.md`**).

## 2. Goal and success criteria

- **Goal (one paragraph):**
- **Done means:**

## 3. Task list → Assignments

| ID | Owner hint | Task | Plan / paths | Notes |
|----|------------|------|--------------|-------|
| T1 | planner / coder | … | `dev-docs/plans/…` | |

*(Orchestrator normalizes this into **`plans/orchestration-state.md`** **Assignments**.)*

## 4. Constraints (required)

- **Repo root:** (if not cwd)
- **Venv / runtime:** e.g. `.\.venv\Scripts\Activate.ps1` then `python -m pytest …`
- **Git:** e.g. “do not push”; “may create `feature/*` branches without asking”
- **Backups:** e.g. “back up files under `backups/<slug>/` before edits”
- **Docs / changelog:** e.g. “update CHANGELOG Unreleased for user-visible changes”

## 5. Guardrails (optional)

Edit defaults in **`plans/orchestration-state.md`** section **Global orchestration guard** if the run is large:

- **Max orchestrator cycles** (default **40** in template): raise for long campaigns (e.g. **80**).
- **Max specialist completions** (default **120**): optional ceiling on specialist **`Task`** finishes in **`autonomous`** mode.

## 6. Invocation line for the primary agent

**Default (autonomous)** — paste:

```text
Run Task(orchestrator) with this packet. Default chain mode is autonomous: after each non-orchestrator specialist, Task(orchestrator) again until Phase complete/blocked or guard limit. Obey .cursor/rules/orchestration-auto-chain.mdc.
```

Explicit opt-in (same as default):

```text
CHAIN_MODE: autonomous — Run Task(orchestrator) with this packet; after each non-orchestrator specialist, Task(orchestrator) again until Phase complete/blocked or guard limit. Obey .cursor/rules/orchestration-auto-chain.mdc.
```

One step per user turn:

```text
CHAIN_MODE: step — Run Task(orchestrator) once; chain only the NEXT_TASK_TOOL the orchestrator returns; then stop for user review.
```

---

## Related files (this repo)

| File | Purpose |
|------|---------|
| `.cursor/rules/orchestration-auto-chain.mdc` | Parent **`Task`** chaining rules |
| `.claude/skills/team-orchestration-delegation/SKILL.md` | HANDOFF format, state template, parallel/git policy |
| `.claude/agents/orchestrator.md` | **`NEXT_TASK_TOOL:`** / **`NEXT_TASK_TOOL_SECOND:`** |
| `plans/orchestration-state.md` | Live state: Goal, Assignments, **Chain mode**, **Global orchestration guard**, Handoff log |

## Porting to another repository

Copy the **`.cursor/rule`**, **`.claude/agents/*.md`** you use, **`.claude/skills/team-orchestration-delegation/`**, and this **`dev-docs/orchestration/`** folder (or merge into that repo’s docs). Keep **`plans/orchestration-state.md`** at **`plans/orchestration-state.md`** or update references in agent/rule text to match.
