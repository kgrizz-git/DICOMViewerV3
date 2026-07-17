# Cursor project rules (tracked in git)

This folder holds **shared** [Cursor rules](https://docs.cursor.com/context/rules) for DICOM Viewer V3. There is intentionally no always-on orchestration rule: one agent is the default, and delegation is opt-in.

**Not in git:** other `.cursor/` content (e.g. `.cursor/plans/`, local debug logs) stays gitignored. The only project-local skill retained is the DICOM Viewer agent smoke harness.
