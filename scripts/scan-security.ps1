# Security Scanner PowerShell Wrapper
# Quick access to security scanning tools
# 
# Usage:
#   .\scripts\scan-security.ps1                  # Run all checks
#   .\scripts\scan-security.ps1 -Semgrep         # Run only Semgrep
#   .\scripts\scan-security.ps1 -Secrets         # Run only secrets checks
#   .\scripts\scan-security.ps1 -Verbose         # Verbose output
#   .\scripts\scan-security.ps1 -Report          # JSON report

param(
    [switch]$All,
    [switch]$Semgrep,
    [switch]$Secrets,
    [switch]$DebugFlags,
    [switch]$Deps,
    [switch]$Verbose,
    [switch]$Report,
    [switch]$Quick,
    [switch]$Help
)

$ErrorActionPreference = "Continue"

function Write-Header {
    param([string]$Text)
    Write-Host "`n$('='*60)" -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan -NoNewline
    Write-Host "$('='*60)" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Text)
    Write-Host "✓ $Text" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Text)
    Write-Host "✗ $Text" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Text)
    Write-Host "⚠ $Text" -ForegroundColor Yellow
}

if ($Help) {
    Write-Host @"
Security Scanner - Run security checks locally

USAGE:
    .\scripts\scan-security.ps1 [OPTIONS]

OPTIONS:
    -All              Run all checks (default)
    -Semgrep          Run only Semgrep SAST
    -Secrets          Run only secrets detection (Detect-secrets + TruffleHog)
    -DebugFlags       Check debug flags only
    -Deps             Run pip-audit dependency scan
    -Quick            Run fast checks only (Semgrep + Debug flags)
    -Verbose          Detailed output
    -Report           Output JSON report
    -Help             Show this help

EXAMPLES:
    # Quick check before commit
    .\scripts\scan-security.ps1 -Quick

    # Full scan before push
    .\scripts\scan-security.ps1 -All -Verbose

    # Only check for hardcoded secrets
    .\scripts\scan-security.ps1 -Secrets

    # JSON output for CI/CD
    .\scripts\scan-security.ps1 -All -Report
"@
    exit 0
}

# Resolve project Python from common venv locations
$pythonExe = $null
$activateScript = $null
if (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonExe = ".\.venv\Scripts\python.exe"
    $activateScript = ".\.venv\Scripts\Activate.ps1"
} elseif (Test-Path ".\venv\Scripts\python.exe") {
    $pythonExe = ".\venv\Scripts\python.exe"
    $activateScript = ".\venv\Scripts\Activate.ps1"
}

if (-not $pythonExe) {
    Write-Error-Custom "No project virtual environment found (.venv or venv)."
    exit 1
}

if ($env:VIRTUAL_ENV -eq $null -and (Test-Path $activateScript)) {
    Write-Warning-Custom "Activating virtual environment..."
    & $activateScript
}

# Build the Python command
$pythonCmd = "$pythonExe scripts\run_security_scan.py"

if ($All -or (-not $Semgrep -and -not $Secrets -and -not $DebugFlags -and -not $Quick)) {
    $pythonCmd += " --all"
}
elseif ($Quick) {
    $pythonCmd += " --semgrep --debug-flags"
}
else {
    if ($Semgrep) { $pythonCmd += " --semgrep" }
    if ($Secrets) { $pythonCmd += " --secrets" }
    if ($DebugFlags) { $pythonCmd += " --debug-flags" }
    if ($Deps) { $pythonCmd += " --deps" }
}

if ($Verbose) { $pythonCmd += " --verbose" }
if ($Report) { $pythonCmd += " --report" }

Write-Header "Security Scanner"
Write-Host "Running: $pythonCmd`n" -ForegroundColor DarkGray

# Execute the scan
Invoke-Expression $pythonCmd
$scanExitCode = $LASTEXITCODE

# Show result
Write-Host ""
if ($scanExitCode -eq 0) {
    Write-Success "Scan completed successfully"
} else {
    Write-Error-Custom "Scan completed with exit code: $scanExitCode"
}

exit $scanExitCode
