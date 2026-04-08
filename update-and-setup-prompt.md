# Update and Setup Prompt

Run all update prompts in sequence, then optionally offer a context-aware setup menu based on what is actually present in the repo.

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

After all update prompts complete, load [.agent_files/repo-setup-manifest.md](.agent_files/repo-setup-manifest.md) and use it as a planning aid.

Before proposing any setup/install action:
- Scan the repo to verify what toolchains and workflows are actually present.
- Cross-check the manifest against current files and references.
- Confirm assumptions with the user before running anything.

Important defaults:
- Do not assume every repo needs package installs, browser binaries, sync scripts, subtree operations, or external clones.
- In many repos, only Phase 1 update prompts are needed; treat setup steps as optional unless evidence suggests they are useful.

> Always show the exact commands you plan to run **before** running them and wait for the user to confirm.

---

### Group A — Package Manager Dependencies (Only if detected)

**What:** Offer dependency installation only when a package manager manifest is present (for example: `package.json`, `requirements.txt`, `pyproject.toml`, `Pipfile`, `poetry.lock`, `Cargo.toml`, `go.mod`, etc.).

**Ask (example):** "I found <manifest>. Would you like me to install dependencies now?"

**Command rule:** Propose commands appropriate to the detected ecosystem (for example, `npm install`, `pnpm install`, `pip install -r requirements.txt`, `poetry install`), and explain why each command is relevant.

---

### Group B — Test/Runtime Tooling Assets (Only if detected)

**What:** Offer installation/setup of secondary tooling assets only if required by detected tools (for example Playwright browsers, language toolchains, local runtimes, codegen prerequisites).

**Ask (example):** "I found <tool> configuration. Would you like to install the required runtime assets now?"

**Options rule:** Offer a minimal option, a full option, and skip whenever practical.

---

### Group C — Repo Scripts and Automation (Only if useful)

For each script listed in `.agent_files/repo-setup-manifest.md` (and any scripts discovered in the repo), explain:
1. What it does
2. Why it may help in this repo
3. Risks/side effects (network calls, file writes, git operations)

Then ask whether the user wants to run it.

Do not assume scripts should be run by default.

---

### Group D — Cross-Repo / IDE Sync (Only if requested)

If the repo contains portable agent/skill/prompt content, offer sync actions only if the user asks for them.

Possible sync targets may include global user directories or another repo. Always ask for target paths explicitly and confirm overwrite/delete behavior for `rsync --delete` style commands.

Show all planned commands and wait for confirmation before running any sync.

---

### Group E — Git/Subtree Operations (Only if requested)

Offer git remote/subtree operations only when the user explicitly wants to link repos that way.

Do not run git topology changes by default.

---

### Group F — External Repositories (Optional)

Offer clone/pull/explore actions for external repos only when they are relevant to the user's stated goal.

If proposing external repos from references, explain the purpose of each and ask before any network operation.

---

### Group G — Relevance Cleanup (Audit First, Remove Only with Approval)

Evaluate whether currently installed packages/tools appear unrelated to the repo's present purpose.

Audit signals may include:
- Dependencies not referenced by source, scripts, tests, docs, or CI config
- Tooling installed for workflows no longer present
- Duplicate/overlapping tools where one is clearly unused

For each candidate, present:
1. Why it appears potentially unnecessary
2. What could break if removed
3. Exact uninstall/remove command(s)

Then ask the user if they want to remove it. Do not remove anything without explicit confirmation.

---

### Decision Heuristics (Required)

Before proposing Group A-G actions, classify each as:
- `likely helpful now`
- `optional / later`
- `not recommended for this repo right now`

Base this on concrete repo evidence plus user goals, not on template assumptions.

---

### Manifest Hygiene

Maintain `.agent_files/repo-setup-manifest.md` as an agent-side planning file.

At the top of that file, keep a short project-context summary (purpose, major tech/tooling, common tasks). On every run, verify it is still accurate by scanning the repo and confirming with the user.

If stale, update the manifest before proposing setup actions.

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

Phase 2 removals performed:
  [list each removal action taken, or "none"]
```

If the user declined all setup options, note that `.agent_files/repo-setup-manifest.md` is available for future runs.
