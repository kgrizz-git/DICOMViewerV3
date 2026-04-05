# Update and Setup Prompt

Run all update prompts in sequence, then offer the user an interactive install/setup menu for everything referenced in the repo.

---

## Exclusion Reference

See [updates-EXCLUSION-LIST.md](updates-EXCLUSION-LIST.md) for global and per-prompt exclusions. All three update prompts below inherit those rules.

---

## Phase 1: Run All Update Prompts (in order)

Execute the following prompts sequentially. Each one depends on the previous being complete before starting.

### Step 1 — Update list files
Follow the full workflow in [update-lists-prompt.md](update-lists-prompt.md).

- Scan directories, create/update `list-[dirname].md` files, prune stale entries.
- Ask the user about any new directories not yet in the exclusion list before proceeding.
- Do not start Step 2 until this is complete.

### Step 2 — Update markdown links
Follow the full workflow in [update-links-prompt.md](update-links-prompt.md).

- Run link cleanup first, then link generation.
- Respect all Isolation Rules from `updates-EXCLUSION-LIST.md`.
- Do not start Step 3 until this is complete.

### Step 3 — Update repo guide
Follow the full workflow in [update-repo-guide.md](update-repo-guide.md).

- Regenerate `repo-guide.md` with updated section summaries and external links.
- Prune dead internal links and empty sections.

---

## Phase 1b: Structure Review

After all three update prompts complete, assess the overall state of the repo's file and folder structure:

1. **Complexity check** — Are any files becoming very long, covering too many unrelated topics, or hard to navigate?
2. **Link density check** — Are any files accumulating an unusually high number of inbound or outbound links, suggesting they've become an informal hub that would benefit from splitting?
3. **Naming/grouping check** — Are there files that logically belong in a subdirectory, or subdirectories that could be merged or renamed for clarity?
4. **Folder sprawl check** — Are there loose files at the repo root that would fit better in an existing subdirectory?

If any of the above apply, **suggest** specific structural changes to the user (e.g., "Consider moving X to Y" or "File Z has grown large — suggest splitting into A and B"). Do not make any structural changes without explicit user approval.

If the structure looks clean, note that briefly and move on.

---

## Phase 2: Install and Setup Menu

After all update prompts complete, load [repo-setup-manifest.md](repo-setup-manifest.md) and present the user with the following grouped menu. For each group, describe what will happen, then ask for confirmation before running anything.

> Always show the exact commands you plan to run **before** running them and wait for the user to confirm.

---

### Group A — npm Packages

**What:** Install `@playwright/test` and `@types/node` from `package.json`.

**Ask:** "Would you like to run `npm install` to install the repo's npm devDependencies?"

**Command:**
```bash
npm install
```

---

### Group B — Playwright Browser Binaries

**What:** Download browser binaries required to run the Playwright test suite in `tests/`.

**Ask:** "Would you like to install Playwright browser binaries? (Required to run tests)"

**Options to offer:**
1. All browsers: `npx playwright install`
2. Chromium only: `npx playwright install chromium`
3. Skip

---

### Group C — Shell Scripts in `tools/`

For each script listed in `repo-setup-manifest.md` Section 3, describe its purpose and ask the user if they want to run it.

**`tools/sync-external-skills-subtree.sh`**  
Pulls an external GitHub skills repo into `.claude/skills/external-<owner>-<repo>` via git subtree.

**Ask:** "Would you like to pull any external skills repos using the subtree sync script?"

If yes, prompt for:
- Which repos to pull (offer the vetted list from Manifest Section 6: K-Dense-AI/claude-scientific-skills, anthropics/skills)
- Or a custom OWNER/REPO to specify

Show the exact command and wait for confirmation before running.

---

### Group D — Agent & Skill Sync

**What:** Sync the `agents_and_skills/` folder to IDE-specific directories (global and/or per-repo).

**Ask:** "Would you like to sync agents and skills from this repo to other locations?"

Offer the following sub-options (the user may choose one, multiple, or none):

1. **Global (machine-wide)** — sync to `~/.cursor/` and `~/.claude/` so all your projects use these agents and skills  
   *(uses rsync — Manifest Section 4a)*

2. **Another repo** — sync into a target repo's `.claude/` and `.cursor/` directories  
   *(prompt user for the absolute path to the target repo — Manifest Section 4b)*

3. **VS Code user prompts** — copy any prompts to `~/Library/Application Support/Code/User/prompts/` (macOS)  
   *(Manifest Section 4c)*

Show all commands and wait for confirmation before running any rsync.

---

### Group E — Git Subtree Operations

**What:** Pull this entire Notes_and_Ideas repo as a subtree into another repo, or update an existing subtree.

**Ask:** "Would you like to set up or update a git subtree link to this repo in another project?"

If yes:
- Ask: Add new subtree (one-time setup) or update an existing one?
- Prompt for target repo path
- Show the commands from Manifest Section 5c and wait for confirmation

---

### Group F — (Optional) External Repos

**What:** Clone or otherwise pull in external repos referenced in `info/agents-skills-tools-collection.md` (beyond the subtree script above).

**Ask:** "Are there any external repos you'd like to clone or explore? (e.g., K-Dense-AI/claude-scientific-skills, anthropics/skills)"

Only proceed if the user explicitly confirms. Do not clone anything silently.

---

## Completion Summary

After all phases and any confirmed installs are done, print a brief summary:

```
Phase 1 complete:
  ✓ list files updated
  ✓ markdown links updated
  ✓ repo-guide.md updated

Phase 2 installs performed:
  [list each action taken, or "none" if user skipped all]
```

If the user declined all install options, note that `repo-setup-manifest.md` is available for reference if they want to run anything later.
