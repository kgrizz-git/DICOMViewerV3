# Cross-Repo Reuse: Agents, Skills, and Prompts (Multi-IDE)

How to pull content from this repo (agents, skills, templates, prompts) into other/future repos when you use multiple IDEs (Cursor, VS Code, Antigravity, Kiro, Windsurf, and potentially Warp).

---

## Table of Contents

- [tl;dr recommendation](#tldr-recommendation)
- [Exact commands to run (copy/paste quickstart)](#exact-commands-to-run-copypaste-quickstart)
- [Repo-first portable layout (recommended)](#repo-first-portable-layout-recommended)
- [Global sync across IDEs (machine-wide)](#global-sync-across-ides-machine-wide)
- [Subtree vs submodule for shared repo content](#subtree-vs-submodule-for-shared-repo-content)
  - [Git subtree (best default)](#git-subtree-best-default)
  - [Git submodule (when pinning matters)](#git-submodule-when-pinning-matters)
- [Pulling skills from other people's GitHub repos](#pulling-skills-from-other-peoples-github-repos)
  - [Drop-in script for external skills (subtree)](#drop-in-script-for-external-skills-subtree)
- [Where to put reusable custom prompts](#where-to-put-reusable-custom-prompts)
  - [VS Code (recommended locations)](#vs-code-recommended-locations)
  - [Cross-IDE prompt strategy](#cross-ide-prompt-strategy)
- [What to copy where](#what-to-copy-where)
- [Practical sync script for project repos](#practical-sync-script-for-project-repos)
- [Decision guide](#decision-guide)
- [Related](#related)

---

## tl;dr recommendation

| Goal | Best approach |
|------|---------------|
| Reuse across many repos and teammates | [Git subtree into repo-local portable folders](#repo-first-portable-layout-recommended) (`.claude/`, `.github/`) |
| Reuse across all your local projects quickly | [`rsync` into each IDE's global directory](#global-sync-across-ides-machine-wide) (where supported) |
| Pin an exact shared version and update intentionally | [Git submodule + sync script](#git-submodule-when-pinning-matters) |
| Pull skills from other people's repos safely | [`git subtree` (trusted/stable) or `submodule` (strict pinning)](#pulling-skills-from-other-peoples-github-repos) |
| One-time copy with no maintenance | [Plain `cp -r` or `rsync` without `--delete`](#exact-commands-to-run-copypaste-quickstart) |
| Reusable custom prompts in VS Code | [Store in `.github/prompts/*.prompt.md`](#where-to-put-reusable-custom-prompts) (+ optional user prompt folder) |

If you only pick one repo layout for portability, use `.claude/skills` and `.claude/agents` for cross-tool compatibility, and add `.github/prompts` for VS Code prompt files.

[↑ Back to top](#table-of-contents)

---

## Exact commands to run (copy/paste quickstart)

> **Platform note (macOS/Linux):** These commands require `bash` and `rsync`, which are standard on macOS and most Linux distros but are **not available by default on Windows**. On Windows, use Git Bash or WSL, or replace `rsync` with `robocopy`/`xcopy`. The `SOURCE_REPO` path on the first line is hardcoded to this machine — update it before running on another machine. Step 3 uses a **macOS-specific** VS Code prompts path; see [Where to put reusable custom prompts](#where-to-put-reusable-custom-prompts) for Linux and Windows equivalents.

```bash
# 0) Set paths (edit TARGET_REPO only)
SOURCE_REPO="/Users/kevingrizzard/Documents/GitHub/Notes_and_Ideas"
TARGET_REPO="/absolute/path/to/your/other-repo"

# 1) Machine-wide global sync (Cursor + Claude-compatible global dirs)
mkdir -p "$HOME/.cursor/agents" "$HOME/.cursor/skills" "$HOME/.claude/agents" "$HOME/.claude/skills"
rsync -a --delete "$SOURCE_REPO/agents_and_skills/agents/" "$HOME/.cursor/agents/"
rsync -a --delete "$SOURCE_REPO/agents_and_skills/skills/" "$HOME/.cursor/skills/"
rsync -a --delete "$SOURCE_REPO/agents_and_skills/agents/" "$HOME/.claude/agents/"
rsync -a --delete "$SOURCE_REPO/agents_and_skills/skills/" "$HOME/.claude/skills/"

# 2) Per-repo sync into portable folders (.claude + optional .cursor mirror + VS Code prompts)
cd "$TARGET_REPO"
mkdir -p .claude/agents .claude/skills .cursor/agents .cursor/skills .github/prompts
rsync -a --delete "$SOURCE_REPO/agents_and_skills/agents/" .claude/agents/
rsync -a --delete "$SOURCE_REPO/agents_and_skills/skills/" .claude/skills/
rsync -a --delete .claude/agents/ .cursor/agents/
rsync -a --delete .claude/skills/ .cursor/skills/
if [ -d "$SOURCE_REPO/prompts" ]; then rsync -a "$SOURCE_REPO/prompts/" .github/prompts/; fi

# 3) Optional: VS Code user-level prompts on macOS
mkdir -p "$HOME/Library/Application Support/Code/User/prompts"
if [ -d "$SOURCE_REPO/prompts" ]; then rsync -a "$SOURCE_REPO/prompts/" "$HOME/Library/Application Support/Code/User/prompts/"; fi

# 4) Optional: subtree setup for long-term repo sharing (run once per target repo)
# git remote add notes-and-ideas https://github.com/kgrizz-git/Notes_and_Ideas.git
# git fetch notes-and-ideas
# git subtree add --prefix=.claude notes-and-ideas main --squash
# Later updates:
# git fetch notes-and-ideas
# git subtree pull --prefix=.claude notes-and-ideas main --squash
```

> **How step 4 works:** `git remote add` registers the source repo as a named remote (one-time only). `git fetch` downloads its commits. `git subtree add --prefix=.claude notes-and-ideas main --squash` copies **the entire Notes_and_Ideas repo** into a `.claude/` folder in your current repo — every file from the root lands there (ideas, info, templates, etc.), not just agents and skills. `--squash` collapses the source history into a single commit. To copy only agents and skills, use the [Practical sync script](#practical-sync-script-for-project-repos) (`rsync`) instead. See [Git subtree command breakdown](#git-subtree-best-default) for full flag details.

[↑ Back to top](#table-of-contents)

---

## Repo-first portable layout (recommended)

In each target repo, keep shared assets in portable directories and treat them as source of truth:

- `.claude/agents/`
- `.claude/skills/`
- `.github/prompts/`
- Optional: `.github/skills/` and `.github/agents/` when you want VS Code-native organization

Why this works:

- Most agent-capable tools can consume `.claude/*`-style layout directly or with minimal adaptation.
- VS Code Copilot explicitly supports `.github/prompts/` for prompt files and supports skill-style layouts under `.github/skills/` and `.claude/skills/`.
- Repo-local config travels with the project and works for teammates/CI without machine-specific setup.

[↑ Back to top](#table-of-contents)

---

## Global sync across IDEs (machine-wide)

Use this when you want your personal defaults available everywhere on one machine.

> **Platform note (macOS/Linux):** Requires `bash` and `rsync`. The default `NOTES_REPO` fallback path (`$HOME/Documents/GitHub/Notes_and_Ideas`) reflects a typical macOS layout — pass your actual path as the first argument on other machines. On Windows, run in Git Bash or WSL.
>
> **macOS Sonoma (14) and later:** Apple removed `rsync` from the OS. If you get "command not found", run `brew install rsync` first.
>
> **Do not paste this script directly into your terminal.** The `set -euo pipefail` line makes your live shell session exit on any error, which will kill the terminal window. Save it to a file and run it as `bash global-sync.sh` instead.

```bash
#!/usr/bin/env bash
set -euo pipefail

NOTES_REPO="${1:-$HOME/Documents/GitHub/Notes_and_Ideas}"

# Canonical source in this repo
SRC_AGENTS="$NOTES_REPO/agents_and_skills/agents/"
SRC_SKILLS="$NOTES_REPO/agents_and_skills/skills/"

# Known global targets (create if missing)
TARGETS=(
  "$HOME/.cursor/agents|$HOME/.cursor/skills"
  "$HOME/.claude/agents|$HOME/.claude/skills"
)

for pair in "${TARGETS[@]}"; do
  AGENTS_DIR="${pair%%|*}"
  SKILLS_DIR="${pair##*|}"
  mkdir -p "$AGENTS_DIR" "$SKILLS_DIR"
  rsync -a --delete "$SRC_AGENTS" "$AGENTS_DIR/"
  rsync -a --delete "$SRC_SKILLS" "$SKILLS_DIR/"
  echo "Synced -> $AGENTS_DIR and $SKILLS_DIR"
done
```

Notes:

- Add additional targets as you confirm each tool's global folder conventions.
- For tools without stable global agent paths, prefer repo-local `.claude/` and/or `.github/` directories.
- Use `--delete` only when you want strict mirror behavior.

[↑ Back to top](#table-of-contents)

---

## Subtree vs submodule for shared repo content

### Git subtree (best default)

A subtree embeds shared files in each consuming repo so normal clone workflows still work.

```bash
git remote add notes-and-ideas https://github.com/kgrizz-git/Notes_and_Ideas.git
git fetch notes-and-ideas

# Example: embed whole main branch into .subtree/ or wherever
git subtree add --prefix=.subtree notes-and-ideas main --squash
```

The trailing `\` is a shell line-continuation character. It means "this command continues on the next line." If you paste only one line, paste them separately, or accidentally include trailing spaces after the `\`, the shell can throw an error. For copy/paste docs, a single-line version is safer.

Without `--prefix`, `git subtree add` has no destination subdirectory to merge into, so it would try to merge the other repo's root tree directly into the root of the repo you are currently in. That does **not** create or target a folder named after the remote or repo such as `Notes_and_Ideas/`; it overlays the imported files into the current repo root, which is usually not what you want unless both trees were designed for that.

`fatal: working tree has modifications. Cannot add.` means Git sees local changes in the repo where you are running `git subtree add`, and subtree refuses to proceed on top of a dirty working tree. Usually you should either commit those changes first, stash them temporarily, or run the subtree command in a clean branch or worktree. You do **not** have to commit permanently if you do not want to; `git stash push -u` is often enough.

Update later:

```bash
git fetch notes-and-ideas
git subtree pull --prefix=.subtree notes-and-ideas main --squash
```

**Command breakdown:**

| Part | Meaning |
|------|---------|
| `git remote add notes-and-ideas <url>` | Registers the source repo as an additional named remote (one-time setup); it does not replace or overwrite `origin` |
| `git fetch notes-and-ideas` | Downloads all commits and branches from that remote |
| `--prefix=.subtree` | Destination folder in your repo; all files from the remote root land here |
| `notes-and-ideas main` | Remote name and branch to pull from |
| `--squash` | Collapses the entire source repo history into one commit, keeping your log clean |

> **Scope note:** `git subtree add` copies the *entire* remote repo into the prefix folder — so `--prefix=.subtree` puts everything from Notes_and_Ideas (ideas, info, templates, etc.) into `.subtree/`, not just agents and skills. For a more targeted sync of only agents and skills, use the [Practical sync script](#practical-sync-script-for-project-repos) with `rsync`.

> **Remote note:** `notes-and-ideas` here is just a local remote alias, similar to `origin` or `upstream`. Git allows multiple remotes in one repo. `git remote add notes-and-ideas ...` will only fail if a remote with that exact name already exists; it will not confuse Git and it will not overwrite your existing `origin` remote.

> **Cleanup note:** Keep the `notes-and-ideas` remote if you want to run future `git subtree pull` updates. Remove it only if this was a one-time import and you do not want the extra remote alias hanging around: `git remote remove notes-and-ideas`. If `git subtree add` failed before creating a commit, there is usually no subtree-specific cleanup needed beyond getting back to a clean working tree with `git status`, then either commit or stash your local changes.

Use subtree when you want low friction for collaborators.

### Git submodule (when pinning matters)

Use submodule when you want strict version pinning and explicit upgrades.

```bash
git submodule add https://github.com/YOUR_ORG/Notes_and_Ideas.git .shared-notes
git submodule update --init --recursive
```

Then sync only what you need into `.claude/`, `.cursor/`, or `.github/`.

```bash
rsync -a .shared-notes/agents_and_skills/agents/ .claude/agents/
rsync -a .shared-notes/agents_and_skills/skills/ .claude/skills/
```

Use submodule when explicit pin/update control is more important than teammate convenience.

[↑ Back to top](#table-of-contents)

---

## Pulling skills from other people's GitHub repos

Short answer: yes, `git subtree` is usually a strong default if you trust the source and want low-friction usage for teammates.

Use this rule of thumb:

- Prefer `git subtree` when you want contributors to clone once and just have the skills present.
- Prefer `git submodule` when you need strict, explicit version pinning and review gates before every update.
- Prefer one-time vendoring (`rsync`/`cp`) when upstream is unstable or you only need a snapshot.

Recommended safe pattern for third-party skill packs:

1. Import into a clearly namespaced path such as `.claude/skills/external-<owner>-<repo>/`.
2. Keep your own team skills in separate folders so updates do not collide.
3. Review license, tool permissions, and any shell commands in imported skills before enabling them.
4. Update intentionally on a schedule (for example monthly) rather than on every upstream commit.

Example using subtree from an external repo:

```bash
# Add external upstream once
git remote add ext-skillpack https://github.com/OWNER/REPO.git
git fetch ext-skillpack

# Import only into a namespaced folder under .claude
git subtree add --prefix=.claude/skills/external-owner-repo ext-skillpack main --squash

# Pull updates later (intentional cadence)
git fetch ext-skillpack
git subtree pull --prefix=.claude/skills/external-owner-repo ext-skillpack main --squash
```

If you want stronger supply-chain control, fork first and subtree from your fork instead of directly from a third-party default branch.

### Drop-in script for external skills (subtree)

Save as `tools/sync-external-skills-subtree.sh` in a target repo:

```bash
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
```

Recommended usage notes:

- Run this in a branch and review the resulting diff before merge.
- Keep one external source per folder to avoid mixed ownership and update conflicts.
- If upstream renames default branch, pass it explicitly as the third argument.

#### Terminal-pasteable one-shot version

Use this when you don't want to save a script file first. Set the three variables at the top, then paste the whole block at once. It omits the shebang and `set -euo pipefail` so it's safe to run in an interactive shell.

```bash
OWNER="acme"          # replace with GitHub owner/org
REPO="ai-skills"      # replace with repo name
BRANCH="main"         # replace if needed

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
```

[↑ Back to top](#table-of-contents)

---

## Where to put reusable custom prompts

### VS Code (recommended locations)

Per workspace/project prompt files:

- `.github/prompts/*.prompt.md`

Per-user prompt files:

- **macOS:** `~/Library/Application Support/Code/User/prompts/`
- **Linux:** `~/.config/Code/User/prompts/`
- **Windows:** `%APPDATA%\Code\User\prompts\`

These map to reusable slash-style prompt files in VS Code Copilot. See [vscode-copilot-customization-reference.md](vscode-copilot-customization-reference.md).

### Cross-IDE prompt strategy

Because prompt file support differs by IDE, keep a canonical prompt library in-repo and sync/adapt outward:

- Canonical source: `prompts/` (or `.shared/prompts/`)
- VS Code target: `.github/prompts/*.prompt.md`
- Other IDE targets: copy/symlink/transform as needed once each tool's prompt format is confirmed

Practical approach:

1. Author prompts in a neutral markdown template under `prompts/`.
2. Generate or copy IDE-specific variants (for VS Code, `.prompt.md` with frontmatter).
3. Keep a small sync script to publish prompts into each tool's expected location.

[↑ Back to top](#table-of-contents)

---

## What to copy where

| Source in this repo | Portable target in other repos | Notes |
|---------------------|--------------------------------|-------|
| `agents_and_skills/agents/*.md` | `.claude/agents/` or `.cursor/agents/` | Agent definitions |
| `agents_and_skills/skills/*/` | `.claude/skills/` or `.cursor/skills/` | Skill packs (`SKILL.md`) |
| `templates-generalized/` | `docs/templates/` | Reusable documentation scaffolds |
| `info/*.md` | `docs/` | Team onboarding/reference notes |
| Prompt templates (new) | `prompts/` | Canonical, tool-agnostic source |
| VS Code prompt variants | `.github/prompts/*.prompt.md` | VS Code Copilot prompt files |

[↑ Back to top](#table-of-contents)

---

## Practical sync script for project repos

Save as `tools/sync-ai-config.sh` inside a target repo:

> **Platform note (macOS/Linux):** Requires `bash` and `rsync`. The default `NOTES_REPO` fallback path assumes a macOS-style `$HOME/Documents/GitHub/...` layout — pass your actual absolute path as the first argument on other machines. On Windows, run in Git Bash or WSL.
>
> **macOS Sonoma (14) and later:** Apple removed `rsync` from the OS. If you get "command not found", run `brew install rsync` first.
>
> ***Do not paste this script directly into your terminal.*** The `set -euo pipefail` line makes your live shell session exit on any error, which will kill the terminal window. Save it to a file (e.g. `tools/sync-ai-config.sh`), make it executable (`chmod +x tools/sync-ai-config.sh`), then run it as `bash tools/sync-ai-config.sh`.

```bash
#!/usr/bin/env bash
set -euo pipefail

NOTES_REPO="${1:-$HOME/Documents/GitHub/Notes_and_Ideas}"

mkdir -p .claude/agents .claude/skills .cursor/agents .cursor/skills .github/prompts

rsync -a --delete "$NOTES_REPO/agents_and_skills/agents/" .claude/agents/
rsync -a --delete "$NOTES_REPO/agents_and_skills/skills/" .claude/skills/

# Optional mirrors for tools that read .cursor/
rsync -a --delete .claude/agents/ .cursor/agents/
rsync -a --delete .claude/skills/ .cursor/skills/

# Optional prompt sync if you add canonical prompts folder in source repo
if [ -d "$NOTES_REPO/prompts" ]; then
  rsync -a "$NOTES_REPO/prompts/" .github/prompts/
fi

echo "Synced shared AI config into .claude/, .cursor/, and .github/prompts/."
```

[↑ Back to top](#table-of-contents)

---

## Decision guide

```
Need lowest friction for collaborators?
  YES -> subtree
  NO  -> submodule or rsync script

Need exact pinning + explicit upgrades?
  YES -> submodule
  NO  -> subtree

Using multiple IDEs in the same repo?
  YES -> keep canonical .claude/ (+ .github/prompts for VS Code)

Want personal machine-wide defaults?
  YES -> rsync to ~/.cursor and ~/.claude (plus other confirmed globals)
```

[↑ Back to top](#table-of-contents)

---

## Related

- [agents_and_skills/README.md](../agents_and_skills/README.md) — source layout and Cursor sync notes
- [info/vscode-copilot-customization-reference.md](vscode-copilot-customization-reference.md) — VS Code prompt/agent/skill reference
- [info/agent-orchestration-and-skills-guide.md](agent-orchestration-and-skills-guide.md) — broader orchestration background
- [AGENTS.md](../AGENTS.md) — current team layout and portability notes

[↑ Back to top](#table-of-contents)
