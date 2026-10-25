$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$folder=Join-Path $root 'out/g05'
$evidence=Join-Path $root 'tests/evidence/G05'
New-Item -ItemType Directory -Force $folder,$evidence | Out-Null
$batch=Get-Content (Join-Path $root 'out/g04/build-msvc.cmd') -Raw
$batch=$batch.Replace('out\g04\build','out\g05\build').Replace('out/g04/build','out/g05/build')
$batch | Set-Content (Join-Path $folder 'build-msvc.cmd') -Encoding ascii
& $env:ComSpec /d /c (Join-Path $folder 'build-msvc.cmd') 2>&1 | Tee-Object (Join-Path $evidence 'build.txt')
if($LASTEXITCODE -ne 0){throw "G05 Release build/CTest failed: $LASTEXITCODE"}
