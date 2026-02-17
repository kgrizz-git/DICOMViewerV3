# Refactor Assessment Template - [PROJECT_NAME]

## Purpose

This document provides a systematic approach to analyze shell scripts and helper files in the codebase for refactoring opportunities. The assessment identifies files exceeding 750 lines and provides structured recommendations for breaking them into smaller, more maintainable modules.

## How to Use This Document

### Important: Creating Assessment Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each refactor assessment:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/refactor-assessments/refactor-assessment-YYYY-MM-DD-HHMMSS.md`
   - Use format: `refactor-assessment-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp [DEV_DOCS]/templates/refactor-assessment-template.md "[DEV_DOCS]/refactor-assessments/refactor-assessment-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Add specific recommendations and evaluations for each file
   - Document any refactoring suggestions discovered during the assessment

3. **After completing the assessment**:
   - Review all findings in the timestamped file
   - If new assessment patterns or criteria are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific assessment

### Critical: No Code Changes During Assessment

**DO NOT edit any code files during the refactor assessment.** The assessment is for **analysis and documentation only**.

- **Document opportunities, don't implement them**: When you identify a refactoring opportunity, document it thoroughly in the timestamped assessment file with:
  - Exact location (file and line numbers)
  - Description of the refactoring opportunity
  - Proposed structure and migration strategy
  - Evaluation scores and justifications
  - Benefits and risks

- **Only edit the timestamped assessment file**: The only file that should be modified during the assessment is the new timestamped markdown file created for this specific assessment.

- **Separate phases**: 
  - **Phase 1 (Assessment)**: Identify and document all refactoring opportunities
  - **Phase 2 (Implementation)**: After assessment completion, review findings with team/user and implement refactorings separately

This approach ensures:
- The assessment remains focused on discovery and analysis, not implementation
- All opportunities are documented before any code changes
- The user/team can prioritize which refactorings to address first
- The assessment results provide a complete picture of all refactoring opportunities
- Assessment results are not mixed with actual code changes

### Assessment Process

1. **After significant code changes or periodically**, create a new timestamped copy and run through the entire assessment
2. **Identify all shell scripts** in the codebase (`.sh` files in root and `[LIB_DIR]/` directories)
3. **Count lines** for each file and identify those exceeding 750 lines
4. **Analyze each large file** for refactoring opportunities:
   - Identify logical groupings of functions
   - Identify reusable code patterns
   - Identify dependencies and coupling
   - Identify potential new module boundaries
5. **Evaluate each refactoring suggestion** using the criteria below
6. **Prioritize recommendations** based on evaluation scores

## Line Count Threshold

- **Threshold**: 750 lines per file
- **Rationale**: Files exceeding this threshold may become difficult to maintain, test, and understand. Breaking them into smaller modules improves:
  - Code organization and readability
  - Testability (smaller units are easier to test)
  - Maintainability (easier to locate and fix issues)
  - Reusability (smaller modules can be reused more easily)
  - Collaboration (smaller files reduce merge conflicts)

**Note**: This threshold is a guideline, not a hard rule. Some files may be appropriately large due to their nature, but should still be evaluated for refactoring opportunities.

---

## Assessment Methodology

### Step 1: Identify Files to Analyze

1. **Find all shell scripts**:
   - Root directory: `*.sh` files
   - Library directory: `[LIB_DIR]/*.sh` files
   - Test directory: `tests/*.sh` files (optional, for reference)

2. **Count lines** for each file:
   - Use `wc -l` or similar tool
   - Include comments and blank lines in count
   - Document the exact line count

3. **List files exceeding threshold**:
   - Create a table with filename, line count, and location

### Step 2: Analyze Each Large File

For each file exceeding 750 lines, perform the following analysis:

1. **Function Inventory**:
   - List all functions in the file
   - Note function line counts
   - Identify function groupings (related functionality)

2. **Dependency Analysis**:
   - What other files/modules does this file depend on?
   - What files/modules depend on this file?
   - Identify tight coupling vs. loose coupling

3. **Code Organization**:
   - How is the code currently organized?
   - Are there clear sections or logical groupings?
   - Are there repeated patterns that could be extracted?

4. **Refactoring Opportunities**:
   - Identify functions that could be moved to separate modules
   - Identify code patterns that could be extracted into helper functions
   - Identify configuration or data that could be separated
   - Identify UI/logic separation opportunities

### Step 3: Propose Refactoring Plan

For each refactoring opportunity, create a detailed plan:

1. **Proposed Structure**:
   - What new files/modules would be created?
   - What functions would move to each new module?
   - What would remain in the original file?

2. **Migration Strategy**:
   - How would existing code be migrated?
   - What would be the impact on other files?
   - What testing would be needed?

3. **Benefits**:
   - What improvements would this refactoring provide?
   - How would it improve maintainability?
   - How would it improve testability?

### Step 4: Evaluate Each Refactoring Suggestion

For each refactoring suggestion, evaluate using the following criteria:

#### Evaluation Criteria

1. **Ease of Implementation** (1-5 scale):
   - **1 (Very Difficult)**: Requires extensive changes, high risk of breaking existing functionality, complex dependencies
   - **2 (Difficult)**: Significant changes required, some risk, moderate complexity
   - **3 (Moderate)**: Moderate changes, manageable risk, straightforward implementation
   - **4 (Easy)**: Simple changes, low risk, clear implementation path
   - **5 (Very Easy)**: Minimal changes, very low risk, obvious implementation

2. **Safety** (1-5 scale):
   - **1 (High Risk)**: High probability of introducing bugs, affects critical functionality, difficult to test
   - **2 (Moderate-High Risk)**: Some risk of bugs, affects important functionality, requires careful testing
   - **3 (Moderate Risk)**: Moderate risk, manageable with testing, affects non-critical areas
   - **4 (Low Risk)**: Low risk, easy to test, affects isolated functionality
   - **5 (Very Low Risk)**: Very low risk, straightforward testing, minimal impact

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
- [ ] **Remember: Only edit the timestamped assessment file - do not modify any code files**
- [ ] Identify all `.sh` files in codebase
- [ ] Count lines for each file
- [ ] Create list of files exceeding 750 lines

### Analysis

For each file exceeding 750 lines:

- [ ] Document file path and line count
- [ ] List all functions in the file
- [ ] Identify function groupings
- [ ] Analyze dependencies (what it uses, what uses it)
- [ ] Identify code organization patterns
- [ ] Identify refactoring opportunities
- [ ] Document proposed refactoring plan
- [ ] Evaluate each refactoring suggestion (Ease, Safety, Practicality, Recommendation)
- [ ] Calculate overall score for each suggestion
- [ ] Prioritize recommendations

### Documentation

- [ ] Create summary table of all files analyzed
- [ ] Create prioritized list of refactoring recommendations
- [ ] Document any files that are appropriately large (with justification)
- [ ] Note any patterns or observations about the codebase structure

---

## Assessment Results Template

Use this structure in your timestamped assessment file:

```markdown
# Refactor Assessment - YYYY-MM-DD HH:MM:SS

## Assessment Date
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Assessor**: [Name/AI Agent]

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds Threshold | Status |
|------|----------|------------|-------------------|--------|
| filename.sh | path/to/file | XXX | Yes/No | Analyzed |

## Detailed Analysis

### File: [filename.sh]

**Location**: `path/to/filename.sh`  
**Line Count**: XXX  
**Exceeds Threshold**: Yes/No

#### Function Inventory
- Function 1 (lines X-Y): Description
- Function 2 (lines X-Y): Description
- ...

#### Function Groupings
- **Group 1**: Functions A, B, C (related to X functionality)
- **Group 2**: Functions D, E, F (related to Y functionality)
- ...

#### Dependencies
- **Depends on**: 
  - `[LIB_DIR]/[MODULE_NAME].sh` (functions: func1, func2)
  - `[LIB_DIR]/[OTHER_MODULE].sh` (functions: func3)
- **Depended upon by**:
  - `other-script.sh` (uses functions: funcA, funcB)
  - `[LIB_DIR]/other-module.sh` (uses functions: funcC)

#### Code Organization
- Current organization: [Description]
- Logical sections: [List sections]
- Repeated patterns: [Identify patterns]

#### Refactoring Opportunities

##### Opportunity 1: [Brief Description]

**Proposed Structure**:
- New module: `[LIB_DIR]/[NEW_MODULE].sh`
  - Functions to move: func1, func2, func3
- Remaining in original: func4, func5, main logic

**Migration Strategy**:
1. Create new module file
2. Move functions to new module
3. Update source statements in original file
4. Update any files that depend on moved functions
5. Test thoroughly

**Benefits**:
- Reduces original file by ~XXX lines
- Improves separation of concerns
- Makes func1, func2, func3 reusable
- Improves testability

**Evaluation**:
- **Ease of Implementation**: X/5 - [Justification]
- **Safety**: X/5 - [Justification]
- **Practicality**: X/5 - [Justification]
- **Recommendation**: X/5 - [Justification]
- **Overall Score**: X.XX/5

**Priority**: High/Medium/Low

##### Opportunity 2: [Brief Description]
[Repeat structure for each opportunity]

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.sh
   - Justification: [Why this is high priority]

### Medium Priority (Overall Score 3.0-3.9)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.sh
   - Justification: [Why this is medium priority]

### Low Priority (Overall Score < 3.0)
1. [Refactoring opportunity] - Score: X.XX/5
   - File: filename.sh
   - Justification: [Why this is low priority or not recommended]

## Files Appropriately Large

The following files exceed 750 lines but are appropriately large with justification:

- **filename.sh** (XXX lines): [Justification for why refactoring is not recommended]

## Observations and Patterns

- [Any patterns observed across multiple files]
- [Common refactoring opportunities across the codebase]
- [Structural observations about the codebase]

## Next Steps

- [ ] Review prioritized recommendations with team/user
- [ ] Create implementation plans for high-priority refactorings
- [ ] Schedule refactoring work
- [ ] Update this assessment after refactorings are completed
```

---

## Notes

- **Assessment-Only Phase**: This assessment is for analysis and documentation only. Do not modify any code files during the assessment. Only the timestamped assessment markdown file should be edited. Code changes should be made in a separate implementation phase after reviewing assessment results.

- **Modular Architecture**: This codebase follows a modular architecture pattern. When refactoring, maintain consistency with existing module structure in `[LIB_DIR]/` directory.

- **Backward Compatibility**: Consider impact on existing scripts and [INIT_SYSTEM] services that may depend on current file structure.

- **Testing**: All refactoring should be accompanied by appropriate testing to ensure functionality is preserved.

- **Documentation**: Update relevant documentation when files are refactored (README, user guides, technical docs).

- **Incremental Approach**: Large refactorings should be done incrementally, one module at a time, with testing between steps.

---

## Template Version

- **Version**: 1.0
- **Created**: 2026-01-20
- **Last Updated**: 2026-01-20
