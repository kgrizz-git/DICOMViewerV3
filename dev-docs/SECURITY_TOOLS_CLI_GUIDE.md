# Security Tools CLI Guide

**Local Security Scanning in Development**

This guide shows how to use the security scanning tools installed in your venv. These are the same tools used in GitHub Actions workflows, but you can run them locally before committing.

---

## Installation

These tools are **not** in the main `requirements.txt` (that file is for running the app and tests).

### Step 1: Install Python-based dev scanners

```bash
pip install -r requirements-dev.txt
```

This installs `requirements.txt` plus **semgrep** and **detect-secrets**.

Install dependency CVE scanner (`pip-audit`) in the same venv:

```bash
python -m pip install pip-audit
```

### Step 2: Install TruffleHog v3 binary (recommended; aligns with CI)

From project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath
```

Optional version pin:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -Version v3.94.0 -AddToUserPath
```

### Step 3: Verify versions

```bash
semgrep --version
trufflehog --version
detect-secrets --version
```

Example versions (your venv may differ slightly):

```
semgrep         1.156.x  (Python SAST scanner)
trufflehog      3.94.x   (Secrets scanner; official TruffleHog binary line)
detect-secrets  1.5.x    (Secrets detector)
```

**Activation (PowerShell) for Python tools:**

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## Tool Overview

| Tool | Purpose | Speed | Detection | Use Case |
|------|---------|-------|-----------|----------|
| **semgrep** | Security rules SAST | Fast | Logic bugs, unsafe patterns | Pre-commit scanning |
| **truffleHog** | Credential/secret scanning | Medium | High-confidence secrets (verified) | Verify no credentials in code |
| **detect-secrets** | Secret patterns | Fast | Low-confidence patterns | Find potential secrets |

---

## 1. Semgrep (Rule-Based SAST)

### Basic Usage

**Scan the entire src/ directory:**
```bash
semgrep --config=p/security-audit src/
```

**Scan with multiple rulesets (security + OWASP):**
```bash
semgrep --config=p/security-audit --config=p/owasp-top-ten src/
```

**Scan a single file:**
```bash
semgrep --config=p/security-audit src/core/dicom_loader.py
```

**Output formats:**

```bash
# JSON (for CI/CD and parsing)
semgrep --config=p/security-audit --json src/ > /tmp/semgrep-results.json

# SARIF (GitHub Security tab format)
semgrep --config=p/security-audit --sarif src/ > /tmp/semgrep-results.sarif

# GitHub format (for PR comments)
semgrep --config=p/security-audit --github-json src/ > /tmp/semgrep-github.json
```

### What It Detects

Semgrep with `p/security-audit` ruleset finds:
- SQL injection vulnerabilities
- Command injection (`subprocess.run` misuse)
- Insecure deserialization (`pickle`, `yaml.load`)
- Weak cryptography
- Hardcoded credentials
- Debug code left in production
- Path traversal vulnerabilities
- Unsafe object deserialization

### Example: Find all subprocess calls

```bash
semgrep --config=p/owasp-top-ten --include="*.py" --pattern="subprocess.*" src/
```

### Python-Specific Rules

```bash
# Python security audit
semgrep --config=p/python src/

# Python with OWASP Top 10
semgrep --config=p/python --config=p/owasp-top-ten src/
```

---

## 2. TruffleHog v3 (Advanced Secrets Scanning)

TruffleHog v3 finds credentials by scanning git history and files. It supports verified/unverified/unknown result types and can enforce failure with `--fail`.

### Basic Usage

**Scan filesystem (current directory):**
```bash
trufflehog filesystem . --fail --no-update
```

**Scan a specific file:**
```bash
trufflehog filesystem src/utils/config_manager.py
```

**Scan git history (current repo):**
```bash
trufflehog git file://. --only-verified
```

### Output Options

```bash
# JSON output
trufflehog filesystem . --json

# Human-readable table
trufflehog filesystem . --debug
```

### What It Detects

- AWS credentials (AKIA... patterns)
- Private keys (RSA, Ed25519, etc.)
- API keys and tokens (GitHub, Slack, etc.)
- Database connection strings
- OAuth tokens
- Verified secrets (high confidence only with `--only-verified`)

### Common Filters

```bash
# Exclude directories
trufflehog filesystem . --fail \
  --exclude-paths=".git" \
  --exclude-paths="venv" \
  --exclude-paths="build"

# Only specific entropers (entropy-based detection)
trufflehog filesystem . --detectors=Slack,GitHub,AWS
```

---

## 3. Detect-Secrets (Pattern-Based Secrets)

Detect-secrets finds potential secrets using regex patterns. Lower confidence than truffleHog but faster.

### Basic Usage

**Scan the entire project:**
```bash
detect-secrets scan src/ --baseline .secrets.baseline
```

**Scan a single file:**
```bash
detect-secrets scan src/utils/config_manager.py
```

**Initialize a baseline (for CI/CD):**
```bash
# Create baseline - ignore known false positives
detect-secrets scan --all-files --force-use-all-plugins 2>/dev/null > .secrets.baseline

# Audit baseline (mark as valid if false positive)
detect-secrets audit .secrets.baseline
```

