# Security and Safety Scan Template - [PROJECT_NAME]

**Template Version**: 2.1  
**Last Updated**: 2026-03-22

## Purpose

This document provides a comprehensive security and safety scan checklist that should be run periodically and after code updates to identify potential security vulnerabilities, safety concerns, and risky behaviors. The scan checks for:

- Security vulnerabilities (injection attacks, authentication issues, data exposure)
- Unsafe file operations (unintended deletions, path traversal)
- Dependency vulnerabilities (outdated or compromised packages)
- Configuration security issues
- Data handling and privacy concerns
- Access control and authorization flaws
- Input validation gaps
- Error handling that could leak sensitive information

## How to Use This Document

### Important: Creating Scan Copies

**DO NOT mark off checklist items in this file.** This is the master template that should remain unchanged.

Instead, for each security/safety scan:

1. **Create a new timestamped copy** of this template:
   - Copy this entire file to `[DEV_DOCS]/safety-scans/safety-scan-YYYY-MM-DD-HHMMSS.md`
   - Use format: `safety-scan-2024-01-15-143022.md` (year-month-day-hour-minute-second)
   - Example command: `cp [DEV_DOCS]/templates/safety-scan-template.md "[DEV_DOCS]/safety-scans/safety-scan-$(date +%Y-%m-%d-%H%M%S).md"`

2. **Work with the timestamped copy**:
   - Fill in the analysis sections with actual findings
   - Mark off items in the timestamped file as you complete them
   - Document all identified vulnerabilities and safety concerns
   - Provide specific recommendations with severity ratings

3. **After completing the scan**:
   - Review all findings in the timestamped file
   - If new security concerns are discovered, add them to this master template
   - Keep the timestamped file as a record of that specific scan

### Critical: No Code Changes During Scan

**DO NOT edit any code files during the security/safety scan.** The scan is for **analysis and documentation only**.

