<#
.SYNOPSIS
  SBO interactive setup for Windows. Creates vault pair from skeletons + emits
  Claude Desktop config snippet.

.EXAMPLE
  pwsh ./scripts/setup.ps1
#>

[CmdletBinding()]
param(
  [string]$VaultParent = "$HOME/second-brain"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path "$PSScriptRoot/..").Path

Write-Host "`nSecond Brain OS -- Setup`n" -ForegroundColor Cyan

# 1. Create vault pair
$brainPath = Join-Path $VaultParent "brain"
$privatePath = Join-Path $VaultParent "private"

if ((Test-Path $brainPath) -or (Test-Path $privatePath)) {
  Write-Host "Vault already exists at $VaultParent. Aborting to avoid overwrite." -ForegroundColor Yellow
  exit 1
}

Write-Host "Creating brain/ at $brainPath ..."
Copy-Item -Recurse "$repoRoot/templates/brain-vault-skeleton" $brainPath
Write-Host "Creating private/ at $privatePath ..."
Copy-Item -Recurse "$repoRoot/templates/private-vault-skeleton" $privatePath

# 2. Run privacy verification on the new private vault
Write-Host "`nRunning privacy verification ..."
& "$repoRoot/scripts/verify-privacy.ps1" -PrivateVault $privatePath

# 3. Emit Claude Desktop config snippet
$snippet = @"
{
  "mcpServers": {
    "sbo-obsidian": {
      "command": "uvx",
      "args": ["mcp-obsidian"],
      "env": {
        "OBSIDIAN_API_KEY": "<from Local REST API plugin in brain vault>",
        "OBSIDIAN_HOST": "https://localhost:27124"
      }
    }
  }
}
"@

Write-Host "`nNext steps:`n" -ForegroundColor Cyan
Write-Host "1. Open Obsidian and add your new brain vault at $brainPath"
Write-Host "2. Install community plugins (Obsidian will prompt -- confirm Local REST API + 9 others)"
Write-Host "3. In Local REST API plugin settings: copy the API key"
Write-Host "4. Add this snippet to your Claude Desktop config:`n"
Write-Host $snippet -ForegroundColor DarkGray
Write-Host "`n5. Add your private vault at $privatePath as a SEPARATE vault"
Write-Host "6. Request your Claude.ai data export: Settings > Privacy > Export data"
Write-Host "   (delivered via email within 24h)"
Write-Host "7. Request your ChatGPT export: Settings > Data Controls > Export"
Write-Host "8. When exports arrive, run:`n"
Write-Host "   `$env:SBO_BRAIN_VAULT_ROOT='$brainPath'" -ForegroundColor DarkGray
Write-Host "   `$env:SBO_PRIVATE_VAULT_ROOT='$privatePath'" -ForegroundColor DarkGray
Write-Host "   `$env:ANTHROPIC_API_KEY='<your-key>'" -ForegroundColor DarkGray
Write-Host "   sbo-ingest path/to/conversations.json`n" -ForegroundColor DarkGray
Write-Host "Setup complete." -ForegroundColor Green
