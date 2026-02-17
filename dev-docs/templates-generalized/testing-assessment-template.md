# Testing Assessment Template - [PROJECT_NAME]

## Purpose

This document provides a systematic approach to identify what tests need to be performed for the [PROJECT_NAME]. The assessment:

- Identifies existing tests that should be re-run due to code changes
- Suggests new tests needed to cover functionality and edge cases
- Examines code and documentation to extract test requirements
- Analyzes shell scripts to identify functionality that requires testing
- Categorizes tests by automation feasibility (automated vs manual/interactive)
- Identifies test environment requirements and setup possibilities
- Provides prioritized recommendations for critical testing needs

## How to Use This Document

### Important: Creating Assessment Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each testing assessment:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/testing-assessments/testing-assessment-YYYY-MM-DD-HHMMSS.md`
   - Use format: `testing-assessment-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp dev-docs/templates/testing-assessment-template.md "[DEV_DOCS]/testing-assessments/testing-assessment-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Document all identified testing gaps and requirements
   - Categorize tests by type and automation feasibility
   - Provide specific recommendations with priorities

3. **After completing the assessment**:
   - Review all findings in the timestamped file
   - If new testing patterns or requirements are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific assessment

### Critical: No Code Changes During Assessment

**DO NOT edit any code files or test files during the assessment.** The assessment is for **analysis and documentation only**.

- **Document testing needs, don't implement them**: When you identify a testing gap, document it thoroughly in the timestamped assessment file with:
  - Exact location in documentation or code (file and line numbers/sections)
  - Description of what needs to be tested
  - Test type (automated vs manual)
  - Required conditions or environment setup
  - Priority level (critical, high, medium, low)
  - Suggested test approach (but don't implement it yet)

- **Only edit the timestamped assessment file**: The only file that should be modified during the assessment is the new timestamped markdown file created for this specific assessment.

- **Separate phases**: 
  - **Phase 1 (Assessment)**: Identify and document all testing requirements
  - **Phase 2 (Test Implementation)**: After assessment completion, review findings with team/user and implement tests separately

This approach ensures:
- The assessment remains focused on discovery and analysis, not implementation
- All testing needs are documented before any test code changes
- The user/team can prioritize which tests to address first
- The assessment results provide a complete picture of all testing requirements
- Assessment results are not mixed with actual test implementation

### Assessment Process

1. **Identify tests that need re-running**:
   - Examine all test files in `[TEST_DIR]/` directory
   - Check when tests were last modified vs codebase changes using `git log`
   - Check `[DEV_DOCS]/testing-assessments/test-history.md` for the last time each test was run
   - Identify tests that should be re-run due to code changes
   - Run existing tests and document which pass, fail, or need updates
   - Note any broken or flaky tests that need attention

2. **Extract test requirements from documentation**:
   - Read `[DEV_DOCS]/plan-phase-4-testing.md` to identify pending tests
   - Read `[DEV_DOCS]/TECHNICAL_DETAILS.md` to extract test requirements for features
   - Review `[DEV_DOCS]/STEAMOS_GAMING_MODE.md` for [PLATFORM_MODE]-specific test needs
   - Check enhancement documents in `[DEV_DOCS]/enhancements/` for feature-specific test requirements
   - Review `[DEV_DOCS]/REMAINING_WORK_SUMMARY.md` for testing-related work items
   - Focus on identifying what tests need to be created, not evaluating the documentation itself

3. **Examine code to identify missing tests**:
   - Review main scripts (`[MAIN_SCRIPT].sh`, `[CONFIG_SCRIPT].sh`, `[MANAGE_SCRIPT].sh`, `[INSTALL_SCRIPT].sh`, `un[INSTALL_SCRIPT].sh`)
   - Review library modules in `[LIB_DIR]/` directory
   - Identify functionality that may not be covered by existing tests
   - Look for error handling paths that need testing
   - Identify edge cases and boundary conditions
   - Compare code functionality with existing test coverage

4. **Categorize test needs**:
   - **Automated tests**: Can be run without user interaction
   - **Manual/Interactive tests**: Require user interaction or specific conditions
   - **Environment setup possible**: Can be tested via virtual environment, container, or temporary setup
   - **Requires specific hardware/software**: Needs actual [PLATFORM_NAME], specific desktop environment, etc.

5. **Prioritize test recommendations**:
   - **CRITICAL**: Tests that verify core functionality or prevent system-breaking issues
   - **HIGH**: Tests for important features or edge cases
   - **MEDIUM**: Tests for less critical functionality
   - **LOW**: Nice-to-have tests or low-risk areas

---

## Assessment Sections

### Section 0: Tests That Need Re-Running

#### 0.1: Identify Tests Requiring Re-Execution

**Location**: `[TEST_DIR]/` directory

**Purpose**: Identify which existing tests should be re-run due to code changes or need updates.

**Tasks**:
- [ ] List all test files in `[TEST_DIR]/` directory
- [ ] For each test file, identify what code it tests
- [ ] Use `git log` to check if tested code has changed since test was written
- [ ] Check `[DEV_DOCS]/testing-assessments/test-history.md` for the last time each test was run
- [ ] Compare test file modification dates with codebase file modification dates
- [ ] **CRITICAL: Identify tests that modify the actual configuration file** (`${HOME}/[CONFIG_FILE_PATH]`)
  - [ ] Check if test backs up the config file before modifying it
  - [ ] Check if test uses a trap (e.g., `trap cleanup EXIT`) to ensure config is restored even if test is interrupted
  - [ ] Check if test restores the config file after completion
  - [ ] Document which tests modify the actual config file (not just test configs)
  - [ ] For tests that modify the actual config, add warnings to the test file header and README
  - [ ] Recommend adding traps to tests that modify config but don't have them
- [ ] Run each test and document results (pass/fail/skip)
- [ ] Identify tests that fail due to code changes (not just bugs)
- [ ] Note tests that need updates to work with new functionality
- [ ] **Identify outdated tests**: Check if any tests test functionality that no longer exists, has been removed, or is no longer relevant
  - [ ] For each outdated test, determine if it should be removed or kept for historical reference
  - [ ] Suggest adding a comment at the top of outdated tests stating they are outdated and no longer relevant
  - [ ] Document the reason why the test is outdated (e.g., feature removed, functionality changed, replaced by different approach)
- [ ] Update `[DEV_DOCS]/testing-assessments/test-history.md` with current test execution dates and results

**For each test file**:
- [ ] Document what the test covers
- [ ] Check if tested code files have been modified (use `git log --follow <file>`)
- [ ] **CRITICAL: Check if test modifies the actual configuration file**
  - [ ] Does test modify `${HOME}/[CONFIG_FILE_PATH]`? (Yes/No/Uses test config)
  - [ ] Does test backup config before modifying? (Yes/No/N/A)
  - [ ] Does test use trap to ensure cleanup? (Yes/No/N/A)
  - [ ] Does test restore config after completion? (Yes/No/N/A)
  - [ ] **WARNING**: If test modifies actual config without proper backup/restore/trap, mark as **CRITICAL ISSUE**
- [ ] **Recommendation**: Should this test be re-run? (Yes/No/Needs Update/Outdated)
- [ ] If needs update, note what changes are required
- [ ] **Check if test is outdated**: Does this test cover functionality that no longer exists or is no longer relevant?
  - [ ] If outdated, document why (feature removed, functionality changed, replaced by different approach)
  - [ ] Suggest adding a comment in the test file stating it is outdated and no longer relevant
  - [ ] Determine if test should be removed or kept for historical reference
- [ ] Check test dependencies (required tools: expect, wmctrl, xdotool, zenity, yad, kdialog, etc.)
- [ ] Note if test is currently broken or flaky

**Documentation Format**:
```
### Tests Requiring Re-Execution

