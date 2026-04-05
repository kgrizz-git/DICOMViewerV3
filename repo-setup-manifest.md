# Repo Setup Manifest

> **Agent reference file** — consulted by [update-and-setup-prompt.md](update-and-setup-prompt.md).  
> Do not present this file to the user directly. Use it to populate the install/setup menu at runtime.  
> Update this file whenever new packages, scripts, or external references are added to the repo.

---

## 1. npm Packages

Source: `package.json`

| Package | Type | Install command |
|---------|------|-----------------|
| `@playwright/test` | devDependency | `npm install` (covered by `npm install` from repo root) |
| `@types/node` | devDependency | same |

**One-shot install (from repo root):**
```bash
npm install
```

---

## 2. Playwright Browser Binaries

Required after `npm install` to run the test suite (`tests/example.spec.ts`).

```bash
npx playwright install
```

To install only specific browsers:
```bash
npx playwright install chromium
npx playwright install firefox
npx playwright install webkit
```

Config file: `playwright.config.ts`  
Test location: `tests/`

---

## 3. Shell Scripts (`tools/`)

| Script | Purpose | Usage |
|--------|---------|-------|
| `tools/sync-external-skills-subtree.sh` | Pull an external GitHub skills repo into `.claude/skills/external-<owner>-<repo>` via git subtree | `bash tools/sync-external-skills-subtree.sh <OWNER> <REPO> [BRANCH]` |

**Example — pull K-Dense scientific skills:**
```bash
bash tools/sync-external-skills-subtree.sh K-Dense-AI claude-scientific-skills main
```

**Example — pull Anthropic skills:**
```bash
bash tools/sync-external-skills-subtree.sh anthropics skills main
```

---

## 4. Agent & Skill Sync (rsync to global / per-repo)

Source of truth: `agents_and_skills/`  
Reference doc: `info/cross-repo-reuse-agents-skills.md`

### 4a. Machine-wide global sync (Cursor + Claude-compatible)
```bash
mkdir -p "$HOME/.cursor/agents" "$HOME/.cursor/skills" "$HOME/.claude/agents" "$HOME/.claude/skills"
rsync -a --delete "agents_and_skills/agents/" "$HOME/.cursor/agents/"
rsync -a --delete "agents_and_skills/skills/" "$HOME/.cursor/skills/"
rsync -a --delete "agents_and_skills/agents/" "$HOME/.claude/agents/"
rsync -a --delete "agents_and_skills/skills/" "$HOME/.claude/skills/"
```

### 4b. Per-repo sync (portable .claude + optional .cursor mirror + VS Code prompts)
```bash
# Run from the TARGET repo directory
SOURCE_REPO="/Users/kevingrizzard/Documents/GitHub/Notes_and_Ideas"
mkdir -p .claude/agents .claude/skills .cursor/agents .cursor/skills .github/prompts
rsync -a --delete "$SOURCE_REPO/agents_and_skills/agents/" .claude/agents/
rsync -a --delete "$SOURCE_REPO/agents_and_skills/skills/" .claude/skills/
rsync -a --delete .claude/agents/ .cursor/agents/
rsync -a --delete .claude/skills/ .cursor/skills/
if [ -d "$SOURCE_REPO/prompts" ]; then rsync -a "$SOURCE_REPO/prompts/" .github/prompts/; fi
```

### 4c. VS Code user-level prompts (macOS)
```bash
mkdir -p "$HOME/Library/Application Support/Code/User/prompts"
SOURCE_REPO="/Users/kevingrizzard/Documents/GitHub/Notes_and_Ideas"
if [ -d "$SOURCE_REPO/prompts" ]; then
  rsync -a "$SOURCE_REPO/prompts/" "$HOME/Library/Application Support/Code/User/prompts/"
fi
```

---

## 5. Git Subtree Operations

### 5a. One-time setup (add remote + subtree add)
```bash
# Pattern: git remote add ext-<owner>-<repo> https://github.com/<owner>/<repo>.git
# Then:    git subtree add --prefix=.claude/skills/external-<owner>-<repo> ext-<owner>-<repo> main --squash
```

### 5b. Update an existing subtree
```bash
git fetch ext-<owner>-<repo> main
git subtree pull --prefix=.claude/skills/external-<owner>-<repo> ext-<owner>-<repo> main --squash
```

### 5c. Pull this repo into another repo as a subtree
```bash
# Run from the target repo:
git remote add notes-and-ideas https://github.com/kgrizz-git/Notes_and_Ideas.git
git fetch notes-and-ideas
git subtree add --prefix=.claude notes-and-ideas main --squash
# Later updates:
git fetch notes-and-ideas
git subtree pull --prefix=.claude notes-and-ideas main --squash
```

---

## 6. External Repositories (Referenced in Collection)

Source: `info/agents-skills-tools-collection.md`

| Repo | Purpose | URL | Trust/Safety note |
|------|---------|-----|-------------------|
| K-Dense-AI/claude-scientific-skills | Scientific agent skills (EDA, literature review, writing, etc.) | https://github.com/K-Dense-AI/claude-scientific-skills | K-Dense flagship repo; verify per-skill license |
| anthropics/skills | Official Anthropic skills collection | https://github.com/anthropics/skills | Official platform repo |

**Vetted individual skills to import from K-Dense-AI/claude-scientific-skills** (screened in collection file):
- `exploratory-data-analysis`
- `literature-review`
- `scientific-writing`
- `scientific-critical-thinking`
- `scientific-visualization`
- `database-lookup`
- `paper-lookup`
- `hypothesis-generation`
- `markdown-mermaid-writing`
- `get-available-resources`

---

## 7. IDE Skill / Agent Target Directories

Directories that agents and skills should be written to per platform:

| Platform | Agents | Skills |
|----------|--------|--------|
| Cursor (project) | `.cursor/agents/` | `.cursor/skills/` |
| Cursor (global) | `~/.cursor/agents/` | `~/.cursor/skills/` |
| Claude Code (project) | `.claude/agents/` | `.claude/skills/` |
| Claude Code (global) | `~/.claude/agents/` | `~/.claude/skills/` |
| Kiro | `.kiro/agents/` or `~/.kiro/agents/` | `.kiro/skills/` or `~/.kiro/skills/` |
| Antigravity | `.agents/agents/` or `~/.gemini/antigravity/` | `.agents/skills/` |
| VS Code (prompts) | `.github/prompts/` or `~/.../Code/User/prompts/` | `.github/skills/` |
| Portable (this repo) | `agents_and_skills/agents/` | `agents_and_skills/skills/` |

---

## 8. Python Environment (Reference Only)

No Python packages are currently committed to this repo.  
If Python tooling is added, see the skill at `agents_and_skills/skills/python-venv-dependencies/` for venv setup conventions.

---

## Maintenance Notes

- When adding new npm packages to `package.json`, update Section 1.
- When adding new scripts to `tools/`, update Section 3.
- When adding new external repo references to `info/agents-skills-tools-collection.md`, update Section 6.
- When adding new IDE platforms to `info/agents-skills-tools-collection.md`, update Section 7.
