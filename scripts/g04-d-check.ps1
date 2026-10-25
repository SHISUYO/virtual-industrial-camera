# G04-D bug acceptance only. Reuse installed TAP and the existing native SDK probe.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$exe=Join-Path $root 'out/tap-poc/build/VICTapPoC.exe'
$help=& $exe --help
if($LASTEXITCODE -ne 0 -or $help[0] -notlike 'VICTapPoC 0.1.1 G04-D*'){throw 'Build TAP-POC-0.1.1 / G04-D first; no camera started'}
Write-Output ('BUILD: TAP-POC-0.1.1 / G04-D SHA256='+(Get-FileHash $exe -Algorithm SHA256).Hash)
$evidence=Join-Path $root ('tests/evidence/G04-D/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force (Split-Path $evidence -Parent) | Out-Null
& (Join-Path $PSScriptRoot 'tap-r2-check.ps1') -EvidenceRoot $evidence
exit $LASTEXITCODE
