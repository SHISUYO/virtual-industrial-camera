$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$template=Join-Path $root 'out/g04/build-msvc.cmd'
if(!(Test-Path $template)){throw 'The backed-up G04 build environment is required; this script does not modify it.'}
$batch=Get-Content $template -Raw
$pocSource=Join-Path $root 'poc/tap-camera'
$batch=$batch.Replace(('-S "'+$root+'"'),('-S "'+$pocSource+'"'))
$batch=$batch.Replace('out\g04\build','out\tap-poc\build').Replace('out/g04/build','out/tap-poc/build')
if(!$batch.Contains(('-S "'+$pocSource+'"'))){throw 'Cannot safely select standalone PoC source directory'}
$folder=Join-Path $root 'out/tap-poc'
$evidence=Join-Path $root 'tests/evidence/tap-research'
New-Item -ItemType Directory -Force $folder,$evidence | Out-Null
$batch | Set-Content (Join-Path $folder 'build-msvc.cmd') -Encoding ascii
& $env:ComSpec /d /c (Join-Path $folder 'build-msvc.cmd') 2>&1 | Tee-Object (Join-Path $evidence 'poc-build.txt')
if($LASTEXITCODE -ne 0){throw "Standalone TAP user-mode PoC build/CTest failed: $LASTEXITCODE"}
