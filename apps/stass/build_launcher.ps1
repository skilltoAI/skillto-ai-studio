[CmdletBinding()]
param([string]$OutputPath = (Join-Path $PSScriptRoot '../../runtime/Skillto.ai Studio.exe'))
$ErrorActionPreference = 'Stop'
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($OutputPath)) | Out-Null
Push-Location (Join-Path $PSScriptRoot 'modules/table/scripts/windows')
try {
    if ((& go env GOOS) -ne 'windows' -or (& go env GOARCH) -ne 'amd64') {
        throw 'STASS launcher requires Windows amd64'
    }
    # Resource generation is mandatory: plain go build silently omits branding.
    & go run github.com/tc-hib/go-winres@v0.3.3 make --in winres/winres.json --arch amd64 --out rsrc
    if ($LASTEXITCODE -ne 0) { throw 'Icon resource generation failed' }
    & go vet -tags "desktop,production" .
    if ($LASTEXITCODE -ne 0) { throw 'go vet failed' }
    & go build -tags "desktop,production,wv2runtime.browser" -trimpath -ldflags '-H=windowsgui -s -w' -o $OutputPath .
    if ($LASTEXITCODE -ne 0) { throw 'Launcher build failed' }
    $bytes = [IO.File]::ReadAllBytes($OutputPath)
    $peOffset = [BitConverter]::ToInt32($bytes, 60)
    $subsystem = [BitConverter]::ToUInt16($bytes, $peOffset + 24 + 68)
    if ($subsystem -ne 2) { throw 'Launcher must use Windows GUI subsystem (no console)' }
    Add-Type -AssemblyName System.Drawing
    $icon = [Drawing.Icon]::ExtractAssociatedIcon($OutputPath)
    if ($null -eq $icon) { throw 'Launcher icon missing' }
    $icon.Dispose()
    Write-Output "Built GUI launcher: $OutputPath"
} finally { Pop-Location }
