# Security and Safety Scan Template - [PROJECT_NAME]

**Template Version**: 2.3
**Last Updated**: 2026-05-31

## Purpose

Use this template for recurring security and safety reviews after significant code changes and on a regular cadence. It is designed to catch:

- Security vulnerabilities such as injection, auth, access-control, and data-exposure flaws
- Unsafe file or system operations such as path traversal, unintended deletion, and risky command execution
- Dependency, supply-chain, and configuration risks
- Privacy, logging, and error-handling issues
- Availability, resource-exhaustion, and operational safety concerns

---

## How to Use This Template

### Master Template Rule

**Do not check items off in this file.** Keep this file unchanged as the master template.

For each scan, create a timestamped copy in `dev-docs/safety-scans/` and work only in that copy.

### Create a Scan Copy

Suggested filename format:

`safety-scan-YYYY-MM-DD-HHMMSS.md`

Examples:

**PowerShell**
```powershell
$ts = Get-Date -Format "yyyy-MM-dd-HHmmss"
Copy-Item "dev-docs/templates-generalized/safety-scan-template.md" "dev-docs/safety-scans/safety-scan-$ts.md"
```

**bash / zsh**
```bash
ts="$(date +%Y-%m-%d-%H%M%S)"
cp "dev-docs/templates-generalized/safety-scan-template.md" "dev-docs/safety-scans/safety-scan-$ts.md"
```

### Scan Rules

- **Analysis only**: Do not edit code while running the scan.
- **Document, do not fix**: Record findings with evidence, impact, and remediation guidance.
- **Edit only the timestamped copy** during the scan.
- **Separate phases**:
  - **Phase 1 - Scan**: Inspect, test, and document issues.
  - **Phase 2 - Remediation**: Review findings, prioritize, and fix issues separately.

### Status Convention

Use the following status meanings in the timestamped copy:

- `[x]` Completed and verified
- `[ ]` Not yet reviewed
- `N/A` Not applicable to this project or this scan scope
- `Follow-up` Reviewed, but needs later confirmation or a separate investigation

### Scan Process

1. Create a timestamped copy and define the scan scope.
2. Run the recurring checklist.
3. Record findings with severity, evidence, and recommended remediation.
4. Mark one-time setup items as verified, `N/A`, or follow-up as appropriate.
5. Review results with the team/user before any fixes are made.
6. If the scan reveals a missing class of check, add that check back to this master template later.

### Recommended Scan Cadence

- **Before releases**: Run a full scan before any production or distribution release.
- **After significant PRs**: Scan when new features, refactors, or dependency updates land.
- **After dependency updates**: Re-run dependency and supply-chain sections after bulk upgrades.
- **Monthly minimum**: If none of the above triggers fire, run at least once per month.
- **After security incidents**: Run a targeted scan on affected areas after any incident or vulnerability disclosure.

---

## Severity Ratings

- **CRITICAL**: Immediate risk of compromise, major data exposure, destructive misuse, or severe loss of function. Fix immediately.
- **HIGH**: Significant exploitable risk or major safety concern. Fix soon.
- **MEDIUM**: Real but bounded risk, often dependent on conditions or chaining. Schedule deliberately.
- **LOW**: Minor issue, defense-in-depth improvement, or low-impact weakness.

When in doubt, document the reasoning used to assign severity.

---

## Recurring Scan Checklist

### 1. Input Validation and Sanitization

#### 1.1 User Input Validation
- [ ] **Verify** all user inputs are validated before use
- [ ] **Check** type, length, range, and format constraints
- [ ] **Test** malicious or malformed payloads relevant to the stack
- [ ] **Verify** validation occurs in every trusted boundary that matters
- [ ] **Check** validation errors do not reveal internal details

#### 1.2 File Path Validation
- [ ] **Verify** file paths are validated against traversal and escaping attacks
- [ ] **Check** paths cannot escape intended directories via `../`, absolute paths, drive roots, or symlink indirection
- [ ] **Test** access attempts outside allowed paths
- [ ] **Verify** file operations are constrained to approved directories
- [ ] **Check** uploaded or user-provided file names are sanitized

