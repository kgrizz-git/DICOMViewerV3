# Documentation Refactor Assessment Template - [PROJECT_NAME]

## Purpose

This document provides a systematic approach to analyze documentation markdown files in the codebase for refactoring opportunities. The assessment identifies documentation files exceeding 750 lines and provides structured recommendations for breaking them into smaller, more maintainable documentation modules while preserving key information and improving readability.

## How to Use This Document

### Important: Creating Assessment Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each documentation refactor assessment:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/refactor-assessments/docs-refactor-assessment-YYYY-MM-DD-HHMMSS.md`
   - Use format: `docs-refactor-assessment-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp [DEV_DOCS]/templates/doc-refactor-assessment-template.md "[DEV_DOCS]/refactor-assessments/docs-refactor-assessment-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Add specific recommendations and evaluations for each file
   - Document any refactoring suggestions discovered during the assessment

3. **After completing the assessment**:
   - Review all findings in the timestamped file
   - If new assessment patterns or criteria are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific assessment

### Critical: No Documentation Changes During Assessment

**DO NOT edit any documentation files during the refactor assessment.** The assessment is for **analysis and documentation only**.

- **Document opportunities, don't implement them**: When you identify a refactoring opportunity, document it thoroughly in the timestamped assessment file with:
  - Exact location (file and line numbers or sections)
  - Description of the refactoring opportunity
  - Proposed structure and content organization
  - What should remain in the original file
  - What should be moved to new files
  - How files should reference each other
  - Evaluation scores and justifications
  - Benefits and risks

- **Only edit the timestamped assessment file**: The only file that should be modified during the assessment is the new timestamped markdown file created for this specific assessment.

- **Separate phases**: 
  - **Phase 1 (Assessment)**: Identify and document all refactoring opportunities
  - **Phase 2 (Implementation)**: After assessment completion, review findings with team/user and implement refactorings separately

This approach ensures:
- The assessment remains focused on discovery and analysis, not implementation
- All opportunities are documented before any documentation changes
- The user/team can prioritize which refactorings to address first
- The assessment results provide a complete picture of all refactoring opportunities
- Assessment results are not mixed with actual documentation changes

### Important: Plan Files Are Analysis-Only

**DO NOT edit plan MD files during this assessment phase.** Plan files should be analyzed for refactoring opportunities, but no changes should be made to them during the assessment. Only the analysis results should be documented in the timestamped assessment file.

### Assessment Process

1. **After significant documentation additions or periodically**, create a new timestamped copy and run through the entire assessment
2. **Identify all documentation markdown files** in the codebase (excluding `[DEV_DOCS]/completed-plans/`, `[DEV_DOCS]/info/`, `[DEV_DOCS]/doc-assessments/`, `[DEV_DOCS]/refactor-assessments`, `[DEV_DOCS]/testing-assessments`, and `[DEV_DOCS]/safety-scans` which should be ignored)
3. **Count lines** for each file and identify those exceeding 750 lines
4. **Analyze each large file** for refactoring opportunities:
   - Identify key ideas and checklists that should remain
   - Identify background information or extra details that could be moved
   - Identify sections that could be split into separate files
   - Identify plan files with very long checklists that could be split
5. **Evaluate each refactoring suggestion** using the criteria below
6. **Prioritize recommendations** based on evaluation scores

## Line Count Threshold

- **Threshold**: 750 lines per documentation file
- **Rationale**: Documentation files exceeding this threshold may become difficult to navigate, maintain, and understand. Breaking them into smaller, focused documents improves:
  - Readability and navigation
  - Maintainability (easier to locate and update specific information)
  - Organization (related information grouped together)
  - Reusability (background information can be referenced from multiple documents)
  - Collaboration (smaller files reduce merge conflicts)

**Note**: This threshold is a guideline, not a hard rule. Some files may be appropriately large due to their nature, but should still be evaluated for refactoring opportunities.

---

## Assessment Methodology

### Step 1: Identify Files to Analyze

1. **Find all documentation markdown files**:
   - Root directory: `*.md` files (README, etc.)
   - `[DEV_DOCS]/` directory and subdirectories
   - `user-docs/` directory and subdirectories (if applicable)
   - **Exclude**: `[DEV_DOCS]/completed-plans/` (ignore during this analysis)

2. **Count lines** for each file:
   - Use `wc -l` or similar tool
   - Include all content (headers, text, code blocks, lists, etc.)
   - Document the exact line count

3. **List files exceeding threshold**:
   - Create a table with filename, line count, location, and file type

### Step 2: Analyze Each Large File

For each file exceeding 750 lines, perform the following analysis:

1. **Content Inventory**:
   - List major sections and their line counts
   - Identify key ideas and checklists
   - Identify background information or extra details
   - Identify repetitive content
   - Identify content that could stand alone

2. **Content Organization**:
   - How is the content currently organized?
   - Are there clear sections or logical groupings?
   - Are there sections that could be extracted?
   - Are there plan files with very long checklists that could be split?

3. **Refactoring Opportunities**:
   - Identify background information that could be moved to `[DEV_DOCS]/info/`
   - Identify extra details that could be moved to separate files
   - Identify plan files with long checklists that could be split (e.g., "plan-30a.md" and "plan-30b.md")
   - Identify content that should remain in the original (key ideas, checklists, summaries)

### Step 3: Propose Refactoring Plan

For each refactoring opportunity, create a detailed plan:

1. **Proposed Structure**:
   - What new files would be created?
   - What content would move to each new file?
   - What would remain in the original file?
   - How should files reference each other?

2. **File Naming Strategy**:
   - New files should be descriptively named
   - New files should relate to the original file name (unless information is more general)
   - Examples:
     - If extracting background info from `TECHNICAL_DETAILS.md` about specific technology, create `[technology]-background-info.md` or similar
     - If extracting general dev background info, use descriptive name and place in `[DEV_DOCS]/info/`
     - If splitting a plan file, use numbered suffixes like `plan-30a.md` and `plan-30b.md`

3. **Content Organization**:
   - Key ideas and checklists should remain in the original
   - Background information and extra details should move to new files
   - Original file should reference new files where appropriate
   - New files should be self-contained and well-documented

4. **Location Strategy**:
   - If content is for developers and is background information or extra details or is generally applicable, place in `[DEV_DOCS]/info/`
   - If content is specific to a particular document or feature, place it near the original file or in an appropriate subdirectory
   - Plan files should remain in their current location if split (e.g., both `plan-30a.md` and `plan-30b.md` in same directory)

### Step 4: Evaluate Each Refactoring Suggestion

For each refactoring suggestion, evaluate using the following criteria:

#### Evaluation Criteria

1. **Ease of Implementation** (1-5 scale):
   - **1 (Very Difficult)**: Requires extensive reorganization, complex dependencies between sections, unclear boundaries
   - **2 (Difficult)**: Significant reorganization required, some dependencies, moderate complexity
   - **3 (Moderate)**: Moderate reorganization, manageable dependencies, straightforward implementation
   - **4 (Easy)**: Simple reorganization, clear boundaries, low complexity
   - **5 (Very Easy)**: Minimal reorganization, obvious boundaries, very straightforward

2. **Safety** (1-5 scale):
   - **1 (High Risk)**: High probability of losing information, breaking references, or creating confusion
   - **2 (Moderate-High Risk)**: Some risk of information loss or broken references
   - **3 (Moderate Risk)**: Moderate risk, manageable with careful planning
   - **4 (Low Risk)**: Low risk, clear content boundaries, easy to verify
   - **5 (Very Low Risk)**: Very low risk, obvious boundaries, minimal impact

3. **Practicality** (1-5 scale):
   - **1 (Impractical)**: Not worth the effort, minimal benefit, high cost
   - **2 (Questionable)**: Benefits unclear, significant effort required
   - **3 (Moderate)**: Reasonable benefit-to-effort ratio, worthwhile if time permits
   - **4 (Practical)**: Good benefit-to-effort ratio, recommended when possible
   - **5 (Highly Practical)**: Excellent benefit-to-effort ratio, should be prioritized

4. **Recommendation** (1-5 scale):
   - **1 (Not Recommended)**: Should not be done, risks outweigh benefits
   - **2 (Low Priority)**: Can be considered but not urgent, low priority
   - **3 (Consider)**: Worth considering, moderate priority
   - **4 (Recommended)**: Should be done, good priority
   - **5 (Highly Recommended)**: Should be prioritized, high value

**Overall Score**: Average of the four criteria (Ease + Safety + Practicality + Recommendation) / 4

---

## Assessment Checklist

### Preparation

- [ ] Create timestamped copy of this template
- [ ] **Remember: Only edit the timestamped assessment file - do not modify any documentation files**
- [ ] **Remember: Plan MD files are analysis-only - do not edit them during assessment**
- [ ] Identify all `.md` documentation files in codebase (excluding `[DEV_DOCS]/completed-plans/`)
- [ ] Count lines for each file
- [ ] Create list of files exceeding 750 lines

### Analysis

For each file exceeding 750 lines:

- [ ] Document file path and line count
- [ ] Identify file type (user-facing doc, dev doc, plan, enhancement, info, template, assessment, etc.)
- [ ] List major sections and their approximate line counts
- [ ] Identify key ideas and checklists that should remain in original
- [ ] Identify background information or extra details that could be moved
- [ ] Identify content that could be extracted to separate files
- [ ] For plan files: Identify if checklist is very long and could be split
- [ ] Analyze content organization and structure
- [ ] Identify refactoring opportunities
- [ ] Document proposed refactoring plan (what stays, what moves, where it goes)
- [ ] Evaluate each refactoring suggestion (Ease, Safety, Practicality, Recommendation)
- [ ] Calculate overall score for each suggestion
- [ ] Prioritize recommendations

### Documentation

- [ ] Create summary table of all files analyzed
- [ ] Create prioritized list of refactoring recommendations
- [ ] Document any files that are appropriately large (with justification)
- [ ] Note any patterns or observations about the documentation structure
- [ ] Document file naming strategies for proposed new files
- [ ] Document location strategies for proposed new files

---

## Assessment Results Template

Use this structure in your timestamped assessment file:

```markdown
# Documentation Refactor Assessment - YYYY-MM-DD HH:MM:SS

