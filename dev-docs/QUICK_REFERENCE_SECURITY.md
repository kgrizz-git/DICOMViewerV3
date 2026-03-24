"""
Quick Reference: Debug Flags & Log Sanitization

Keep this file handy while developing.
"""

# ============════════════════════════════════════════════════════════════════════
# DEBUG FLAGS - Temporary diagnostic switches
# ============════════════════════════════════════════════════════════════════════

# Location: src/utils/debug_flags.py
# Current flags: DEBUG_LAYOUT, DEBUG_LOADING, DEBUG_CROSSHAIR, DEBUG_NAV,
#                DEBUG_WL, DEBUG_MAGNIFIER, DEBUG_MPR, DEBUG_MEASUREMENT_DRAG,
#                DEBUG_MEASUREMENT_SERIES, DEBUG_PROJECTION, DEBUG_OFFSET,
#                DEBUG_SPATIAL_ALIGNMENT, DEBUG_DIAG, DEBUG_WIDGET_PAN,
#                DEBUG_RESIZE, DEBUG_ANNOTATION, DEBUG_AGENT_LOG, DEBUG_FONT_VARIANT

from src.utils.debug_flags import DEBUG_LAYOUT, DEBUG_LOADING, DEBUG_ANNOTATION

# Usage: Only in development - wrap debug output behind a flag
if DEBUG_LAYOUT:
    print(f"[DEBUG-LAYOUT] Viewport resized to {width}x{height}")

# ⚠️  ALWAYS reset to False before `git commit`


# ============════════════════════════════════════════════════════════════════════
# LOG SANITIZATION - Remove PII before logging
# ============════════════════════════════════════════════════════════════════════

from src.utils.log_sanitizer import (
    sanitize_message,
    sanitize_exception,
    validate_no_pii_in_output,
    SafeExceptionLogger,
)

# --- Case 1: Sanitizing a message ---
msg = f"Error for patient {patient_name}: {error_detail}"
safe = sanitize_message(msg)
logger.error(safe)
# Output: "Error for patient [REDACTED]: [REDACTED]"

# --- Case 2: Sanitizing an exception ---
try:
    risky_operation()
except Exception as e:
    safe_trace = sanitize_exception(traceback.format_exc())
    logger.debug(safe_trace)  # Only in debug/development mode
    logger.error("Operation failed (see debug log for details)")

# --- Case 3: Validating before logging ---
msg = f"Patient {patient_id} processed"
is_safe, issues = validate_no_pii_in_output(msg)
if is_safe:
    logger.info(msg)
else:
    logger.warning(f"Unsafe message detected: {issues}")

# --- Case 4: Safe exception logger (recommended) ---
safe_logger = SafeExceptionLogger(logger, debug_enabled=DEBUG_LOADING)

try:
    load_dicom(file_path)
except Exception as e:
    safe_logger.log_exception(e, context="DICOM file loading")
    # Automatically sanitizes and respects debug flag


# ============════════════════════════════════════════════════════════════════════
# PROTECTED PATIENT FIELDS (Never log these directly)
# ============════════════════════════════════════════════════════════════════════

# PatientName,          # Surname^GivenName^MiddleName^Prefix^Suffix
# PatientID,            # Medical Record Number (MRN)
# PatientBirthDate,     # YYYYMMDD format
# PatientAge,           # Age of patient
# PatientSex,           # M / F / O
# PatientAddress,       # Street^City^State^ZipCode^Country
# PatientTelephoneNumbers,
# ResponsiblePerson,
# EmergencyContactTelephoneNumber,
# ...and others in DICOM standard


# ============════════════════════════════════════════════════════════════════════
# GIT HOOKS - Automatic validation on commit/push
# ============════════════════════════════════════════════════════════════════════

# Installed via: bash scripts/setup-hooks.sh

# Hook 1: pre-commit (runs on `git commit`)
#   ✓ Checks all DEBUG_* flags are False
#   ✓ Blocks commit if any flag is True
#   ✓ Bypass: git commit --no-verify (emergency only)

