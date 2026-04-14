<#
.SYNOPSIS
Installs repository-managed local Git hooks.

.DESCRIPTION
Copies hooks from .githooks/ into .git/hooks/ so local pre-commit and pre-push
security gates run automatically. Existing hooks with the same name are backed up.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourceHooksDir = Join-Path $repoRoot ".githooks"
$targetHooksDir = Join-Path $repoRoot ".git/hooks"

if (-not (Test-Path $targetHooksDir)) {
    throw "Git hooks directory not found at '$targetHooksDir'. Are you in a git repo?"
}

if (-not (Test-Path $sourceHooksDir)) {
    throw "Source hooks directory not found at '$sourceHooksDir'."
}

$hookNames = @("pre-commit", "pre-push")
foreach ($hookName in $hookNames) {
    $sourcePath = Join-Path $sourceHooksDir $hookName
    $targetPath = Join-Path $targetHooksDir $hookName

    if (-not (Test-Path $sourcePath)) {
        throw "Expected hook file missing: $sourcePath"
    }

    if (Test-Path $targetPath) {
        $backupPath = "$targetPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -Path $targetPath -Destination $backupPath -Force
        Write-Host "Backed up existing $hookName to $backupPath" -ForegroundColor Yellow
    }

    Copy-Item -Path $sourcePath -Destination $targetPath -Force
    Write-Host "Installed $hookName hook" -ForegroundColor Green
}

Write-Host ""
Write-Host "Local Git hooks are installed." -ForegroundColor Cyan
Write-Host "Hooks copied from: $sourceHooksDir"
Write-Host "Hooks active in:   $targetHooksDir"
