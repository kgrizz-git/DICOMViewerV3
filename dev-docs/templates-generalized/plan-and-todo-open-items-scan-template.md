# Plan and To-Do Open Items Scan Template - [PROJECT_NAME]

**Template Version**: 1.0  
**Last Updated**: 2026-03-31

## Purpose

This document provides a systematic approach to scan Markdown files across a repository, identify planning and to-do content, and assess what has **not** been marked complete (or otherwise indicated as complete).

This scan is intended to answer:

- Which Markdown files contain plans, TODOs, checklists, or pending tasks
- Which items are still open or unclear
- Which items appear complete based on explicit status markers
- Where status tracking is inconsistent or ambiguous

## Scope

This template is for **documentation status scanning only**:

- Scan repository Markdown files (`*.md`)
- Focus on plans, action lists, TODOs, checklists, and milestones
- Assess completion status based on what is explicitly written
- Produce a clear backlog of open and unresolved items

## How to Use This Document

### Important: Create a Timestamped Copy

**Do not check boxes in this master template.**

For each scan:

1. Create a timestamped copy in your scan-results folder.
2. Perform the scan using the copy.
3. Keep this template unchanged for future scans.

Recommended filename format:

- `plan-todo-open-items-scan-YYYY-MM-DD-HHMMSS.md`

### Critical Rules for This Scan

- **No code edits**: Do not modify any source code files.
- **No documentation edits**: Do not modify existing docs as part of scan.
- **Only update the timestamped scan file**.
- **Do not infer completion from assumptions**: only explicit markers count.
- **Ignore backup folders and backup files** during discovery and analysis.

### Line Count Target for Result File

Keep the final timestamped scan result to around **800 lines or fewer** by:

- Prioritizing high-signal findings first
- Grouping similar low-priority items
- Avoiding repeated context for the same file
- Using summary tables instead of long prose where possible

---

## Assessment Methodology

### Step 1: Discover Markdown Files

Discover all `*.md` files in scope, then exclude backup content.

#### Exclusion Rules (Required)

Ignore Markdown files inside backup-related locations and backup-like filenames, including patterns such as:

- `**/backup/**`
- `**/backups/**`
- `**/.backup/**`
- `**/archive/**` when used as backup storage
- `**/*backup*.md` when the file is clearly a backup copy
- Timestamped backup naming patterns (for example: `*-backup-YYYYMMDD*`)

If uncertain whether a file is a backup artifact, mark it as "excluded - likely backup" and continue.

#### Discovery Notes

Record:

- Total Markdown files found before exclusions
- Total excluded as backup-related
- Total remaining in-scope Markdown files

### Step 2: Identify Candidate Plan/To-Do Documents

From in-scope Markdown files, flag files that likely contain task tracking. Common indicators:

- Filenames containing: `todo`, `to-do`, `plan`, `roadmap`, `next`, `remaining`, `backlog`, `milestone`
- Sections containing checklist syntax (`[ ]`, `[x]`)
- Sections with status labels (for example: `In Progress`, `Done`, `Pending`, `Blocked`)
- Action-oriented headings (for example: "Next Steps", "Implementation Plan", "Outstanding Work")

Classify each candidate file as one of:

- Plan document
- To-do/task tracker
- Mixed (plan + status tracking)
- Not a status-tracking document (false positive)

### Step 3: Parse Completion Signals

For each candidate file, extract items and classify their status strictly from explicit signals.

#### Explicitly Complete Signals

Treat as complete only when clearly marked by one or more of:

- Checked checkbox: `[x]` or `[X]`
- Completed status words: `done`, `complete`, `completed`, `implemented`
- Completion markers: `✅`
- Date-stamped completion notes (for example: "Completed on 2026-03-01")

#### Explicitly Open Signals

Treat as open when marked by one or more of:

- Unchecked checkbox: `[ ]`
- Open status words: `todo`, `pending`, `remaining`, `not started`, `blocked`
- Open markers: `❌`, `🚧`, `⏳`, or equivalent "not complete" labels

#### Ambiguous Signals

If status is unclear, classify as **Ambiguous** (do not force complete/open).

Examples:

- Item described in past tense without explicit completion marker
- Conflicting markers in the same item/section
- Checklist item with no status marker and unclear context

### Step 4: Assess "Not Marked Complete"

Build the unresolved set using:

- Explicitly Open items
- Ambiguous items
- Items with conflicting status markers

Report unresolved items with:

- File path
- Item text (trimmed for readability)
- Status type (Open, Ambiguous, Conflicting)
- Reason for classification
- Suggested doc-follow-up action (for later, not now)

### Step 5: Consolidate and Prioritize

Prioritize unresolved items:

