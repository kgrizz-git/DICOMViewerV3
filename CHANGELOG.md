# Changelog

All notable changes to this repository will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-04-05

### Added

- **`plans/orchestration-state.md`** and **`plans/README.md`**: canonical multi-agent run state (goal, phase, assignments, git/cloud, iteration guard, handoff log) for long-horizon workflows.
- **`logs/README.md`** and **`logs/test-ledger.md`**: align the test ledger with agent definitions under `logs/`.

### Changed

- **Orchestrator** and **`team-orchestration-delegation`** skill: read/update state file first; structured **HANDOFF → orchestrator** blocks; git branch/worktree **propose/approve**; **Cloud Task Packet** template; hard/soft autonomy stops and verify-loop cap.
- **All subagents**: required HANDOFF footer; planner/coder/tester/secops can propose branch or cloud runs; reviewer adds **merge recommendation**.
- **Skills**: `plans-folder-authoring` (task graph and gates), `reviewer-spec-alignment`, `coder-implementation-standards`, `test-ledger-runner` (ledger path `logs/test-ledger.md`), `documentation-review-write-handoff`, `security-scanning-secops`, `ux-evaluation-web` (handoff note).
- **`AGENTS.md`**, **`list-.cursor.md`**, **`agents_and_skills/README.md`**, root **`README.md`**, **`list-plans.md`**: document orchestration state and updated conventions.
- Synced **`agents_and_skills/agents/`** and **`agents_and_skills/skills/`** with **`.cursor/`**.

## [0.1.2] - 2026-04-04

### Added

- Root index files `list-agents_and_skills.md`, `list-assessments.md`, `list-logs.md`, `list-plans.md`, and `list-.cursor.md`, each listing files in the corresponding subdirectory with short summaries and links (per `update-lists-prompt.md`).

### Changed

- Refreshed `Last updated` timestamps on `list-ideas.md`, `list-info.md`, and `list-templates-generalized.md`.
- `list-ideas.md`: added entry for `ideas/relativistic_mri_analysis_plan-04-01-26.md`.
- `README.md`: noted root `list-<folder>.md` index files and `update-lists-prompt.md`.

## [0.1.1] - 2026-04-04

### Added

- `agents_and_skills/README.md`: guide to creating Cursor subagents and skills (with doc links), summary of this repo’s team definitions, sync instructions, and a section on research/academic subagents plus [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills).

## [0.1.0] - 2026-04-04

### Added

- Cursor **subagents** under `.cursor/agents/` (orchestrator, planner, coder, ux, reviewer, secops, tester, docreviewer, docwriter).
- Cursor **skills** under `.cursor/skills/` for shared workflows (orchestration, planning, coding standards, UX evaluation, review, secops tooling, testing ledger, documentation handoff, Python venv usage).
- Working directories `plans/`, `logs/` (including `test-ledger.md` starter), and `assessments/` with short README files.
- `AGENTS.md` describing how to use the team layout; `VERSION` file for semver tracking.
