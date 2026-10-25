$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force (Join-Path $root 'out/06-fix'),(Join-Path $root 'tests/evidence/06-source-fix') | Out-Null
$batch=(Get-Content (Join-Path $root 'out/g04/build-msvc.cmd') -Raw).Replace('out\g04\build','out\06-fix\build').Replace('out/g04/build','out/06-fix/build')
$batch | Set-Content (Join-Path $root 'out/06-fix/build-msvc.cmd') -Encoding ascii
& $env:ComSpec /d /c (Join-Path $root 'out/06-fix/build-msvc.cmd') 2>&1 | Tee-Object (Join-Path $root 'tests/evidence/06-source-fix/build.txt')
if($LASTEXITCODE -ne 0){throw '06 source integration build/CTest failed'}
