# Template: Scan for General/Reusable Information Files

**Template Version**: 2.0  
**Last Updated**: 2026-02-18

## Purpose

This template instructs you to scan the project documentation for markdown files that contain general information or are designed to be reusable reference material. These files are intended to be **portable and reusable across different projects**—they can be copied to other projects, used as reference material, or adapted for different contexts.

These are **not** plans, implementation details, or project-specific documentation, but rather informational resources that provide:
- General knowledge about technologies, tools, or concepts
- Reusable templates for common tasks
- Reference information that applies beyond this specific project
- Best practices and comparisons that are broadly applicable

## What to Look For

### General/Reusable Information Files

These files typically:
- Provide reference information about technologies, tools, or concepts
- Explain options, comparisons, or best practices
- Contain information that could be useful in multiple contexts
- Are located in directories like:
  - `[DEV_DOCS]/info/` - General information files
  - `[DEV_DOCS]/templates/` - Template files for assessments and documentation

### What to Exclude

**DO NOT** include:
- Plan files (files starting with "plan-" or containing implementation plans)
- Enhancement files (files in `[DEV_DOCS]/enhancements/` that describe specific features)
- Assessment files (timestamped assessment files in various assessment directories)
- Completed plan files
- Project-specific documentation that describes current implementation

## Instructions

1. **Scan the documentation directories**:
   - Review all `.md` files in `[DEV_DOCS]/info/`
   - Review all `.md` files in `[DEV_DOCS]/templates/`
   - Check for any other directories that might contain general/reusable information

2. **For each file found**:
   - Read the file to understand its purpose
   - Determine if it contains general/reusable information (not project-specific plans)
   - Create an entry in `[DEV_DOCS]/info/GENERAL-REUSABLE-INFO.md` with:
     - File name and path
     - Brief summary (2-4 sentences)
     - Link to the file
     - Category/type of information

3. **Update `GENERAL-REUSABLE-INFO.md`**:
   - Add new entries for files not yet listed
   - Review existing entries for accuracy
   - Update summaries if information has changed
   - Ensure all links are correct

## Critical Rule: File Modification

**ONLY modify `[DEV_DOCS]/info/GENERAL-REUSABLE-INFO.md`**

- ✅ **DO** update `GENERAL-REUSABLE-INFO.md` with new entries or corrections
- ❌ **DO NOT** modify any other files during this scanning process
- ❌ **DO NOT** edit the source information files themselves
- ❌ **DO NOT** change template files

The purpose is to create and maintain a **catalog/index** of reusable information that can be easily:
- **Referenced** within this project
- **Copied** to other projects
- **Shared** as reference material
- **Adapted** for different contexts

This catalog makes it easy to identify which files are portable and useful for other projects, not just this one.

## Format for Entries

Each entry in `GENERAL-REUSABLE-INFO.md` should follow this format:

```markdown
### [File Name]

**Location**: `[DEV_DOCS]/info/filename.md` (or `[DEV_DOCS]/templates/filename.md`)

**Summary**: Brief description of what information this file contains and when it would be useful.

**Category**: [Information Type] (e.g., "Tool Comparison", "License Information", "Technical Reference", "Template")

**Portability**: Note how portable/useful this file is for other projects (e.g., "Highly portable - can be copied directly", "Project-specific references may need adaptation", "Universal template - works for any project")
```

When assessing portability, consider:
- Does it contain project-specific references that would need to be changed?
- Is the information general enough to apply to other projects?
- Can templates be used as-is or do they need customization?
- Are there any dependencies on this specific project's structure?

## Completion

After scanning and updating `GENERAL-REUSABLE-INFO.md`:
- Verify all entries are accurate
- Ensure all links work
- Confirm no general/reusable info files were missed
- Document any files that were excluded and why
