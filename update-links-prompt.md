# Update Links Prompt

Create and update markdown links across the repo based on file references and semantic relationships.

## Exclusion Reference

See [updates-EXCLUSION-LIST.md](updates-EXCLUSION-LIST.md) for:
- **Global Exclusions** — applied to all update prompts
- **Link Generation Exclusions** — specific to this prompt

Do not add links to or from files in these lists.

## Workflow

**Before processing files:**
1. Load the Exclusion List from `updates-EXCLUSION-LIST.md`
2. Identify all markdown files in the repo (excluding those in Global Exclusions and Link Generation Exclusions)
3. For any markdown file that was not in the last run:
   - Ask the user: "Should file `[filename]` be excluded from link generation?"
   - Update `updates-EXCLUSION-LIST.md` → Link Generation Exclusions if user confirms

**Link Cleanup (enforce rules on existing links):**
1. Scan all markdown files for existing markdown links: `[text](path/to/file)`
2. For each link, verify:
   - Does the target file exist?
   - Is the target file in Global Exclusions or Link Generation Exclusions?
   - Do the source and target files respect Isolation Rules?
3. For any broken or rule-violating links:
   - **Remove the link** (keep the display text if it's meaningful prose, otherwise remove entirely)
   - Report what was removed and why (e.g., "Removed link from `info/guide.md` to `list-ideas.md` — list files are excluded from linking")
   - Ask the user to confirm each removal if unsure

**Link Generation (add new links):**
1. Scan markdown files for:
   - Bare file names or paths (e.g., "see `agents_and_skills/README.md`" or "the planner.md file")
   - Folder references (e.g., "in the `info/` directory")
   - Section references (e.g., "as described in Agent Orchestration section")
2. For each reference, determine:
   - Does a corresponding file/section exist in the repo?
   - Is that file/section in the Exclusion List?
   - Do the source and target files respect the Isolation Rules (Fenced, Only-In, Only-Out)?
   - Is it already linked?
3. If conditions are met, create or update the markdown link using the format:
   - File: `[path/to/file.md](path/to/file.md)`
   - File with section: `[descriptive text](path/to/file.md#L10-L20)` or `[descriptive text](path/to/file.md)`
   - Ambiguous cases: ask the user before creating the link

## Link Format

Follow these conventions:
- Use workspace-relative paths (no `file://` or `vscode://`)
- Display text should be descriptive or match the filename
- For cross-file links, format: `[text](path/to/file.md)`
- Avoid overlinking — prioritize clarity and avoid cluttering text with excessive brackets

## Exclusion Checks

Before modifying any file:
- Verify it's not in Global Exclusions or Link Generation Exclusions
- Apply Isolation Rules from `updates-EXCLUSION-LIST.md`:
  - **Fenced directories**: only allow links between files within the same directory
  - **Only-In directories**: allow links from outside → in, but not from inside → out
  - **Only-Out directories**: allow links from inside → out, but not from outside → in
- If referencing another file, verify that file is also not in exclusions and that the link direction respects isolation rules
- Do not create links to or from excluded files, and do not violate isolation rules