#### Tests That Should Be Re-Run
- **test-[FEATURE].sh**: Tests `[MAIN_SCRIPT].sh` which was modified on 2024-01-15
  - Code changes: Added new feature X (lines 45-67)
  - Recommendation: Re-run to verify existing functionality still works
  - Status: [Passed/Failed/Needs Update]
  - **Config File Impact**: [Modifies actual config/Uses test config/No config used]
  - **Safety**: [Has backup+restore+trap/Needs improvement/No config impact]

#### Tests Requiring Updates
- **test-[FEATURE].sh**: Tests `[CONFIG_SCRIPT].sh` which added new option Y
  - Required updates: Test needs to cover new option Y
  - Current coverage: Only tests options A, B, C
  - Missing coverage: Option Y validation and error handling
  - **Config File Impact**: [Modifies actual config/Uses test config/No config used]
  - **Safety**: [Has backup+restore+trap/Needs improvement/No config impact]

#### Tests That Modify Actual Configuration File
- **test-[FEATURE].sh**: Modifies `${HOME}/[CONFIG_FILE_PATH]`
  - Backup: [Yes/No] - Uses backup function
  - Restore: [Yes/No] - Restores at end
  - Trap: [Yes/No] - Uses `trap cleanup EXIT` to ensure restore on interrupt
  - **Risk Level**: [CRITICAL/HIGH/MEDIUM/LOW] - If interrupted, config may not be restored
  - **Recommendation**: [Add trap/Add backup/Add restore/Already safe/No changes needed]
  - **Warning Added**: [Yes/No] - Test file has warning in header/README

#### Test Execution Results
- Tests Run: [X of Y]
- Tests Passed: [X]
- Tests Failed: [X] - [List with reasons]
- Tests Skipped: [X] - [List with reasons]
- **Config Files Affected**: [X tests modified actual config, Y tests used test configs]

#### Broken or Flaky Tests
- **test-[FEATURE].sh**: Intermittent failures due to timing issues
  - Issue: Race condition in test setup
  - Recommendation: Fix test or mark as known issue
  - **Config File Impact**: [Modifies actual config/No config impact]

#### Outdated Tests (No Longer Relevant)
- **test-[FEATURE].sh**: Tests functionality that has been removed or replaced
  - Reason outdated: [Feature removed/Functionality changed/Replaced by different approach]
  - Tested code: [What code/feature it was testing]
  - Recommendation: Add comment at top of test file stating: "# OUTDATED: This test is no longer relevant because [reason]. Kept for historical reference."
  - Action: [Remove test/Keep with comment/Update to test new functionality]
  - **Config File Impact**: [Modifies actual config/Uses test config/No config used]
