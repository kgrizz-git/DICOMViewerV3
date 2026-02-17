# Functionality Integrity Assessment Template - [PROJECT_NAME]

## Purpose

This document provides a systematic approach to analyze shell scripts in the codebase for functionality integrity, code flow consistency, and system-wide compatibility. The assessment:

- Traces code execution paths from entry points through all execution branches
- Examines interactions between scripts, functions, and files
- Verifies consistency of variable names and arguments across the codebase
- Checks compatibility between different parts of the system
- Identifies conflicts, gaps, contradictions, and edge cases
- Evaluates overall functionality and integrity as a cohesive system
- Documents findings without modifying any code files

## How to Use This Document

### Important: Creating Assessment Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each functionality integrity assessment:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/code-assessments/functionality-integrity-assessment-YYYY-MM-DD-HHMMSS.md`
   - Use format: `functionality-integrity-assessment-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp [DEV_DOCS]/templates/functionality-integrity-assessment-template.md "[DEV_DOCS]/code-assessments/functionality-integrity-assessment-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Document all identified issues, inconsistencies, and integrity concerns
   - Provide specific recommendations with priority and difficulty ratings

3. **After completing the assessment**:
   - Review all findings in the timestamped file
   - If new assessment patterns or criteria are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific assessment

### Critical: No Code Changes During Assessment

**DO NOT edit any code files during the functionality integrity assessment.** The assessment is for **analysis and documentation only**.

- **Document issues and inconsistencies, don't fix them**: When you identify a problem or inconsistency, document it thoroughly in the timestamped assessment file with:
  - Exact location (file and line numbers)
  - Description of the issue or inconsistency
  - Potential impact/severity
  - Suggested fix or improvement approach (but don't implement it yet)
  - Priority level (CRITICAL, HIGH, MEDIUM, LOW)
  - Implementation difficulty (EASY, MODERATE, DIFFICULT, VERY DIFFICULT)

- **Only edit the timestamped assessment file**: The only file that should be modified during the assessment is the new timestamped markdown file created for this specific assessment.

- **Separate phases**: 
  - **Phase 1 (Assessment)**: Identify and document all functionality integrity issues, inconsistencies, and compatibility problems
  - **Phase 2 (Implementation)**: After assessment completion, review findings with team/user and implement improvements separately

### Assessment Process

1. **Identify entry point scripts** in the base directory: `[MAIN_SCRIPT].sh`, `[CONFIGURE_SCRIPT].sh`, `[INSTALL_SCRIPT].sh`, `[UNINSTALL_SCRIPT].sh`, and any other executable scripts
2. **Trace execution paths** for each entry point: Follow function calls, script sourcing, execution branches, and map dependencies
3. **Examine interactions**: How scripts call library functions, how modules interact, data flow, configuration file operations, state management
4. **Verify consistency**: Variable names, function arguments, return values, error handling patterns, configuration variable names
5. **Check compatibility**: Function calls, sourced files, dependencies, configuration formats, data structures
6. **Identify issues**: Conflicts (contradictory logic/behavior), gaps (missing functionality/error handling), contradictions (inconsistent assumptions), edge cases (unhandled boundary conditions)

### Scope

**Files to Analyze**:
- Shell scripts (`.sh` files) in the base directory
- All scripts and files in `[LIB_DIR]/` directory that are called by base directory scripts
- Configuration files (`.conf` files) that are read/written by scripts
- Service files that invoke scripts

**Files to Exclude**:
- Markdown documentation files (`.md` files)
- Files in the `tests/` directory
- Backup files and Git-related files

---

## Assessment Methodology

### Step 1: Identify Entry Points and Create Execution Map

- [ ] Identify all executable `.sh` files in base directory and document their purpose
- [ ] For each entry point, trace all `source` statements and map function call hierarchies
- [ ] Document conditional execution paths and identify all library modules used
- [ ] List all files in `[LIB_DIR]/` directory and map inter-library dependencies
- [ ] Create dependency graph showing relationships between scripts and modules

### Step 2: Code Flow Analysis

For each entry point script, trace execution through all paths:

- [ ] **Main Execution Path**: 
  - Identify flow from start to finish
  - Document all function calls in order with file locations
  - Note all conditional branches (`if/elif/else`, `case`)
  - Track all file I/O operations (reads/writes with locations)
  - Document all external command invocations

- [ ] **Error Handling Paths**: 
  - Trace error handling for each function call
  - Document error exit points
  - Check if errors are properly propagated
  - Verify cleanup operations on errors
  - Check for error handling gaps

- [ ] **Conditional Branches**: 
  - Map all `if/elif/else` branches
  - Document all `case` statement branches
  - Trace execution through each branch
  - Verify all branches have proper handling
  - Check for unreachable code

- [ ] **Loop Execution Paths**: 
  - Identify all loops (`for`, `while`, `until`)
  - Trace execution through loop iterations
  - Verify loop termination conditions
  - Check for infinite loop possibilities
  - Document loop variable usage

- [ ] **Function Call Chains**: 
  - For each function call, trace to its definition
  - Verify function exists (in same file or sourced library)
  - Check function argument count and types
  - Verify return value handling
  - Document nested function call chains

### Step 3: Variable and Argument Consistency

- [ ] **Variable Name Consistency**: 
  - Check if same variables use consistent names across scripts
  - Verify configuration variable names match between scripts that read config, scripts that write config, and config file format
  - Check for typos or variations in variable names (e.g., `${VAR}` vs `${VAR_NAME}`)
  - Verify environment variable names are consistent
  - Check for variable name conflicts (same name, different purpose)
  - **Methods**: Search for variable assignments/usages across scripts, compare config read vs. write code, verify exported variables match import expectations

- [ ] **Function Argument Consistency**: 
  - For each function, verify all call sites use correct argument count
  - Check argument order matches function definition
  - Verify argument types (strings, numbers, arrays) match expectations
  - Check for missing arguments in function calls
  - Verify optional arguments are handled consistently
  - **Methods**: For each function definition, find all call sites, compare signature with invocations, check for positional vs. named argument inconsistencies

- [ ] **Return Value Consistency**: 
  - Verify functions that return values are called correctly
  - Check return value handling is consistent (e.g., `$?` checks)
  - Verify exit codes are used consistently (0=success, non-zero=error)
  - Check for functions that should return values but don't
  - Verify error return values are handled appropriately

- [ ] **Configuration Variable Consistency**: 
  - Verify config file variable names match script expectations
  - Check that all config variables read are defined in config file format
  - Verify default values match between different scripts
  - Check for config variables that are written but never read
  - Verify config variable types are consistent (string, number, boolean)

### Step 4: Compatibility Analysis

- [ ] **Function Call Compatibility**: 
  - Verify all function calls have corresponding definitions
  - Check function signatures match between definition and calls
  - Verify functions are sourced before being called
  - Check for circular dependencies in sourcing
  - Verify function availability at call time

- [ ] **File Sourcing Compatibility**: 
  - Verify all `source` or `.` statements point to existing files
  - Check sourcing order is correct (dependencies loaded first)
  - Verify sourced files don't have conflicting function/variable names
  - Check for missing source statements
  - Verify paths in source statements are correct

- [ ] **Data Structure Compatibility**: 
  - Verify data formats match between reading and writing
  - Check array usage is consistent across scripts
  - Verify string formats are compatible
  - Check numeric formats are compatible
  - Verify boolean representation is consistent (0/1, true/false, yes/no)

- [ ] **Configuration File Compatibility**: 
  - Verify config file format matches parser expectations
  - Check config file reading and writing use same format
  - Verify default values are compatible
  - Check for version compatibility issues
  - Verify config file locking/unlocking is compatible (if applicable)

- [ ] **External Command Compatibility**: 
  - Verify external commands are used consistently
  - Check command-line argument formats are compatible
  - Verify fallback mechanisms work correctly
  - Check for command availability checks
  - Verify error handling for missing commands

### Step 5: Conflict Detection

- [ ] **Logic Conflicts**: 
  - Check for contradictory conditional logic
  - Verify no conflicting assumptions about system state
  - Check for race conditions in file operations
  - Verify no conflicting configuration settings
  - Check for contradictory error handling approaches

- [ ] **Behavior Conflicts**: 
  - Verify consistent behavior for same operations
  - Check for conflicting default values
  - Verify no contradictory function behaviors
  - Check for conflicting error messages
  - Verify consistent user experience

- [ ] **State Management Conflicts**: 
  - Check for conflicting state assumptions
  - Verify state is managed consistently
  - Check for state corruption possibilities
  - Verify cleanup operations don't conflict
  - Check for conflicting lock mechanisms

### Step 6: Gap Detection

- [ ] **Missing Functionality**: 
  - Identify functions that are called but not defined
  - Check for missing error handling
  - Verify all execution paths have proper handling
  - Check for missing validation
  - Verify all user inputs are validated

- [ ] **Missing Error Handling**: 
  - Check for unhandled error conditions
  - Verify all file operations have error handling
  - Check for missing cleanup on errors
  - Verify all external commands have error handling
  - Check for missing validation error handling

- [ ] **Missing Edge Case Handling**: 
  - Check for unhandled boundary conditions
  - Verify empty input handling
  - Check for missing null/empty checks
  - Verify extreme value handling
  - Check for missing timeout handling

### Step 7: Contradiction Detection

- [ ] **Documentation vs. Implementation**: Verify code matches comments/documentation, check for contradictory comments, verify function descriptions match implementation
- [ ] **Assumption Contradictions**: Check for contradictory assumptions about system state, file locations, user permissions, environment
- [ ] **Design Contradictions**: Check for contradictory design patterns, verify consistent architectural approaches, check for conflicting module responsibilities

### Step 8: Edge Case Analysis

- [ ] **Boundary Conditions**: 
  - Test minimum values (0, empty strings, null)
  - Test maximum values (large numbers, long strings)
  - Test boundary values (exactly at limits)
  - Verify off-by-one error possibilities
  - Check for integer overflow possibilities

- [ ] **Unusual Inputs**: 
  - Test with special characters in inputs
  - Test with whitespace-only inputs
  - Test with very long inputs
  - Test with malformed configuration files
  - Test with missing required files

- [ ] **System State Edge Cases**: 
  - Test with missing dependencies
  - Test with insufficient permissions
  - Test with full disk (write failures)
  - Test with locked files
  - Test with corrupted configuration files

- [ ] **Timing Edge Cases**: 
  - Test rapid successive calls
  - Test concurrent execution possibilities
  - Test timeout scenarios
  - Test with system clock changes
  - Test with very short or very long execution times

### Step 9: Overall Integrity Evaluation

- [ ] **System Cohesion**: 
  - Evaluate how well components work together
  - Check for cohesive module design
  - Verify clear separation of concerns
  - Check for proper abstraction levels
  - Verify consistent design patterns

- [ ] **Functional Completeness**: 
  - Verify all required functionality is present
  - Check for missing features
  - Verify all user requirements are met
  - Check for incomplete implementations
  - Verify all error cases are handled

- [ ] **Reliability**: 
  - Evaluate error recovery capabilities
  - Check for robustness in error conditions
  - Verify graceful degradation
  - Check for data integrity protection
  - Verify system stability

---

## Assessment Checklist

### Preparation
- [ ] Create timestamped assessment file
- [ ] List all entry point scripts and library files
- [ ] Create initial execution flow map

### Analysis
- [ ] Trace execution paths for each entry point (main, error, branches, loops, function chains)
- [ ] Check variable/argument/return value/configuration consistency
- [ ] Verify function call, file sourcing, data structure, config file, external command compatibility
- [ ] Identify logic/behavior/state management conflicts
- [ ] Identify missing functionality/error handling/edge case handling
- [ ] Identify documentation/assumption/design contradictions
- [ ] Analyze boundary conditions, unusual inputs, system state, timing edge cases
- [ ] Evaluate system cohesion, functional completeness, reliability

### Documentation
- [ ] Create summary of all findings
- [ ] Create prioritized recommendations table
- [ ] Document execution flow maps and all issues
- [ ] Note well-integrated components

---

## Assessment Results Template

Use this structure in your timestamped assessment file:

```markdown
# Functionality Integrity Assessment - YYYY-MM-DD HH:MM:SS