- **High**: likely active work items or blockers in primary planning docs
- **Medium**: unresolved items in secondary docs
- **Low**: minor ambiguity, stale docs, or low-impact tracking gaps

When multiple files track the same item, consolidate into one normalized entry and list all source files.

### Step 6: Produce a Concise Final Report

Output should include:

- Scan scope summary
- File inventory summary
- Status totals (Complete/Open/Ambiguous/Conflicting)
- Prioritized unresolved items
- Follow-up recommendations (documentation-only, no edits performed)

Keep the output concise enough to remain around the 800-line target.

---

## Checklist

### Preparation

- [ ] Create timestamped copy of this template
- [ ] Confirm scan is analysis-only (no code/doc edits)
- [ ] Define markdown discovery scope
- [ ] Define backup exclusions

### Discovery

- [ ] Enumerate all `*.md` files
- [ ] Exclude backup folders/files
- [ ] Record discovery counts
- [ ] Identify candidate plan/to-do documents

### Status Analysis

- [ ] Extract tracked items from each candidate file
- [ ] Classify explicit complete items
- [ ] Classify explicit open items
- [ ] Classify ambiguous/conflicting items
- [ ] Consolidate duplicates across files

### Reporting

- [ ] Summarize totals by status type
- [ ] List unresolved items with rationale
- [ ] Prioritize unresolved items
- [ ] Add follow-up recommendations
- [ ] Verify report is around 800 lines or less

---

## Results Template (for Timestamped Copy)

```markdown
# Plan and To-Do Open Items Scan - YYYY-MM-DD HH:MM:SS

## Scan Metadata
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Assessor**: [Name/AI Agent]
- **Repository**: [PROJECT_NAME]
- **Mode**: Analysis only (no code/doc edits)

## Scope and Exclusions
- **File type scanned**: Markdown (`*.md`)
- **Backup exclusions applied**: Yes
- **Excluded backup patterns**:
  - `**/backup/**`
  - `**/backups/**`
  - `**/.backup/**`
  - `**/*backup*.md`
  - [Any project-specific exclusions]

## Discovery Summary
- **Markdown files discovered (pre-exclusion)**: X
- **Excluded as backup-related**: X
- **Markdown files in scope**: X
- **Candidate plan/to-do files**: X
- **False positives**: X

## Candidate File Inventory

| File | Type | Contains Checklists | Contains Status Labels | Included |
|------|------|---------------------|------------------------|----------|
| `dev-docs/TO_DO.md` | To-do | Yes | Yes | Yes |
| `dev-docs/plans/example-plan.md` | Plan | Yes | Yes | Yes |
| `dev-docs/archive/old-plan.md` | Plan | Yes | No | No (backup/archive) |

## Status Totals
- **Complete**: X
- **Open**: X
- **Ambiguous**: X
- **Conflicting**: X
- **Total unresolved (Open + Ambiguous + Conflicting)**: X

## Unresolved Items (Prioritized)

### High Priority
1. **Item**: [Text]
   - **Status Type**: Open / Ambiguous / Conflicting
   - **Source**: `path/to/file.md`
   - **Reason**: [Why unresolved]
   - **Follow-up**: [Suggested doc update for later]

### Medium Priority
1. **Item**: [Text]
   - **Status Type**: Open / Ambiguous / Conflicting
   - **Source**: `path/to/file.md`
   - **Reason**: [Why unresolved]
   - **Follow-up**: [Suggested doc update for later]

### Low Priority
1. **Item**: [Text]
   - **Status Type**: Open / Ambiguous / Conflicting
   - **Source**: `path/to/file.md`
   - **Reason**: [Why unresolved]
   - **Follow-up**: [Suggested doc update for later]

## Ambiguity and Conflict Notes
- [File/section]: [Brief description of ambiguity/conflict]
- [File/section]: [Brief description of ambiguity/conflict]

## Recommended Next Actions (No Edits Performed)
- Review high-priority unresolved items with project owner
- Update source planning docs in a separate documentation-update phase
- Standardize completion markers across planning docs
- Re-run this scan after updates

## Output Size Check
- **Approximate line count**: X
- **Within target (<= ~800 lines)**: Yes / No
```

---

## Notes

- This template intentionally separates **status scanning** from **implementation**.
- If you later perform doc updates, do so in a separate pass with explicit approval.
- When in doubt, classify as Ambiguous rather than assuming completion.
- If scanning multiple planning ecosystems (for example `dev-docs/`, `docs/`, project root), keep one combined report to avoid duplication.

---

## Template Version

- **Version**: 1.0
- **Created**: 2026-03-31
- **Last Updated**: 2026-03-31
- **SemVer Impact Note**: Documentation-only template addition; no application/runtime behavior change.