```

#### 0.2: Config File Safety in Tests

**Purpose**: Ensure that tests never modify the actual installed configuration file (`${HOME}/[CONFIG_FILE_PATH]`) without proper safeguards. This section provides guidelines and requirements for test safety.

**CRITICAL REQUIREMENT**: Tests must never modify the actual config file without proper backup and restore mechanisms, or better yet, should use dummy/test config files whenever possible.

**PRIMARY APPROACH**: When feasible, design and run tests using a "dummy" copy config file that mimics a real one. If modifying actual `.sh` scripts is required, make copies of those scripts and modify the copies instead. Do this with as many `.sh` files and dummy test files as needed to run tests without modifying the actual config file or script files.

**Tasks**:
- [ ] **Identify all tests that interact with config files**:
  - [ ] List all tests that read, write, or modify configuration files
  - [ ] For each test, determine if it uses the actual config file or a test/dummy config file
  - [ ] Document which tests modify the actual config file (this should be minimal or zero)
  - [ ] Identify tests that could be refactored to use dummy config files that mimic real ones

- [ ] **Verify tests use dummy config files that mimic real ones**:
  - [ ] Check if tests create dummy config files in test directories (e.g., `[TEST_DIR]/test-configs/`)
  - [ ] Verify dummy config files mimic the structure and format of real config files
  - [ ] Verify tests use test-specific config file paths instead of actual config paths
  - [ ] Check if tests require script modifications to use dummy config files
  - [ ] Document tests that successfully use dummy config files
  - [ ] Identify tests that should be refactored to use dummy config files

- [ ] **Verify script copying and modification approach**:
  - [ ] Identify tests that require modifications to actual `.sh` scripts
  - [ ] Verify tests create copies of original scripts (e.g., `cp [CONFIG_SCRIPT].sh [TEST_DIR]/test-[CONFIG_SCRIPT].sh`)
  - [ ] Check that tests modify the copied scripts, not the original scripts
  - [ ] Verify tests use as many copied `.sh` files and dummy test files as needed
  - [ ] Document which scripts were copied and why
  - [ ] Ensure copied scripts are modified to use dummy config file paths
  - [ ] Verify that actual installed scripts are never modified during testing

- [ ] **Track edits that should be applied to original scripts**:
  - [ ] For each test that modifies copied scripts, identify what changes were made
  - [ ] Document which edits to copied scripts should be applied to the actual original scripts
  - [ ] Note when those edits should be applied (e.g., after testing, during next development cycle)
  - [ ] **CRITICAL**: Do not make these edits at test time - only track and report them
  - [ ] Create a list of recommended edits to original scripts based on test script modifications
  - [ ] Report tracked edits in the assessment documentation

- [ ] **Verify backup and restore mechanisms for tests that must modify actual config**:
  - [ ] For tests that must modify the actual config file (last resort only), verify they:
    - [ ] Create a backup of the config file before any modifications
    - [ ] Use a trap mechanism (e.g., `trap cleanup EXIT`) to ensure restoration even if test is interrupted
    - [ ] Restore the config file after test completion (both success and failure cases)
    - [ ] Handle edge cases (config file doesn't exist, backup fails, restore fails)
  - [ ] Document which tests modify actual config and their safety mechanisms
  - [ ] Identify tests that modify actual config but lack proper backup/restore/trap mechanisms
  - [ ] Recommend refactoring these tests to use dummy config files instead

- [ ] **Document config file safety status**:
  - [ ] Create a summary of all tests and their config file handling approach
  - [ ] Mark tests that are safe (use dummy configs) vs risky (modify actual config)
  - [ ] List tests that need improvements to be safer
  - [ ] Document tracked edits that should be applied to original scripts (but not applied during testing)
  - [ ] Provide recommendations for making tests safer

**Best Practices for Test Config File Safety**:

1. **Use Dummy Config Files That Mimic Real Ones** (PRIMARY APPROACH - RECOMMENDED):
   - Create dummy config files in `[TEST_DIR]/test-configs/` or similar test-specific directories
   - **CRITICAL**: Dummy config files should mimic the structure and format of real config files
   - Use dummy config files that accurately represent real-world configurations
   - This approach completely isolates tests from the actual installed configuration
   - Example: Create `[TEST_DIR]/test-configs/test-config.conf` that mimics `${HOME}/[CONFIG_FILE_PATH]`

2. **Copy and Modify Scripts When Needed** (REQUIRED IF SCRIPTS MUST BE MODIFIED):
   - **NEVER modify actual `.sh` scripts during testing**
   - If a test requires script modifications (e.g., to use dummy config paths), create copies:
     - Copy original script: `cp [CONFIG_SCRIPT].sh [TEST_DIR]/test-[CONFIG_SCRIPT].sh`
     - Copy as many `.sh` files as needed: `cp [LIB_DIR]/config.sh [TEST_DIR]/test-lib/test-[FEATURE].sh`
     - Modify the copied scripts to use dummy config file paths
     - Test the modified copies, not the original scripts
   - **CRITICAL**: Use as many copied `.sh` files and dummy test files as needed to avoid modifying actual files
   - Document which scripts were copied and why
   - **Track edits for later application**:
     - Keep a record of what changes were made to copied scripts
     - Document which edits should be applied to the actual original scripts
     - Note when those edits should be applied (e.g., after testing phase, during next development cycle)
     - **DO NOT apply these edits at test time** - only track and report them
     - Report tracked edits in the assessment documentation

3. **If Actual Config Must Be Modified** (LAST RESORT - AVOID IF POSSIBLE):
   - **ONLY use this approach if using dummy config files is not feasible**
   - **ALWAYS** create a backup before any modification
   - **ALWAYS** use a trap to ensure restoration on exit/interrupt:
     ```bash
     CONFIG_BACKUP="${HOME}/[CONFIG_FILE_PATH].backup.$(date +%Y%m%d_%H%M%S)"
     
     cleanup() {
         if [ -f "$CONFIG_BACKUP" ]; then
             mv "$CONFIG_BACKUP" "${HOME}/[CONFIG_FILE_PATH]"
         fi
     }
     trap cleanup EXIT INT TERM
     
     # Backup before modification
     cp "${HOME}/[CONFIG_FILE_PATH]" "$CONFIG_BACKUP"
     ```
   - **ALWAYS** restore the config file in both success and failure scenarios
   - **ALWAYS** handle edge cases (file doesn't exist, backup fails, etc.)
   - **ALWAYS** add clear warnings in test file headers and documentation
   - **Consider refactoring**: If a test must modify actual config, consider if it can be refactored to use dummy config files with copied scripts

**Documentation Format**:
```
### Config File Safety Assessment

