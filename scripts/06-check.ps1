$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root 'out/g05/venv/Scripts/python.exe'
$evidence=Join-Path $root ('tests/evidence/06/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force (Split-Path $evidence -Parent) | Out-Null
$priorPlatform=$env:QT_QPA_PLATFORM
Push-Location $root
try {
    $env:QT_QPA_PLATFORM='offscreen'
    $ErrorActionPreference='Continue'
    & $python -u tests/automated/06_gui_run.py --out $evidence 2>&1 | ForEach-Object {$_.ToString()} | Tee-Object -FilePath ($evidence+'.txt')
    $code=$LASTEXITCODE;$ErrorActionPreference='Stop'
    if($code -ne 0){throw "06 GUI check failed; preserve $evidence"}
    Write-Output 'PASS: local Engine and GUI checks. GenTL/Harvester/Consumer checks BLOCKED, not compatibility PASS.'
    Write-Output "EVIDENCE: $evidence"
} finally {$env:QT_QPA_PLATFORM=$priorPlatform;Pop-Location}
