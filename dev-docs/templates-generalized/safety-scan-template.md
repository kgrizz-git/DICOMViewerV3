# Security and Safety Scan Template - [PROJECT_NAME]

**Template Version**: 2.0  
**Last Updated**: 2026-02-18

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
- [ ] **Test**: Run dependency vulnerability scanner (npm audit, pip-audit, etc.)
- [ ] **Verify**: No known vulnerabilities in current dependency versions
- [ ] **Check**: Dependencies are regularly updated

#### 5.2 Supply Chain Security
- [ ] **Verify**: Dependency integrity is verified (checksums, signatures)
- [ ] **Check**: No dependencies from untrusted or compromised sources
- [ ] **Test**: Review dependency tree for suspicious packages
- [ ] **Verify**: Build process is secure and reproducible
- [ ] **Check**: No malicious code in dependencies (manual review of critical deps)

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
- **Security Tools Used**: [List tools: SAST scanners, dependency checkers, etc.]

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
- Python: bandit, safety
- JavaScript/Node.js: npm audit, eslint-plugin-security
- Java: SpotBugs, FindSecBugs
- Ruby: brakeman
- Go: gosec
- General: SonarQube, Semgrep

**Dependency Scanning**:
- Python: pip-audit, safety
- JavaScript/Node.js: npm audit, yarn audit, Snyk
- Ruby: bundler-audit
- Java: OWASP Dependency-Check
- General: Snyk, WhiteSource, Dependabot

**Dynamic Analysis (DAST)** (if applicable):
- OWASP ZAP
- Burp Suite
- Nikto

### Security Resources
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE Top 25: https://cwe.mitre.org/top25/
- SANS Top 25: https://www.sans.org/top25-software-errors/
- Security best practices for your language/framework

---

## Notes

- **Regular Scans**: Perform security scans regularly (weekly/monthly) and after significant code changes
- **Automated Scanning**: Integrate security scanners into CI/CD pipeline
- **Manual Review**: Automated tools don't catch everything; manual code review is essential
- **Stay Updated**: Keep informed about new vulnerabilities and security best practices
- **Defense in Depth**: Implement multiple layers of security
- **Assume Breach**: Design systems assuming attackers will get in; limit damage they can do

---