#### Tests Using Dummy Config Files (SAFE)
- **test-[FEATURE].sh**: Uses `[TEST_DIR]/test-configs/test-config.conf`
  - Approach: Creates dummy config file in test directory that mimics real config structure
  - Dummy Config: `[TEST_DIR]/test-configs/test-config.conf` (mimics `${HOME}/[CONFIG_FILE_PATH]`)
  - Safety Level: SAFE - No risk to actual config
  - Script Modifications: None needed

- **test-[CONFIG_SCRIPT].sh**: Uses modified copy of [CONFIG_SCRIPT].sh with dummy config path
  - Approach: Copies `[CONFIG_SCRIPT].sh` to `[TEST_DIR]/test-[CONFIG_SCRIPT].sh` and modifies to use dummy config
  - Copied Scripts: `[TEST_DIR]/test-[CONFIG_SCRIPT].sh` (copy of `[CONFIG_SCRIPT].sh`)
  - Dummy Config: `[TEST_DIR]/test-configs/test-config.conf` (mimics real config)
  - Script Modifications: Modified copy uses `TEST_CONFIG_PATH` variable pointing to dummy config
  - Safety Level: SAFE - No risk to actual config or scripts
  - Tracked Edits for Original Scripts:
    - [ ] Edit 1: Add `TEST_CONFIG_PATH` variable support to `[CONFIG_SCRIPT].sh` (apply after testing phase)
    - [ ] Edit 2: [Description of other edits that should be applied to original script]
  - Edits Applied at Test Time: NO - Only tracked for later application

#### Tests Modifying Actual Config File (REQUIRES SAFETY MECHANISMS)
- **test-[FEATURE].sh**: Modifies `${HOME}/[CONFIG_FILE_PATH]`
  - Backup: YES - Creates timestamped backup before modification
  - Restore: YES - Restores config after test completion
  - Trap: YES - Uses `trap cleanup EXIT INT TERM` to ensure restore on interrupt
  - Safety Level: SAFE - Proper safeguards in place
  - Warning in Header: YES - Test file has clear warning about modifying actual config
  - Recommendation: Consider refactoring to use test config file if possible

#### Tests Needing Safety Improvements (RISKY)
- **test-[FEATURE].sh**: Modifies actual config without proper safeguards
  - Issues:
    - No backup before modification
    - No trap mechanism
    - Config may not be restored if test is interrupted
  - Safety Level: RISKY - Could leave config in modified state
  - Priority: CRITICAL - Must be fixed before running
  - Recommendations:
    1. Refactor to use test config file (preferred)
    2. If refactoring not possible, add backup + restore + trap mechanism
    3. Add warning in test file header

#### Tracked Edits for Original Scripts (Not Applied at Test Time)
- **Edits from test-[CONFIG_SCRIPT].sh**:
  - Edit 1: Add `TEST_CONFIG_PATH` variable support to `[CONFIG_SCRIPT].sh`
    - Reason: Allows [CONFIG_SCRIPT].sh to work with test config files
    - When to Apply: After testing phase, during next development cycle
    - Status: Tracked, not applied
  - Edit 2: [Additional edit description]
    - Reason: [Why this edit is needed]
    - When to Apply: [When it should be applied]
    - Status: Tracked, not applied

- **Edits from test-[MANAGE_SCRIPT].sh**:
  - [List edits from other tests...]

