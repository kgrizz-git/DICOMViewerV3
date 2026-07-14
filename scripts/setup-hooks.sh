#!/usr/bin/env bash
# Point Git at repository-managed hooks so they activate automatically.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "Error: .git not found. Run from a git working tree." >&2
  exit 1
fi

if [[ ! -d "$REPO_ROOT/.githooks" ]]; then
  echo "Error: .githooks/ directory not found." >&2
  exit 1
fi

chmod +x "$REPO_ROOT/.githooks/pre-commit" "$REPO_ROOT/.githooks/pre-push"
git -C "$REPO_ROOT" config core.hooksPath .githooks
echo "core.hooksPath set to .githooks — hooks are active."
