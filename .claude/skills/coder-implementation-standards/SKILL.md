---
name: coder-implementation-standards
description: >-
  Implements plans with modular structure, docstrings, lint awareness, trusted
  online docs for APIs, and checklist updates on plans when tasks complete. Use
  when coding from plans or when orchestrator assigns implementation work.
---

# Coder implementation standards

## Execution

- Follow the active plan you are given; if the plan has `- [ ]` items for your work, **mark them complete** when done and add short notes for surprises or follow-ups.
- Prefer **small modules**, clear names, and **reasonable file/function size**; if unavoidable growth, flag **refactor** for orchestrator before dumping more into one unit.
- Add **comments only** where they explain non-obvious intent; use **docstrings** on public APIs and complex functions.

## Quality gates

- Run project **linters/formatters** if present; fix new violations you introduce.
- Write **tests** when the plan instructs; prefer minimal repro tests near the code.

## References

- When unsure about a library, consult **official documentation** or maintainer guidance—not unverified forums alone.

## Handoff

- Notify orchestrator: what changed (paths), tests run, lint status, and suggested next assignee (**reviewer**, **tester**, **ux**, etc.).

## Environment

- Apply **`python-venv-dependencies`** for Python projects.
