<#
.SYNOPSIS
Export Dependabot alerts for a GitHub repository.

.DESCRIPTION
Uses GitHub CLI (`gh`) to query Dependabot alerts from the GitHub REST API,
then writes normalized JSON and CSV outputs locally.

Requires:
- GitHub CLI installed (`gh`)
- Authenticated session (`gh auth login`)
- Token permissions sufficient for Dependabot alerts (Security Events read)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Repo,

    [Parameter(Mandatory = $false)]
    [ValidateSet("open", "fixed", "dismissed", "auto_dismissed")]
    [string]$State = "open",

    [Parameter(Mandatory = $false)]
    [string]$OutputJson = "dev-docs/security/dependabot-alerts.json",

    [Parameter(Mandatory = $false)]
    [string]$OutputCsv = "dev-docs/security/dependabot-alerts.csv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-GhExecutable {
    $fromPath = Get-Command gh -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $candidates = @(
        "C:\Program Files\GitHub CLI\gh.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\GitHub CLI\gh.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Get-RepoSlugFromGit {
    $origin = (git remote get-url origin 2>$null)
    if (-not $origin) {
        throw "Could not resolve 'origin' remote URL. Pass -Repo owner/name explicitly."
    }

    if ($origin -match "github\.com[:/](?<slug>[^/]+/[^/.]+)(\.git)?$") {
        return $Matches["slug"]
    }
    throw "Could not parse GitHub repo slug from origin URL: $origin"
}

function Ensure-Directory([string]$path) {
    $parent = Split-Path -Path $path -Parent
    if (-not [string]::IsNullOrWhiteSpace($parent) -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

function Convert-AlertsToRows($alerts) {
    $rows = @()
    foreach ($alert in $alerts) {
        $rows += [PSCustomObject]@{
            number                = $alert.number
            state                 = $alert.state
            ecosystem             = $alert.dependency.package.ecosystem
            package               = $alert.dependency.package.name
            manifest_path         = $alert.dependency.manifest_path
            severity              = $alert.security_advisory.severity
            ghsa_id               = $alert.security_advisory.ghsa_id
            cve_id                = (($alert.security_advisory.cve_id | Out-String).Trim())
            summary               = $alert.security_advisory.summary
            created_at            = $alert.created_at
            updated_at            = $alert.updated_at
            fixed_at              = $alert.fixed_at
            dismissed_at          = $alert.dismissed_at
            html_url              = $alert.html_url
            dependency_scope      = $alert.dependency.scope
            first_patched_version = $alert.security_vulnerability.first_patched_version.identifier
            vulnerable_version    = $alert.security_vulnerability.vulnerable_version_range
        }
    }
    return $rows
}

try {
    $ghExe = Get-GhExecutable
    if (-not $ghExe) {
        throw "GitHub CLI not found. Install first (e.g., winget install GitHub.cli)."
    }

    $authCheck = & $ghExe auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI is not authenticated. Run: gh auth login"
    }

    if ([string]::IsNullOrWhiteSpace($Repo)) {
        $Repo = Get-RepoSlugFromGit
    }

    # Dependabot alerts REST API uses Link-header pagination only; `page=` returns HTTP 400.
    # `gh api --paginate` follows `rel="next"` until all pages are merged into one JSON array.
    $endpoint = "/repos/$Repo/dependabot/alerts?state=$State&per_page=100"
    $raw = & $ghExe api --paginate `
        -H "Accept: application/vnd.github+json" `
        -H "X-GitHub-Api-Version: 2022-11-28" `
        $endpoint

    if ($LASTEXITCODE -ne 0) {
        throw "Failed querying Dependabot alerts from endpoint: $endpoint"
    }

    $parsed = $raw | ConvertFrom-Json
    if ($null -eq $parsed) {
        $alerts = @()
    } elseif ($parsed -is [System.Array]) {
        $alerts = @($parsed)
    } else {
        $alerts = @($parsed)
    }

    Ensure-Directory -path $OutputJson
    Ensure-Directory -path $OutputCsv

    $alerts | ConvertTo-Json -Depth 50 | Out-File -FilePath $OutputJson -Encoding utf8
    $rows = Convert-AlertsToRows -alerts $alerts
    $rows | Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding utf8

    Write-Host "Export complete for repo '$Repo' (state=$State)." -ForegroundColor Green
    Write-Host "Alerts exported: $($alerts.Count)"
    Write-Host "JSON: $OutputJson"
    Write-Host "CSV : $OutputCsv"
}
catch {
    Write-Host "Dependabot export failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