#### 1.3 Command Injection Prevention
- [ ] **Verify** user input is never executed directly as a shell or system command
- [ ] **Check** external command calls use safe APIs and explicit argument passing
- [ ] **Test** command-injection payloads where command execution exists
- [ ] **Verify** special characters are escaped or rejected when needed
- [ ] **Check** dangerous dynamic execution patterns are absent or tightly controlled

#### 1.4 Database Injection Prevention (if applicable)
- [ ] **Verify** queries use parameterization, prepared statements, or safe ORM patterns
- [ ] **Check** user input is not concatenated into query text
- [ ] **Test** injection payloads on all query-bearing inputs
- [ ] **Verify** database libraries are used securely
- [ ] **Check** database errors do not expose schema or internal details

#### 1.5 Script Injection / XSS Prevention (if applicable)
- [ ] **Verify** untrusted content is escaped before rendering
- [ ] **Check** HTML, script, and style injection paths are sanitized
- [ ] **Test** malicious content injection on relevant surfaces
- [ ] **Verify** CSP or equivalent browser defenses are configured where applicable
- [ ] **Check** dangerous DOM APIs are not used unsafely

#### 1.6 Deserialization Safety
- [ ] **Verify** untrusted data is not deserialized with unsafe loaders (e.g., `pickle.loads`, `yaml.load` without `SafeLoader`, Java `ObjectInputStream`)
- [ ] **Check** deserialization inputs are validated or restricted to known-safe types
- [ ] **Test** malicious serialized payloads where deserialization exists
- [ ] **Verify** safer alternatives are used where available (e.g., JSON, `yaml.safe_load`, protocol buffers)
- [ ] **Check** deserialization libraries are current and patched

---

### 2. Authentication and Authorization

#### 2.1 Authentication Security
- [ ] **Verify** passwords are hashed with strong algorithms where passwords exist
- [ ] **Check** secrets are not stored in plain text
- [ ] **Test** authentication flows for incorrect or incomplete implementations
- [ ] **Verify** tokens or session identifiers are generated securely
- [ ] **Check** failures do not leak whether a username, secret, or token was the incorrect part

#### 2.2 Authorization and Access Control
- [ ] **Verify** sensitive actions enforce authorization server-side or in the true trust boundary
- [ ] **Check** the principle of least privilege is followed
- [ ] **Test** restricted actions without the required role or identity
- [ ] **Verify** object-level authorization is enforced, not just page or route access
- [ ] **Check** horizontal and vertical privilege escalation paths

#### 2.3 Session and Credential Lifecycle
- [ ] **Verify** sessions expire appropriately
- [ ] **Check** logout invalidates active sessions or tokens where applicable
- [ ] **Test** fixation, reuse, and stale-session scenarios
- [ ] **Verify** secrets and tokens are transmitted securely when sent over networks
- [ ] **Check** tokens do not appear in URLs, logs, or analytics

---

### 3. Data Security and Privacy

#### 3.1 Sensitive Data Handling
- [ ] **Verify** sensitive data is protected at rest where appropriate
- [ ] **Check** sensitive data is protected in transit where applicable
- [ ] **Test** encryption, key use, and failure behavior where implemented
- [ ] **Verify** secrets, tokens, and protected data are not logged
- [ ] **Check** sensitive material is not committed to version control, including history if relevant

#### 3.2 Data Exposure Prevention
- [ ] **Verify** outputs expose only necessary fields
- [ ] **Check** errors, stack traces, and diagnostics do not reveal internals to untrusted users
- [ ] **Test** failure paths for information disclosure
- [ ] **Verify** debug-only behaviors are off in production or release contexts
- [ ] **Check** comments, client bundles, and generated artifacts for sensitive information

#### 3.3 Personal Data / PII (if applicable)
- [ ] **Verify** personal data collection is necessary and scoped
- [ ] **Check** storage and access controls match data sensitivity
- [ ] **Test** retention and deletion workflows where required
- [ ] **Verify** deletion/export rights are supported if required by policy or regulation
- [ ] **Check** privacy disclosures are accurate

---

### 4. File Operations and System Safety

