# Cursor project rules (tracked in git)

This folder holds **shared** [Cursor rules](https://docs.cursor.com/context/rules) for DICOM Viewer V3.

| Path | Role |
|------|------|
| [`orchestration-auto-chain.mdc`](orchestration-auto-chain.mdc) | Parent agent: chain `Task(orchestrator)` / specialists per `plans/orchestration-state.md` (`alwaysApply`) |

**Not in git:** other `.cursor/` content (e.g. `.cursor/plans/`, local debug logs) stays gitignored. Agent team definitions live under [`.claude/`](../../.claude/).
