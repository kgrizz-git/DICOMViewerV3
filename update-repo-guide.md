# Update Repo Guide Prompt

Generate and maintain a high-level overview of the repository in `repo-guide.md`, serving as the entry point for navigation and discovery.

## Exclusion Reference

See [updates-EXCLUSION-LIST.md](updates-EXCLUSION-LIST.md) for Global Exclusions. This prompt ignores those directories.

## Workflow

**Before generating guide:**
1. Scan all non-excluded directories in the repo root
2. For each directory, gather:
   - Its corresponding `list-[dirname].md` file (if it exists)
   - A README.md within the directory (if it exists)
   - Directory structure and key files

**Generate repo-guide.md sections:**

1. **Quick Navigation** — Create a bullet list of all major sections with anchor links
2. **Section Summaries** — For each main directory:
   - Extract a brief (1-2 sentence) description of what it contains
   - Reference the corresponding `list-[dirname].md` file
   - Include any key nested links (e.g., to agents_and_skills/agents, agents_and_skills/skills)
3. **External Links** — Scan ALL markdown files in the repo for external links (http://, https://):
   - Extract each unique external link with its display text
   - Categorize links by apparent topic (e.g., Documentation, Tools, Agent Frameworks, Azure, GitHub, Other)
   - Present as an organized section with subcategories
   - Avoid duplicates
4. **Metadata** — Add at the top: "Last updated: $(date +%Y-%m-%d %H:%M:%S)"
5. **Cleanup & Integrity** — Before saving, remove stale references:
   - Remove links to internal files/directories that no longer exist (dead internal links)
   - Remove references to list files or repo files that were deleted
   - If a section becomes empty after cleanup, remove that empty section

## Link Structure

For sections that have list files:
- Provide link: `See [list-dirname.md](list-dirname.md) for complete catalog`

For nested content:
- Link to subdirectories or files within: `[agents_and_skills/agents/](agents_and_skills/agents/)`

For external links section:
- Format: `[Link Text](https://example.com)` — Category

## External Links Collection

When scanning for external links:
1. Extract from all markdown files (excluding global exclusions)
2. Look for patterns: `[text](http...`, `(https://...`, bare URLs if contextually clear
3. Group by category:
   - **Documentation** — Official docs, guides, tutorials
   - **Agent & AI Frameworks** — Microsoft Agent Framework, Cursor, Claude, etc.
   - **Azure Services** — Azure documentation and tools
   - **GitHub & DevOps** — GitHub, Git, CI/CD tools
   - **Development Tools** — IDEs, extensions, utilities
   - **Other** — Miscellaneous references
4. Remove duplicates (same URL only appears once, but note if called by multiple names)
5. Present with brief context (e.g., "Referenced in [filename]")

## Important Notes

- Keep summaries brief and scannable
- Maintain links to all list-*.md files so they remain discoverable
- Update only if there are material changes to directory contents or new external links added
- Always prune dead internal links and entries for deleted files during each update
- Do not edit files in excluded directories
