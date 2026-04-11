---
name: documentation-review-write-handoff
description: "Defines doc review/write workflow with timestamped logs and clear handoff between docwriter and coder."
---

# Documentation review, writing, and handoff

## docreviewer

- **Input**: scope (whole docs set or paths), whether to include code comments/docstrings.
- **Output**: `docs_log-YYYYMMDD-HHMM.md` with findings (accuracy, clarity, gaps), suggested restructures, and tooling recommendations (Sphinx, MkDocs, RTD, linked HTML). To determine where file should be created, search repo for any subfolder matching **`docs-assessments`** or **`docs-log`**. If none is found, create **`docs-assessments`** in repo root.
- **Do not** edit product code or HTML source; **recommend** edits. Route:
  - Comment/docstring/code-adjacent fixes → suggest **coder**.
  - Prose, organization, `docs/` markdown → suggest **docwriter**.

## docwriter

- Implement doc changes per orchestrator instructions; follow project style guides.
- After completion, report paths changed and recommend **docreviewer** pass.

## Quality bar

- Precise terminology, consistent headings, working **relative links**, and explicit audience (user vs operator vs developer).

## Handoff to orchestrator

- **docreviewer** and **docwriter** each end with the structured **HANDOFF → orchestrator** block (see skill `team-orchestration-delegation`). Optionally append a short entry under **Handoff log** in `plans/orchestration-state.md` (append-only).