## Assessment Date
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Assessor**: [Name/AI Agent]

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds Threshold | File Type | Status |
|------|----------|------------|-------------------|-----------|--------|
| filename.md | path/to/file | XXX | Yes/No | [Type] | Analyzed |

**File Type Categories**:
- User-facing documentation
- Developer documentation
- Plan file
- Enhancement document
- Info/background document
- Template
- Assessment/analysis document
- Other

## Detailed Analysis

### File: [filename.md]

**Location**: `path/to/filename.md`  
**Line Count**: XXX  
**Exceeds Threshold**: Yes/No  
**File Type**: [Type]

#### Content Inventory

**Major Sections**:
- Section 1 (lines X-Y, ~ZZ lines): [Description]
- Section 2 (lines A-B, ~CC lines): [Description]
- ...

**Key Ideas and Checklists** (should remain in original):
- [List key ideas, checklists, summaries that should stay]

**Background Information or Extra Details** (candidates for extraction):
- [List background info, extra details, deep dives that could be moved]

**Repetitive Content**:
- [Identify any repetitive content that could be consolidated]

**Standalone Content**:
- [Identify content that could stand alone in separate files]

#### Content Organization

- Current organization: [Description]
- Logical sections: [List sections]
- Content flow: [Describe how content flows]
- Dependencies: [Note any dependencies between sections]