**IMPORTANT**: These edits are tracked for reporting purposes only. They should NOT be applied to original scripts during test execution. Apply them separately after reviewing the assessment.

#### Summary
- Total Tests: [X]
- Tests Using Dummy Configs: [X] (SAFE)
- Tests Using Copied Scripts: [X] (SAFE)
- Tests Modifying Actual Config with Safeguards: [X] (SAFE)
- Tests Modifying Actual Config without Safeguards: [X] (RISKY - MUST FIX)
- Tests Needing Refactoring: [List]
- Total Tracked Edits for Original Scripts: [X] (not applied at test time)
```

**Critical Notes**:
- **During restricted or blocked hours**: Tests that modify the actual config file should NOT be run. Use dummy config files or skip these tests during restricted hours.
- **Test abort scenarios**: Traps must handle all exit scenarios (normal exit, interrupt, termination) to ensure config is always restored.
- **Documentation**: All tests that modify actual config must have clear warnings in their headers and in test documentation.
- **Script modifications**: When tests require script modifications, always copy scripts and modify the copies. Never modify actual `.sh` scripts during testing.
- **Tracking edits**: If edits to copied scripts should be applied to original scripts, track them but DO NOT apply them at test time. Report tracked edits in the assessment documentation for later review and application.
- **Dummy config files**: Dummy config files should mimic the structure and format of real config files to ensure realistic testing.

### Section 1: Test Requirements from Documentation

#### 1.1: Extract Test Requirements from Phase 4 Testing Plan

**Location**: `[DEV_DOCS]/plan-phase-4-testing.md`

**Purpose**: Identify specific tests that are documented as needed but not yet implemented or completed.

**Tasks**:
- [ ] Extract all tests marked as `[ ]` (not completed) from Checklist 4.1: Functional Testing
- [ ] Extract all tests marked as `[X]` but with "NOT TESTED" annotations
- [ ] Identify tests marked as "CRITICAL" that need to be performed
- [ ] Extract pending tests from Checklist 4.2: Edge Case Testing
- [ ] Extract pending tests from Checklist 4.3: Installation and Uninstall Testing
- [ ] Extract pending tests from Checklist 4.4: System Integration Testing
- [ ] Extract pending supplemental tests
- [ ] For each identified test, document:
  - Test name/description
  - What functionality it should test
  - Priority level (if specified)
  - Whether it's a new test or needs to be re-run

**Documentation Format**:
```
### Test Requirements from Phase 4 Testing Plan

#### Functional Tests Needed
- **Test: [Name]**
  - Description: [What it should test]
  - Priority: [CRITICAL/HIGH/MEDIUM/LOW]
  - Status: New test needed / Needs re-run
  - Location in plan: Checklist 4.1, item X

#### Edge Case Tests Needed
- **Test: [Name]**
  - Description: [What edge case it should test]
  - Priority: [CRITICAL/HIGH/MEDIUM/LOW]
  - Status: New test needed
  - Location in plan: Checklist 4.2, item X

#### Installation/Uninstall Tests Needed
- [Similar format]

#### Integration Tests Needed
- [Similar format]
```

#### 1.2: Extract Test Requirements from Test Suite Documentation

**Location**: `[TEST_DIR]/README.md`

**Purpose**: Identify tests mentioned in documentation that may not exist yet or need to be created.

**Tasks**:
- [ ] Extract any test requirements or test cases mentioned in `[TEST_DIR]/README.md`
- [ ] Compare documented tests with actual test files in `[TEST_DIR]/` directory
- [ ] Identify tests documented but not implemented
- [ ] Note any "future tests" or "planned tests" mentioned

**Documentation Format**:
```
### Test Requirements from Test Suite Documentation

#### Documented Tests Not Yet Implemented
- **Test: [Name from README]**
  - Description: [What it should test]
  - Status: Needs to be created
  - Reference: [TEST_DIR]/README.md, section X

#### Tests Mentioned But Missing
- [List of tests documented but not found in [TEST_DIR]/ directory]
```

### Section 2: Test Requirements from Technical Documentation

#### 2.1: Extract Test Requirements from TECHNICAL_DETAILS.md

**Location**: `[DEV_DOCS]/TECHNICAL_DETAILS.md`

**Purpose**: Identify what tests are needed based on features and implementation details described in technical documentation.

**Tasks**:
- [ ] Extract explicit testing requirements mentioned in "Testing Requirements" sections
- [ ] For each feature described, identify what tests should verify it works
- [ ] Note any "CRITICAL" or "MUST TEST" annotations and create test requirements
- [ ] Identify environment-specific test needs ([DISPLAY_PROTOCOL], [DISPLAY_PROTOCOL], [PLATFORM_MODE], etc.)

**Key Features to Extract Test Requirements For**:
- [ ] Minimum Display Time Feature (lines 114-156): What tests verify [DISPLAY_PROTOCOL]/[DISPLAY_PROTOCOL] behavior, window manager compatibility, auto-reopen, countdown?
- [ ] Full-Screen Application Compatibility (lines 157-201): What tests verify desktop environment compatibility, display protocols, [PLATFORM_MODE] behavior?
- [ ] Display Access and Detection (lines 90-106): What tests verify [DISPLAY_PROTOCOL]/[DISPLAY_PROTOCOL] detection, fallbacks, [PLATFORM_MODE] detection?
- [ ] Configuration File Format (lines 54-82): What tests verify parsing, validation, edge cases (overnight ranges, multiple ranges)?
- [ ] 24/7 Restriction Prevention (lines 264-383): What tests verify validation algorithm, overlap detection, safety features?
- [ ] Timer Configuration (lines 203-209): What tests verify interval config, timer file updates, accuracy?
- [ ] Script Implementation: What tests are needed for [CONFIG_SCRIPT].sh, [MANAGE_SCRIPT].sh, [INSTALL_SCRIPT].sh, un[INSTALL_SCRIPT].sh?

**Documentation Format**:
```
### Test Requirements from TECHNICAL_DETAILS.md

