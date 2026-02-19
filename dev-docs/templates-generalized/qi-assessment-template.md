# Quality Improvement Assessment Template - [PROJECT_NAME]

**Template Version**: 2.0  
**Last Updated**: 2026-02-18

## Purpose

This document provides a systematic approach to analyze code files in the codebase for quality issues, errors, and improvement opportunities. The assessment:

- Identifies code errors such as repeated lines or sections, garbled code, undefined variables or functions
- Detects potential bugs and problematic code patterns
- Suggests significant quality improvements
- Proposes new features or approaches to enhance the codebase
- Evaluates recommendations by priority and implementation difficulty
- Documents findings without modifying any code files

## How to Use This Document

### Important: Creating Assessment Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each quality improvement assessment:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/code-assessments/qi-assessment-YYYY-MM-DD-HHMMSS.md`
   - Use format: `qi-assessment-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp [DEV_DOCS]/templates/qi-assessment-template.md "[DEV_DOCS]/code-assessments/qi-assessment-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Document all identified issues and improvement opportunities
   - Provide specific recommendations with priority and difficulty ratings

3. **After completing the assessment**:
   - Review all findings in the timestamped file
   - If new assessment patterns or criteria are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific assessment

### Critical: No Code Changes During Assessment

**DO NOT edit any code files during the quality improvement assessment.** The assessment is for **analysis and documentation only**.

- **Document issues and opportunities, don't implement them**: When you identify a problem or improvement opportunity, document it thoroughly in the timestamped assessment file with:
  - Exact location (file and line numbers)
  - Description of the issue or opportunity
  - Potential impact/severity
  - Suggested fix or improvement approach (but don't implement it yet)
  - Priority level (CRITICAL, HIGH, MEDIUM, LOW)
  - Implementation difficulty (EASY, MODERATE, DIFFICULT, VERY DIFFICULT)

- **Only edit the timestamped assessment file**: The only file that should be modified during the assessment is the new timestamped markdown file created for this specific assessment.

- **Separate phases**: 
  - **Phase 1 (Assessment)**: Identify and document all quality issues and improvement opportunities
  - **Phase 2 (Implementation)**: After assessment completion, review findings with team/user and implement improvements separately

This approach ensures:
- The assessment remains focused on discovery and analysis, not implementation
- All issues and opportunities are documented before any code changes
- The user/team can prioritize which improvements to address first
- The assessment results provide a complete picture of all quality concerns
- Assessment results are not mixed with actual code changes

### Assessment Process

1. **Identify all code files** in the codebase:
   - Root directory: source files (e.g., `*.py`, `*.js`, `*.sh`, `*.java`, `*.cpp`, etc.)
   - Source directories: `src/`, `lib/`, `utils/`, `scripts/`, and other relevant directories
   - Test directory: `tests/`, `test/`, `__tests__/` (for reference)
   - **Exclude backup files**: Files with "backup", "_BAK", ".bak" in name or in backup folders
   - Main application files, configuration files, utility modules

2. **Check each file for errors**:
   - Repeated lines or sections
   - Garbled or corrupted code
   - Undefined variables or functions
   - Syntax errors
   - Logic errors
   - Missing error handling
   - Inconsistent code style

3. **Identify quality improvement opportunities**:
   - Code organization improvements
   - Performance optimizations
   - Maintainability enhancements
   - Documentation improvements
   - Error handling improvements
   - Code reuse opportunities

4. **Suggest new features or approaches**:
   - New functionality that could enhance the system
   - Alternative implementation approaches
   - Better design patterns
   - Integration opportunities

5. **Evaluate and prioritize recommendations**:
   - Assign priority levels (CRITICAL, HIGH, MEDIUM, LOW)
   - Assess implementation difficulty (EASY, MODERATE, DIFFICULT, VERY DIFFICULT)
   - Consider impact vs. effort

---

## Assessment Methodology

### Step 1: Identify Files to Analyze

1. **Find all code files**:
   - Root directory: source files (e.g., `*.py`, `*.js`, `*.sh`, `*.java`, `*.cpp`, etc.)
   - Source directories: `src/`, `lib/`, `utils/`, `scripts/`, and other relevant directories
   - Test directory: `tests/`, `test/`, `__tests__/` (for reference)
   - **Exclude backup files**: Files with "backup", "_BAK", ".bak" in name or in backup folders

2. **Create file inventory**:
   - List all code files with their locations
   - Note file sizes and purposes
   - Identify main application files vs. library modules vs. utilities

### Step 2: Error Detection

For each code file, check for:

#### 2.1: Repeated Lines or Sections

- [ ] Scan for duplicate code blocks
- [ ] Check for copy-paste errors
- [ ] Identify repeated function/method/class definitions
- [ ] Look for duplicate variable/constant assignments
- [ ] Check for repeated conditional blocks or logic

**Tools/Methods**:
- Visual inspection
- Use diff tools to compare sections
- Look for identical or near-identical code blocks
- Check for functions/methods/classes defined multiple times

#### 2.2: Garbled Code

- [ ] Check for corrupted or malformed code
- [ ] Look for incomplete statements
- [ ] Identify broken function/method/class definitions
- [ ] Check for malformed conditionals or loops
- [ ] Verify proper file structure (imports, proper syntax)

**Indicators**:
- Incomplete function/method/class definitions
- Missing closing brackets, braces, or quotes
- Syntax errors that prevent compilation/execution
- Malformed expressions or statements
- Broken multi-line constructs

#### 2.3: Undefined Variables or Functions

- [ ] Check for variables used before assignment
- [ ] Verify all function/method calls have corresponding definitions
- [ ] Check for typos in variable, function, or class names
- [ ] Verify all imported/required modules exist
- [ ] Check for missing import/include/require statements

**Methods**:
- Trace variable usage through the code
- Verify all import/include/require statements point to existing files
- Check function/method definitions match calls
- Use language-specific syntax checkers (linters, compilers)
- Look for variables that may not be initialized before use

#### 2.4: Syntax Errors

- [ ] Run language-specific syntax checkers (linters, compilers) on each file
- [ ] Check for unclosed quotes, brackets, braces, or parentheses
- [ ] Verify proper use of language-specific syntax
- [ ] Check for proper data structure syntax (arrays, objects, dictionaries)
- [ ] Verify proper use of operators and expressions

#### 2.5: Logic Errors

- [ ] Check for incorrect conditional logic
- [ ] Verify loop termination conditions
- [ ] Check for off-by-one errors
- [ ] Verify proper error handling paths
- [ ] Check for race conditions or timing issues

#### 2.6: Missing Error Handling

- [ ] Check if code handles errors gracefully
- [ ] Verify proper use of try-catch/exception handling where appropriate
- [ ] Check for proper error messages
- [ ] Verify cleanup on errors (finally blocks, defer, destructors)
- [ ] Check for validation of inputs and dependencies

### Step 3: Quality Improvement Opportunities

For each file, identify opportunities for:

#### 3.1: Code Organization

- [ ] Functions/methods/classes that could be better organized
- [ ] Code that could be modularized
- [ ] Better separation of concerns
- [ ] Improved file/package structure
- [ ] Better naming conventions

#### 3.2: Performance Optimizations

- [ ] Unnecessary operations or computations
- [ ] Inefficient loops or iterations
- [ ] Redundant I/O operations (file, network, database)
- [ ] Opportunities for caching or memoization
- [ ] Better algorithm or data structure choices

#### 3.3: Maintainability Enhancements

- [ ] Code that is difficult to understand
- [ ] Missing or inadequate comments
- [ ] Magic numbers that should be constants
- [ ] Complex logic that could be simplified
- [ ] Better variable naming

#### 3.4: Documentation Improvements

- [ ] Missing function/method/class documentation
- [ ] Unclear code comments
- [ ] Missing usage examples
- [ ] Incomplete error messages
- [ ] Missing inline documentation (docstrings, JSDoc, etc.)

#### 3.5: Error Handling Improvements

- [ ] Better error messages
- [ ] More comprehensive error handling
- [ ] Better validation of inputs
- [ ] Improved error recovery
- [ ] Better logging

#### 3.6: Code Reuse Opportunities

- [ ] Duplicate code that could be extracted to functions/methods
- [ ] Common patterns that could be library functions/utilities
- [ ] Repeated logic that could be consolidated
- [ ] Opportunities to use existing library functions/modules

### Step 4: New Features or Approaches

Consider:

- [ ] New functionality that would enhance the system
- [ ] Alternative implementation approaches
- [ ] Better design patterns
- [ ] Integration with other tools or systems
- [ ] User experience improvements
- [ ] Performance enhancements
- [ ] Security improvements
- [ ] Compatibility improvements

### Step 5: Evaluation and Prioritization

For each finding, evaluate:

#### Priority Levels

- **CRITICAL**: Issues that cause bugs, security vulnerabilities, or system failures. Must be addressed immediately.
- **HIGH**: Significant quality issues or improvements that affect functionality, maintainability, or user experience. Should be addressed soon.
- **MEDIUM**: Moderate quality improvements that would benefit the codebase but don't cause immediate problems. Can be addressed when time permits.
- **LOW**: Minor improvements or nice-to-have enhancements. Can be addressed as part of other work or during refactoring.

#### Implementation Difficulty

- **EASY**: Simple changes requiring minimal effort (1-2 hours). Examples: fixing typos, adding comments, simple refactoring.
- **MODERATE**: Changes requiring moderate effort (half day to 1 day). Examples: extracting functions, improving error handling, moderate refactoring.
- **DIFFICULT**: Changes requiring significant effort (2-5 days). Examples: major refactoring, implementing new features, architectural changes.
- **VERY DIFFICULT**: Changes requiring extensive effort (1+ weeks). Examples: major architectural overhauls, complex new features, significant system redesigns.

#### Evaluation Criteria

When evaluating each finding, consider:

1. **Impact**: How much does this issue affect functionality, maintainability, or user experience?
2. **Risk**: What is the risk if this issue is not addressed?
3. **Effort**: How much work is required to fix or implement?
4. **Dependencies**: Are there dependencies or prerequisites?
5. **Testing**: How much testing will be required?
6. **Breaking Changes**: Will this require changes to other parts of the system?

---

## Assessment Checklist

### Preparation

- [ ] Create timestamped assessment file
- [ ] List all code files to analyze (root, `src/`, `lib/`, `utils/`, `scripts/`, etc.)
- [ ] **Exclude backup files** (files with "backup", "_BAK", ".bak" in name or in backup folders)
- [ ] Set up analysis environment

### Error Detection

- [ ] Check all files for repeated lines/sections
- [ ] Check all files for garbled code
- [ ] Check all files for undefined variables
- [ ] Check all files for undefined functions/methods/classes
- [ ] Check all files for syntax errors
- [ ] Check all files for logic errors
- [ ] Check all files for missing error handling

### Quality Improvements

- [ ] Identify code organization improvements
- [ ] Identify performance optimizations
- [ ] Identify maintainability enhancements
- [ ] Identify documentation improvements
- [ ] Identify error handling improvements
- [ ] Identify code reuse opportunities

### New Features/Approaches

- [ ] Suggest new features
- [ ] Suggest alternative approaches
- [ ] Suggest design pattern improvements
- [ ] Suggest integration opportunities

### Evaluation

- [ ] Assign priority to each finding
- [ ] Assess implementation difficulty for each finding
- [ ] Create prioritized recommendations list
- [ ] Document impact vs. effort analysis

### Documentation

- [ ] Create summary of all findings
- [ ] Create prioritized recommendations table
- [ ] Document any patterns or observations
- [ ] Note any files that are in good shape

---

## Assessment Results Template

Use this structure in your timestamped assessment file:

```markdown
# Quality Improvement Assessment - YYYY-MM-DD HH:MM:SS

