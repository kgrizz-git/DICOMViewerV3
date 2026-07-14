<#
.SYNOPSIS
Installs the official TruffleHog v3 Windows binary from GitHub releases.

.DESCRIPTION
Downloads the selected TruffleHog release archive for Windows (amd64 or arm64),
extracts `trufflehog.exe` into a local tools directory, and optionally adds
that directory to the current user's PATH.

This script is intended for local development setup so the CLI behavior is
closer to CI (which uses the TruffleHog v3 action/binary line).

.PARAMETER Version
Release tag to install, e.g. v3.94.0.

.PARAMETER InstallDir
Directory where trufflehog.exe will be installed.

.PARAMETER AddToUserPath
If provided, appends InstallDir to the current user's PATH if missing.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Version = "v3.94.0",

    [Parameter(Mandatory = $false)]
    [string]$InstallDir = "$PSScriptRoot\..\tools\trufflehog-v3",

    [Parameter(Mandatory = $false)]
    [switch]$AddToUserPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$arch = if ($env:PROCESSOR_ARCHITECTURE -match "ARM64") { "arm64" } else { "amd64" }
$archiveName = "trufflehog_{0}_windows_{1}.tar.gz" -f $Version.TrimStart("v"), $arch
$downloadUrl = "https://github.com/trufflesecurity/trufflehog/releases/download/$Version/$archiveName"
$archivePath = Join-Path $env:TEMP $archiveName
$extractDir = Join-Path $env:TEMP ("trufflehog-extract-" + [Guid]::NewGuid().ToString("N"))

Write-Host "Installing TruffleHog $Version" -ForegroundColor Cyan
Write-Host "Download URL: $downloadUrl"
Write-Host "Install dir : $resolvedInstallDir"

New-Item -ItemType Directory -Force -Path $resolvedInstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath
    tar -xzf $archivePath -C $extractDir

    $exe = Get-ChildItem -Path $extractDir -Filter "trufflehog.exe" -Recurse | Select-Object -First 1
    if (-not $exe) {
        throw "trufflehog.exe not found in archive."
    }

    $targetExe = Join-Path $resolvedInstallDir "trufflehog.exe"
    Copy-Item -Path $exe.FullName -Destination $targetExe -Force

    Write-Host "Installed: $targetExe" -ForegroundColor Green
    & $targetExe --version

    if ($AddToUserPath) {
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $parts = @()
        if (-not [string]::IsNullOrWhiteSpace($userPath)) {
            $parts = $userPath.Split(";")
        }

        if ($parts -notcontains $resolvedInstallDir) {
            $newPath = ($parts + $resolvedInstallDir | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ";"
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "Added to User PATH. Restart terminal to use `trufflehog` globally." -ForegroundColor Yellow
        } else {
            Write-Host "Install directory already exists in User PATH." -ForegroundColor Yellow
        }
    } else {
        Write-Host "PATH unchanged. Run via full path or add manually." -ForegroundColor Yellow
    }
}
finally {
    if (Test-Path $archivePath) {
        Remove-Item -Path $archivePath -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path $extractDir) {
        Remove-Item -Path $extractDir -Force -Recurse -ErrorAction SilentlyContinue
    }
}