# Hook 2: pre-push (runs on `git push`)
#   ✓ Strict check when pushing to main/develop/tags
#   ✓ Prevents release builds with debugging enabled
#   ✓ Bypass: git push --no-verify (emergency only)

# Manual setup (if hooks.sh doesn't work):
# $ cp .githooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# $ cp .githooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push


# ============════════════════════════════════════════════════════════════════════
# GITHUB SECURITY WORKFLOWS
# ============════════════════════════════════════════════════════════════════════

# Location: .github/workflows/

# Enabled workflows / scanning:
# 1. CodeQL             - Python SAST via GitHub default code scanning (not codeql.yml; custom workflow conflicts with default)
# 2. semgrep.yml        - Semgrep SAST (rule-based security)
# 3. grype.yml          - Grype (CVE scanning)
# 4. security-checks.yml - Debug flags + secrets validation
# 5. dependabot.yml     - Dependency updates: pip + GitHub Actions (add Docker only with a Dockerfile)

# Results visible at: GitHub → Security → Code scanning


# ============════════════════════════════════════════════════════════════════════
# COMMON PATTERNS
# ============════════════════════════════════════════════════════════════════════

# --- Pattern 1: Safe exception in file operations ---
try:
    dataset = dcmread(file_path)
except Exception as e:
    safe_msg = sanitize_message(str(e))
    logger.error(f"Failed to load file: {safe_msg}")
    return None

# --- Pattern 2: Debug-gated verbose output ---
if DEBUG_LOADING:
    logger.debug(f"Loaded {len(datasets)} datasets from {folder}")
else:
    logger.info(f"Loaded {len(datasets)} datasets")

# --- Pattern 3: Safe error dialog ---
QMessageBox.warning(
    self,
    "Error",
    sanitize_message(f"Could not process file: {error}")
)

# --- Pattern 4: Validation before commit logging ---
is_safe, issues = validate_no_pii_in_output(log_msg)
if not is_safe:
    logger.warning(f"Rejecting log message due to PII: {issues}")
    return
logger.info(log_msg)


# ============════════════════════════════════════════════════════════════════════
# CHECKLIST: Before each commit
# ============════════════════════════════════════════════════════════════════════

# [ ] All DEBUG_* flags set to False in src/utils/debug_flags.py
# [ ] No traceback.print_exc() left in code (use sanitized logging)
# [ ] Patient field names wrapped in sanitize_message() or not logged
# [ ] File paths only logged in debug mode or sanitized
# [ ] Error dialogs use generic messages (not raw exception text)
# [ ] New log calls checked: `python3 -c "from src.utils.log_sanitizer import ..."`
# [ ] Pre-commit hook passes: `git commit` should work without --no-verify


# ============════════════════════════════════════════════════════════════════════
# USEFUL COMMANDS
# ============════════════════════════════════════════════════════════════════════

# Setup hooks:
#   bash scripts/setup-hooks.sh

# Test sanitizer:
#   python3 -c "from src.utils.log_sanitizer import sanitize_message; \
#   print(sanitize_message('Patient John Doe (ID: MRN123)'))"

# Check debug flags:
#   grep "DEBUG_.*= True" src/utils/debug_flags.py

# View GitHub Actions results:
#   https://github.com/your-org/DICOMViewerV3/actions

# Bypass hook (emergency):
#   git commit --no-verify
#   git push --no-verify


# ============════════════════════════════════════════════════════════════════════
# ADDITIONAL RESOURCES
# ============════════════════════════════════════════════════════════════════════

# Full guide: dev-docs/SECURITY_HARDENING_GUIDE.md
# Debug flags: src/utils/debug_flags.py
# Sanitizer module: src/utils/log_sanitizer.py
# Safety scan: dev-docs/safety-scans/safety-scan-2026-03-21-234150.md
