## Exclusion Reference

See [updates-EXCLUSION-LIST.md](updates-EXCLUSION-LIST.md) for:
- **Global Exclusions** — applied to all update prompts
- **List Generation Exclusions** — specific to this prompt

These are filtered out automatically before scanning.

## Workflow

**Before scanning directories:**
1. Load exclusions from `updates-EXCLUSION-LIST.md` (Global Exclusions and List Generation Exclusions)
2. Identify all subdirectories in the repo root
3. Filter out: anything matched by `.gitignore` and anything in the Exclusion Lists
4. For any remaining directory that does **not** already have a "list-[dirname].md" file:
   - Check if it's in the Exclusion Lists → if yes, skip it
   - If not in the Exclusion Lists, **ask the user**: "Should directory `[dirname]/` be excluded from list generation?"
   - Update `updates-EXCLUSION-LIST.md` → List Generation Exclusions if user confirms exclusion
5. For each existing `list-[dirname].md` that will be maintained, remove dead internal links and entries that reference files no longer present in that directory
6. Proceed with list file generation (see below)

## List File Generation

For each subdirectory **that is not ignored by `.gitignore`** and not in the Exclusion Lists, create or update an md file in the repo base named "list-[subdirectory_name].md" that contains a list of the files in the subdirectory with a 2-sentence summary and a link to the file. Do not create or maintain list files for gitignored paths or excluded directories. There may already be list items in the md file that do not have detailed md files written up in the subdirectory. That is fine; do not delete them from the list.

Before saving each list file, validate links and prune stale content:
- Remove entries whose linked files no longer exist in the target subdirectory
- Remove or repair dead internal markdown links (links to missing repo files/directories)
- Keep legitimate entries that still point to existing files, even if descriptions are brief or incomplete

Add at the top of each: "Last updated: $(date +%Y-%m-%d %H:%M:%S)"