#!/usr/bin/env bash
# Install repository-managed hooks for local security gating.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/.githooks"
TARGET_DIR="$REPO_ROOT/.git/hooks"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Error: .git/hooks not found. Run from a git working tree." >&2
  exit 1
fi

for hook in pre-commit pre-push; do
  src="$SOURCE_DIR/$hook"
  dst="$TARGET_DIR/$hook"
  if [[ ! -f "$src" ]]; then
    echo "Error: missing hook source $src" >&2
    exit 1
  fi
  if [[ -f "$dst" ]]; then
    cp "$dst" "$dst.bak-$(date +%Y%m%d-%H%M%S)"
  fi
  cp "$src" "$dst"
  chmod +x "$dst"
  echo "Installed $hook"
done

echo "Hooks installed in $TARGET_DIR"
