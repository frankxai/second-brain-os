# One interactive processing pass. This does not install a watcher or schedule.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CaptureRoot,
    [Parameter(Mandatory)][string]$BrainRoot,
    [Parameter(Mandatory)][string]$PrivateRoot,
    [string]$PythonExe = 'python'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
foreach ($path in @($CaptureRoot, $BrainRoot, $PrivateRoot)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Folder does not exist: $path" }
}
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repo 'src'
    & $PythonExe -m sbo_ingestion.ingest $CaptureRoot --brain-root $BrainRoot --private-root $PrivateRoot --mode agent
    if ($LASTEXITCODE -ne 0) { throw "Capture processing failed. Completed items have receipts; rerun after fixing the reported input." }
    $receiptRoot = Join-Path $PrivateRoot '_distill/kura'
    $refreshCount = 0
    if (Test-Path -LiteralPath $receiptRoot -PathType Container) {
        foreach ($receipt in Get-ChildItem -LiteralPath $receiptRoot -Filter '*.json' -File) {
            $state = Get-Content -LiteralPath $receipt.FullName -Raw | ConvertFrom-Json
            if ($state.refresh_pending -eq $true) { $refreshCount++ }
        }
    }
    Write-Output "[sbo] $refreshCount preserved note(s) have changed-source receipts awaiting review."
    & $PythonExe -m sbo_ingestion.distill list --brain-root $BrainRoot --limit 10
    if ($LASTEXITCODE -ne 0) { throw 'Could not list pending summaries.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
