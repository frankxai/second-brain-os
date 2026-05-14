<#
.SYNOPSIS
  Verify the SBO privacy hardening checklist for a private vault.

.PARAMETER PrivateVault
  Path to the private/ vault root.

.NOTES
  Two modes:
    strict   (default)        — all 6 checks must pass; for a real install
    template (SBO_VERIFY_MODE=template env var) — only vault-shape checks.
                                Skips Windows Search exclusion (machine-level).
                                Used by CI on the template skeleton.

.EXAMPLE
  pwsh ./scripts/verify-privacy.ps1 -PrivateVault "$HOME/second-brain/private"

.EXAMPLE
  $env:SBO_VERIFY_MODE = 'template'; pwsh ./scripts/verify-privacy.ps1 -PrivateVault templates/private-vault-skeleton
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$PrivateVault
)

$ErrorActionPreference = "Stop"
$script:fail = 0
$script:pass = 0
$script:skipped = 0
$Mode = if ($env:SBO_VERIFY_MODE) { $env:SBO_VERIFY_MODE } else { "strict" }

function Check {
  param([string]$Name, [scriptblock]$Test, [switch]$MachineLevel)
  Write-Host -NoNewline ("  [{0}] " -f $Name)
  if ($MachineLevel -and $Mode -eq "template") {
    Write-Host "SKIP (machine-level; mode=template)" -ForegroundColor Yellow
    $script:skipped++
    return
  }
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

Write-Host "`nSBO Privacy Verification (mode: $Mode)`n" -ForegroundColor Cyan
Write-Host "Vault: $PrivateVault`n"

if (-not (Test-Path $PrivateVault)) {
  Write-Host "[error] private vault not found at $PrivateVault" -ForegroundColor Red
  exit 2
}

Check "1. Windows Search exclusion" -MachineLevel {
  # Machine-level: Windows Search exclusion lives in registry under
  # HKLM:\SOFTWARE\Microsoft\Windows Search\CrawlScopeManager.
  # Programmatic verification is brittle across Windows builds — the canonical
  # check is documented manual setup. Strict mode flags this for user review;
  # template mode (CI) skips it.
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
Write-Host "Pass:    $script:pass" -ForegroundColor Green
if ($script:skipped -gt 0) { Write-Host "Skipped: $script:skipped" -ForegroundColor Yellow }
Write-Host "Fail:    $script:fail" -ForegroundColor $(if ($script:fail -eq 0) { "Green" } else { "Red" })
Write-Host ""
if ($script:fail -gt 0) {
  Write-Host "Privacy verification FAILED. Address the issues above." -ForegroundColor Red
  exit 1
}
Write-Host "Privacy verification PASSED." -ForegroundColor Green