#### Refactoring Opportunities

##### Opportunity 1: [Brief Description]

**Content to Remain in Original**:
- Key ideas: [List]
- Checklists: [List]
- Summaries: [List]
- Essential information: [List]

**Content to Move**:
- Background information: [Description and approximate lines]
- Extra details: [Description and approximate lines]
- Deep dives: [Description and approximate lines]

**Proposed New File(s)**:
- **New file**: `path/to/new-filename.md`
  - Content to include: [Description]
  - Approximate line count: ~XXX lines
  - Location rationale: [Why this location?]
  - Naming rationale: [Why this name?]

**How Files Should Reference Each Other**:
- Original file should: [How to reference new file]
- New file should: [How to reference original if needed]

**Migration Strategy**:
1. Create new file with extracted content
2. Update original file to remove extracted content
3. Add references in original file to new file where appropriate
4. Ensure new file is self-contained and well-documented
5. Verify all links and references still work
6. Test navigation and readability

**Benefits**:
- Reduces original file by ~XXX lines (to ~YYY lines)
- Improves focus and readability of original
- Makes background information reusable from multiple documents
- Improves maintainability
- Better organization of information

**Evaluation**:
- **Ease of Implementation**: X/5 - [Justification]
- **Safety**: X/5 - [Justification]
- **Practicality**: X/5 - [Justification]
- **Recommendation**: X/5 - [Justification]
- **Overall Score**: X.XX/5

**Priority**: High/Medium/Low

##### Opportunity 2: Split Plan File Checklist

**For Plan Files with Very Long Checklists**:

**Current Checklist Structure**:
- Total checklist items: XXX
- Approximate lines: ~YYY
- Logical groupings: [Identify natural groupings]

