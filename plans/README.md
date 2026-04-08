# Plans

- **`*.md`** — feature and task plans (primarily from the **planner** subagent).
- **`orchestration-state.md`** — **single source of truth** for long-running multi-agent work. The **orchestrator** updates goal, phase, assignments, git/cloud decisions, next action, and iteration guards; specialists **append** handoff entries to the Handoff log only (see skill `team-orchestration-delegation`).

If `orchestration-state.md` is missing, the orchestrator should create it from the structure already used in this repo’s template section of that file (or copy and fill the sections).
