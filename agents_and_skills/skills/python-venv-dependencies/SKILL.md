---
name: python-venv-dependencies
description: >-
  Detects and uses Python virtual environments (venv), respects requirements
  files, and runs commands with the correct interpreter. Use when the project
  uses Python, before pip install or pytest, or when orchestrator/coder/tester
  secops need environment-aware commands.
---

# Python venv and dependencies

## Before running Python tooling

1. Check for a project venv: common paths `venv/`, `.venv/`, `env/` (also honor user rules: activate existing venv before shell commands).
2. If present, **activate** (Unix: `source venv/bin/activate` or `.venv/bin/activate`; Windows: `venv\Scripts\activate`).
3. Prefer **`python -m pip`** and **`python -m pytest`** so the active interpreter is unambiguous.

## Dependency files

- Prefer installing from **`requirements.txt`**, **`pyproject.toml`**, or **`uv.lock`** / **`poetry.lock`** as the project defines.
- After manifest changes, note what was added/removed for reviewer and secops.

## Secops and tester

- Run security and test commands **inside** the same environment the app uses.
- Do not commit secrets; use env vars or local untracked config per project norms.