#### Tests Needed for Minimum Display Time Feature
- **Test: [DISPLAY_PROTOCOL] minimum display time behavior**
  - Purpose: Verify minimum display time works correctly on [DISPLAY_PROTOCOL]
  - Priority: HIGH
  - Environment: [DISPLAY_PROTOCOL] desktop environment
  - Reference: TECHNICAL_DETAILS.md lines 114-156

#### Tests Needed for Configuration File Format
- **Test: Overnight time range parsing**
  - Purpose: Verify configuration correctly parses overnight ranges (e.g., 22:00-06:00)
  - Priority: HIGH
  - Reference: TECHNICAL_DETAILS.md lines 54-82

[Continue for each feature...]
```

#### 2.2: Extract Test Requirements from STEAMOS_GAMING_MODE.md

**Location**: `[DEV_DOCS]/STEAMOS_GAMING_MODE.md`

**Purpose**: Identify [PLATFORM_MODE]-specific tests that need to be performed.

**Tasks**:
- [ ] Extract [PLATFORM_MODE]-specific test requirements
- [ ] Identify display detection tests needed for [PLATFORM_MODE]
- [ ] Identify popup behavior tests needed for [PLATFORM_MODE]
- [ ] Identify [INIT_SYSTEM] service tests needed
- [ ] For each requirement, document what test should verify

**Documentation Format**:
```
### Test Requirements from STEAMOS_GAMING_MODE.md

#### [PLATFORM_MODE] Display Detection Tests Needed
- **Test: [PLATFORM_MODE] display detection**
  - Purpose: Verify system correctly detects [PLATFORM_MODE] environment
  - Priority: CRITICAL
  - Environment: [PLATFORM_NAME]
  - Reference: STEAMOS_GAMING_MODE.md, section X

#### [PLATFORM_MODE] Popup Behavior Tests Needed
- **Test: Popup display in [PLATFORM_MODE]**
  - Purpose: Verify popup appears correctly in [PLATFORM_MODE]
  - Priority: CRITICAL
  - Environment: [PLATFORM_NAME] with full-screen game
  - Reference: STEAMOS_GAMING_MODE.md, section Y

[Continue for each requirement...]
```

#### 2.3: Extract Test Requirements from Enhancement Documents

**Location**: `[DEV_DOCS]/enhancements/`

**Purpose**: Identify tests needed for features described in enhancement documents.

**Tasks**:
- [ ] For each enhancement document, extract test requirements
- [ ] Identify features that may not have corresponding tests yet
- [ ] Check for "Testing Requirements" or "Test Cases" sections
- [ ] Document what tests should verify each enhancement works

**Documentation Format**:
```
### Test Requirements from Enhancement Documents

#### Tests Needed for Enhancement X
- **Test: [Name]**
  - Purpose: [What it should verify]
  - Priority: [Level]
  - Enhancement: enhancement-X.md
  - Status: New test needed

[Continue for each enhancement...]
```

### Section 3: Identify Missing Tests from Code Analysis

#### 3.1: Tests Needed for Main Scripts

**Scripts to Review**:
- `[MAIN_SCRIPT].sh` - Main entry point
- `[CONFIG_SCRIPT].sh` - Configuration wizard
- `[MANAGE_SCRIPT].sh` - Management interface
- `[INSTALL_SCRIPT].sh` - Installation script
- `un[INSTALL_SCRIPT].sh` - Uninstall script

**Purpose**: Identify functionality in main scripts that needs testing but may not be covered by existing tests.

**Tasks**:
- [ ] For each script, compare functionality with existing test coverage
- [ ] Identify main execution paths that need tests
- [ ] Identify error handling paths that need tests
- [ ] Identify edge cases and boundary conditions that need tests
- [ ] Identify input validation points that need tests
- [ ] Identify external dependency interactions that need tests
- [ ] Identify environment-specific behavior that needs tests
- [ ] For each identified gap, suggest a specific test

**Documentation Format**:
```
### Tests Needed for Main Scripts

#### [MAIN_SCRIPT].sh
- **Test: Main execution path with valid config**
  - Purpose: Verify script runs correctly with valid configuration
  - Priority: CRITICAL
  - Status: [Exists/Needs creation/Needs re-run]

- **Test: Error handling for missing config file**
  - Purpose: Verify script handles missing config gracefully
  - Priority: HIGH
  - Status: [Exists/Needs creation]

