[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ManifestSha256,
    [string]$Root,
    [string]$MigratedData,
    [ValidateRange(1,65535)][int]$Port
)
$ErrorActionPreference = 'Stop'
$sha256 = [Security.Cryptography.SHA256]::Create()
$manifest = [IO.File]::OpenRead((Join-Path $PSScriptRoot 'release.json'))
try { $actual = [BitConverter]::ToString($sha256.ComputeHash($manifest)).Replace('-', '') }
finally { $manifest.Dispose(); $sha256.Dispose() }
if ($actual -ne $ManifestSha256) { throw 'Offline release manifest SHA-256 mismatch' }
$arguments = @('-B', '-X', 'utf8', (Join-Path $PSScriptRoot 'program/offline_install.py'), '--package', $PSScriptRoot, '--manifest-sha256', $ManifestSha256.ToLowerInvariant())
if ($Root) { $arguments += @('--root', $Root) }
if ($MigratedData) { $arguments += @('--migrated-data', $MigratedData) }
if ($PSBoundParameters.ContainsKey('Port')) { $arguments += @('--port', "$Port") }
& (Join-Path $PSScriptRoot 'runtime/python.exe') @arguments
if ($LASTEXITCODE -ne 0) { throw 'STASS offline installation failed' }
