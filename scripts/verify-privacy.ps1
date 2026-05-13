<#
.SYNOPSIS
  Verify the 6-item SBO privacy hardening checklist for a private vault.

.PARAMETER PrivateVault
  Path to the private/ vault root.

.EXAMPLE
  pwsh ./scripts/verify-privacy.ps1 -PrivateVault "$HOME/second-brain/private"
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$PrivateVault
)

$ErrorActionPreference = "Stop"
$script:fail = 0
$script:pass = 0

function Check {
  param([string]$Name, [scriptblock]$Test)
  Write-Host -NoNewline ("  [{0}] " -f $Name)
  try {
    $result = & $Test
    if ($result -eq $true) {
      Write-Host "PASS" -ForegroundColor Green
      $script:pass++
    } else {
      Write-Host ("FAIL -- " + $result) -ForegroundColor Red
      $script:fail++
    }
  } catch {
    Write-Host ("ERROR -- " + $_.Exception.Message) -ForegroundColor Red
    $script:fail++
  }
}

Write-Host "`nSBO Privacy Verification`n" -ForegroundColor Cyan
Write-Host "Vault: $PrivateVault`n"

if (-not (Test-Path $PrivateVault)) {
  Write-Host "[error] private vault not found at $PrivateVault" -ForegroundColor Red
  exit 2
}

Check "1. Windows Search exclusion" {
  # Best-effort check -- Windows Search exclusion paths live in registry keys depending on configuration mode.
  # Programmatic verification varies; documented manual check is canonical.
  return "manual verification needed: Settings > Search > Searching Windows > Excluded folders should contain $PrivateVault"
}

Check "2. macOS Spotlight exclusion" {
  if ($IsMacOS) {
    return (Test-Path (Join-Path $PrivateVault ".metadata_never_index"))
  }
  return $true  # N/A on non-macOS
}

Check "3. Cloud-backup exclusion (OneDrive)" {
  $oneDrivePath = $env:OneDrive
  if ($oneDrivePath -and $PrivateVault.StartsWith($oneDrivePath, [System.StringComparison]::OrdinalIgnoreCase)) {
    return "private vault is inside OneDrive sync path -- MOVE IT OUTSIDE"
  }
  return $true
}

Check "4. Obsidian Sync prohibition" {
  $marker = Join-Path $PrivateVault ".obsidian-no-sync"
  if (-not (Test-Path $marker)) {
    return "marker file missing -- privacy contract violated"
  }
  return $true
}

Check "5. Local REST API plugin prohibition" {
  $pluginPath = Join-Path $PrivateVault ".obsidian/plugins/obsidian-local-rest-api"
  if (Test-Path $pluginPath) {
    return "Local REST API plugin installed in private vault -- REMOVE IMMEDIATELY"
  }
  return $true
}

Check "6. Smart Connections / Text Generator prohibition" {
  $smart = Join-Path $PrivateVault ".obsidian/plugins/smart-connections"
  $textgen = Join-Path $PrivateVault ".obsidian/plugins/text-generator-obsidian"
  if ((Test-Path $smart) -or (Test-Path $textgen)) {
    return "LLM-calling plugin installed in private vault -- REMOVE IMMEDIATELY"
  }
  return $true
}

Write-Host ""
Write-Host "Pass: $script:pass" -ForegroundColor Green
Write-Host "Fail: $script:fail" -ForegroundColor $(if ($script:fail -eq 0) { "Green" } else { "Red" })
Write-Host ""
if ($script:fail -gt 0) {
  Write-Host "Privacy verification FAILED. Address the issues above." -ForegroundColor Red
  exit 1
}
Write-Host "Privacy verification PASSED." -ForegroundColor Green