### Verify Against Baseline

```bash
# Fail if new secrets found (relative to baseline)
detect-secrets scan --baseline .secrets.baseline src/ && echo "✓ No new secrets"
```

### What It Detects

- AWS keys, private keys
- BasicAuth credentials
- JWT tokens
- Crypto keys
- Slack tokens
- Asymmetric keys
- PEM formatted secrets
- Artifactory credentials

### Output Formats

```bash
# JSON (default)
detect-secrets scan src/ --json

# Pretty print
detect-secrets scan src/ --only-json
```

---

## Quick Start Workflow

### Before Each Commit

```bash
# 1. Activate venv
.\.venv\Scripts\Activate.ps1

# 2. Run semgrep (fast)
semgrep --config=p/security-audit src/ || echo "⚠ Review semgrep findings"

# 3. Check for secrets (fast)
detect-secrets scan src/ && echo "✓ No secrets detected"

# 4. If you want thorough verification:
trufflehog filesystem . --fail --no-update && echo "✓ No verified secrets"
```

### Combine All Checks (One Command)

```powershell
# Wrapper script (recommended)
.\scripts\scan-security.ps1 -All -Report
```

Equivalent direct Python command:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_security_scan.py --all --report
```

Fast check matching the **pre-commit** hook (staged files only; run from repo root with a staged index):

```powershell
.\.venv\Scripts\python.exe .\scripts\run_security_scan.py --pre-commit --report
```

Privacy / logging checks on **staged `src/*.py`** (same script the hook runs first; all branches when hooks are installed):

```powershell
.\.venv\Scripts\python.exe .\scripts\git_hook_privacy_checks.py
```

Set **`DICOMVIEWER_PRIVACY_HOOK=warn`** to print violations without failing the hook (useful when tuning new code against heuristics).

### Enforce scans for `main` via Git hooks

Keep `.githooks/` **tracked in git** (do not gitignore it) so everyone gets the same hook logic.

Install local hooks from this repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-local-git-hooks.ps1
```

macOS/Linux install:

```bash
bash ./scripts/setup-hooks.sh
```

Behavior:

- `pre-commit` (**all branches**): runs **`scripts/git_hook_privacy_checks.py`** first (staged **`src/*.py`** only): blocks **`traceback.print_exc(`** in real code (matches inside **`tokenize`** **STRING** / **COMMENT** spans—docstrings, string literals, `#` comments—are ignored); on **added** lines, heuristics for patient tag names in log/print lines, path-like literals in `logger.*` calls, raw-exception patterns in `QMessageBox` / dialog calls, and `logger.*` calls whose message is non-literal without **`sanitize_message`** / **`sanitize_exception`**. Set **`DICOMVIEWER_PRIVACY_HOOK=warn`** to log issues without blocking.
- `pre-commit` (branch **`main`**): after the privacy script, runs a **light** security check — debug flags plus **detect-secrets** on **staged** files only (`scripts/run_security_scan.py --pre-commit`). Skips Semgrep, TruffleHog, and pip-audit for speed. To run the **full** suite on every commit instead, set environment variable **`DICOMVIEWER_PRECOMMIT_FULL_SECURITY_SCAN=1`** (e.g. in your shell profile) before committing. **`run_security_scan.py`** exits with a **non-zero** status when any configured check fails (so the hook can block).
- `pre-commit`: prunes `backups/` on **`main`** / **`WIP`** — **`scripts/git-hook-prune-backups.py --days 3 --max-commits 10`**: **tracked** files are removed if **more than 10 commits** since the last commit that touched the path **or** (when **more than 10** commits landed in the last **3** days) the touch is **strictly older than 3 days**; **untracked** files use embedded **`YYYYMMDD`** and **mtime** (the **older** of the two), removed when **strictly older than 3 days**. Then **`git add -u -- backups`** stages tracked removals (other branches: no prune). Shallow clones may skew Git counts; prune / staging errors are **non-fatal**.
- `pre-push`: runs **full** scans whenever a push updates `refs/heads/main` (covers fast-forward merges pushed to `main`) — `run_security_scan.py --all`

---

## Integration with Git Hooks

You can run security scans as part of pre-commit hooks. Example:

**`.git/hooks/pre-commit` enhancement (optional):**

```bash
#!/bin/bash
# ... existing debug flags check ...

echo "Running security scans..."

# Semgrep
semgrep --config=p/python src/ --quiet || {
    echo "❌ Semgrep found security issues"
    exit 1
}

# Detect-secrets
detect-secrets scan src/ --baseline .secrets.baseline || {
    echo "❌ Potential secrets detected"
    exit 1
}

echo "✓ Security checks passed"
exit 0
```

---

## Interpreting Results

### Semgrep Findings

**High severity findings that should block commit:**
- SQL Injection
- Command Injection
- Hardcoded credentials
- Insecure deserialization

**Medium findings to review:**
- Use of print() for debugging
- Weak cryptography
- Path traversal risks

**Low findings (informational):**
- Debug code patterns
- Code quality suggestions

### TruffleHog Findings

**Verified secrets = MUST FIX:**
- Output shows "Verified: YES"
- Rotate the credential immediately
- Update `.gitignore`

**Unverified findings:**
- May be false positives
- Review manually before rotating

### Detect-Secrets Findings

**Common false positives:**
- Base64-encoded data
- Test fixtures
- Mock API keys

**Handle:**
```bash
# Mark as false positive
detect-secrets audit .secrets.baseline
# Select findings to mark as ok
# Press 'y' to mark as OK, 'n' to reject
```

---

## Troubleshooting

### Semgrep not found

```powershell
# Verify installation
.\.venv\Scripts\python.exe -m semgrep --version

# Or use python module directly
python -m semgrep --config=p/security-audit src/
```

### TruffleHog takes too long

```bash
# Scan only current working tree (not history)
trufflehog filesystem . --no-git-history --fail

# Exclude large directories
trufflehog filesystem . --exclude-paths="build" --exclude-paths="dist"
```

### Detect-secrets baseline issues

```bash
# Recreate baseline
rm .secrets.baseline
detect-secrets scan --all-files --force-use-all-plugins > .secrets.baseline 2>/dev/null
```

---

## GitHub Actions Integration

The same tools run automatically in CI:

- **Semgrep:** `.github/workflows/semgrep.yml`
- **Secrets detection:** `.github/workflows/security-checks.yml` (uses TruffleHog + detect-secrets)

**Local vs CI:**
- Local: Run before committing (fast feedback)
- CI: Runs on every push/PR (final verification)

---

## Dependabot Alert Export (Local)

After installing/authenticating GitHub CLI, you can export Dependabot alerts to local files:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export-dependabot-alerts.ps1
```

Optional parameters:

```powershell
# Explicit repository and state
powershell -ExecutionPolicy Bypass -File .\scripts\export-dependabot-alerts.ps1 `
  -Repo "kgrizz-git/DICOMViewerV3" `
  -State open `
  -OutputJson "dev-docs/security/dependabot-open.json" `
  -OutputCsv "dev-docs/security/dependabot-open.csv"
```

Notes:
- Requires `gh auth login` first.
- Uses GitHub REST endpoint `/repos/{owner}/{repo}/dependabot/alerts` with `gh api --paginate` (this API does not accept `?page=` pagination).
- Exports normalized CSV columns for easier triage/spreadsheet use.
- Output filenames matching `dev-docs/security/dependabot-*.json` / `dependabot-*.csv` are listed in `.gitignore` so snapshots stay local. If you ever committed them before adding ignore rules, stop tracking them once (files stay on disk), e.g. PowerShell: `Get-ChildItem dev-docs/security/dependabot-*.json, dev-docs/security/dependabot-*.csv | ForEach-Object { git rm --cached -- $_.FullName }`.

---

## Recommended Pre-Commit Checklist

Before `git commit`:

- [ ] `semgrep --config=p/security-audit src/ --quiet` (no output = passed)
- [ ] `detect-secrets scan src/` (no findings = passed)
- [ ] Debug flags all False in `src/utils/debug_flags.py`
- [ ] No patient PII in log output
- [ ] tests pass: `python -m pytest tests/ -v`

---

## Weekly Full Scan

Run this weekly to catch issues before they reach CI:

```bash
$tools = @{
    "Semgrep (security-audit)" = "semgrep --config=p/security-audit --config=p/owasp-top-ten --json src/"
    "Semgrep (secrets)" = "semgrep --config=p/secrets --json src/"
    "Detect-secrets" = "detect-secrets scan src/ --baseline .secrets.baseline --json"
    "TruffleHog (verified)" = "trufflehog filesystem . --only-verified --json"
}

foreach ($tool in $tools.GetEnumerator()) {
    Write-Host "`n=== $($tool.Name) ===" -ForegroundColor Cyan
    Invoke-Expression $tool.Value | Out-Null
    echo "✓ Completed"
}
```

---

## Reference: Rulesets

**Available Semgrep rulesets:**

- `p/security-audit` - General security audit
- `p/owasp-top-ten` - OWASP Top 10 vulnerabilities
- `p/python` - Python-specific security issues
- `p/secrets` - Hardcoded secrets patterns
- `p/cwe-top-25` - CWE Top 25 issues

**Combine multiple:**
```bash
semgrep \
  --config=p/security-audit \
  --config=p/owasp-top-ten \
  --config=p/python \
  --config=p/secrets \
  src/
```

---

## Performance Tips

**Fastest (dev machine):**
```bash
semgrep --config=p/python src/ --quiet  # ~5 sec
```

**Thorough (pre-push):**
```bash
semgrep --config=p/security-audit --config=p/owasp-top-ten src/  # ~10 sec
```

**Full (before release):**
```bash
semgrep --config=p/security-audit --config=p/secrets --config=p/python --config=p/owasp-top-ten src/
detect-secrets scan src/ --baseline .secrets.baseline
trufflehog filesystem . --only-verified
```

---

**Document Version:** 1.0  
**Created:** 2026-03-22  
**Last Updated:** 2026-03-22