#### 4.1 File Deletion Safety
- [ ] **Verify** deletion targets are explicit and narrow
- [ ] **Check** wildcard or recursive deletions cannot match unintended files
- [ ] **Test** deletion behavior with representative fixtures
- [ ] **Verify** critical files and directories are protected from accidental removal
- [ ] **Check** backup, temp, or user data locations are handled intentionally

#### 4.2 File Creation and Modification
- [ ] **Verify** files are created with appropriate permissions
- [ ] **Check** temp files are created safely
- [ ] **Test** overwrite behavior for existing files and collisions
- [ ] **Verify** write flows are atomic where partial writes would be dangerous
- [ ] **Check** race conditions in create/replace flows

#### 4.3 Directory Operations
- [ ] **Verify** directory creation uses intended permissions
- [ ] **Check** directory deletion is tightly scoped
- [ ] **Test** operations near parent boundaries and symlinked paths
- [ ] **Verify** recursive directory removal has explicit safeguards
- [ ] **Check** traversal is limited to intended roots

---

### 5. Dependency and Supply-Chain Security

#### 5.1 Third-Party Dependencies
- [ ] **Verify** dependencies come from trusted registries or approved sources
- [ ] **Check** versions are pinned or otherwise controlled appropriately for the ecosystem
- [ ] **Run** dependency vulnerability tooling relevant to the stack
- [ ] **Verify** known critical or high-severity vulnerabilities are triaged
- [ ] **Check** dependency updates are reviewed regularly

#### 5.2 Supply-Chain Integrity
- [ ] **Verify** integrity controls such as lockfiles, checksums, signatures, or reproducible inputs are used where appropriate
- [ ] **Check** no suspicious or abandoned packages appear in the dependency tree
- [ ] **Review** critical transitive dependencies and install-time behaviors where risk is elevated
- [ ] **Verify** the build process does not fetch or execute untrusted content unsafely
- [ ] **Consider** maintaining an SBOM if the project distribution model benefits from it

#### 5.3 Hosted Dependency Monitoring
- [ ] **Verify** repository-native alerting such as Dependabot is enabled where available
- [ ] **Check** update automation covers the package ecosystems actually used by the project
- [ ] **Review** open dependency alerts and update PRs
- [ ] **Verify** dismissals or deferrals are documented

---

### 6. Configuration Security

#### 6.1 Configuration Files
- [ ] **Verify** sensitive configuration files have appropriate permissions
- [ ] **Check** configs do not contain plaintext secrets unless explicitly unavoidable and protected
- [ ] **Test** malformed configuration handling
- [ ] **Verify** configuration changes are validated before use
- [ ] **Check** defaults are secure

#### 6.2 Environment and Secret Injection
- [ ] **Verify** sensitive settings use environment variables, secret managers, or equivalent secure storage
- [ ] **Check** env vars are not logged or echoed in unsafe contexts
- [ ] **Test** missing or malformed secret/config handling
- [ ] **Verify** there are no hardcoded secrets in code
- [ ] **Check** operational configuration is documented clearly enough to avoid unsafe ad hoc setup

#### 6.3 Development Workflow Security
- [ ] **Verify** repo-managed hooks from `.githooks/` are installed locally when the project depends on them
- [ ] **Check** `.githooks/` is under version control and not in `.gitignore`
- [ ] **Verify** pre-commit hooks enforce linting, formatting, or secret scanning as intended
- [ ] **Check** branch protection rules enforce reviews and status checks on protected branches
- [ ] **Verify** merge strategies do not bypass required checks

---

### 7. Error Handling and Logging

#### 7.1 Error Handling
- [ ] **Verify** important failures are caught and handled intentionally
- [ ] **Check** user-visible errors do not reveal sensitive details
- [ ] **Test** representative failure scenarios
- [ ] **Verify** the system fails closed where that is the safer behavior
- [ ] **Check** unhandled exceptions do not create security or safety gaps

#### 7.2 Logging Security
- [ ] **Verify** logs exclude secrets, credentials, and protected personal data
- [ ] **Check** log files, sinks, and dashboards use appropriate access controls
- [ ] **Test** representative logs for accidental leakage
- [ ] **Verify** logging volume cannot be abused into a DoS or storage blow-up
- [ ] **Check** retention, rotation, and redaction practices

