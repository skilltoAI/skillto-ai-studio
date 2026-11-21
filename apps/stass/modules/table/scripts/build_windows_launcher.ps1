[CmdletBinding()]
param(
    [string]$PythonExecutable,
    [string]$ServiceScript,
    [string]$WorkingDirectory,
    [string]$DataRoot = (Join-Path $env:USERPROFILE 'skillto-table-data'),
    [string]$InstalledSkill = (Join-Path $env:USERPROFILE '.codex\skills\skillto-ai-studio-table'),
    [switch]$Install,
    [switch]$Desktop
)
$ErrorActionPreference = 'Stop'
$skillRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectRoot = [IO.Path]::GetFullPath((Join-Path $skillRoot '..\..'))
if (-not $WorkingDirectory) { $WorkingDirectory = $projectRoot }
if (-not $PythonExecutable) { $PythonExecutable = Join-Path $WorkingDirectory '.venv\Scripts\python.exe' }
if (-not $ServiceScript) { $ServiceScript = Join-Path $WorkingDirectory 'runtime\pet_refresh_20261028\serve_local.py' }
foreach ($required in @($PythonExecutable, $ServiceScript, $WorkingDirectory, $DataRoot)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing dependency: $required" }
}
$go = (Get-Command go -ErrorAction Stop).Source
$sourceDir = Join-Path $PSScriptRoot 'windows'
$exePath = Join-Path $skillRoot 'SkillToTable.exe'
$oldGOOS = $env:GOOS
$oldGOARCH = $env:GOARCH
$oldCGO = $env:CGO_ENABLED
try {
    $env:GOOS = 'windows'
    $env:GOARCH = 'amd64'
    $env:CGO_ENABLED = '0'
    Push-Location -LiteralPath $sourceDir
    try {
        $iconResource = Join-Path $sourceDir 'rsrc_windows_amd64.syso'
        $iconInputs = @((Join-Path $sourceDir 'winres\winres.json'), (Join-Path $sourceDir 'winres\logo.png'))
        $regenerateIcon = -not (Test-Path -LiteralPath $iconResource)
        if (-not $regenerateIcon) {
            $resourceTime = (Get-Item -LiteralPath $iconResource).LastWriteTimeUtc
            foreach ($inputFile in $iconInputs) {
                if ((Get-Item -LiteralPath $inputFile).LastWriteTimeUtc -gt $resourceTime) { $regenerateIcon = $true }
            }
        }
        if ($regenerateIcon) {
            & $go run github.com/tc-hib/go-winres@v0.3.3 make --in winres/winres.json --arch amd64 --out rsrc
            if ($LASTEXITCODE -ne 0) { throw 'Windows icon resource generation failed' }
        }
        & $go fmt .
        if ($LASTEXITCODE -ne 0) { throw 'go fmt failed' }
        & $go vet .
        if ($LASTEXITCODE -ne 0) { throw 'go vet failed' }
        & $go build -trimpath -ldflags '-H=windowsgui -s -w' -o $exePath .
        if ($LASTEXITCODE -ne 0) { throw 'go build failed' }
    } finally { Pop-Location }
} finally {
    $env:GOOS = $oldGOOS
    $env:GOARCH = $oldGOARCH
    $env:CGO_ENABLED = $oldCGO
}
$config = [ordered]@{
    pythonExecutable = [IO.Path]::GetFullPath($PythonExecutable)
    serviceScript = [IO.Path]::GetFullPath($ServiceScript)
    workingDirectory = [IO.Path]::GetFullPath($WorkingDirectory)
    dataRoot = [IO.Path]::GetFullPath($DataRoot)
    url = 'http://127.0.0.1:8880/'
}
[IO.File]::WriteAllText((Join-Path $skillRoot 'launcher.local.json'), ($config | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
if ($Install) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstalledSkill 'SKILL.md'))) { throw "Install the skill first: $InstalledSkill" }
    if ([IO.Path]::GetFullPath($InstalledSkill) -ne $skillRoot) {
        New-Item -ItemType Directory -Path (Join-Path $InstalledSkill 'scripts\windows') -Force | Out-Null
        Copy-Item -LiteralPath $exePath -Destination (Join-Path $InstalledSkill 'SkillToTable.exe') -Force
        Copy-Item -LiteralPath (Join-Path $skillRoot 'launcher.local.json') -Destination (Join-Path $InstalledSkill 'launcher.local.json') -Force
        foreach ($name in @('launcher_service.py', 'build_windows_launcher.ps1', 'browser_profiles.py', 'browser_mcp.py')) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $InstalledSkill "scripts\$name") -Force
        }
        foreach ($name in @('browser-users.html', 'browser-users.js')) {
            Copy-Item -LiteralPath (Join-Path $skillRoot "assets\$name") -Destination (Join-Path $InstalledSkill "assets\$name") -Force
        }
        foreach ($name in @('main.go', 'window.go', 'stop.go', 'go.mod', 'rsrc_windows_amd64.syso')) {
            Copy-Item -LiteralPath (Join-Path $sourceDir $name) -Destination (Join-Path $InstalledSkill "scripts\windows\$name") -Force
        }
        Copy-Item -LiteralPath (Join-Path $sourceDir 'winres') -Destination (Join-Path $InstalledSkill 'scripts\windows') -Recurse -Force
    }
}
if ($Desktop) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstalledSkill 'launcher.local.json'))) { throw 'Desktop launcher requires installed launcher configuration; use -Install -Desktop.' }
    $desktopDir = [Environment]::GetFolderPath('DesktopDirectory')
    $desktopExe = Join-Path $desktopDir '启动本地报表.exe'
    Copy-Item -LiteralPath $exePath -Destination $desktopExe -Force
    Write-Output "Desktop: $desktopExe"
}
Write-Output "EXE: $exePath"
Write-Output 'URL: http://127.0.0.1:8880/'

# Notify Explorer about changed EXE resources without restarting Explorer.
if (-not ('SkillToTable.IconNotification' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace SkillToTable {
    public static class IconNotification {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern void SHChangeNotify(uint eventId, uint flags, string item, IntPtr unused);
        public static void Updated(string path) { SHChangeNotify(0x00002000, 0x00001005, path, IntPtr.Zero); }
    }
}
'@
}
[SkillToTable.IconNotification]::Updated($exePath)
if ($Install) { [SkillToTable.IconNotification]::Updated((Join-Path $InstalledSkill 'SkillToTable.exe')) }
if ($Desktop) { [SkillToTable.IconNotification]::Updated($desktopExe) }
