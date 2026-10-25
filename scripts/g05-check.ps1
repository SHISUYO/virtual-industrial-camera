$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if(Get-Process VICGigEControl,VICTapPoC,VICGigE,CogQuickBuild,WindowsSandbox -ErrorAction SilentlyContinue){throw 'Close VIC camera services, QuickBuild and Sandbox first; no process was stopped'}
$python=Join-Path $root 'out/g05/venv/Scripts/python.exe'
if(!(Test-Path -LiteralPath $python)){throw 'Build the isolated G05 environment using control/requirements.txt first'}
$evidence=Join-Path $root ('tests/evidence/G05/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force (Split-Path $evidence -Parent) | Out-Null
$oldPlatform=$env:QT_QPA_PLATFORM
Push-Location $root
try {
    $env:QT_QPA_PLATFORM='offscreen'
    # Preserve complete native stderr under Windows PowerShell 5.1 as well.
    $ErrorActionPreference='Continue'
    & $python -u tests/automated/g05_run.py --out $evidence 2>&1 | ForEach-Object {$_.ToString()} | Tee-Object -FilePath ($evidence+'.txt')
    $code=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if($code -ne 0){throw "G05 test failed (exit=$code); preserve $evidence and $evidence.txt"}
    Write-Output 'G05 AUTOMATED PASS; QuickBuild manual acceptance still pending. GenTL regression BLOCKED.'
    Write-Output "EVIDENCE: $evidence"
} finally {$env:QT_QPA_PLATFORM=$oldPlatform;Pop-Location}