---

### 8. Network and API Security (if applicable)

#### 8.1 Transport Security
- [ ] **Verify** network traffic uses secure transport where required
- [ ] **Check** protocol and cipher choices are current enough for the deployment context
- [ ] **Test** certificate validation and failure behavior
- [ ] **Verify** insecure mixed-transport paths are absent where they matter
- [ ] **Check** security headers or equivalent controls for web delivery

#### 8.2 API Security
- [ ] **Verify** APIs require appropriate authentication and authorization
- [ ] **Check** rate limiting or abuse controls where exposure warrants it
- [ ] **Test** unauthenticated and cross-tenant access attempts
- [ ] **Verify** CORS or equivalent cross-origin policy is intentionally configured
- [ ] **Check** versioning and deprecation behavior for security-sensitive APIs

#### 8.3 SSRF Prevention (if applicable)
- [ ] **Verify** user-supplied URLs are validated against an allowlist of permitted hosts or schemes
- [ ] **Check** requests cannot target internal services, localhost, or cloud metadata endpoints (e.g., `169.254.169.254`)
- [ ] **Test** SSRF payloads including DNS rebinding, IPv6, and URL encoding bypasses
- [ ] **Verify** URL resolution and redirection following are restricted where needed
- [ ] **Check** responses from fetched URLs are not reflected unsafely to users

#### 8.4 Webhook and Third-Party Integration Security (if applicable)
- [ ] **Verify** inbound webhooks validate signatures or shared secrets before processing
- [ ] **Check** callback or redirect URLs are validated against expected origins
- [ ] **Test** replay attacks and out-of-order delivery on webhook endpoints
- [ ] **Verify** OAuth state parameters or PKCE are used to prevent CSRF in auth flows
- [ ] **Check** third-party API keys and tokens are scoped to minimum required permissions

---

### 9. Secure Coding and Cryptography

#### 9.1 Secure Coding Practices
- [ ] **Verify** deprecated or insecure APIs are not used in risky contexts
- [ ] **Check** the code follows language-appropriate secure coding practices
- [ ] **Run** static analysis or SAST tools relevant to the stack
- [ ] **Verify** security findings are triaged, not ignored
- [ ] **Check** code review expectations include security considerations

#### 9.2 Cryptography
- [ ] **Verify** standard, modern cryptographic primitives are used
- [ ] **Check** custom cryptography is absent unless strongly justified and externally reviewed
- [ ] **Test** implementation correctness where feasible
- [ ] **Verify** key generation, storage, and rotation practices are appropriate
- [ ] **Check** crypto failures degrade safely

#### 9.3 Concurrency and Race Conditions
- [ ] **Verify** TOCTOU (time-of-check-to-time-of-use) patterns are absent or mitigated in security-sensitive paths
- [ ] **Check** shared state mutations use appropriate locking or atomic operations
- [ ] **Test** concurrent access to critical resources (auth checks, balance updates, resource allocation)
- [ ] **Verify** database transactions use appropriate isolation levels for sensitive operations
- [ ] **Check** distributed or multi-process workflows handle conflicts and partial failures safely

---

### 10. Availability and DoS Resistance

#### 10.1 Resource Exhaustion
- [ ] **Verify** size, rate, and complexity limits exist where needed
- [ ] **Check** loops, recursion, parsing, and decompression are bounded
- [ ] **Test** memory, CPU, disk, and request-abuse scenarios relevant to the app
- [ ] **Verify** timeouts and cancellation paths exist for long-running operations
- [ ] **Check** cleanup occurs when work fails or is interrupted

#### 10.2 Availability and Recovery
- [ ] **Verify** the application degrades safely under load or partial failure
- [ ] **Check** single points of failure are understood and accepted or mitigated
- [ ] **Test** restart, retry, and degraded-mode behavior where relevant
- [ ] **Verify** leaks of memory, descriptors, temp files, or workers are not present
- [ ] **Check** operational recovery guidance exists for serious failures

---

