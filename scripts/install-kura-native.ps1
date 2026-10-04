# Prepare a current-user Chrome native host. No watcher or service is installed.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-p]{32}\z')][string]$ExtensionId,
    [Parameter(Mandatory)][string]$PythonExe,
    [Parameter(Mandatory)][string]$InstallRoot,
    [Parameter(Mandatory)][string]$CaptureRoot,
    [Parameter(Mandatory)][string]$BrainRoot,
    [Parameter(Mandatory)][string]$PrivateRoot,
    [switch]$Register
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') { throw 'This installer supports Windows Chrome only.' }
$repoSource = Join-Path (Split-Path -Parent $PSScriptRoot) 'src'
$nativeRoots = @($CaptureRoot, $BrainRoot, $PrivateRoot) | ForEach-Object {
    if (-not (Test-Path -LiteralPath $_ -PathType Container)) { throw 'Vault roots must already exist.' }
    (Resolve-Path -LiteralPath $_).ProviderPath
}
for ($i = 0; $i -lt $nativeRoots.Count; $i++) {
    for ($j = $i + 1; $j -lt $nativeRoots.Count; $j++) {
        $left = $nativeRoots[$i].TrimEnd('\')
        $right = $nativeRoots[$j].TrimEnd('\')
        if ($left -eq $right -or $left.StartsWith($right + '\', [StringComparison]::OrdinalIgnoreCase) -or $right.StartsWith($left + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Capture, brain and private roots must not overlap.' }
    }
}
$nativePython = (Resolve-Path -LiteralPath $PythonExe).ProviderPath
if (-not (Test-Path -LiteralPath $nativePython -PathType Leaf) -or [IO.Path]::GetExtension($nativePython) -ne '.exe') { throw 'Select an existing Python executable.' }
$nativeInstall = [IO.Path]::GetFullPath($InstallRoot)
foreach ($vaultRoot in $nativeRoots) {
    if ($nativeInstall -eq $vaultRoot -or $nativeInstall.StartsWith($vaultRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or $vaultRoot.StartsWith($nativeInstall.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep native host files separate from every vault root.' }
}
foreach ($nativePath in @($nativePython, $nativeInstall, $repoSource)) {
    if ($nativePath -match '[%!*&|<>^"\r\n]') { throw 'Launcher paths contain unsupported command characters.' }
}
$configPath = Join-Path $nativeInstall 'config.json'
$launcherPath = Join-Path $nativeInstall 'kura-intake.cmd'
$manifestPath = Join-Path $nativeInstall 'ai.frankx.kura_intake.json'
$configuration = [ordered]@{version=1;extension_id=$ExtensionId;capture_root=$nativeRoots[0];brain_root=$nativeRoots[1];private_root=$nativeRoots[2]} | ConvertTo-Json
$manifest = [ordered]@{name='ai.frankx.kura_intake';description='Kura local second-brain intake';path=$launcherPath;type='stdio';allowed_origins=@("chrome-extension://$ExtensionId/")} | ConvertTo-Json
$pinnedSource = Join-Path $nativeInstall 'lib'
$launcher = "@echo off`r`nchcp 65001 >nul`r`nset `"PYTHONPATH=$pinnedSource`"`r`n`"$nativePython`" -P -m sbo_ingestion.native_host --config `"$configPath`" %*`r`n"
$preparedFiles = @(@{path=$configPath;value=$configuration},@{path=$manifestPath;value=$manifest},@{path=$launcherPath;value=$launcher})
$packageSource = Join-Path $repoSource 'sbo_ingestion'
$packageFiles = Get-ChildItem -LiteralPath $packageSource -Recurse -File -Filter '*.py'
$sourceDigests = [ordered]@{}
foreach ($packageFile in $packageFiles) {
    if ($packageFile.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Pinned source files must be regular files.' }
    $relativeSource = $packageFile.FullName.Substring($packageSource.Length).TrimStart('\')
    $snapshotPath = Join-Path (Join-Path $pinnedSource 'sbo_ingestion') $relativeSource
    $sourceDigests[$relativeSource] = (Get-FileHash -LiteralPath $packageFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Test-Path -LiteralPath $snapshotPath) -and (Get-FileHash -LiteralPath $snapshotPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceDigests[$relativeSource]) { throw 'Existing pinned source differs. Preserve it and reconcile explicitly.' }
}
$preparedFiles += @{path=(Join-Path $nativeInstall 'source-sha256.json');value=($sourceDigests | ConvertTo-Json)}
foreach ($checkedPath in @($nativeInstall, $nativeRoots[0], $nativeRoots[1], $nativeRoots[2])) {
    $ancestor = $checkedPath
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and (Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Host and vault paths must not traverse junctions or symlinks.' }
        $parentPath = Split-Path -Parent $ancestor
        if ($parentPath -eq $ancestor) { break }
        $ancestor = $parentPath
    }
}
$registryPath = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\ai.frankx.kura_intake'
if ($Register -and (Test-Path -LiteralPath $registryPath)) {
    if ((Get-Item -LiteralPath $registryPath).GetValue('') -ne $manifestPath) { throw 'A different host is registered. Preserve it and reconcile explicitly.' }
}
foreach ($prepared in $preparedFiles) {
    if ((Test-Path -LiteralPath $prepared.path) -and (Get-Content -LiteralPath $prepared.path -Raw -Encoding UTF8).Trim() -ne $prepared.value.Trim()) { throw 'Existing host files differ. Preserve them and reconcile explicitly.' }
}
New-Item -ItemType Directory -Path $nativeInstall -Force | Out-Null
foreach ($packageFile in $packageFiles) {
    $relativeSource = $packageFile.FullName.Substring($packageSource.Length).TrimStart('\')
    $snapshotPath = Join-Path (Join-Path $pinnedSource 'sbo_ingestion') $relativeSource
    if (-not (Test-Path -LiteralPath $snapshotPath)) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $snapshotPath) -Force | Out-Null
        Copy-Item -LiteralPath $packageFile.FullName -Destination $snapshotPath
    }
    if ((Get-FileHash -LiteralPath $snapshotPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceDigests[$relativeSource]) { throw 'Source changed during preparation; reconcile the preserved snapshot.' }
}
foreach ($prepared in $preparedFiles) {
    if (-not (Test-Path -LiteralPath $prepared.path)) { [IO.File]::WriteAllText($prepared.path, $prepared.value, [Text.UTF8Encoding]::new($false)) }
}
if ($Register) {
    New-Item -Path $registryPath -Force | Out-Null
    Set-Item -LiteralPath $registryPath -Value $manifestPath
    Write-Output '[sbo] Current-user Chrome host registered. It runs only when Kura connects.'
} else {
    Write-Output '[sbo] Host files prepared. Use -Register to register this exact configuration.'
}