## Assessment Date
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Assessor**: [Name/AI Agent]

## Files Analyzed

### Summary Table

| File | Location | Lines | Language | Status | Issues Found | Improvements Suggested |
|------|----------|-------|----------|--------|--------------|------------------------|
| filename.ext | path/to/file | XXX | [Language] | Analyzed | X | Y |

## Error Detection Results

### Critical Errors

#### Error 1: [Brief Description]

**File**: `path/to/filename.sh`  
**Location**: Lines X-Y  
**Type**: [Repeated Code/Garbled Code/Undefined Variable/Undefined Function/Syntax Error/Logic Error/Missing Error Handling]

**Description**:
[Detailed description of the error]

**Impact**:
[What happens because of this error? What functionality is affected?]

**Example**:
```[language]
# Problematic code snippet
```

**Suggested Fix**:
[How to fix this issue]

**Priority**: CRITICAL  
**Implementation Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]  
**Estimated Effort**: [Time estimate]

---

#### Error 2: [Brief Description]
[Repeat structure for each critical error]

### High Priority Errors

#### Error 1: [Brief Description]
[Same structure as Critical Errors]

### Medium Priority Errors

#### Error 1: [Brief Description]
[Same structure as Critical Errors]

### Low Priority Errors

#### Error 1: [Brief Description]
[Same structure as Critical Errors]

