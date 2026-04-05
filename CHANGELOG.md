# Changelog

All notable changes to this repository will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
