#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   tools/sync-external-skills-subtree.sh OWNER REPO [BRANCH]
# Example:
#   tools/sync-external-skills-subtree.sh acme ai-skills main

OWNER="${1:?owner required}"
REPO="${2:?repo required}"
BRANCH="${3:-main}"

REMOTE="ext-${OWNER}-${REPO}"
PREFIX=".claude/skills/external-${OWNER}-${REPO}"
URL="https://github.com/${OWNER}/${REPO}.git"

mkdir -p .claude/skills

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  git remote add "$REMOTE" "$URL"
fi

git fetch "$REMOTE" "$BRANCH"

if [ -d "$PREFIX" ]; then
  git subtree pull --prefix="$PREFIX" "$REMOTE" "$BRANCH" --squash
else
  git subtree add --prefix="$PREFIX" "$REMOTE" "$BRANCH" --squash
fi

echo "Synced external skills into $PREFIX"