**Proposed Split**:
- **Original file**: `plan-30.md` (keep overview, context, and summary)
- **New file 1**: `plan-30a.md` (checklist items 1-N, focus area A)
- **New file 2**: `plan-30b.md` (checklist items N+1-M, focus area B)
- [Add more if needed]

**Content Distribution**:
- Overview and context: [Which file?]
- Checklist group A: [Which file?]
- Checklist group B: [Which file?]
- Summary and next steps: [Which file?]

**How Files Should Reference Each Other**:
- [Describe how split files should reference each other]

**Migration Strategy**:
1. Create new plan files (30a, 30b, etc.)
2. Distribute checklist items across files based on logical groupings
3. Keep overview/context in original or create a master plan file
4. Add cross-references between files
5. Ensure each file is self-contained but references others where needed
6. Verify all links and references still work

**Benefits**:
- Reduces each file to manageable size
- Improves focus on specific areas
- Makes it easier to work on specific parts
- Better organization

**Evaluation**:
- **Ease of Implementation**: X/5 - [Justification]
- **Safety**: X/5 - [Justification]
- **Practicality**: X/5 - [Justification]
- **Recommendation**: X/5 - [Justification]
- **Overall Score**: X.XX/5

**Priority**: High/Medium/Low

##### Opportunity 3: [Brief Description]
[Repeat structure for each opportunity]

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.md
   - Justification: [Why this is high priority]
   - Proposed new file(s): [List]

### Medium Priority (Overall Score 3.0-3.9)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.md
   - Justification: [Why this is medium priority]
   - Proposed new file(s): [List]

### Low Priority (Overall Score < 3.0)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.md
   - Justification: [Why this is low priority or not recommended]
   - Proposed new file(s): [List]

## Files Appropriately Large

The following files exceed 750 lines but are appropriately large with justification:

- **filename.md** (XXX lines): [Justification for why refactoring is not recommended]

## Observations and Patterns

- [Any patterns observed across multiple files]
- [Common refactoring opportunities across the documentation]
- [Structural observations about the documentation]
- [File naming patterns observed]
- [Content organization patterns observed]

## File Naming and Location Guidelines

### Naming Conventions
- New files should be descriptively named
- New files should relate to the original file name (unless information is more general)
- Use clear, descriptive names that indicate content
- For split plan files, use numbered suffixes (e.g., `plan-30a.md`, `plan-30b.md`)

### Location Guidelines
- **[DEV_DOCS]/info/**: For developer background information, extra details, or generally applicable information
- **Same directory as original**: For content specific to a particular document or feature
- **Appropriate subdirectory**: For content that fits into existing organizational structure

## Next Steps

- [ ] Review prioritized recommendations with team/user
- [ ] Create implementation plans for high-priority refactorings
- [ ] Schedule refactoring work
- [ ] Update this assessment after refactorings are completed
```

---

## Notes

- **Assessment-Only Phase**: This assessment is for analysis and documentation only. Do not modify any documentation files during the assessment. Only the timestamped assessment markdown file should be edited. Documentation refactorings should be made in a separate phase after reviewing assessment results.

- **Plan Files Are Analysis-Only**: Plan MD files should be analyzed for refactoring opportunities, but should NOT be edited during this assessment phase. Only the analysis results should be documented in the timestamped assessment file.

- **Completed Plans Directory**: The `[DEV_DOCS]/completed-plans/` directory should be ignored during this analysis.

- **Key Ideas vs. Background Information**: 
  - **Key ideas and checklists** should remain in the original file to maintain focus and usability
  - **Background information and extra details** should be moved to separate files that can be referenced when needed
  - This improves readability while preserving all information

- **File Naming and Relationships**: 
  - New files should be descriptively named
  - New files should relate to the original file name (unless information is more general)
  - This helps maintain context and discoverability

- **Location Strategy**: 
  - Developer background information or generally applicable information should go in `[DEV_DOCS]/info/`
  - Content specific to a document or feature should be placed near the original file
  - This maintains logical organization

- **Plan File Splitting**: 
  - For plan files with very long checklists, consider splitting into multiple files (e.g., "plan-30a.md" and "plan-30b.md")
  - Split based on logical groupings of checklist items
  - Maintain overview and context appropriately

- **References and Links**: 
  - When extracting content, ensure proper references are maintained
  - Original files should reference new files where appropriate
  - New files should be self-contained but may reference originals if needed
  - Verify all links and references work after refactoring

- **Incremental Approach**: Large refactorings should be done incrementally, one file at a time, with verification between steps.

---

## Template Version

- **Version**: 1.0
- **Created**: 2026-01-21
- **Last Updated**: 2026-01-21