## Assessment Date
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Assessor**: [Name/AI Agent]

## Entry Points Analyzed

| Entry Point | Location | Library Dependencies | Execution Paths | Issues Found |
|-------------|----------|---------------------|-----------------|--------------|
| [MAIN_SCRIPT].sh | / | [LIB_DIR]/*.sh | X paths | Y issues |

## Execution Flow Analysis

### Entry Point: [script-name].sh

#### Main Execution Path
**Flow**: [Step-by-step flow from start to finish]
**Functions Called**: [List in order with file locations]
**Library Dependencies**: [List all dependencies]
**File I/O**: [Reads/Writes with locations]
**External Commands**: [List all external commands]

#### Error Handling Paths
**Error Path 1**: [Description]
- Trigger: [What causes this]
- Flow: [How handled]
- Issues: [Any problems]

#### Conditional Branches
**Branch 1**: [Description]
- Condition: [if/case condition]
- Flow: [What happens]
- Issues: [Any problems]

#### Function Call Chains
**Chain 1**: [Function name]
- Entry: [Called from location with arguments]
- Definition: [File and line]
- Arguments: [arg1, arg2, ...]
- Return: [How return value used]
- Issues: [Any problems]

## Variable and Argument Consistency

### Variable Name Inconsistencies

#### Inconsistency 1: [Variable Name]
**Location**: 
- Used as `${VAR_NAME}` in file1.sh line X
- Used as `${VARNAME}` in file2.sh line Y
- Defined as `VAR_NAME` in [LIB_DIR]/[MODULE_NAME].sh line Z
**Impact**: [What problems this causes]
**Suggested Fix**: [How to make consistent]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Function Argument Inconsistencies

#### Inconsistency 1: [Function Name]
**Function Definition**: [LIB_DIR]/example.sh line X - `function_name(arg1, arg2, arg3)`
**Call Sites**:
- file1.sh line Y: `function_name(arg1, arg2)` [MISSING arg3]
- file2.sh line Z: `function_name(arg1, arg2, arg3, arg4)` [EXTRA arg4]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to fix]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Configuration Variable Inconsistencies

#### Inconsistency 1: [Config Variable]
**Config File Format**: `CONFIG_VAR=value`
**Script Expectations**:
- [LIB_DIR]/[MODULE_NAME].sh reads `CONFIG_VAR` (line X)
- [CONFIGURE_SCRIPT].sh writes `CONFIG_VAR_NAME` (line Y) [DIFFERENT NAME]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to make consistent]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

## Compatibility Issues

### Function Call Compatibility

#### Issue 1: [Function Name]
**Problem**: [Description]
**Location**: Function defined in [LIB_DIR]/example.sh line X, called from file1.sh line Y
**Details**: [Specific compatibility problem]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to fix]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### File Sourcing Compatibility

#### Issue 1: [Source Statement]
**Problem**: [Description]
**Location**: file1.sh line X - `source "${LIB_DIR}/missing-file.sh"`
**Details**: [File doesn't exist or wrong path]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to fix]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Data Structure Compatibility

#### Issue 1: [Data Structure]
**Problem**: [Description]
**Location**: Written in file1.sh line X, read in file2.sh line Y
**Details**: [Format mismatch or incompatibility]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to fix]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

## Conflicts

### Logic Conflicts

#### Conflict 1: [Brief Description]
**Location**: file1.sh line X: [Logic A] vs file2.sh line Y: [Contradictory Logic B]
**Description**: [Detailed description]
**Impact**: [What problems this causes]
**Example**:
```bash
# file1.sh - assumes config exists
if [ -f "$CONFIG_FILE" ]; then load_config; fi
# file2.sh - assumes config may not exist
load_config  # No check, will fail if config missing
```
**Suggested Fix**: [How to resolve]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Behavior Conflicts

#### Conflict 1: [Brief Description]
**Location**: [Files and line numbers]
**Description**: [Detailed description of conflicting behavior]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to resolve]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

## Gaps

### Missing Functionality

#### Gap 1: [Brief Description]
**Location**: [Where functionality is expected but missing]
**Description**: [What functionality is missing]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to add missing functionality]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Missing Error Handling

#### Gap 1: [Brief Description]
**Location**: file1.sh line X
**Description**: [What error handling is missing]
**Impact**: [What problems this causes]
**Example**:
```bash
# Missing error handling
rm "$TEMP_FILE"  # No check if rm fails
```
**Suggested Fix**: [How to add error handling]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Missing Edge Case Handling

#### Gap 1: [Brief Description]
**Location**: file1.sh line X
**Description**: [What edge case is not handled]
**Impact**: [What problems this causes]
**Example**:
```bash
# No handling for empty input
TOTAL=$((VAR1 + VAR2))  # Fails if VAR1 or VAR2 is empty
```
**Suggested Fix**: [How to handle edge case]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

## Contradictions

### Documentation vs. Implementation

#### Contradiction 1: [Brief Description]
**Location**: file1.sh line X
**Description**: [What contradicts between docs and code]
**Documentation Says**: [What documentation claims]
**Code Does**: [What code actually does]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to resolve]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Assumption Contradictions

#### Contradiction 1: [Brief Description]
**Location**: [Files and line numbers]
**Description**: [What assumptions contradict]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to resolve]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

## Edge Cases

### Boundary Conditions

#### Edge Case 1: [Brief Description]
**Location**: file1.sh line X
**Description**: [What boundary condition is not handled]
**Scenario**: [Specific edge case scenario]
**Current Behavior**: [What happens currently]
**Expected Behavior**: [What should happen]
**Impact**: [What problems this causes]
**Suggested Fix**: [How to handle edge case]
**Priority**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Difficulty**: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]

### Unusual Inputs

#### Edge Case 1: [Brief Description]
[Same structure as Boundary Conditions]

### System State Edge Cases

#### Edge Case 1: [Brief Description]
[Same structure as Boundary Conditions]

### Timing Edge Cases

#### Edge Case 1: [Brief Description]
[Same structure as Boundary Conditions]

## Overall Integrity Assessment

### System Cohesion
**Assessment**: [Overall evaluation]
**Strengths**: [List strengths]
**Weaknesses**: [List weaknesses]
**Recommendations**: [List recommendations]

### Functional Completeness
**Assessment**: [Overall evaluation]
**Missing Features**: [List missing features]
**Incomplete Implementations**: [List incomplete implementations]
**Recommendations**: [List recommendations]

### Reliability
**Assessment**: [Overall evaluation]
**Error Recovery**: [Assessment]
**Robustness**: [Assessment]
**Data Integrity**: [Assessment]
**Recommendations**: [List recommendations]

## Prioritized Recommendations

### Critical Priority (Must Address Immediately)
1. **[Issue Name]** - Priority: CRITICAL, Difficulty: [EASY/MODERATE/DIFFICULT/VERY DIFFICULT]
   - Location: `filename.sh` line X
   - Type: [Consistency/Compatibility/Conflict/Gap/Contradiction/Edge Case]
   - Impact: [Description]
   - Effort: [Time estimate]
   - Justification: [Why critical]

### High Priority (Should Address Soon)
[Same structure as Critical]

### Medium Priority (Address When Time Permits)
[Same structure as Critical]

### Low Priority (Nice to Have)
[Same structure as Critical]

## Impact vs. Effort Matrix

### Quick Wins (High Impact, Low Effort)
- [List items with HIGH/CRITICAL priority and EASY difficulty]

### Major Projects (High Impact, High Effort)
- [List items with HIGH/CRITICAL priority and DIFFICULT/VERY DIFFICULT difficulty]

### Fill-ins (Low Impact, Low Effort)
- [List items with LOW/MEDIUM priority and EASY difficulty]

### Thankless Tasks (Low Impact, High Effort)
- [List items with LOW/MEDIUM priority and DIFFICULT/VERY DIFFICULT difficulty]

## Well-Integrated Components
- **Component 1**: [Brief note on why it's well-integrated]

## Patterns and Observations
- [Pattern 1]: [Description and examples]
- [Observation 1]: [Description]

## Execution Flow Diagrams

### Entry Point: [MAIN_SCRIPT].sh
```
[ASCII or text-based flow diagram showing execution paths]
Example:
  START
    ↓
  Source [LIB_DIR]/[MODULE_NAME].sh
    ↓
  Source [LIB_DIR]/[MODULE_NAME].sh
    ↓
  Load configuration
    ↓
  Check conditions
    ↓
  [Branch: Condition met?]
    ├─ YES → Execute action
    └─ NO → Exit silently
```

### Entry Point: [CONFIGURE_SCRIPT].sh
```
[ASCII or text-based flow diagram showing execution paths]
```

## Next Steps
- [ ] Review prioritized recommendations with team/user
- [ ] Create implementation plans for critical and high-priority items
- [ ] Schedule improvement work
- [ ] Update this assessment after improvements are completed
```

---

## Notes

- **Assessment-Only Phase**: This assessment is for analysis and documentation only. Do not modify any code files during the assessment. Only the timestamped assessment markdown file should be edited.

- **Comprehensive Flow Analysis**: Be thorough in tracing execution paths. Follow every branch, every function call, and every conditional. Use multiple methods (code reading, execution tracing, dependency analysis) to ensure nothing is missed.

- **Focus on Integration**: This assessment focuses on how components work together as a system, not just individual component quality. Pay special attention to interactions, dependencies, and data flow.

- **Variable and Argument Consistency**: Pay careful attention to variable names and function arguments. Inconsistencies here can cause subtle bugs that are hard to detect.

- **Edge Case Analysis**: Don't just verify "normal" operation. Think about boundary conditions, unusual inputs, error conditions, and system state edge cases.

- **Modular Architecture**: This codebase follows a modular architecture pattern. When analyzing, maintain awareness of module boundaries and inter-module dependencies.

- **Configuration File Operations**: Be aware of configuration file locking (if applicable) and verify its integration with other components.

- **Scope**: Do not analyze files in the `tests/` directory or markdown documentation files. Focus on production code only.

---

## Template Version

- **Version**: 1.0
- **Created**: 2026-01-24
- **Last Updated**: 2026-01-24
