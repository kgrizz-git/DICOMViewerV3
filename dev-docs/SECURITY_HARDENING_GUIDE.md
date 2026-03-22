# Security Hardening Guide: Debug Flags, PII Protection, and Automation

This guide covers the new security features implemented to address safety scan findings:
1. **Debug flag hooks** - Prevent builds with debug enabled
2. **Log sanitization** - Redact patient PII from logs
3. **Security automation** - GitHub Actions for continuous scanning
4. **Best practices** - Exception handling and safe logging

---

## Table of Contents

- [Overview](#overview)
- [Part 1: Debug Flag Protection](#part-1-debug-flag-protection)
- [Part 2: PII Sanitization](#part-2-pii-sanitization)
- [Part 3: GitHub Security Automation](#part-3-github-security-automation)
- [Part 4: Best Practices & Examples](#part-4-best-practices--examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

**What changed:**
- New git hooks (`pre-commit`, `pre-push`) that prevent debug flags from being committed/pushed
- New sanitization utility (`src/utils/log_sanitizer.py`) to redact sensitive data from logs
- New GitHub Actions workflows for automated security scanning
- Enhanced `debug_flags.py` with additional flag definitions

**Why it matters:**
- Medical DICOM data contains patient PII (name, ID, DOB, address)
- Debug code paths may leak this information to logs/stdout
- Accidental builds with debug enabled can expose sensitive paths and error details
- Continuous security scanning catches vulnerabilities early

---

## Part 1: Debug Flag Protection

### What are debug flags?

Located in `src/utils/debug_flags.py`, debug flags are boolean toggles for optional diagnostic output:

```python
DEBUG_LAYOUT: bool = False          # Layout tracing
DEBUG_LOADING: bool = False         # File loading tracing  
DEBUG_AGENT_LOG: bool = False       # Diagnostic logging to file
DEBUG_ANNOTATION: bool = False      # Annotation debugging
# ... etc (currently 19 flags)
```

**Default behavior:**
- All flags default to `False` (no debug output in production)
- Set to `True` temporarily while debugging
- **Must be reset to `False` before commit**

### Git Hooks Overview

Two hooks prevent debug flags from entering the repository:

#### **pre-commit hook** (runs on `git commit`)

**What it does:**
- Checks `src/utils/debug_flags.py` for any `DEBUG_* = True`
- Blocks commit if debugging is left on
- Runs automatically on every commit

**Example:**
```bash
$ git commit -m "Fix layout bug"
[pre-commit] Checking for debug flags set to True...
[ERROR] Debug flag is set to True: DEBUG_LAYOUT
  To proceed, set DEBUG_LAYOUT = False in src/utils/debug_flags.py

# Fix the flag, then try again:
$ vim src/utils/debug_flags.py  # Change DEBUG_LAYOUT = False
$ git commit -m "Fix layout bug"
[OK] All debug flags are False.
```

#### **pre-push hook** (runs on `git push`)

**What it does:**
- Strict validation when pushing to `main`, `develop`, or version tags
- Blocks pushes with any `DEBUG_* = True`
- Prevents release builds with debugging enabled

**Example:**
```bash
$ git push origin main
[pre-push] Strict validation for protected branch: refs/heads/main
[ERROR] Cannot push to protected branch with debug flags enabled:
  - DEBUG_MEASUREMENT_DRAG
  - DEBUG_SPATIAL_ALIGNMENT

# Fix flags and try again
$ git push origin main
[OK] No debug flags detected; push is allowed.
```

### Setup (First Time)

1. **Run the setup script:**
   ```bash
   bash scripts/setup-hooks.sh
   ```
   
   This:
   - Copies git hooks to `.git/hooks/`
   - Makes them executable
   - Displays confirmation messages

2. **Verify:**
   ```bash
   ls -la .git/hooks/pre-*
   ```
   
   You should see `pre-commit` and `pre-push` with execute permissions.

### Bypassing hooks (emergency only)

If you **absolutely must** commit with debug flags:

```bash
git commit --no-verify -m "Emergency fix"  # Skips pre-commit
git push --no-verify                       # Skips pre-push
```

⚠️ **Only use in genuine emergencies** - the hooks exist for a reason.

---

## Part 2: PII Sanitization

### Protected Patient Data

The sanitizer redacts these DICOM fields and patterns:

**Protected DICOM fields:**
```
PatientName, PatientID, PatientBirthDate, PatientAge, PatientSex,
PatientAddress, PatientTelephoneNumbers, PatientComments,
ResponsiblePerson, ResponsiblePersonRole, EmergencyContactTelephoneNumber
```

**Other patterns:**
- Dates that appear near date-related keywords (DOB, birthdate)
- File paths with user identifiers
- MRN and patient ID patterns

### Using log_sanitizer

#### **Basic Sanitization**

```python
from src.utils.log_sanitizer import sanitize_message

# Unsafe message
msg = f"Error loading patient {patient_name} (ID: {patient_id}): {error}"

# Safe message
safe_msg = sanitize_message(msg)
print(safe_msg)
# Output: "Error loading patient [REDACTED] (ID: [REDACTED]): File not found"
```

#### **Exception Sanitization**

```python
from src.utils.log_sanitizer import sanitize_exception
import traceback

try:
    process_dicom(dataset)
except Exception as e:
    # Unsafe: prints full paths and patient data
    # traceback.print_exc()
    
    # Safe: redacts sensitive info
    safe_trace = sanitize_exception(traceback.format_exc())
    logger.error(f"Error: {e}\n{safe_trace}")
```

#### **Safe Exception Handler Class**

```python
from src.utils.log_sanitizer import SafeExceptionLogger
import logging

logger = logging.getLogger(__name__)
safe_logger = SafeExceptionLogger(logger, debug_enabled=DEBUG_MODE)

try:
    risky_operation()
except Exception as e:
    # Automatically sanitizes before logging
    safe_logger.log_exception(e, context="patient data loading")
    # Output: Error (patient data loading): ValueError: Invalid DICOM file
    # (Full traceback logged only if DEBUG_MODE=True)
```

#### **Validation Before Logging**

```python
from src.utils.log_sanitizer import validate_no_pii_in_output

msg = f"Processing study {study_date} for patient {patient_id}"
is_safe, issues = validate_no_pii_in_output(msg)

if not is_safe:
    print(f"PII detected: {issues}")  # ['Potential patient ID or MRN']
    # Don't log this message!
else:
    logger.info(msg)
```

### Integration Examples

#### **Example 1: Replacing raw traceback printing**

**Before (UNSAFE):**
```python
# src/core/dicom_loader.py
except Exception as e:
    error_msg = str(e)
    self.failed_files.append((file_path, error_msg))
    traceback.print_exc()  # ❌ Prints full path + patient data
```

**After (SAFE):**
```python
from src.utils.log_sanitizer import sanitize_exception, sanitize_message
import traceback

except Exception as e:
    error_msg = sanitize_message(str(e))
    self.failed_files.append((file_path, error_msg))
    if DEBUG_MODE:  # Only in development
        safe_trace = sanitize_exception(traceback.format_exc())
        logger.debug(safe_trace)
```

#### **Example 2: Safe error dialog**

**Before (UNSAFE):**
```python
QMessageBox.critical(
    self, 
    "Error", 
    f"Failed to load {file_path}: {str(exception)}"
)
```

**After (SAFE):**
```python
from src.utils.log_sanitizer import sanitize_message

QMessageBox.critical(
    self,
    "Error",
    sanitize_message(f"Failed to load file: {str(exception)[:100]}")
)
```

### Validation Checklist

Before committing changes that log data:

- [ ] No direct `traceback.print_exc()` in production paths
- [ ] All exception messages use `sanitize_message()` or `sanitize_exception()`
- [ ] Patient field names (PatientName, PatientID, etc.) never logged
- [ ] File paths redacted or logged only in debug mode
- [ ] Debug flags left as `False`

---

## Part 3: GitHub Security Automation

### Enabled Workflows

Four new security workflows now run automatically:

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| **CodeQL** | Push to main/develop, weekly | Python SAST (semantic analysis) |
| **Semgrep** | Every commit, weekly | Rule-based SAST (security audit, OWASP Top 10, secrets) |
| **Grype** | Push to main/develop, weekly | CVE scanning (dependencies) |
| **Security Checks** | Every PR, push to main/develop | Debug flags, secrets, PII validation |

### Dependabot Configuration

Located in `.github/dependabot.yml`:

- **Tracks:** Python (pip), GitHub Actions, Docker (future)
- **Frequency:** Weekly (Monday 3 AM UTC)
- **Auto-PR:** Opens automated dependency update PRs
- **Labels:** `dependencies`, `python`, `security`

### Workflow Results

#### **On GitHub UI:**

1. **Security → Code scanning:** View SAST and CVE results
2. **Security → Dependabot alerts:** Dependency vulnerabilities
3. **Security → Secret scanning:** Exposed credentials (if enabled)
4. **Pull requests → Checks:** Per-PR validation status

#### **In Pull Requests:**

- Semgrep posts comment with HIGH/CRITICAL findings
- Grype posts comment with vulnerable dependencies
- Security checks block merge if debug flags detected
- All SARIF reports uploaded to Security tab

#### **Example PR Comment (Semgrep):**

```
## 🔒 Security Scan Results

Found 3 potential issue(s) from Semgrep:

❌ **python.lang.security.audit.unsafe-pickle-usage**: Avoid using pickle for deserializing untrusted data
⚠️ **python.lang.best-practice.use-fstring-over-format**: Use f-string instead of .format()
❌ **python.lang.security.audit.hardcoded-sql-string**: SQL should not be hardcoded

Please review and address security findings before merging.
```

### Enabling/Disabling Workflows

**To enable a workflow:**
1. Push the `.github/workflows/*.yml` file to repo
2. GitHub auto-detects and enables it
3. Runs on next trigger event

**To disable:**
1. Edit the `.yml` file and set `on:` to empty or remove it
2. Or delete the `.yml` file

**To see results:**
1. Go to **Security → Code scanning**
2. Or **Actions** tab → workflow name

### Manual Trigger (optional)

You can manually run workflows from the GitHub UI:

1. Go to **Actions** → choose workflow
2. Click **Run workflow** → select branch
3. Workflow runs immediately

---

## Part 4: Best Practices & Examples

### Exception Handling Best Practices

#### ✅ DO:

```python
# 1. Sanitize before logging
from src.utils.log_sanitizer import sanitize_message

try:
    load_dicom(path)
except Exception as e:
    safe_error = sanitize_message(str(e))
    logger.error(f"Failed: {safe_error}")

# 2. Gate debugging behind a flag
from src.utils.debug_flags import DEBUG_LOADING

try:
    process_data()
except Exception as e:
    logger.error("Processing failed")
    if DEBUG_LOADING:
        # Full diagnostics only in debug mode
        logger.debug(f"Details: {trace_details}")

# 3. Use user-friendly error messages
except Exception as e:
    # For UI dialogs, show generic message
    QMessageBox.warning(self, "Error", "Could not load the selected file.")
    # Log detailed error server-side only
    logger.error(f"Load error: {sanitize_message(str(e))}")

# 4. Redact paths in messages
except Exception as e:
    filename = os.path.basename(file_path)  # Don't show full path
    logger.error(f"Error processing {filename}: {e}")
```

#### ❌ DON'T:

```python
# 1. Print raw tracebacks
except Exception as e:
    traceback.print_exc()  # ❌ Shows full path + patient data

# 2. Log unvalidated patient data
except Exception as e:
    logger.error(f"Patient {dataset.PatientName} error: {e}")  # ❌ PII exposed

# 3. Show full paths in UI messages
except Exception as e:
    QMessageBox.critical(self, "Error", str(e))  # ❌ Path may contain user info

# 4. Leave debug flags on
DEBUG_LAYOUT = True  # ❌ Will be blocked by pre-commit hook
```

### Common Patterns

#### **Pattern 1: Safe file operation error**

```python
try:
    dataset = dcmread(file_path)
    pixel_array = dataset.pixel_array
except MemoryError:
    logger.error("File too large to load into memory")
except Exception as e:
    # Sanitize before logging
    from src.utils.log_sanitizer import sanitize_message
    safe_msg = sanitize_message(str(e))
    logger.error(f"Failed to load file: {safe_msg}")
```

#### **Pattern 2: Safe dataset processing**

```python
try:
    for dataset in datasets:
        process_metadata(dataset)
except Exception as e:
    from src.utils.log_sanitizer import sanitize_message
    # Only log generic error in production
    logger.error("Metadata processing error")
    # Full diagnostic only behind flag
    if DEBUG_AGENT_LOG:
        logger.debug(f"Details: {sanitize_message(str(e))}")
```

#### **Pattern 3: Safe dialog reporting**

```python
if len(failed_files) > 0:
    # User-facing: generic message
    count = len(failed_files)
    QMessageBox.warning(
        self,
        "Load Completed with Errors",
        f"{count} file(s) could not be loaded.\n\nSee the status bar for details."
    )
    
    # Server-side: sanitized details
    for file_path, error_msg in failed_files:
        from src.utils.log_sanitizer import sanitize_message
        safe_error = sanitize_message(error_msg)
        logger.warning(f"Failed to load: {safe_error}")
```

### Testing Your Changes

#### **1. Test the sanitizer manually:**

```bash
$ python3 -c "
from src.utils.log_sanitizer import sanitize_message, validate_no_pii_in_output

msg = 'Patient John Doe (ID: MRN12345, DOB: 1985-03-15) loaded'
safe = sanitize_message(msg)
print(f'Original: {msg}')
print(f'Safe: {safe}')

is_ok, issues = validate_no_pii_in_output(msg)
print(f'Valid: {is_ok}, Issues: {issues}')
"
```

#### **2. Test the git hooks:**

```bash
# Commit with exception printing (will pass hook - it doesn't block this)
$ git add src/core/dicom_loader.py
$ git commit -m "Add safe exception handling"

# Now set a debug flag and try to commit
$ echo "DEBUG_LAYOUT = True" >> src/utils/debug_flags.py
$ git add src/utils/debug_flags.py
$ git commit -m "Debug"
# Should be blocked: [ERROR] Debug flag is set to True: DEBUG_LAYOUT
```

#### **3. Test GitHub Actions locally (optional):**

```bash
# Install act: https://github.com/nektos/act
act pull_request -j debug-flags-check
```

---

## Troubleshooting

### Problem: "pre-commit hook not found"

**Cause:** Hooks weren't installed or got lost

**Fix:**
```bash
bash scripts/setup-hooks.sh
```

### Problem: "pre-commit hook is not executable"

**Cause:** File permissions lost (common on Windows)

**Fix:**
```bash
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-push
```

### Problem: "Can't import log_sanitizer"

**Cause:** Python path not set correctly

**Fix:**
```bash
# From project root:
cd src
python3 -c "from utils.log_sanitizer import sanitize_message; print('OK')"
```

### Problem: "GitHub workflows not running"

**Cause:** 
- Workflows disabled in Settings
- Files not committed to repo
- Branch protection not configured

**Fix:**
```bash
# 1. Check Settings → Actions → General → "Allow all actions"
# 2. Commit workflow files
git add .github/workflows/
git commit -m "Add security workflows"
git push

# 3. View in GitHub UI: https://github.com/your-org/your-repo/actions
```

### Problem: "Debug flag hook blocks legitimate commit"

**Cause:** Flag left on accidentally

**Fix:**
```bash
# 1. Reset the flag
sed -i 's/DEBUG_LAYOUT: bool = True/DEBUG_LAYOUT: bool = False/' src/utils/debug_flags.py

# 2. Stage and commit
git add src/utils/debug_flags.py
git commit -m "Disable debug flag"
```

---

## Summary Checklist

After implementing these changes:

- [ ] Run `bash scripts/setup-hooks.sh` to install git hooks
- [ ] Verify debug flags are all `False` in `src/utils/debug_flags.py`
- [ ] Test pre-commit hook: `git commit --no-verify` skips it
- [ ] Import `log_sanitizer` in exception handlers (start with 2-3 key files)
- [ ] Test sanitization: `python3 -c "from src.utils.log_sanitizer import sanitize_message"`
- [ ] Check GitHub: **Settings → Security** and enable Dependabot/CodeQL if not already done
- [ ] Commit `.github/workflows/*.yml` and `.github/dependabot.yml` files
- [ ] Verify workflows appear in **Actions** tab
- [ ] Document in team wiki: new sanitization requirements for PR reviews

---

## Additional Resources

- [OWASP Top 10 - A09: Security Logging](https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/)
- [HIPAA Security Rule - 45 CFR § 164.312(a)(2)(ii)](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [Semgrep Documentation](https://semgrep.dev/docs/)
- [GitHub Code Scanning](https://docs.github.com/en/code-security/code-scanning)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-22  
**Status:** Draft (Review with team before full adoption)
