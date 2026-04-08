---
name: coder-implementation-standards
description: "Sets coding standards for plan-driven implementation, modularity, docs, linting, and handoff quality."
---

# Coder implementation standards

## Execution

- Follow the active plan you are given; if the plan has `- [ ]` items for your work, **mark them complete** when done and add short notes for surprises or follow-ups.
- Prefer **small modules**, clear names, and **reasonable file/function size**; if unavoidable growth, flag **refactor** for orchestrator before dumping more into one unit.
- Add **comments only** where they explain non-obvious intent; use **docstrings** on public APIs and complex functions.
- When **`plans/orchestration-state.md`** exists, do not edit orchestrator sections; you may **append** to **Handoff log** after your work or include HANDOFF in chat for the orchestrator to paste.

## Quality gates

- Run project **linters/formatters** if present; fix new violations you introduce.
- Write **tests** when the plan instructs; prefer minimal repro tests near the code.

## References

- When unsure about a library, consult **official documentation** or maintainer guidance—not unverified forums alone.

## Git and isolation

- If your work would race another stream (same files, lockfiles, or generated trees), set **Git proposal** in your HANDOFF (branch name + reason + path scope). **Orchestrator approves** before you create the branch unless the user has pre-authorized branching.
- For large batch refactors spanning many files, you may add **Cloud: REQUEST:** in HANDOFF for orchestrator to consider a cloud agent (include objective, branch/commit, definition of done—no secrets).

## Handoff

- Notify orchestrator: what changed (paths), tests run, lint status, and suggested next assignee (**reviewer**, **tester**, **ux**, etc.).
- End with the structured **HANDOFF → orchestrator** block (see skill `team-orchestration-delegation`).

## Environment

- Apply **`python-venv-dependencies`** for Python projects.