## One-Time or Infrequent Setup Verification

These checks do not need to be re-proven in every scan unless the hosting model, CI/CD, or security tooling changed.

### 11. Automated Security Tooling

#### 11.1 Semgrep or Equivalent SAST

**Recommended recurring commands**
```bash
semgrep --config=p/security-audit .
semgrep --config=p/secrets .
```

**Checklist**
- [ ] **Run** the main security ruleset and review findings
- [ ] **Run** a secrets-focused ruleset or equivalent secret scanner
- [ ] **Verify** high-severity findings are triaged or documented
- [ ] **Check** SAST runs in CI/CD on pull requests or pushes
- [ ] **Consider** a project-specific ignore file for known false positives

#### 11.2 Grype, Trivy, pip-audit, npm audit, or Equivalent Dependency Scanners

**Recommended recurring commands**
```bash
grype dir:.
grype dir:. --fail-on high
```

**Checklist**
- [ ] **Run** one or more dependency scanners appropriate to the project stack
- [ ] **Verify** critical and high-severity dependency findings are triaged
- [ ] **Document** CVE, affected package, impact, and fix path for each real finding
- [ ] **Check** dependency scanning runs in CI/CD where practical
- [ ] **Consider** generating an SBOM for distributed artifacts or regulated environments

#### 11.3 Secret Detection Tooling

**Recommended recurring commands**
```bash
gitleaks detect
trufflehog filesystem .
```

**Checklist**
- [ ] **Run** at least one secret scanner and review findings
- [ ] **Verify** no real secrets remain in the current codebase
- [ ] **Check** secret scanning is part of pre-commit, CI/CD, hosted scanning, or a deliberate equivalent
- [ ] **Test** the workflow blocks or alerts on representative test secrets where feasible
- [ ] **Document** false-positive handling and any custom detector rules

#### 11.4 IaC / Container Security (if applicable)

**Recommended recurring commands**
```bash
checkov -d .
trivy config .
trivy fs .
```

**Checklist**
- [ ] **Run** IaC or container scanning if the project ships infrastructure or container assets
- [ ] **Verify** critical and high-severity misconfigurations are triaged
- [ ] **Check** scans run before deployment where practical
- [ ] **Document** any accepted risks and their rationale

#### 11.5 Type Checking for Security-Sensitive Code (if applicable)

**Recommended recurring commands**
```bash
pyright .
mypy .
```

**Checklist**
- [ ] **Run** the project's type checker(s) if type safety materially reduces security risk
- [ ] **Verify** security-sensitive paths are covered well enough to matter
- [ ] **Check** type checking runs in CI/CD if it is a project standard

#### 11.6 Hosted GitHub Security Features (if using GitHub)

**Checklist**
- [ ] **Verify** Dependabot alerts are enabled
- [ ] **Check** `.github/dependabot.yml` covers the ecosystems the repo actually uses
- [ ] **Review** open Dependabot alerts and update PRs
- [ ] **Verify** code scanning is enabled and has run successfully at least once
- [ ] **Verify** secret scanning is enabled where available
- [ ] **Verify** push protection is enabled where available
- [ ] **Check** dismissed alerts require documented justification
- [ ] **Consider** `SECURITY.md` for disclosure guidance

#### 11.7 Agent / MCP Security (if applicable)

**Recommended recurring commands**
```bash
uvx snyk-agent-scan@latest --skills
```

**Checklist**
- [ ] **Run** agent or MCP security scans if the project includes agents, MCP servers, or installable skills
- [ ] **Verify** prompt-injection, tool-poisoning, and unsafe tool-surface findings are triaged
- [ ] **Check** newly enabled tools and skills are reviewed before adoption

#### 11.8 CI/CD Pipeline Security (if applicable)

**Checklist**
- [ ] **Verify** workflow files do not inject untrusted PR inputs (e.g., `github.event.pull_request.title`) into `run:` blocks
- [ ] **Check** `permissions:` in GitHub Actions workflows follow least privilege (avoid blanket `write-all`)
- [ ] **Verify** third-party actions are pinned to full commit SHAs, not mutable tags
- [ ] **Check** self-hosted runners are hardened and ephemeral where feasible
- [ ] **Verify** secrets are not exposed in workflow logs or artifact uploads
- [ ] **Check** deployment workflows require approval gates for production environments

