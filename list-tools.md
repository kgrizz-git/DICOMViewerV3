Last updated: 2026-04-05 00:00:00

# Tools Directory Files

## Utility Scripts

- [sync-external-skills-subtree.sh](tools/sync-external-skills-subtree.sh) - Shell script for pulling skills from an external GitHub repository into the local `.claude/skills/` directory using git subtree. It accepts an owner, repo, and optional branch argument, adds a git remote if not already present, then performs a `git subtree add` or `git subtree pull` to keep external skill sets in sync.