[Continue for each script and functionality...]
```

#### 3.2: Tests Needed for Library Modules

**Modules to Review**: All files in `[LIB_DIR]/` directory (config.sh, logging.sh, display-detection.sh, desktop-environment.sh, window-management.sh, time-validation.sh, popup-display.sh, uninstall-verification.sh, configure-*.sh, etc.)

**Purpose**: Identify functions and features in library modules that need testing.

**Tasks**:
- [ ] For each module, list all functions
- [ ] Compare functions with existing test coverage
- [ ] Identify functions that need unit tests
- [ ] Identify error conditions that need tests
- [ ] Identify edge cases that need tests
- [ ] Identify external dependency interactions that need tests
- [ ] Identify environment-specific behavior that needs tests
- [ ] For each identified gap, suggest a specific test

**Documentation Format**:
```
### Tests Needed for Library Modules

#### [LIB_DIR]/config.sh
- **Test: load_config() with valid config file**
  - Purpose: Verify config loading works correctly
  - Priority: CRITICAL
  - Function: load_config()
  - Status: [Exists/Needs creation/Needs re-run]

- **Test: load_config() with invalid config file**
  - Purpose: Verify error handling for invalid config
  - Priority: HIGH
  - Function: load_config()
  - Status: [Exists/Needs creation]

[Continue for each module and function...]
```

### Section 4: Test Execution and Results

#### 4.0: Test Execution Status

**Tasks**:
- [ ] Run existing automated tests and document results
- [ ] Note which tests pass, fail, or are skipped
- [ ] Document any test failures with error messages
- [ ] Identify tests that cannot be run (missing dependencies, environment issues)
- [ ] Check test execution time (identify slow tests)
- [ ] Verify test cleanup (configs restored, temp files removed)

**Documentation Format**:
```
### Test Execution Results
- Tests Run: [X of Y]
- Tests Passed: [X]
- Tests Failed: [X] - [List with error details]
- Tests Skipped: [X] - [List with reasons]
- Slow Tests (>30s): [List]
- Missing Dependencies: [List]
```

### Section 5: Test Categorization

#### 5.1: Automated Tests

**Definition**: Tests that can be run without user interaction, typically using scripts, test frameworks, or automated tools.

**Tasks**:
- [ ] Identify all tests that can be automated
- [ ] Categorize by test type:
  - [ ] Unit tests (individual functions/modules)
  - [ ] Integration tests (multiple components)
  - [ ] Configuration file parsing tests
  - [ ] Validation logic tests
  - [ ] Error handling tests
  - [ ] Edge case tests (that don't require user interaction)

**Documentation Format**:
```
### Automated Tests
- Unit Tests: [List]
- Integration Tests: [List]
- Configuration Tests: [List]
- Validation Tests: [List]
- Error Handling Tests: [List]
```

#### 5.2: Manual/Interactive Tests

**Definition**: Tests that require user interaction, specific hardware, or conditions that cannot be easily automated.

**Tasks**:
- [ ] Identify all tests requiring user interaction, specific hardware ([PLATFORM_NAME], desktop environments), specific conditions (full-screen games, time of day), categorize by requirement type

**Documentation Format**:
```
### Manual/Interactive Tests
- User Interaction Required: [List]
- Specific Hardware Required: [List]
- Specific Conditions Required: [List]
- Time-Dependent Tests: [List]
```

#### 5.3: Environment Setup Possibilities

**Definition**: Tests that could be automated or simplified if a virtual environment, container, or temporary setup can be created.

**Tasks**:
- [ ] Identify tests that could use virtual environments, containers, temporary configurations, or mock/stub tools
- [ ] Note setup requirements and feasibility for each

**Documentation Format**:
```
### Environment Setup Possibilities
- Virtual Environment Tests: [List with setup requirements and feasibility]
- Container-Based Tests: [List with setup requirements and feasibility]
- Temporary Configuration Tests: [List with setup requirements and feasibility]
- Mock/Stub Tests: [List with setup requirements and feasibility]
```

### Section 6: Recommendations and Priorities

#### 6.1: Critical Recommendations

**Definition**: Tests that are essential for system reliability, prevent system-breaking issues, or verify core functionality.

**Tasks**:
- [ ] List all critical testing recommendations
- [ ] Provide justification for critical status
- [ ] Note any dependencies or prerequisites
- [ ] Suggest implementation approach

**Documentation Format**:
```
### Critical Recommendations

#### [Test Name/Area]
- **Priority**: CRITICAL
- **Justification**: [Why critical]
- **Dependencies**: [Prerequisites]
- **Implementation Approach**: [Suggested approach]
- **Estimated Effort**: [Time/complexity]

[Repeat for each critical recommendation]
```

#### 6.2: High Priority Recommendations

**Definition**: Tests for important features, significant edge cases, or areas with high user impact.

**Tasks**:
- [ ] List all high priority testing recommendations with justification, dependencies, implementation approach, and effort estimate

**Documentation Format**:
```
### High Priority Recommendations