#### 11.9 DAST / Dynamic Testing (if applicable)

**Recommended recurring commands**
```bash
zap-cli quick-scan --self-contained --start-options '-config api.disablekey=true' <target-url>
nuclei -u <target-url> -t cves/ -t vulnerabilities/
```

**Checklist**
- [ ] **Run** dynamic application security testing against staging or test environments where the project exposes web or API surfaces
- [ ] **Verify** critical and high-severity dynamic findings are triaged
- [ ] **Check** DAST runs are included in pre-release validation where practical
- [ ] **Document** any accepted risks from dynamic scan findings

---

## Adding New Security Checks

If a scan reveals a recurring class of issue that this template does not already cover, update the master template after the scan is complete.

1. **Identify the gap**: Describe the missing vulnerability or safety concern in the timestamped scan first.
2. **Categorize it**: Add it to the most appropriate existing section, or create a new section if needed.
3. **Add concrete checks**: Write checklist items that make the issue reviewable in future scans.
4. **Document remediation guidance**: Include the expected mitigation direction or review standard.

---

## Scan Results Template

Use this structure in the timestamped scan copy.

```markdown
# Security and Safety Scan - YYYY-MM-DD HH:MM:SS

## Scan Metadata
- **Date**: YYYY-MM-DD
- **Time**: HH:MM:SS
- **Scanner**: [Name / AI Agent]
- **Previous Scan**: [Link to last scan file, or "Initial scan"]
- **Scope**: [Repo-wide / directories / feature area / release candidate]
- **Trigger**: [Pre-release / post-PR / dependency update / scheduled / incident response]
- **Files Reviewed**: [Count or estimate]
- **Duration**: [Time spent on the scan, e.g., "2 hours" or "45 minutes"]
- **Tools Used**: [Semgrep, Grype, CodeQL, Gitleaks, etc.]

## Scope Definition
- **Directories**: [List specific directories scanned, or "all"]
- **Recent PRs / Commits**: [PR numbers or commit SHAs that triggered this scan, if applicable]
- **Feature Areas**: [New auth module / API refactor / dependency upgrade / etc.]
- **Exclusions**: [Any directories, files, or areas explicitly excluded and why]

## Status Summary
- **Recurring Checklist Completed**: [Yes/Partial/No]
- **One-Time Setup Checks Reviewed**: [Yes/Partial/No]
- **Open Follow-ups**: [Count]

## Findings

### Finding N: [Brief Title]
- **Severity**: [CRITICAL/HIGH/MEDIUM/LOW]
- **Category**: [Input Validation / Auth / Dependency / Logging / etc.]
- **CWE**: [CWE-ID if applicable, e.g., CWE-79, CWE-89]
- **Location**: `path/to/file.ext` lines X-Y, workflow, config key, or external setting
- **Evidence**: [Command output, alert URL, screenshot path, or concise proof]
- **Description**: [What is wrong]
- **Attack or Failure Scenario**: [How it could be exploited or triggered]
- **Impact**: [Likely consequence]
- **Proof of Concept**: [Optional short repro, payload, or exploit sketch]
- **Recommended Remediation**: [Specific fix direction]
- **Regression Test**: [Test added or planned to prevent recurrence, or "N/A"]
- **Status**: [Open / Accepted risk / False positive / Fixed later]
- **False Positive Rationale**: [Required if status is "False positive" — explain why]

## Critical Findings
- [Repeat the full finding structure for any CRITICAL items]

## High Severity Findings
- [Repeat the full finding structure for any HIGH items]

## Medium Severity Findings
- [Repeat the full finding structure for any MEDIUM items]

## Low Severity Findings
- [Repeat the full finding structure for any LOW items]

## Dependency Vulnerabilities

### [Package Name]
- **Current Version**: X.Y.Z
- **Advisory**: [CVE / GHSA / vendor advisory]
- **Severity**: [CRITICAL/HIGH/MEDIUM/LOW]
- **Affected Surface**: [Runtime / dev-only / container / build]
- **Fixed In**: X.Y.Z
- **Remediation**: [Upgrade / pin / remove / mitigate]

## Positive Controls Observed
- [Security practice implemented well]

## Security Best Practices Review

### Positive Findings
- [List practices implemented well]

### Areas for Improvement
- [List weaknesses, hygiene gaps, or defense-in-depth opportunities]

## Follow-up Items
- [Owner or next action]

## Summary
- **Total Findings**: X
- **Critical**: X
- **High**: X
- **Medium**: X
- **Low**: X
- **Overall Posture**: [Excellent/Good/Fair/Poor]

## Recommendations Priority

### Immediate Action Required (Critical)
1. [Critical item requiring immediate action]

### Short-Term (High Priority)
1. [High-priority item to address soon]

### Medium-Term
1. [Medium-severity or structural improvement]

### Long-Term
1. [Low-severity or strategic hardening item]

## Next Steps
- [ ] Review findings with team/user
- [ ] Create remediation tickets or tasks
- [ ] Prioritize critical and high items
- [ ] Re-scan after fixes land
```

