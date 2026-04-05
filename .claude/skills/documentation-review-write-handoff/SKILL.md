---
name: documentation-review-write-handoff
description: >Reviews or updates documentation with timestamped logs, clear handoffs between docwriter and coder, and optional Sphinx/ReadTheDocs structure notes. Use for docreviewer or docwriter subagents or doc audits.
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
