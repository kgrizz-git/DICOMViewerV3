# Safety Scan Plan - [PROJECT_NAME]

## Purpose

This document provides a comprehensive safety scan prompt that should be run repeatedly after code updates to identify potential system-breaking behaviors, security vulnerabilities, and safety concerns. The scan checks for scenarios that could:

- Lock users out of their system completely
- Make the system unresponsive
- Prevent critical operations (configuration, uninstallation, config editing)
- Create security vulnerabilities
- Cause unintended system behavior
- Remove or modify unintended files (project directory files, files outside installation locations)

## How to Use This Document

### Important: Creating Scan Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each safety scan:

1. **Create a new timestamped copy** of this checklist:
   - Copy this entire file to `[DEV_DOCS]/safety-scans/safety-scan-YYYY-MM-DD-HHMMSS.md`
   - Use format: `safety-scan-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp dev-docs/templates/safety-scan-template.md "dev-docs/safety-scans/safety-scan-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Mark off items in the timestamped file as you complete them
   - Add notes, findings, and test results directly in the timestamped file
   - Document any issues discovered during the scan

3. **After completing the scan**:
   - Review all findings in the timestamped file
   - If new safety concerns are discovered, add them to this master template (safety-scan-template.md)
   - Keep the timestamped file as a record of that specific scan

### Critical: No Code Changes During Scan

**DO NOT edit the codebase during the safety scan.** The scan is for **analysis and identification only**.

- **Document issues, don't fix them**: When you identify a problem, document it thoroughly in the timestamped scan file with:
  - Exact location (file and line numbers)
  - Description of the issue
  - Potential impact/severity
  - Steps to reproduce (if applicable)
  - Suggested fix approach (but don't implement it yet)

- **Alert the user**: After documenting an issue, immediately alert the user about the finding so they can decide how to proceed

- **Separate phases**: 
  - **Phase 1 (Scan)**: Identify and document all issues
  - **Phase 2 (Fix)**: After scan completion, review findings with user and implement fixes separately

This approach ensures:
- The scan remains focused on discovery, not implementation
- All issues are documented before any code changes
- The user can prioritize which issues to address first
- The scan results provide a complete picture of all safety concerns

### Scan Process

1. **After any code changes**, create a new timestamped copy and run through the entire checklist
2. **For each item**, verify that the system cannot be configured to achieve the described problematic behavior
3. **Document any findings** in the timestamped scan file - If a vulnerability or issue is found, also add it to this master checklist template
4. **Test edge cases** - Don't just verify "normal" operation; test boundary conditions and malicious configurations
5. **Review related code** - When checking an item, review all related code paths, not just the obvious ones
6. **Perform code flow analysis** - Trace execution paths through the codebase to understand how data flows and where vulnerabilities might exist
7. **Consider error conditions** - Analyze how the system handles invalid input, corrupted files, missing dependencies, and other error states
8. **General security review** - In addition to the specific checklist items, perform a general security review looking for common vulnerabilities and poor security practices (see "General Security Practices Review" in Analysis Methodology section)

## Important Notes

- **THRESHOLD_WARN**: Currently set to **[WARNING_THRESHOLD]** (16 hours/day × 7 days) in `[LIB_DIR]/configure-core.sh` ([CONFIG_THRESHOLD])
- **THRESHOLD_BLOCK**: Currently set to **[MAXIMUM_THRESHOLD]** (24 hours/day × 7 days) in `[LIB_DIR]/configure-core.sh` ([CONFIG_THRESHOLD])
- If these thresholds are changed in the future, update this document accordingly
- **Window size limits**: Currently minimum [MIN_DIMENSIONS], maximum [MAX_DIMENSIONS] (see `[LIB_DIR]/config.sh`)

---

## Analysis Methodology

When performing safety scans, use a systematic approach to analyze code flow and identify vulnerabilities. This section outlines the types of analysis to perform for each checklist item.

### Code Flow Analysis

For each safety check, trace the execution path through the codebase:

1. **Entry Points**: Identify all ways a function/feature can be invoked:
   - Direct script execution
   - [INIT_SYSTEM] timer/service calls
   - User commands ([CONFIG_SCRIPT].sh, [MANAGE_SCRIPT].sh, un[INSTALL_SCRIPT].sh)
   - Library function calls from other modules

2. **Data Flow**: Follow data from input to output:
   - Where does user input enter the system?
   - How is it validated and sanitized?
   - What transformations occur?
   - Where is it used (file I/O, command execution, calculations)?

3. **Control Flow**: Understand decision points:
   - What conditions determine execution paths?
   - Are there bypass conditions that could skip validation?
   - Do error conditions lead to safe fallbacks or dangerous states?

4. **Dependencies**: Identify what the code depends on:
   - External commands ([INIT_SYSTEM], dialog tools, window managers)
   - File system state (config files, log files, directories)
   - Environment variables
   - System state (time, display availability)

5. **Exit Points**: Understand how execution ends:
   - Normal completion paths
   - Error exit paths
   - Early returns that might skip cleanup

### Input Validation and Error Handling Analysis

For each input point, analyze how the system handles:

#### Incorrectly Formatted Input

- **Config file values**: What happens with:
  - Invalid time ranges (e.g., "25-30", "-5", "abc-def", "5-3" when start > end in normal ranges)
  - Malformed window sizes (e.g., "abc", "200x", "x300", "200x300x400")
  - Invalid boolean values (e.g., "yes", "1", "on" when expecting "true"/"false")
  - Extra whitespace, special characters, newlines in unexpected places
  - Empty values vs. missing values vs. whitespace-only values

- **Command-line arguments**: How are invalid flags/options handled?
- **User prompts**: What if user enters unexpected responses in interactive mode?

#### Wrong Data Types

- **String vs. Integer**: What if a numeric field receives a string?
  - Example: `CHECK_INTERVAL=abc` or `POPUP_MIN_DISPLAY_TIME=not_a_number`
- **Boolean confusion**: What if boolean fields receive non-boolean values?
- **Array/list confusion**: What if a single value is expected but an array is provided?
- **Type coercion**: Does the code assume types without validation?

#### Corrupted Files

- **Config file corruption**: Analyze behavior when:
  - Config file is partially written (interrupted write)
  - Config file contains invalid syntax (unclosed quotes, unmatched brackets)
  - Config file has duplicate keys (which value is used?)
  - Config file has conflicting values (e.g., both `POPUP_SIZE=small` and `POPUP_SIZE=large`)
  - Config file is binary/corrupted (not valid text)
  - Config file has encoding issues (non-UTF-8 characters)

- **Missing files**: What happens when:
  - Config file doesn't exist (expected behavior: use defaults)
  - Required library files are missing
  - Log directory doesn't exist
  - [INIT_SYSTEM] service/timer files are missing

- **Permission issues**: What happens when:
  - Config file is read-only (can't write updates)
  - Config directory doesn't have write permissions
  - Script files don't have execute permissions

#### Boundary Conditions

- **Numeric boundaries**: Test values at limits:
  - Minimum values (0, 1, -1 if negative allowed)
  - Maximum values (2000 for window width, 300 for min display time)
  - Boundary values (exactly at threshold, one above, one below)
  - Very large numbers (integer overflow, if applicable)
  - Negative numbers (where not expected)

- **String boundaries**: Test with:
  - Empty strings
  - Very long strings (buffer overflow potential)
  - Strings with only whitespace
  - Strings with special characters (quotes, backslashes, newlines)

- **Time boundaries**: Test edge cases:
  - Midnight (00:00) transitions
  - Day boundaries (Sunday ↔ Saturday wrap-around)
  - Year boundaries (if date calculations are involved)
  - Invalid dates/times

#### Concurrent Operations

- **Race conditions**: Consider:
  - Config file being edited while script reads it
  - Multiple instances of [CONFIG_SCRIPT].sh running simultaneously
  - Timer firing while un[INSTALL_SCRIPT].sh is running
  - Popup display while system is shutting down

- **File locking**: Does the system handle:
  - Multiple processes accessing config file
  - Lock file creation/deletion
  - Stale lock files

#### System State Variations

- **Missing dependencies**: What if required tools are missing:
  - Dialog tools (zenity, yad, kdialog)
  - Window management tools (wmctrl, xdotool)
  - [INIT_SYSTEM] (unlikely, but consider)
  - Standard utilities (date, grep, sed, etc.)

- **Environment variations**: Test with:
  - No DISPLAY variable (headless system)
  - Invalid DISPLAY value
  - Different desktop environments
  - Different window managers
  - Wayland vs. X11

- **Resource constraints**: Consider:
  - Disk full (can't write config/log files)
  - Out of memory
  - Too many open file descriptors
  - Process limits reached

- **Signal handling**: Consider:
  - Scripts receiving SIGTERM/SIGINT during critical operations (config writes, uninstall)
  - Orphaned processes if parent is killed
  - Background processes that outlive their parent
  - Process termination failures (SIGTERM/SIGKILL both fail)

- **System state changes**: Consider:
  - Timezone changes during execution
  - System clock adjustments (forward/backward)
  - [INIT_SYSTEM] service manager becoming unavailable
  - Display server disconnection (X11/Wayland)
  - Network filesystem (NFS) becoming unavailable
  - Library files being replaced during execution

- **Atomic operations**: Consider:
  - Config file writes being interrupted (need temp file + rename)
  - State file writes being interrupted (PID files, uptime files)
  - Race conditions in file operations
  - Partial file writes causing corruption

- **Character encoding and special characters**: Consider:
  - UTF-8 encoding in config files
  - Unicode characters in config values
  - Special shell characters (quotes, backslashes, newlines)
  - Path traversal via special characters

### Testing Strategy

For each checklist item, consider:

1. **Happy path**: Does it work correctly with valid input?
2. **Invalid input**: What happens with malformed data?
3. **Missing data**: What happens with empty/null values?
4. **Boundary values**: What happens at limits?
5. **Error conditions**: What happens when dependencies fail?
6. **Malicious input**: Could input be crafted to exploit vulnerabilities?
7. **State corruption**: What happens if system state is inconsistent?

### General Security Practices Review

In addition to the specific checklist items, perform a general security review of the codebase looking for:

1. **Common vulnerabilities**:
   - Command injection (unsanitized input in command execution)
   - Path traversal (unvalidated file paths)
   - Insecure temporary files (predictable names, world-writable)
   - Race conditions (time-of-check to time-of-use issues)
   - Hardcoded secrets or credentials
   - Insecure random number generation (if applicable)

2. **Poor security practices**:
   - Missing input validation or sanitization
   - Insufficient error handling that leaks information
   - Overly permissive file permissions
   - Unnecessary privilege escalation
   - Insecure communication (if network features exist)
   - Weak cryptographic practices (if encryption is used)

3. **Code quality security concerns**:
   - Use of deprecated or insecure functions
   - Missing security headers or protections
   - Inadequate logging of security events
   - Lack of security documentation

4. **Review approach**:
   - Search for common dangerous patterns (e.g., `eval`, unquoted variables in commands, `rm -rf` with variables)
   - Review all external command invocations for proper quoting and sanitization
   - Check all file operations for path validation
   - Verify all user input is validated before use
   - Review error messages for information disclosure

Document any general security concerns found in the timestamped scan file, even if they don't fit into specific checklist categories.

### Documentation Requirements

When documenting issues in the timestamped scan file, include:

- **Location**: Exact file and line numbers
- **Input**: What input/data triggers the issue
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Impact**: Severity and potential consequences
- **Reproduction**: Steps to reproduce the issue
- **Code flow**: Trace of execution path leading to the issue
- **Suggested fix**: Approach to resolve (but don't implement during scan)

---

## Safety Scan Checklist

### 1. Total System Lock-Out Scenarios

#### 1.1 24/7 Restriction Configuration
- [ ] **Verify**: Users cannot configure restrictions that cover all 24 hours × 7 days ([MAXIMUM_THRESHOLD])
- [ ] **Check**: `check_restriction_coverage()` in `[LIB_DIR]/configure-validation.sh` correctly blocks configurations >= [MAXIMUM_THRESHOLD]
- [ ] **Test**: Attempt to configure exactly [MAXIMUM_THRESHOLD] using various range combinations (e.g., "0-12,12-0" for each day)
- [ ] **Test**: Attempt to configure > [MAXIMUM_THRESHOLD] using overlapping ranges
- [ ] **Verify**: Configuration wizard prevents saving when `check_restriction_coverage()` returns "block"
- [ ] **Check**: No code path allows bypassing the 24/7 restriction check
- [ ] **Verify**: Manual config file editing cannot create 24/7 restrictions (check if `[MAIN_SCRIPT].sh` validates on load)

#### 1.2 Near-24/7 Restrictions (High Restriction Levels)
- [ ] **Verify**: When restrictions exceed THRESHOLD_WARN ([WARNING_THRESHOLD]), users are warned but can still proceed
- [ ] **Check**: Warning dialog clearly explains the high restriction level
- [ ] **Test**: Configure exactly 6721 minutes (just above threshold) - should show warning
- [ ] **Test**: Configure exactly 10079 minutes (just below 24/7) - should show warning
- [ ] **Verify**: Warning does not prevent configuration, only informs user

#### 1.3 System Unresponsiveness During Timer Execution
- [ ] **Verify**: Warning popup cannot be configured to be so large it makes the system unresponsive
- [ ] **Check**: Window size validation in `[LIB_DIR]/config.sh` (`get_popup_dimensions()`) enforces maximum limits ([MAX_DIMENSIONS])
- [ ] **Test**: Attempt to configure window size larger than maximum (should fall back to default)
- [ ] **Verify**: Popup cannot be configured to cover entire screen in a way that blocks all interaction
- [ ] **Check**: Minimum display time (`POPUP_MIN_DISPLAY_TIME`) has a maximum limit (currently 300 seconds)
- [ ] **Test**: Configure maximum minimum display time and verify system remains responsive
- [ ] **Verify**: Multiple popups cannot spawn simultaneously (timer interval prevents this)
- [ ] **Check**: Popup display logic in `[LIB_DIR]/popup-display.sh` handles errors gracefully and doesn't hang

#### 1.4 Timer Interval Issues
- [ ] **Verify**: Timer interval (`CHECK_INTERVAL`) has reasonable minimum and maximum limits
- [ ] **Check**: Very short intervals (e.g., 1 minute) don't cause system performance issues
- [ ] **Verify**: Timer cannot be configured to run continuously or too frequently
- [ ] **Test**: Configure minimum interval and verify system remains responsive

---

### 2. Large/Full Screen Window Configuration

#### 2.1 Window Size Above THRESHOLD_WARN
- [ ] **Verify**: When restrictions exceed THRESHOLD_WARN ([WARNING_THRESHOLD]), large or full-screen windows cannot be configured
- [ ] **Check**: Window size validation occurs regardless of restriction level
- [ ] **Test**: Configure restrictions > [WARNING_THRESHOLD] AND large window size (e.g., [MAX_DIMENSIONS]) - should be prevented or warned
- [ ] **Verify**: If THRESHOLD_WARN is changed, window size restrictions are re-evaluated accordingly
- [ ] **Check**: Configuration wizard checks both restriction level AND window size together
- [ ] **Test**: Attempt to manually edit config file to set large window size with high restrictions

#### 2.2 Full Screen Window Scenarios
- [ ] **Verify**: No code path allows "fullscreen" window size option (if implemented, must be restricted)
- [ ] **Check**: Custom window sizes cannot exceed screen dimensions in a way that blocks interaction
- [ ] **Test**: Configure window size equal to or larger than common screen resolutions (e.g., 1920×1080, 3840×2160)
- [ ] **Verify**: Window positioning logic in `[LIB_DIR]/window-management.sh` handles large windows correctly
- [ ] **Check**: Large windows don't prevent access to window controls (close button, etc.)
- [ ] **Test**: Configure maximum allowed window size ([MAX_DIMENSIONS]) and verify system remains usable

#### 2.3 Window Size Validation
- [ ] **Verify**: Window size limits (200-2000 width, 100-2000 height) are enforced in all code paths
- [ ] **Check**: `get_popup_dimensions()` in `[LIB_DIR]/config.sh` validates custom sizes
- [ ] **Test**: Attempt to configure invalid sizes (too small, too large, negative, non-numeric)
- [ ] **Verify**: Invalid sizes fall back to safe defaults (medium: [DEFAULT_DIMENSIONS])
- [ ] **Check**: Configuration wizard validates window size input before saving

---

### 3. System-Breaking Behaviors

#### 3.1 Infinite Loops or Hanging Scripts
- [ ] **Verify**: No infinite loops in timer execution path (`[MAIN_SCRIPT].sh`)
- [ ] **Check**: All loops have exit conditions or timeouts
- [ ] **Verify**: Popup display functions don't hang if dialog tools fail
- [ ] **Test**: Run script when dialog tools are missing or broken
- [ ] **Check**: Error handling in `[LIB_DIR]/popup-display.sh` prevents hanging

#### 3.2 Resource Exhaustion
- [ ] **Verify**: Timer doesn't spawn excessive processes
- [ ] **Check**: Popup processes are properly cleaned up after display
- [ ] **Test**: Run system for extended period and monitor process count
- [ ] **Verify**: Log files don't grow unbounded (check rotation or size limits)
- [ ] **Check**: No memory leaks in long-running scenarios

#### 3.3 File System Issues
- [ ] **Verify**: Scripts don't create files in system directories without permission
- [ ] **Check**: Config file writes don't corrupt existing configuration
- [ ] **Test**: Run with read-only config directory (should fail gracefully)
- [ ] **Verify**: Scripts handle missing directories gracefully (create if needed, or fail with clear error)

#### 3.4 [INIT_SYSTEM] Service Issues
- [ ] **Verify**: Timer cannot be configured to run too frequently ([INIT_SYSTEM] limits)
- [ ] **Check**: Service file doesn't have dependencies that could cause boot issues
- [ ] **Test**: Disable timer and verify system still functions normally
- [ ] **Verify**: Timer failure doesn't prevent system shutdown/reboot

---

### 4. Safety and Security Concerns

#### 4.1 Path Traversal and File Access
- [ ] **Verify**: No user input is used in file paths without validation
- [ ] **Check**: Config file paths are constructed safely (no path traversal)
- [ ] **Test**: Attempt to configure paths with "../" or absolute paths outside home directory
- [ ] **Verify**: Scripts only access files in expected locations (~/.config, ~/.local)

#### 4.2 Code Injection
- [ ] **Verify**: No user input is executed as shell commands without sanitization
- [ ] **Check**: Config file parsing doesn't execute arbitrary code
- [ ] **Test**: Attempt to inject shell commands in config file values
- [ ] **Verify**: All external command execution uses proper quoting

#### 4.3 Permission Issues
- [ ] **Verify**: Scripts don't require root/sudo privileges unnecessarily
- [ ] **Check**: User services are used (not system services) to avoid privilege escalation
- [ ] **Test**: Run all scripts as non-root user
- [ ] **Verify**: No setuid/setgid bits on installed scripts

#### 4.4 Information Disclosure
- [ ] **Verify**: Log files don't contain sensitive information (passwords, tokens)
- [ ] **Check**: Error messages don't reveal system internals unnecessarily
- [ ] **Test**: Review log file contents for sensitive data

#### 4.5 General Security Practices Review
- [ ] **Verify**: No command injection vulnerabilities (all user input properly quoted/sanitized before command execution)
- [ ] **Check**: No use of dangerous functions like `eval` or unquoted variable expansion in command execution
- [ ] **Test**: Search codebase for common security anti-patterns (unquoted variables, `eval`, insecure temp files)
- [ ] **Verify**: All temporary files use secure creation methods (`mktemp` with proper templates)
- [ ] **Check**: No hardcoded secrets, passwords, or sensitive credentials in code
- [ ] **Test**: Review all external command invocations for proper input sanitization
- [ ] **Verify**: File permissions are set appropriately (no world-writable files unless necessary)
- [ ] **Check**: Error handling doesn't expose sensitive system information
- [ ] **Test**: Review code for any deprecated or insecure function usage
- [ ] **Verify**: All user-controlled input is validated before use in file operations or command execution

---

### 5. Preventing [CONFIG_SCRIPT].sh Execution

#### 5.1 Time-Based Blocking
- [ ] **Verify**: `[CONFIG_SCRIPT].sh` respects `CONFIGURE_BLOCK_ENABLED` setting
- [ ] **Check**: When enabled, `[CONFIG_SCRIPT].sh` blocks during restricted hours
- [ ] **Test**: Enable blocking and attempt to run `[CONFIG_SCRIPT].sh` during restricted hours
- [ ] **Verify**: Blocking also applies to `[MANAGE_SCRIPT].sh`
- [ ] **Check**: `check_config_lock_time()` in `[LIB_DIR]/time-validation.sh` correctly identifies restricted hours
- [ ] **Test**: Overnight ranges are handled correctly (e.g., Monday "23-6" blocks Tuesday 0-5)

#### 5.2 Lock Hours (Phase 2)
- [ ] **Verify**: `CONFIG_LOCK_HOURS` settings are respected when `CONFIGURE_BLOCK_ENABLED=true`
- [ ] **Check**: Lock hours work independently of restriction hours (OR logic)
- [ ] **Test**: Configure lock hours and verify blocking works during those hours
- [ ] **Verify**: Lock hours don't prevent configuration during non-lock hours

#### 5.3 Bypass Prevention
- [ ] **Verify**: Time check cannot be bypassed by modifying system time (check uses actual current time)
- [ ] **Check**: No command-line flags allow bypassing the time check
- [ ] **Test**: Attempt to modify system time and verify blocking still works
- [ ] **Verify**: Time check happens early in script execution (before any configuration changes)

#### 5.4 Edge Cases
- [ ] **Verify**: Script handles missing config file gracefully (should allow execution if blocking not configured)
- [ ] **Check**: Invalid time values in config don't cause script to hang
- [ ] **Test**: Configure invalid time ranges and verify script behavior

---

### 6. Preventing Service/Timer/Config File Removal

#### 6.1 Service and Timer Protection
- [ ] **Verify**: No code prevents stopping [INIT_SYSTEM] timer via `systemctl --user stop`
- [ ] **Check**: Timer can be disabled via `systemctl --user disable`
- [ ] **Test**: Verify manual removal of service/timer files is possible
- [ ] **Verify**: Scripts don't recreate removed files automatically (unless explicitly reinstalling)

#### 6.2 Config File Protection
- [ ] **Verify**: Config file locking (`CONFIG_LOCK_ENABLED`) doesn't prevent file deletion
- [ ] **Check**: Lock mechanism (if implemented) doesn't use file permissions that prevent deletion
- [ ] **Test**: Attempt to delete config file when locking is enabled
- [ ] **Verify**: Config file can be edited manually (even if [CONFIG_SCRIPT].sh is blocked)

#### 6.3 File Permissions
- [ ] **Verify**: Installed files don't have restrictive permissions that prevent deletion
- [ ] **Check**: User owns all installed files (not root)
- [ ] **Test**: Verify user can delete all installed files and directories
- [ ] **Verify**: No files are marked as immutable or protected

---

### 7. Preventing Config File Editing

#### 7.1 Time-Based Restrictions
- [ ] **Verify**: Config file editing is not blocked by time-based restrictions
- [ ] **Check**: `CONFIGURE_BLOCK_ENABLED` only blocks script execution, not file editing
- [ ] **Test**: Edit config file manually during restricted hours (should be possible)
- [ ] **Verify**: Manual edits are respected by `[MAIN_SCRIPT].sh` on next execution

#### 7.2 File Locking
- [ ] **Verify**: If config file locking is implemented, it doesn't prevent manual editing
- [ ] **Check**: Lock mechanism (if any) can be bypassed by manual editing
- [ ] **Test**: Attempt to edit locked config file manually
- [ ] **Verify**: Lock doesn't use file system locks that prevent editing

#### 7.3 Validation on Load
- [ ] **Verify**: `[MAIN_SCRIPT].sh` validates config file on load
- [ ] **Check**: Invalid config values don't cause script to hang or fail silently
- [ ] **Test**: Manually edit config with invalid values and verify graceful handling
- [ ] **Verify**: Script falls back to defaults for invalid values

---

### 8. Preventing un[INSTALL_SCRIPT].sh Execution

#### 8.1 Uninstall Protection Modes
- [ ] **Verify**: `UNINSTALL_PROTECTION_MODE` setting is respected
- [ ] **Check**: "none" mode allows uninstall without restrictions
- [ ] **Test**: Enable "difficult" mode and attempt uninstall during restricted hours
- [ ] **Verify**: Verification process (confirmation phrase + algebra) works correctly
- [ ] **Check**: Verification can be completed (not impossible to pass)

#### 8.2 Time-Based Blocking
- [ ] **Verify**: Uninstall protection checks current time correctly
- [ ] **Check**: `check_uninstall_protection_time()` in `[LIB_DIR]/uninstall-verification.sh` works correctly
- [ ] **Test**: Attempt uninstall during restricted hours with protection enabled
- [ ] **Verify**: Overnight ranges are handled correctly

#### 8.3 Bypass Prevention
- [ ] **Verify**: No command-line flags allow bypassing uninstall protection (unless explicitly documented)
- [ ] **Check**: Verification cannot be skipped by modifying script
- [ ] **Test**: Attempt various methods to bypass verification
- [ ] **Verify**: Manual uninstallation (via `manual-uninstall-guide.sh`) is always available

#### 8.4 Edge Cases
- [ ] **Verify**: Uninstall works when config file is missing or corrupted
- [ ] **Check**: Script handles missing verification module gracefully
- [ ] **Test**: Remove `[LIB_DIR]/uninstall-verification.sh` and verify uninstall still works
- [ ] **Verify**: Uninstall doesn't require config file to be valid

---

### 9. Preventing Manual Uninstall Instructions

#### 9.1 Script Availability
- [ ] **Verify**: `manual-uninstall-guide.sh` is always accessible
- [ ] **Check**: Script doesn't check time or restrictions before showing instructions
- [ ] **Test**: Run guide during restricted hours (should work)
- [ ] **Verify**: Guide works even if other scripts are blocked

#### 9.2 Script Execution
- [ ] **Verify**: Guide script doesn't require any special permissions
- [ ] **Check**: Script can be run from any location (not just install directory)
- [ ] **Test**: Copy script to different location and verify it works
- [ ] **Verify**: Script doesn't depend on other system components

#### 9.3 Instructions Completeness
- [ ] **Verify**: Instructions are complete and accurate
- [ ] **Check**: All file paths in instructions are correct
- [ ] **Test**: Follow instructions manually and verify they work
- [ ] **Verify**: Instructions don't require root/sudo (user services only)

#### 9.4 Display Methods
- [ ] **Verify**: Guide works in both GUI and text modes
- [ ] **Check**: Guide doesn't require dialog tools (has text fallback)
- [ ] **Test**: Run guide without GUI (should show text instructions)
- [ ] **Verify**: Instructions are readable in both modes

---

### 10. Additional Safety Checks

#### 10.1 Error Handling
- [ ] **Verify**: All scripts handle errors gracefully (don't crash or hang)
- [ ] **Check**: Missing dependencies are detected and reported clearly
- [ ] **Test**: Run scripts with missing required tools (dialog tools, [INIT_SYSTEM], etc.)
- [ ] **Verify**: Scripts exit with appropriate error codes

#### 10.2 Logging
- [ ] **Verify**: Log files don't grow unbounded
- [ ] **Check**: Log rotation or size limits are implemented
- [ ] **Test**: Generate many log entries and verify file size
- [ ] **Verify**: Logs don't contain sensitive information

#### 10.3 Configuration Validation
- [ ] **Verify**: All config values are validated before use
- [ ] **Check**: Invalid values fall back to safe defaults
- [ ] **Test**: Configure invalid values and verify system behavior
- [ ] **Verify**: Validation happens early (before any actions are taken)

#### 10.4 Backward Compatibility
- [ ] **Verify**: Old config files work with new code versions
- [ ] **Check**: Missing config options use defaults
- [ ] **Test**: Use config file from older version with new code
- [ ] **Verify**: Upgrades don't break existing configurations

---

### 11. File Safety and Unintended File Operations

#### 11.1 Project Directory Protection
- [ ] **Verify**: `un[INSTALL_SCRIPT].sh` never removes files from the project directory (where scripts are developed)
- [ ] **Check**: `un[INSTALL_SCRIPT].sh` uses hardcoded installation paths (`~/[INSTALL_DIR]`, `~/[LIB_INSTALL_DIR]`, `~/.config/[INIT_SYSTEM]/user`, `~/[CONFIG_DIR]`) and never references `SCRIPT_DIR` for deletion
- [ ] **Test**: Run `un[INSTALL_SCRIPT].sh` from the project directory and verify project files (e.g., `[LIB_DIR]/`, `[CONFIG_SCRIPT].sh`, `tests/`, `[DEV_DOCS]/`) remain untouched
- [ ] **Verify**: `SOURCE_LIB_DIR` (used for sourcing) is separate from `LIB_DIR` (used for deletion) in `un[INSTALL_SCRIPT].sh`
- [ ] **Check**: No code path in `un[INSTALL_SCRIPT].sh` uses `rm -rf` with variables that could resolve to project directory
- [ ] **Test**: Create a test project directory structure and run uninstall from it - verify no project files are deleted
- [ ] **Verify**: Project directory files ([CONFIG_SCRIPT].sh, [INSTALL_SCRIPT].sh, [MANAGE_SCRIPT].sh, [LIB_DIR]/, tests/, dev-docs/, etc.) are never referenced in deletion operations

#### 11.2 Unintended File Deletion Prevention
- [ ] **Verify**: `un[INSTALL_SCRIPT].sh` only removes specifically named files, not wildcard patterns that could match unintended files
- [ ] **Check**: All `rm` commands in `un[INSTALL_SCRIPT].sh` use explicit file paths (e.g., `rm -f "$INSTALL_DIR/[MAIN_SCRIPT].sh"`), not wildcards (e.g., `rm -f "$INSTALL_DIR/*"`)
- [ ] **Test**: Create files with similar names in installation directories (e.g., `[MAIN_SCRIPT].sh.backup`, `[PROJECT_NAME]-other.sh`) and verify they are not deleted
- [ ] **Verify**: Directory removal (`rmdir`) only occurs after explicit checks that directory is empty
- [ ] **Check**: `rm -rf "$LIB_DIR"` only removes the specific project library directory, not parent directories
- [ ] **Test**: Verify `LIB_DIR` is always an absolute path and never contains `..` or resolves outside intended location
- [ ] **Verify**: No script uses `rm -rf` with user-provided input or config file values

#### 11.3 Path Validation and Traversal Prevention
- [ ] **Verify**: All file paths used in deletion operations are constructed from hardcoded base paths, not from user input
- [ ] **Check**: No script constructs file paths using values from config files for deletion operations
- [ ] **Test**: Attempt to configure paths with `../` or absolute paths outside home directory - verify they are not used for file operations
- [ ] **Verify**: All directory variables (`INSTALL_DIR`, `LIB_DIR`, `CONFIG_DIR`, `SYSTEMD_USER_DIR`) are set to absolute paths within user's home directory
- [ ] **Check**: Paths are validated to ensure they don't contain path traversal sequences (`..`, symlinks to outside locations)
- [ ] **Test**: Create symlinks in installation directories pointing outside and verify uninstall doesn't follow them dangerously
- [ ] **Verify**: Scripts use `$(cd "$(dirname ...)" && pwd)` or similar to resolve absolute paths safely

#### 11.4 Files Outside Installation Locations
- [ ] **Verify**: No script modifies, deletes, or renames files outside the intended installation locations
- [ ] **Check**: Installation locations are limited to:
  - `~/[INSTALL_DIR]/` (for executable scripts)
  - `~/[LIB_INSTALL_DIR]/` (for library modules)
  - `~/.config/[INIT_SYSTEM]/user/` (for [INIT_SYSTEM] service/timer files)
  - `~/[CONFIG_DIR]/` (for configuration and logs)
- [ ] **Test**: Create test files in other locations (e.g., `~/.bashrc`, `~/.profile`, `/tmp/test-file`) and verify they remain untouched
- [ ] **Verify**: No script attempts to modify system-wide files (e.g., `/etc/`, `/usr/`, `/opt/`)
- [ ] **Check**: Scripts don't use `sudo` or require root privileges for file operations
- [ ] **Test**: Run all scripts as non-root user and verify no permission errors occur for intended operations

#### 11.5 Other Scripts File Safety
- [ ] **Verify**: `[INSTALL_SCRIPT].sh` only creates/copies files to intended installation locations
- [ ] **Check**: `[INSTALL_SCRIPT].sh` doesn't remove or overwrite files outside installation directories
- [ ] **Test**: Run `[INSTALL_SCRIPT].sh` and verify it doesn't modify project directory files
- [ ] **Verify**: `[CONFIG_SCRIPT].sh` only modifies the config file in `~/[CONFIG_DIR]/config/[CONFIG_FILE]` (ensure path handling works for different config locations)
- [ ] **Check**: `[CONFIG_SCRIPT].sh` doesn't delete or rename any files
- [ ] **Test**: Run `[CONFIG_SCRIPT].sh` and verify no files are deleted or renamed
- [ ] **Verify**: `[MANAGE_SCRIPT].sh` doesn't perform any file deletion operations
- [ ] **Check**: Library scripts (in `[LIB_DIR]/`) only perform file operations on config/log files in expected locations
- [ ] **Test**: Review all scripts for any `rm`, `rmdir`, `unlink`, or file deletion operations and verify they are safe

#### 11.6 Backup and Temporary File Safety
- [ ] **Verify**: Backup files created by scripts are stored in safe locations (e.g., `backups/` subdirectory)
- [ ] **Check**: Temporary files are created with safe names and cleaned up properly
- [ ] **Test**: Verify temporary files don't overwrite existing user files
- [ ] **Verify**: Backup file operations don't accidentally delete original files
- [ ] **Check**: Scripts use `mktemp` or similar safe methods for temporary file creation
- [ ] **Test**: Run scripts multiple times and verify temporary files don't accumulate or conflict

#### 11.7 Directory Structure Safety
- [ ] **Verify**: Scripts don't remove parent directories when removing subdirectories
- [ ] **Check**: `rmdir` operations only remove empty directories that were created by the installation
- [ ] **Test**: Create additional files in installation directories and verify uninstall doesn't remove non-empty parent directories
- [ ] **Verify**: Directory removal checks (e.g., `[ -z "$(ls -A "$CONFIG_DIR" 2>/dev/null)" ]`) work correctly before `rmdir`
- [ ] **Check**: No script uses `rm -rf` on directory paths that could resolve to user's home directory or system directories

#### 11.8 Code Review for File Operations
- [ ] **Verify**: All file deletion operations are explicitly listed and documented
- [ ] **Check**: No hidden or indirect file deletion (e.g., through external command execution)
- [ ] **Test**: Search codebase for all `rm`, `rmdir`, `unlink` commands and verify each is safe
- [ ] **Verify**: File operations use absolute paths or properly validated relative paths
- [ ] **Check**: No file operations use unvalidated variables that could contain user input
- [ ] **Test**: Review error handling to ensure failed file operations don't leave system in inconsistent state

---

### 12. Signal Handling and Process Management

#### 12.1 Signal Handling During Critical Operations
- [ ] **Verify**: Scripts handle SIGTERM, SIGINT, and SIGHUP gracefully during critical operations
- [ ] **Check**: Config file writes use atomic operations (temp file + rename) to prevent corruption if interrupted
- [ ] **Test**: Send SIGTERM/SIGINT to scripts during config file write operations and verify no corruption
- [ ] **Verify**: Uninstall script handles signals gracefully and doesn't leave partial uninstallation state
- [ ] **Check**: Timer execution (`[MAIN_SCRIPT].sh`) handles signals without leaving orphaned processes
- [ ] **Test**: Send signals to popup display processes and verify cleanup occurs properly
- [ ] **Verify**: No critical operations are performed without signal handlers or atomic file operations

#### 12.2 Orphaned Process Prevention
- [ ] **Verify**: Background processes (popup timers, window management) check if parent process is still alive
- [ ] **Check**: PID file cleanup occurs even if parent process is killed unexpectedly
- [ ] **Test**: Kill parent process during popup display and verify child processes exit or clean up
- [ ] **Verify**: [INIT_SYSTEM] service properly manages process lifecycle (no orphaned processes after service stop)
- [ ] **Check**: Background helper processes (auto-close timers, window keep-on-top) exit when popup closes

#### 12.3 Process Termination Safety
- [ ] **Verify**: Popup termination (SIGTERM/SIGKILL) doesn't affect other system processes
- [ ] **Check**: Process termination uses correct PID (not PID reuse vulnerabilities)
- [ ] **Test**: Verify PID file validation prevents killing wrong processes if PID is reused
- [ ] **Verify**: Process termination errors are handled gracefully (don't crash script if kill fails)

---

### 13. System State and Environment Safety

#### 13.1 Timezone and Clock Changes
- [ ] **Verify**: System handles timezone changes gracefully (restrictions adapt to new timezone)
- [ ] **Check**: Clock adjustments (forward/backward) don't cause lock-out scenarios
- [ ] **Test**: Change system timezone during restricted hours and verify behavior
- [ ] **Verify**: System clock changes (manual or NTP) don't bypass time-based restrictions
- [ ] **Check**: Time calculations use current system time (not cached values) to handle clock changes
- [ ] **Test**: Set system clock backward during restricted hours and verify restrictions still apply

#### 13.2 [INIT_SYSTEM] Service Manager Availability
- [ ] **Verify**: Scripts handle case where [INIT_SYSTEM] user service manager is not running
- [ ] **Check**: Timer/service operations fail gracefully if [INIT_SYSTEM] is unavailable
- [ ] **Test**: Stop [INIT_SYSTEM] user service manager and verify scripts handle errors appropriately
- [ ] **Verify**: No scripts assume [INIT_SYSTEM] is always available without checking
- [ ] **Check**: Error messages clearly indicate when [INIT_SYSTEM] is required but unavailable

#### 13.3 Display Server Disconnection
- [ ] **Verify**: Popup display handles X11/Wayland session disconnection gracefully
- [ ] **Check**: Scripts don't hang if DISPLAY becomes invalid during execution
- [ ] **Test**: Disconnect X11 session during popup display and verify script handles error
- [ ] **Verify**: Window management operations fail gracefully if display server unavailable
- [ ] **Check**: No infinite retries or hanging when display server is unavailable

#### 13.4 Network Filesystem Issues
- [ ] **Verify**: Scripts handle case where home directory is on NFS/network mount that becomes unavailable
- [ ] **Check**: Config file operations fail gracefully if filesystem becomes read-only or unavailable
- [ ] **Test**: Simulate network filesystem disconnection and verify error handling
- [ ] **Verify**: No scripts hang waiting for network filesystem to become available
- [ ] **Check**: Error messages indicate filesystem issues clearly

#### 13.5 Environment Variable Safety
- [ ] **Verify**: Scripts don't trust environment variables for security-sensitive operations
- [ ] **Check**: PATH variable is not used for locating critical executables (use full paths or `command -v`)
- [ ] **Test**: Set malicious PATH and verify scripts don't execute wrong binaries
- [ ] **Verify**: HOME variable is validated before use (not used directly for file operations without validation)
- [ ] **Check**: No environment variables are used to bypass security checks
- [ ] **Test**: Set malicious environment variables and verify they don't affect script behavior

---

### 14. Atomic Operations and Data Integrity

#### 14.1 Config File Write Atomicity
- [ ] **Verify**: All config file writes use atomic operations (temp file + rename pattern)
- [ ] **Check**: Config file writes don't leave partial/corrupted files if interrupted
- [ ] **Test**: Interrupt config file write (kill process, power loss simulation) and verify no corruption
- [ ] **Verify**: Backup operations use atomic writes to prevent backup corruption
- [ ] **Check**: Snapshot file creation (for config locking) uses atomic operations

#### 14.2 State File Atomicity
- [ ] **Verify**: PID file writes use atomic operations (temp file + rename)
- [ ] **Check**: Uptime state file writes are atomic to prevent corruption
- [ ] **Test**: Interrupt state file writes and verify no corruption or inconsistent state
- [ ] **Verify**: Lock marker file writes use atomic operations
- [ ] **Check**: All state files use safe write patterns to prevent race conditions

#### 14.3 Library File Replacement During Execution
- [ ] **Verify**: Scripts handle case where library files are replaced during execution
- [ ] **Check**: Library files are sourced once at startup (not re-sourced during execution)
- [ ] **Test**: Replace library file while script is running and verify behavior
- [ ] **Verify**: No code re-reads library files during execution (uses already-sourced functions)
- [ ] **Check**: Library file replacement doesn't cause script to use inconsistent code versions

---

### 15. Unicode and Special Character Handling

#### 15.1 Config File Encoding
- [ ] **Verify**: Config file parsing handles UTF-8 encoding correctly
- [ ] **Check**: Non-ASCII characters in config values don't break parsing
- [ ] **Test**: Configure values with Unicode characters (emojis, accented characters, etc.)
- [ ] **Verify**: Config file writes preserve UTF-8 encoding
- [ ] **Check**: Error messages handle non-ASCII characters in config values

#### 15.2 Special Character Injection
- [ ] **Verify**: Config file parsing handles special shell characters safely (quotes, backslashes, newlines)
- [ ] **Check**: Special characters in config values don't cause command injection
- [ ] **Test**: Configure values with quotes, backslashes, newlines, and verify safe handling
- [ ] **Verify**: File paths with special characters are handled safely
- [ ] **Check**: Log messages with special characters don't break logging

---

## Adding New Safety Checks

If during a safety scan (in a timestamped scan file) you identify a new potential issue or vulnerability that is not covered in this master checklist, **add it to this master template** (safety-scan-template.md):

1. **Identify the issue**: Clearly describe the potential problem (document in timestamped scan file first)
2. **Categorize it**: Add it to the appropriate section in this master template, or create a new section if needed
3. **Create check items**: Add specific checkboxes for verifying the issue doesn't exist
4. **Document the fix**: If a fix is implemented, update the master checklist to reflect the verification steps

**Note**: The timestamped scan file should document the discovery and investigation of the new issue. The master template (this file) should be updated to include the new check for future scans.

### Example: Adding a New Check

If you discover that a new feature could allow X, add it like this:

```markdown
#### X.Y New Issue Category
- [ ] **Verify**: [Description of what to verify]
- [ ] **Check**: [Specific code/behavior to check]
- [ ] **Test**: [Specific test case to run]
- [ ] **Verify**: [Additional verification step]
```

---

## Review Process

After completing a safety scan (in your timestamped scan file):

1. **Document findings**: Note any issues found and their severity in the timestamped scan file
2. **Prioritize fixes**: Address critical issues (lock-out scenarios) immediately
3. **Update master checklist**: If new safety concerns are discovered, add them to this master template (safety-scan-template.md)
4. **Test fixes**: Verify that fixes don't introduce new issues
5. **Re-scan**: After fixes, create a new timestamped scan file and run the scan again to verify issues are resolved

### Scan File Organization

- **Master template**: `[DEV_DOCS]/templates/safety-scan-template.md` (this file) - Never modify checkboxes, only add new checks
- **Scan records**: `[DEV_DOCS]/safety-scans/safety-scan-YYYY-MM-DD-HHMMSS.md` - Timestamped copies with completed scans
- Each timestamped scan file serves as a historical record of that specific safety audit

---

## Related Documentation

- `[LIB_DIR]/configure-validation.sh` - Restriction coverage validation
- `[LIB_DIR]/config.sh` - Window size validation
- `[LIB_DIR]/time-validation.sh` - Time-based blocking logic
- `[LIB_DIR]/uninstall-verification.sh` - Uninstall protection
- `[DEV_DOCS]/enhancements/[ENHANCEMENT_NAME]-prevent-configure-execution.md` - Configure blocking
- `[DEV_DOCS]/enhancements/[ENHANCEMENT_NAME]-prevent-24-7-restriction-configuration.md` - 24/7 prevention
- `[DEV_DOCS]/enhancements/[ENHANCEMENT_NAME]-prevent-uninstall-during-restricted-hours.md` - Uninstall protection

---

## Last Updated

- **Date**: [CURRENT_DATE]
- **Version**: Current
- **Changes**: 
  - Added Section 11 "File Safety and Unintended File Operations" to verify that scripts only affect intended files and never remove or modify files from the project directory or unrelated files outside installation locations
  - Added "General Security Practices Review" subsection to Analysis Methodology section
  - Added Section 4.5 "General Security Practices Review" checklist items for common security vulnerabilities and poor security practices
  - Added Section 12 "Signal Handling and Process Management" to verify graceful signal handling, orphaned process prevention, and safe process termination
  - Added Section 13 "System State and Environment Safety" to verify handling of timezone changes, [INIT_SYSTEM] availability, display server disconnection, network filesystem issues, and environment variable safety
  - Added Section 14 "Atomic Operations and Data Integrity" to verify atomic file writes for config files, state files, and handling of library file replacement during execution
  - Added Section 15 "Unicode and Special Character Handling" to verify proper handling of UTF-8 encoding, Unicode characters, and special shell characters in config values
  - Enhanced Analysis Methodology section with additional considerations for signal handling, system state changes, atomic operations, and character encoding