#### [Test Name/Area]
- **Priority**: HIGH
- **Justification**: [Why high priority]
- **Dependencies**: [Prerequisites]
- **Implementation Approach**: [Suggested approach]
- **Estimated Effort**: [Time/complexity]

[Repeat for each high priority recommendation]
```

#### 6.3: Medium Priority Recommendations

**Definition**: Tests for less critical functionality, nice-to-have features, or lower-risk areas.

**Tasks**:
- [ ] List all medium priority testing recommendations with brief justification and implementation approach

**Documentation Format**:
```
### Medium Priority Recommendations

#### [Test Name/Area]
- **Priority**: MEDIUM
- **Justification**: [Why medium priority]
- **Implementation Approach**: [Suggested approach]

[Repeat for each medium priority recommendation]
```

#### 6.4: Low Priority Recommendations

**Definition**: Tests for edge cases with low impact, cosmetic features, or areas with minimal risk.

**Tasks**:
- [ ] List all low priority testing recommendations with brief justification

**Documentation Format**:
```
### Low Priority Recommendations

#### [Test Name/Area]
- **Priority**: LOW
- **Justification**: [Why low priority]

[Repeat for each low priority recommendation]
```

### Section 7: Summary and Next Steps

#### 7.1: Testing Coverage Summary

**Tasks**:
- [ ] Summarize overall testing coverage
- [ ] Identify major gaps
- [ ] Note areas with good coverage
- [ ] Calculate rough percentages if possible

**Documentation Format**:
```
### Testing Coverage Summary
- Overall Coverage: Functional [X%], Edge Case [X%], Installation [X%], Integration [X%]
- Major Gaps: [List]
- Well-Covered Areas: [List]
```

#### 7.2: Implementation Roadmap

**Tasks**:
- [ ] Prioritize test implementation order, group related tests, identify quick wins, note dependencies

**Documentation Format**:
```
### Implementation Roadmap
- Phase 1: Critical Tests (Immediate): [List]
- Phase 2: High Priority Tests (Short-term): [List]
- Phase 3: Medium Priority Tests (Medium-term): [List]
- Phase 4: Low Priority Tests (Long-term): [List]
- Quick Wins: [List of easy-to-implement tests with high value]
```

#### 7.3: Resource Requirements

**Tasks**:
- [ ] Identify required resources: hardware, software/tools, time estimates

**Documentation Format**:
```
### Resource Requirements
- Hardware Requirements: [List]
- Software/Tool Requirements: [List]
- Time Estimates: Critical [X], High [X], Medium [X], Total [X]
```

---

## Important Notes

### Emphasis on Critical Recommendations

When documenting critical recommendations, use **bold text** and clearly mark them as **CRITICAL**. Critical recommendations include:
- **[PLATFORM_NAME] Testing**: [PLATFORM_MODE] functionality tests are typically critical
- **System-Breaking Scenarios**: Tests preventing lockout or inability to configure/uninstall
- **Core Functionality**: Tests for primary user-dependent features
- **Safety Features**: Tests for features preventing dangerous configurations

### Test Environment Considerations

- **Virtual Machines**: For testing different distributions and desktop environments
- **Containers**: For isolated testing environments
- **Temporary Configurations**: For testing changes without affecting production
- **Mock Tools**: For simulating missing dependencies or specific conditions
- **Time Manipulation**: For testing time-dependent functionality (with caution)

### Test Execution Best Practices

- **Run existing tests first**: Execute existing automated tests to establish baseline and identify what needs re-running
- **Document test results**: Record pass/fail status, execution time, and any errors for tests that are re-run
- **Check dependencies**: Verify required tools are available before running tests
- **Use git history**: Compare test file modification dates with code changes using `git log` to identify tests that should be re-run
- **Check test history**: Review `[DEV_DOCS]/testing-assessments/test-history.md` to see when tests were last executed
- **Update test history**: After running tests, update `[DEV_DOCS]/testing-assessments/test-history.md` with execution dates and results
- **Compare code with tests**: For each code file, check if corresponding tests exist and cover all functionality

### Documentation Standards

All test recommendations should include:
- **Clear test description**: What the test should verify
- **Specific location**: File and line numbers/sections where functionality exists
- **Priority justification**: Why this test is critical/high/medium/low priority
- **Test type**: Automated vs manual/interactive
- **Status**: New test needed, needs re-run, or needs update
- **Implementation suggestions**: Suggested approach for creating the test
- **Dependencies and prerequisites**: Required tools, environment, or setup

---

## Assessment Completion Checklist

Before finalizing the assessment:

- [ ] All sections completed
- [ ] All tests requiring re-run identified and documented
- [ ] All new tests needed identified and documented
- [ ] Test recommendations categorized by type and automation feasibility
- [ ] Priorities assigned to all test recommendations
- [ ] Critical test recommendations clearly marked
- [ ] Summary and implementation roadmap completed
- [ ] Resource requirements identified
- [ ] Assessment file saved with timestamp

---

## Template Maintenance

If during the assessment you discover:
- New testing patterns or requirements
- Missing assessment categories
- Better ways to identify tests that need re-running
- Better ways to identify missing tests
- Additional code areas or documentation sources to examine for test requirements

**Add them to this master template** so future assessments benefit from the improvements.
