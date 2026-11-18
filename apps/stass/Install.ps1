[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ManifestSha256,
    [string]$Root,
    [ValidateRange(1,65535)][int]$Port
)
$ErrorActionPreference = 'Stop'
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'release.json')).Hash
if ($actual -ne $ManifestSha256) { throw 'Offline release manifest SHA-256 mismatch' }
$arguments = @('-B', '-X', 'utf8', (Join-Path $PSScriptRoot 'program/offline_install.py'), '--package', $PSScriptRoot, '--manifest-sha256', $ManifestSha256.ToLowerInvariant())
if ($Root) { $arguments += @('--root', $Root) }
if ($PSBoundParameters.ContainsKey('Port')) { $arguments += @('--port', "$Port") }
& (Join-Path $PSScriptRoot 'runtime/python.exe') @arguments
if ($LASTEXITCODE -ne 0) { throw 'STASS offline installation failed' }