---

## Security Tools and References

### Common Tool Choices

**SAST / code scanning**
- Semgrep
- CodeQL
- Language-specific linters or analyzers such as Bandit, Brakeman, or gosec

**Dependency / container scanning**
- Grype
- Trivy
- pip-audit
- npm audit
- Dependabot

**Secret scanning**
- Gitleaks
- TruffleHog
- GitHub secret scanning

**IaC scanning**
- Checkov
- Trivy config

**DAST / dynamic testing**
- OWASP ZAP
- Nuclei
- Nikto

**Container image scanning**
- Trivy (`trivy image <image>`)
- Grype (`grype <image>`)
- Docker Scout

**SBOM generation**
- Syft
- GitHub dependency graph / SBOM export where available

### Quick-Start Commands

```bash
semgrep --config=p/security-audit .
semgrep --config=p/secrets .
grype dir:.
gitleaks detect
trufflehog filesystem .
checkov -d .
trivy fs .
trivy config .
trivy image <image-name>
grype <image-name>
```

### One-Time GitHub Setup Checklist

- [ ] Enable Dependabot alerts
- [ ] Add `.github/dependabot.yml` if version-update PRs are desired
- [ ] Enable code scanning
- [ ] Enable secret scanning and push protection where available
- [ ] Add CI jobs for SAST and dependency scanning
- [ ] Upload SARIF where unified hosted alerting is useful

### Extended Setup Examples

Use these when you want this template to double as a compact setup reference rather than only a scan checklist.

**Semgrep CI example**
```yaml
# .github/workflows/semgrep.yml
name: Semgrep
on: [push, pull_request]
jobs:
  semgrep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: semgrep/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/secrets
```

**Grype CI example**
```yaml
# .github/workflows/grype.yml
name: Grype Vulnerability Scan
on: [push, pull_request]
jobs:
  grype:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anchore/scan-action@v3
        with:
          path: "."
          fail-build: true
          severity-cutoff: high
```

**Dependabot example**
```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

**CodeQL example**
```yaml
# .github/workflows/codeql.yml
name: CodeQL
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
```

**Secret scanning examples**
```bash
gitleaks detect --format sarif --report-path gitleaks-results.sarif
trufflehog filesystem . --json
```

### References

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE Top 25: https://cwe.mitre.org/top25/
- SANS Top 25: https://www.sans.org/top25-software-errors/
- Semgrep docs: https://semgrep.dev/docs/
- Grype docs: https://github.com/anchore/grype
- GitHub code security docs: https://docs.github.com/en/code-security

---

## Notes

- Run scans on the recommended cadence: before releases, after significant PRs, after dependency updates, and at least monthly.
- Use multiple layers: manual review plus automated scanning.
- Record evidence for every real finding and every dismissal.
- Tailor the tooling to the stack; not every project needs every tool.
- If this template misses a recurring class of issue, add it after the scan.
- Track scan-over-scan trends: compare finding counts and categories with previous scans to measure security posture over time.