- **Document issues, don't fix them**: When you identify a vulnerability or safety concern, document it thoroughly in the timestamped scan file with:
  - Exact location (file and line numbers)
  - Description of the vulnerability or concern
  - Potential impact/severity (CRITICAL, HIGH, MEDIUM, LOW)
  - Attack vector or exploitation scenario
  - Suggested remediation approach (but don't implement it yet)

- **Only edit the timestamped scan file**: The only file that should be modified during the scan is the new timestamped markdown file created for this specific scan.

- **Separate phases**: 
  - **Phase 1 (Scan)**: Identify and document all security/safety issues
  - **Phase 2 (Remediation)**: After scan completion, review findings with team/user and implement fixes separately

### Scan Process

1. **After code changes or periodically**, create a new timestamped copy and run through the entire checklist
2. **For each category**, systematically check for vulnerabilities and safety concerns
3. **Document all findings** in the timestamped scan file with severity ratings
4. **Test edge cases** - Don't just verify "normal" operation; test boundary conditions and malicious inputs
5. **Review dependencies** - Check for known vulnerabilities in third-party libraries and packages
6. **Analyze code flow** - Trace execution paths to understand how data flows and where vulnerabilities might exist
7. **Consider attack scenarios** - Think like an attacker: what could go wrong?

---

## Severity Ratings

Use these severity ratings when documenting findings:

- **CRITICAL**: Immediate security risk that could lead to system compromise, data breach, or complete loss of functionality. Must be fixed immediately.
- **HIGH**: Significant security risk or safety concern that could lead to unauthorized access, data exposure, or major functionality issues. Should be fixed soon.
- **MEDIUM**: Moderate security risk or safety concern that could be exploited under certain conditions. Should be addressed when time permits.
- **LOW**: Minor security concern or potential issue that has minimal impact. Can be addressed during regular maintenance.

---

## Security Scan Checklist

### 1. Input Validation and Sanitization

#### 1.1 User Input Validation
- [ ] **Verify**: All user inputs are validated before use
- [ ] **Check**: Input validation includes type checking, length limits, format validation
- [ ] **Test**: Attempt to provide malicious inputs (SQL injection, XSS, command injection payloads)
- [ ] **Verify**: Validation occurs on both client and server side (if applicable)
- [ ] **Check**: Error messages don't reveal system internals or validation logic

#### 1.2 File Path Validation
- [ ] **Verify**: All file paths are validated to prevent path traversal attacks
- [ ] **Check**: Paths don't contain `../`, absolute paths outside allowed directories, or symlinks to sensitive locations
- [ ] **Test**: Attempt to access files outside intended directories using path traversal
- [ ] **Verify**: File operations use whitelisted directories only
- [ ] **Check**: Uploaded file names are sanitized

#### 1.3 Command Injection Prevention
- [ ] **Verify**: No user input is directly executed as system commands
- [ ] **Check**: All external command execution uses parameterized/safe APIs
- [ ] **Test**: Attempt to inject shell commands through user inputs
- [ ] **Verify**: Special characters in user input are properly escaped or rejected
- [ ] **Check**: No use of dangerous functions (eval, exec without sanitization)

#### 1.4 SQL Injection Prevention (if applicable)
- [ ] **Verify**: All database queries use parameterized queries or prepared statements
- [ ] **Check**: No string concatenation used to build SQL queries with user input
- [ ] **Test**: Attempt SQL injection attacks through all input fields
- [ ] **Verify**: ORM/database library is used correctly and securely
- [ ] **Check**: Database errors don't expose schema information

#### 1.5 Cross-Site Scripting (XSS) Prevention (if applicable)
- [ ] **Verify**: All user-generated content is properly escaped before display
- [ ] **Check**: HTML, JavaScript, and CSS in user input is sanitized
- [ ] **Test**: Attempt to inject malicious scripts through input fields
- [ ] **Verify**: Content Security Policy (CSP) headers are configured (if web application)
- [ ] **Check**: No use of dangerous functions (innerHTML without sanitization)

---

### 2. Authentication and Authorization

#### 2.1 Authentication Security
- [ ] **Verify**: Passwords are hashed using strong algorithms (bcrypt, Argon2, PBKDF2)
- [ ] **Check**: No passwords or secrets stored in plain text
- [ ] **Test**: Verify password hashing is implemented correctly
- [ ] **Verify**: Session tokens are generated securely (cryptographically random)
- [ ] **Check**: Authentication failures don't reveal whether username or password was incorrect

#### 2.2 Authorization and Access Control
- [ ] **Verify**: All sensitive operations check user permissions
- [ ] **Check**: Authorization checks occur on server side, not just client side
- [ ] **Test**: Attempt to access restricted resources without proper authorization
- [ ] **Verify**: Principle of least privilege is followed
- [ ] **Check**: No horizontal or vertical privilege escalation vulnerabilities

#### 2.3 Session Management
- [ ] **Verify**: Sessions expire after reasonable timeout
- [ ] **Check**: Session tokens are invalidated on logout
- [ ] **Test**: Verify session fixation attacks are prevented
- [ ] **Verify**: Session tokens are transmitted securely (HTTPS only, if applicable)
- [ ] **Check**: No session tokens in URLs or logs

---

### 3. Data Security and Privacy

#### 3.1 Sensitive Data Handling
- [ ] **Verify**: Sensitive data (passwords, API keys, tokens) is encrypted at rest
- [ ] **Check**: Sensitive data is encrypted in transit (TLS/SSL if network communication)
- [ ] **Test**: Verify encryption is implemented correctly
- [ ] **Verify**: Sensitive data is not logged or exposed in error messages
- [ ] **Check**: No sensitive data in version control (check .git history)

#### 3.2 Data Exposure Prevention
- [ ] **Verify**: API responses don't include unnecessary sensitive data
- [ ] **Check**: Error messages don't reveal system internals, stack traces, or sensitive information
- [ ] **Test**: Review all error handling paths for information disclosure
- [ ] **Verify**: Debug mode is disabled in production
- [ ] **Check**: No sensitive data in client-side code or comments

#### 3.3 Personal Identifiable Information (PII)
- [ ] **Verify**: PII is collected only when necessary
- [ ] **Check**: PII is stored securely and access is restricted
- [ ] **Test**: Verify data retention policies are implemented
- [ ] **Verify**: Users can request data deletion (if applicable)
- [ ] **Check**: Privacy policy is accurate and up-to-date (if applicable)

---

### 4. File Operations and System Safety

#### 4.1 File Deletion Safety
- [ ] **Verify**: File deletion operations only target intended files
- [ ] **Check**: No wildcard deletions that could match unintended files
- [ ] **Test**: Verify deletion operations with test files
- [ ] **Verify**: Critical files have protection against accidental deletion
- [ ] **Check**: Backup files are excluded from deletion operations

#### 4.2 File Creation and Modification
- [ ] **Verify**: File creation uses secure permissions (not world-writable)
- [ ] **Check**: Temporary files are created securely (mktemp or equivalent)
- [ ] **Test**: Verify file operations don't overwrite important files
- [ ] **Verify**: File modifications are atomic (temp file + rename pattern)
- [ ] **Check**: No race conditions in file operations

#### 4.3 Directory Operations
- [ ] **Verify**: Directory creation uses appropriate permissions
- [ ] **Check**: Directory deletion only removes intended directories
- [ ] **Test**: Verify directory operations don't affect parent directories
- [ ] **Verify**: No recursive deletions without explicit safeguards
- [ ] **Check**: Directory traversal is limited to intended paths

---

### 5. Dependency Security

#### 5.1 Third-Party Dependencies
- [ ] **Verify**: All dependencies are from trusted sources
- [ ] **Check**: Dependencies are pinned to specific versions
- [ ] **Test**: Run dependency vulnerability scanner (npm audit, pip-audit, Grype, etc.)
- [ ] **Verify**: No known vulnerabilities in current dependency versions
- [ ] **Check**: Dependencies are regularly updated
- [ ] **Run**: `grype dir:.` (or `grype <image>` for containers) to scan for known CVEs across all dependency types
- [ ] **Review**: Grype output for CRITICAL and HIGH severity CVEs and document any findings

#### 5.2 Supply Chain Security
- [ ] **Verify**: Dependency integrity is verified (checksums, signatures)
- [ ] **Check**: No dependencies from untrusted or compromised sources
- [ ] **Test**: Review dependency tree for suspicious packages
- [ ] **Verify**: Build process is secure and reproducible
- [ ] **Check**: No malicious code in dependencies (manual review of critical deps)
- [ ] **Consider**: Generating an SBOM (Software Bill of Materials) with `syft` and scanning it with `grype sbom:./sbom.json`

#### 5.3 GitHub Dependabot
- [ ] **Verify**: Dependabot is enabled in repository Settings → Security → Code security and analysis
- [ ] **Check**: A `dependabot.yml` configuration file exists in `.github/` (see [Section 11.3](#113-github-dependabot) for setup)
- [ ] **Review**: Open Dependabot alerts in the repository's Security tab and triage each one
- [ ] **Check**: Dependabot version-update PRs are being reviewed and merged promptly
- [ ] **Verify**: Dependabot is configured for all relevant package ecosystems used in the project

---

### 6. Configuration Security

#### 6.1 Configuration File Security
- [ ] **Verify**: Configuration files have appropriate permissions (not world-readable if sensitive)
- [ ] **Check**: No secrets or credentials in configuration files
- [ ] **Test**: Verify configuration parsing handles malformed input safely
- [ ] **Verify**: Configuration changes are validated before application
- [ ] **Check**: Default configurations are secure

#### 6.2 Environment Variables
- [ ] **Verify**: Sensitive configuration uses environment variables or secure vaults
- [ ] **Check**: Environment variables are not logged or exposed
- [ ] **Test**: Verify environment variable handling is secure
- [ ] **Verify**: No hardcoded secrets in code
- [ ] **Check**: Environment variables are documented

---

### 7. Error Handling and Logging

#### 7.1 Error Handling
- [ ] **Verify**: All errors are caught and handled appropriately
- [ ] **Check**: Error messages don't reveal sensitive information
- [ ] **Test**: Trigger error conditions and verify safe handling
- [ ] **Verify**: Application fails securely (fail closed, not open)
- [ ] **Check**: No unhandled exceptions that could crash the application

#### 7.2 Logging Security
- [ ] **Verify**: Logs don't contain sensitive data (passwords, tokens, PII)
- [ ] **Check**: Log files have appropriate permissions
- [ ] **Test**: Review log output for sensitive information
- [ ] **Verify**: Logging doesn't create denial-of-service vulnerability (log flooding)
- [ ] **Check**: Logs are rotated and have size limits

---

### 8. Network Security (if applicable)

#### 8.1 Transport Security
- [ ] **Verify**: All network communication uses TLS/SSL
- [ ] **Check**: TLS configuration uses strong ciphers and protocols
- [ ] **Test**: Verify certificate validation is enabled
- [ ] **Verify**: No mixed content (HTTP and HTTPS)
- [ ] **Check**: HSTS headers are configured (if web application)

#### 8.2 API Security
- [ ] **Verify**: API endpoints require authentication
- [ ] **Check**: Rate limiting is implemented to prevent abuse
- [ ] **Test**: Attempt to access APIs without authentication
- [ ] **Verify**: CORS is configured correctly (if applicable)
- [ ] **Check**: API versioning is implemented

---

### 9. Code Quality and Security Practices

#### 9.1 Secure Coding Practices
- [ ] **Verify**: No use of deprecated or insecure functions
- [ ] **Check**: Code follows security best practices for the language
- [ ] **Test**: Run static analysis security scanner (SAST tools)
- [ ] **Run**: Semgrep with security-focused rulesets (see [Section 11.1](#111-semgrep-static-analysis) for setup)
- [ ] **Verify**: Semgrep results reviewed — no unaddressed HIGH or CRITICAL findings
- [ ] **Verify**: No commented-out sensitive code or credentials
- [ ] **Check**: Code reviews include security considerations

#### 9.2 Cryptography
- [ ] **Verify**: Strong cryptographic algorithms are used (AES-256, RSA-2048+)
- [ ] **Check**: No custom/homebrew cryptography
- [ ] **Test**: Verify cryptographic implementations are correct
- [ ] **Verify**: Cryptographic keys are generated securely
- [ ] **Check**: Keys are stored securely and rotated regularly

---

### 10. Denial of Service (DoS) Prevention

#### 10.1 Resource Exhaustion
- [ ] **Verify**: Input size limits are enforced
- [ ] **Check**: No unbounded loops or recursion
- [ ] **Test**: Attempt to exhaust resources (memory, CPU, disk)
- [ ] **Verify**: Timeouts are configured for long-running operations
- [ ] **Check**: Rate limiting prevents abuse

#### 10.2 Application Availability
- [ ] **Verify**: Application handles high load gracefully
- [ ] **Check**: No single points of failure
- [ ] **Test**: Verify graceful degradation under stress
- [ ] **Verify**: Resource cleanup occurs properly
- [ ] **Check**: No memory leaks or resource leaks

---

### 11. Automated Security Tooling

This section covers the setup, usage, and verification of recommended automated security tools. These tools should be run as part of every scan and ideally integrated into the CI/CD pipeline.

#### 11.1 Semgrep (Static Analysis)

[Semgrep](https://semgrep.dev) is a fast, open-source SAST tool that supports dozens of languages and has an extensive library of security rules maintained by the community and the Semgrep team.

**Running Semgrep locally:**
```bash
# Install (if not already installed)
pip install semgrep
# or: brew install semgrep

# Run with the recommended security ruleset
semgrep --config=p/security-audit .

# Run with OWASP Top 10 rules
semgrep --config=p/owasp-top-ten .

# Run all auto-selected rules for detected languages
semgrep --config=auto .

# Output results as JSON for CI/CD ingestion
semgrep --config=p/security-audit --json -o semgrep-results.json .
```

**Recommended rulesets:**
- `p/security-audit` — broad security audit (good starting point)
- `p/owasp-top-ten` — OWASP Top 10 coverage
- `p/secrets` — detect hardcoded secrets and credentials
- `p/python`, `p/javascript`, `p/java`, etc. — language-specific security rules

**CI/CD integration (GitHub Actions example):**
```yaml
# .github/workflows/semgrep.yml
name: Semgrep
on: [push, pull_request]
jobs:
  semgrep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/secrets
```

**Checklist:**
- [ ] **Run**: `semgrep --config=p/security-audit .` and review all findings
- [ ] **Run**: `semgrep --config=p/secrets .` to check for hardcoded credentials
- [ ] **Verify**: All HIGH/ERROR severity findings are triaged and addressed or documented
- [ ] **Check**: Semgrep is integrated into CI/CD pipeline (runs on every PR/push)
- [ ] **Consider**: Adding a `.semgrepignore` to exclude false-positive paths (similar to `.gitignore`)

---

#### 11.2 Grype (Container and Dependency Vulnerability Scanning)

[Grype](https://github.com/anchore/grype) is an open-source vulnerability scanner by Anchore that checks container images, filesystems, and SBOMs against multiple CVE databases (NVD, GitHub Advisory, etc.).

**Running Grype locally:**
```bash
# Install (if not already installed)
brew install anchore/grype/grype
# or: curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh

# Scan the current directory (all dependency lockfiles, etc.)
grype dir:.

# Scan a specific container image
grype <image-name>:<tag>
# Example: grype myapp:latest

# Scan only HIGH and CRITICAL vulnerabilities
grype dir:. --fail-on high

# Output as table (default), JSON, or SARIF
grype dir:. -o json > grype-results.json
grype dir:. -o sarif > grype-results.sarif

# Generate an SBOM first with syft, then scan it
syft dir:. -o json > sbom.json
grype sbom:./sbom.json
```

**CI/CD integration (GitHub Actions example):**
```yaml
# .github/workflows/grype.yml
name: Grype Vulnerability Scan
on: [push, pull_request]
jobs:
  grype:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan with Grype
        uses: anchore/scan-action@v3
        with:
          path: "."
          fail-build: true
          severity-cutoff: high
      - name: Upload SARIF report
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ${{ steps.scan.outputs.sarif }}
```

**Checklist:**
- [ ] **Run**: `grype dir:.` and review all findings
- [ ] **Verify**: No CRITICAL or HIGH CVEs are present in production dependencies
- [ ] **Document**: All findings with CVE ID, affected package, and severity in the scan report
- [ ] **Check**: Grype is integrated into CI/CD pipeline
- [ ] **Consider**: Uploading Grype SARIF output to GitHub Security tab for centralized visibility
- [ ] **Consider**: Running `syft` to generate and maintain an SBOM for the project

---

#### 11.3 Secret Detection Tools

**GitLeaks**

[GitLeaks](https://github.com/gitleaks/gitleaks) is a fast, lightweight secret scanner designed to prevent hardcoded secrets from being committed to repositories. It's particularly effective as a pre-commit hook.

**Running GitLeaks locally:**
```bash
# Install (if not already installed)
brew install gitleaks
# or: go install github.com/gitleaks/gitleaks/v8/cmd/gitleaks@latest

# Scan current repository
gitleaks detect

# Scan with verbose output
gitleaks detect -v

# Scan specific directory
gitleaks detect --source=/path/to/repo

# Generate SARIF for GitHub Security tab
gitleaks detect --format=sarif --report-path=gitleaks-results.sarif
```

**Pre-commit hook setup:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.16.0
    hooks:
      - id: gitleaks
```

**Checklist:**
- [ ] **Run**: `gitleaks detect` and review all findings
- [ ] **Verify**: No secrets are present in current codebase
- [ ] **Check**: GitLeaks is configured as pre-commit hook
- [ ] **Test**: Attempt to commit a test secret and verify it's blocked
- [ ] **Consider**: Adding custom regex patterns for proprietary secret formats

---

**TruffleHog**

[TruffleHog](https://github.com/trufflesecurity/trufflehog) is a comprehensive secret scanner with high-entropy detection and an extensive pattern library. It's particularly good at finding secrets that don't match known patterns.

**Running TruffleHog locally:**
```bash
# Install (if not already installed)
pip install trufflehog
# or: go install github.com/trufflesecurity/trufflehog/v3/cmd/trufflehog@latest

# Scan current repository (including full history)
trufflehog filesystem .

# Scan only uncommitted changes
trufflehog git .

# Scan with specific rulesets
trufflehog filesystem . --rules=/path/to/custom/rules

# Output as JSON
trufflehog filesystem . --json
```

**Checklist:**
- [ ] **Run**: `trufflehog filesystem .` and review all findings
- [ ] **Verify**: Git history scan doesn't reveal old secrets
- [ ] **Check**: False positive rate is manageable
- [ ] **Consider**: Using TruffleHog for comprehensive scans, GitLeaks for pre-commit
- [ ] **Test**: Verify custom detection rules work for proprietary secrets
---

#### 11.4 Infrastructure as Code Security

**Checkov**

[Checkov](https://github.com/bridgecrewio/checkov) prevents cloud misconfigurations by scanning Terraform, Kubernetes, CloudFormation, and other infrastructure-as-code files.

**Running Checkov locally:**
```bash
# Install (if not already installed)
pip install checkov

# Scan Terraform files
checkov -d .

# Scan Kubernetes manifests
checkov -d . --framework kubernetes

# Scan Docker files
checkov -d . --framework dockerfile

# Skip specific checks
checkov -d . --skip-check CKV_AWS_1,CKV_AWS_2

# Output as JSON/SARIF
checkov -d . --output json
checkov -d . --output sarif
```

**Pre-commit hook setup:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/bridgecrewio/checkov
    rev: '3.0.0'
    hooks:
      - id: checkov
```

**Checklist:**
- [ ] **Run**: `checkov -d .` and review all failed checks
- [ ] **Verify**: No CRITICAL or HIGH severity IaC misconfigurations
- [ ] **Check**: All cloud resources follow security best practices
- [ ] **Test**: Infrastructure changes pass Checkov scans before deployment
- [ ] **Consider**: Adding custom policies for organization-specific requirements

---

**Trivy**

[Trivy](https://github.com/aquasecurity/trivy) is a comprehensive scanner that finds vulnerabilities in dependencies, containers, and infrastructure configurations.

**Running Trivy locally:**
```bash
# Install (if not already installed)
brew install trivy
# or: apt-get install trivy

# Scan file system for vulnerabilities
trivy fs .

# Scan container image
trivy image nginx:latest

# Scan repository for IaC issues
trivy config .

# Scan with severity filter
trivy fs . --severity HIGH,CRITICAL

# Output as JSON/SARIF
trivy fs . --format json -o trivy-results.json
```

**Checklist:**
- [ ] **Run**: `trivy fs .` and review all findings
- [ ] **Run**: `trivy config .` for IaC security issues
- [ ] **Verify**: No CRITICAL vulnerabilities in dependencies
- [ ] **Check**: Container images are scanned before deployment
- [ ] **Consider**: Using Trivy as unified scanner (deps + containers + IaC)
---

#### 11.5 Python Type Checking

**Pyright / BasedPyright**

[Pyright](https://github.com/microsoft/pyright) is a fast Python type checker with excellent IDE integration. [BasedPyright](https://github.com/detachhead/basedpyright) is a community fork with additional features.

**Running locally:**
```bash
# Install Pyright
npm install -g pyright
# or: pip install basedpyright

# Run type checking
pyright .
basedpyright .

# Run in strict mode
pyright --strict .
basedpyright --strict .

# Generate JSON report
pyright --outputjson > pyright-results.json
```

**VS Code setup:**
```json
// settings.json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "pyright.configPath": "./pyproject.toml",
  "basedpyright.configPath": "./pyproject.toml"
}
```

**Checklist:**
- [ ] **Run**: `pyright .` and fix all type errors
- [ ] **Verify**: Strict type checking is enabled for new code
- [ ] **Check**: Type hints are added to security-sensitive functions
- [ ] **Test**: Type errors are caught in CI/CD pipeline
- [ ] **Consider**: Using BasedPyright for additional features

---

**Mypy**

[Mypy](https://github.com/python/mypy) is the original Python type checker and reference implementation of PEP 484.

**Running locally:**
```bash
# Install (if not already installed)
pip install mypy

# Run type checking
mypy .

# Run in strict mode
mypy --strict .

# Check specific file
mypy security_module.py

# Generate JSON report
mypy --json-report mypy-report .
```

**Pre-commit hook setup:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Checklist:**
- [ ] **Run**: `mypy .` and review all type errors
- [ ] **Verify**: Security functions have proper type annotations
- [ ] **Check**: Mypy configuration is optimized for the project
- [ ] **Test**: Type checking runs in CI/CD pipeline
- [ ] **Consider**: Using Pyright for better performance, Mypy for strict compliance

---

#### 11.6 GitHub Dependabot

[Dependabot](https://docs.github.com/en/code-security/dependabot) is GitHub's built-in dependency management service. It monitors dependencies for known vulnerabilities (Dependabot **security alerts**) and optionally opens automated PRs to keep dependencies up to date (Dependabot **version updates**).

**Note**: Dependabot security alerts and GitHub Advanced Security features are **free for all public repositories**.

**Enabling Dependabot:**
1. Go to repository **Settings → Security → Code security and analysis**
2. Enable **Dependabot alerts** (passive monitoring, no PRs)
3. Enable **Dependabot security updates** (auto-creates PRs for vulnerable deps)
4. Enable **Dependabot version updates** (auto-creates PRs for outdated deps; requires `dependabot.yml`)

**Sample `dependabot.yml`** (place in `.github/dependabot.yml`):
```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10

  # JavaScript/Node dependencies
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"

  # Docker
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Checklist:**
- [ ] **Verify**: Dependabot alerts are enabled in repository settings
- [ ] **Check**: `.github/dependabot.yml` exists and covers all relevant package ecosystems
- [ ] **Review**: All open Dependabot security alerts in the Security tab and address or dismiss each
- [ ] **Review**: Open Dependabot version-update PRs and merge or close them
- [ ] **Verify**: Dependabot security update PRs pass CI before merging
- [ ] **Check**: Grouped Dependabot updates are configured if the project has many dependencies (reduces PR noise)

---

#### 11.7 GitHub Advanced Security (Free on Public Repositories)

[GitHub Advanced Security (GHAS)](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security) provides a suite of security features built directly into GitHub. All features are **free for public repositories**; private repositories require a paid GHAS license.

**Features included:**

| Feature | Description |
|---|---|
| **Code Scanning** | SAST powered by CodeQL (and third-party tools via SARIF upload) |
| **Secret Scanning** | Detects secrets/tokens accidentally committed to the repo |
| **Push Protection** | Blocks pushes containing detected secrets before they land |
| **Dependabot** | Dependency vulnerability alerts and automated PRs (see 11.3) |
| **Security Overview** | Centralized dashboard across org repos |

**Enabling Code Scanning (CodeQL):**
1. Go to **Settings → Security → Code security and analysis → Code scanning**
2. Click **Set up → Default** to use GitHub's automatic CodeQL configuration
3. Or add a workflow manually:

```yaml
# .github/workflows/codeql.yml
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday
jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python  # or: javascript, java, go, cpp, csharp, ruby
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
```

**Enabling Secret Scanning and Push Protection:**
1. Go to **Settings → Security → Code security and analysis**
2. Enable **Secret scanning**
3. Enable **Push protection** (blocks pushes containing secrets — strongly recommended)

**Checklist:**
- [ ] **Verify**: Code scanning (CodeQL) is enabled and has run at least once — check the Security → Code scanning tab
- [ ] **Verify**: Secret scanning is enabled — check Settings → Security → Code security and analysis
- [ ] **Verify**: Push protection is enabled to block accidental secret commits
- [ ] **Review**: All open code scanning alerts in Security → Code scanning and triage each
- [ ] **Review**: All open secret scanning alerts in Security → Secret scanning
- [ ] **Check**: No suppressed/dismissed alerts without a documented justification
- [ ] **Verify**: SARIF results from Semgrep or Grype are uploaded to the Security tab for a unified view
- [ ] **Consider**: Enabling the security policy (`SECURITY.md`) for responsible disclosure guidance

---

## Adding New Security Checks

If during a security scan you identify a new potential vulnerability or security concern not covered in this master checklist, **add it to this master template**:

1. **Identify the vulnerability**: Clearly describe the security issue (document in timestamped scan file first)
2. **Categorize it**: Add it to the appropriate section in this master template, or create a new section if needed
3. **Create check items**: Add specific checkboxes for verifying the vulnerability doesn't exist
4. **Document remediation**: Include suggested fixes or mitigation strategies

---

## Scan Results Template

Use this structure in your timestamped scan file:

```markdown
# Security and Safety Scan - YYYY-MM-DD HH:MM:SS

## Scan Date
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Scanner**: [Name/AI Agent]

## Scan Scope
- **Files Scanned**: [Number]
- **Dependencies Checked**: [Number]
- **Security Tools Used**: [e.g., Semgrep p/security-audit, Grype 0.x.x, CodeQL, pip-audit, npm audit]
- **Semgrep Version**: [version or N/A]
- **Grype Version**: [version or N/A]
- **Dependabot Alerts Reviewed**: [Yes/No/N-open alerts]
- **GitHub Advanced Security Active**: [Yes/No/Public repo - included free]

## Critical Findings

### Finding 1: [Brief Description]

**Severity**: CRITICAL  
**Category**: [Input Validation/Authentication/Data Security/etc.]  
**Location**: `path/to/file.ext` lines X-Y

**Description**:
[Detailed description of the vulnerability]

**Attack Vector**:
[How this could be exploited]

**Impact**:
[What could happen if exploited]

**Proof of Concept**:
```[language]
# Example of how to exploit this vulnerability
```

**Remediation**:
[Specific steps to fix this issue]

**Priority**: Immediate

---

## High Severity Findings

### Finding 1: [Brief Description]
[Same structure as Critical Findings]

---

## Medium Severity Findings

### Finding 1: [Brief Description]
[Same structure as Critical Findings]

---

## Low Severity Findings

### Finding 1: [Brief Description]
[Same structure as Critical Findings]

---

## Dependency Vulnerabilities

### Vulnerable Dependency: [Package Name]

**Current Version**: X.Y.Z  
**Vulnerable To**: [CVE-XXXX-XXXXX]  
**Severity**: [CRITICAL/HIGH/MEDIUM/LOW]  
**Description**: [Vulnerability description]  
**Fixed In**: X.Y.Z  
**Remediation**: Update to version X.Y.Z or later

---

## Security Best Practices Review

### Positive Findings
- [List security practices that are implemented well]

### Areas for Improvement
- [List areas where security could be enhanced]

---

## Summary

- **Total Findings**: X
  - **Critical**: X
  - **High**: X
  - **Medium**: X
  - **Low**: X
- **Dependency Vulnerabilities**: X
- **Overall Security Posture**: [Excellent/Good/Fair/Poor]

## Recommendations Priority

### Immediate Action Required (Critical)
1. [Finding with immediate action needed]

### Short-Term (High Priority)
1. [Finding to address soon]

### Medium-Term (Medium Priority)
1. [Finding to address when time permits]

### Long-Term (Low Priority)
1. [Finding for future consideration]

## Next Steps
- [ ] Review findings with team/user
- [ ] Prioritize remediation efforts
- [ ] Create tickets/issues for each finding
- [ ] Schedule remediation work
- [ ] Re-scan after fixes are implemented
```

---

## Security Tools and Resources

### Recommended Security Scanners

**Static Analysis (SAST)**:
- **Semgrep** — multi-language, rule-based SAST; use `p/security-audit`, `p/owasp-top-ten`, `p/secrets` rulesets; free tier available; integrates with GitHub Actions and uploads SARIF to GitHub Security tab
- Python: `bandit`, `safety`
- JavaScript/Node.js: `npm audit`, `eslint-plugin-security`
- Java: SpotBugs, FindSecBugs
- Ruby: `brakeman`
- Go: `gosec`
- General/multi-language: SonarQube, Semgrep, CodeQL (via GitHub Advanced Security)

**Dependency and Container Vulnerability Scanning**:
- **Grype** (by Anchore) — scans filesystems, container images, and SBOMs against NVD, GitHub Advisory DB, and other sources; use with `syft` to generate SBOMs first
- **GitHub Dependabot** — built into GitHub; monitors deps for CVEs and opens automated PRs; free for all public repos
- Python: `pip-audit`, `safety`
- JavaScript/Node.js: `npm audit`, `yarn audit`, Snyk
- Ruby: `bundler-audit`
- Java: OWASP Dependency-Check
- General: Snyk, Grype, Dependabot

**GitHub Advanced Security (free for public repositories)**:
- **CodeQL** — semantic code analysis (SAST) built into GitHub; supports Python, JS/TS, Java, Go, C/C++, C#, Ruby, Swift
- **Secret Scanning** — detects secrets committed to the repo; supports 100+ secret types
- **Push Protection** — blocks pushes containing detected secrets before they are committed
- **Security Overview** — centralized dashboard for org-wide security posture

**Dynamic Analysis (DAST)** (if applicable):
- OWASP ZAP
- Burp Suite
- Nikto

**SBOM Generation**:
- **Syft** (by Anchore) — generates Software Bill of Materials in CycloneDX, SPDX, or Syft JSON; use with Grype for scanning
- **GitHub SBOM export** — available from repository Insights → Dependency graph → Export SBOM

### Quick-Start Commands

```bash
# Semgrep — SAST scan
pip install semgrep
semgrep --config=p/security-audit --config=p/secrets .

# Grype — dependency/container vulnerability scan
# Install: brew install anchore/grype/grype
grype dir:.                     # scan current directory
grype <image>:<tag>             # scan a container image
grype dir:. --fail-on high      # exit non-zero if HIGH/CRITICAL found

# Syft — generate SBOM, then scan with Grype
# Install: brew install anchore/syft/syft
syft dir:. -o json > sbom.json
grype sbom:./sbom.json

# npm audit (Node.js)
npm audit --audit-level=high

# pip-audit (Python)
pip install pip-audit && pip-audit
```

### GitHub Security Setup Checklist (one-time)

- [ ] Enable Dependabot alerts: Settings → Security → Code security and analysis
- [ ] Add `.github/dependabot.yml` for version updates
- [ ] Enable Code scanning (CodeQL): Settings → Security → Code scanning → Set up
- [ ] Enable Secret scanning + Push protection: Settings → Security
- [ ] Add Semgrep and/or Grype GitHub Actions workflows
- [ ] Configure SARIF upload from Semgrep/Grype to unify results in the Security tab

### Security Resources
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE Top 25: https://cwe.mitre.org/top25/
- SANS Top 25: https://www.sans.org/top25-software-errors/
- Semgrep docs: https://semgrep.dev/docs/
- Grype docs: https://github.com/anchore/grype
- GitHub Advanced Security docs: https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security
- GitHub Dependabot docs: https://docs.github.com/en/code-security/dependabot
- Security best practices for your language/framework

---

## Notes

- **Regular Scans**: Perform security scans regularly (weekly/monthly) and after significant code changes
- **Automated Scanning**: Integrate Semgrep, Grype, and CodeQL into CI/CD pipeline so every push and PR is scanned automatically
- **Dependabot**: Enable Dependabot alerts and version updates so dependency vulnerabilities are caught continuously without manual effort
- **GitHub Advanced Security**: All GHAS features (CodeQL, secret scanning, push protection) are free for public repositories — enable them all
- **Manual Review**: Automated tools don't catch everything; manual code review is essential
- **Stay Updated**: Keep informed about new vulnerabilities and security best practices
- **Defense in Depth**: Implement multiple layers of security (SAST + dependency scanning + secret scanning + manual review)
- **Assume Breach**: Design systems assuming attackers will get in; limit damage they can do

---
