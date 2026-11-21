param(
  [string]$Destination,
  [string]$Skill = 'all',
  [ValidateSet('codex', 'claude')][string]$Agent = 'codex',
  [switch]$DryRun,
  [switch]$List,
  [switch]$CodexLegacy,
  [string]$Groups,
  [switch]$ChooseWork,
  [switch]$Augment
)

$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'scripts/install.py'
$installArgs = @($installer, '--agent', $Agent)
if ($Groups -or $ChooseWork) {
  if ($PSBoundParameters.ContainsKey('Skill')) { throw 'Use either -Skill or -Groups / -ChooseWork.' }
  $installArgs += '--groups'
  if ($Groups) { $installArgs += $Groups }
} else {
  $installArgs += @('--skill', $Skill)
}
if ($Augment) { $installArgs += '--augment' }
if ($Destination) { $installArgs += @('--destination', $Destination) }
if ($DryRun) { $installArgs += '--dry-run' }
if ($List) { $installArgs += '--list' }
if ($CodexLegacy) { $installArgs += '--codex-legacy' }
if (Get-Command python -ErrorAction SilentlyContinue) {
  & python @installArgs
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
  & python3 @installArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 @installArgs
} else {
  throw 'Python 3.10+ is required. Install Python and retry.'
}
if ($LASTEXITCODE -ne 0) { throw "Skill installation failed (exit $LASTEXITCODE)." }