## Quality Improvement Opportunities

### Code Organization Improvements

#### Improvement 1: [Brief Description]

**File**: `path/to/filename.sh`  
**Location**: Lines X-Y  
**Type**: Code Organization

**Current State**:
[Description of current code organization]

**Proposed Improvement**:
[Description of proposed improvement]

**Benefits**:
- Benefit 1
- Benefit 2
- Benefit 3

**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Implementation Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]  
**Estimated Effort**: [Time estimate]

---

### Performance Optimizations

#### Optimization 1: [Brief Description]
[Same structure as Code Organization Improvements]

### Maintainability Enhancements

#### Enhancement 1: [Brief Description]
[Same structure as Code Organization Improvements]

### Documentation Improvements

#### Improvement 1: [Brief Description]
[Same structure as Code Organization Improvements]

### Error Handling Improvements

#### Improvement 1: [Brief Description]
[Same structure as Code Organization Improvements]

### Code Reuse Opportunities

#### Opportunity 1: [Brief Description]
[Same structure as Code Organization Improvements]

## New Features and Approaches

### New Features

#### Feature 1: [Brief Description]

**Description**:
[Detailed description of the proposed feature]

**Rationale**:
[Why this feature would be valuable]

**Implementation Approach**:
[How this feature could be implemented]

**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Implementation Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]  
**Estimated Effort**: [Time estimate]

