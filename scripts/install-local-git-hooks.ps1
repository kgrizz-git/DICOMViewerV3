<#
.SYNOPSIS
Points Git at repository-managed hooks so they activate automatically.

.DESCRIPTION
Sets core.hooksPath to .githooks/ so local pre-commit and pre-push security
gates run directly from version-controlled sources. No file copying needed.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    throw "Not a git repository: $repoRoot"
}

if (-not (Test-Path (Join-Path $repoRoot ".githooks"))) {
    throw "Source hooks directory not found at .githooks/"
}

$chmod = Get-Command chmod -ErrorAction SilentlyContinue
if ($null -ne $chmod) {
    & $chmod +x (Join-Path $repoRoot ".githooks/pre-commit") (Join-Path $repoRoot ".githooks/pre-push")
}

git -C $repoRoot config core.hooksPath .githooks
Write-Host "core.hooksPath set to .githooks - hooks are active." -ForegroundColor Green