**Dependencies**:
[List any dependencies or prerequisites]

---

### Alternative Approaches

#### Approach 1: [Brief Description]
[Same structure as New Features]

### Design Pattern Improvements

#### Improvement 1: [Brief Description]
[Same structure as New Features]

### Integration Opportunities

#### Opportunity 1: [Brief Description]
[Same structure as New Features]

## Prioritized Recommendations

### Critical Priority (Must Address Immediately)

1. **[Error/Improvement Name]** - Priority: CRITICAL, Difficulty: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]
   - File: `filename.sh`
   - Location: Lines X-Y
   - Impact: [Description of impact]
   - Effort: [Time estimate]
   - Justification: [Why this is critical]

### High Priority (Should Address Soon)

1. **[Error/Improvement Name]** - Priority: HIGH, Difficulty: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]
   - File: `filename.sh`
   - Location: Lines X-Y
   - Impact: [Description of impact]
   - Effort: [Time estimate]
   - Justification: [Why this is high priority]

### Medium Priority (Address When Time Permits)

1. **[Error/Improvement Name]** - Priority: MEDIUM, Difficulty: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]
   - File: `filename.sh`
   - Location: Lines X-Y
   - Impact: [Description of impact]
   - Effort: [Time estimate]
   - Justification: [Why this is medium priority]

### Low Priority (Nice to Have)

1. **[Error/Improvement Name]** - Priority: LOW, Difficulty: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]
   - File: `filename.sh`
   - Location: Lines X-Y
   - Impact: [Description of impact]
   - Effort: [Time estimate]
   - Justification: [Why this is low priority]

## Impact vs. Effort Matrix

### Quick Wins (High Impact, Low Effort)
- [List items with HIGH/CRITICAL priority and EASY difficulty]

### Major Projects (High Impact, High Effort)
- [List items with HIGH/CRITICAL priority and DIFFICULT/VERY DIFFICULT difficulty]

### Fill-ins (Low Impact, Low Effort)
- [List items with LOW/MEDIUM priority and EASY difficulty]

### Thankless Tasks (Low Impact, High Effort)
- [List items with LOW/MEDIUM priority and DIFFICULT/VERY DIFFICULT difficulty]

## Files in Good Shape

The following files were analyzed and found to be in good condition with minimal issues:

- **filename.sh**: [Brief note on why it's in good shape]

## Patterns and Observations

### Common Issues Across Multiple Files

- [Pattern 1]: [Description and affected files]
- [Pattern 2]: [Description and affected files]

### Code Quality Trends

- [Observation 1]
- [Observation 2]

### Recommendations for Future Development

- [Recommendation 1]
- [Recommendation 2]

## Next Steps

- [ ] Review prioritized recommendations with team/user
- [ ] Create implementation plans for critical and high-priority items
- [ ] Schedule improvement work
- [ ] Update this assessment after improvements are completed
```

---

## Notes

- **Assessment-Only Phase**: This assessment is for analysis and documentation only. Do not modify any code files during the assessment. Only the timestamped assessment markdown file should be edited. Code changes should be made in a separate implementation phase after reviewing assessment results.

- **Comprehensive Analysis**: Be thorough in checking for errors. Use multiple methods (visual inspection, syntax checking, code analysis) to ensure nothing is missed.

- **Prioritization**: Focus on critical errors first, but also document all findings so they can be addressed systematically.

- **Implementation Difficulty**: Be realistic about effort estimates. Consider testing, documentation, and potential side effects when assessing difficulty.

- **Modular Architecture**: When suggesting improvements, maintain consistency with existing module structure (e.g., `src/`, `lib/`, `utils/` directories).

- **Backward Compatibility**: Consider impact on existing code, APIs, and dependencies when suggesting changes.

- **Testing**: All improvements should be accompanied by appropriate testing to ensure functionality is preserved or enhanced.

- **Documentation**: Update relevant documentation when code is improved (README, user guides, technical docs).

---

## Template Version

- **Version**: 1.0
- **Created**: 2026-01-22
- **Last Updated**: 2026-01-22
