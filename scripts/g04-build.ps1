$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=Join-Path $root 'out/g04'
$evidence=Join-Path $root 'tests/evidence/G04'
New-Item -ItemType Directory -Force $out,$evidence | Out-Null
$assemblies='C:\Program Files\Cognex\VisionPro\ReferencedAssemblies'
$response=@"
/nologo
/platform:x64
/r:"$assemblies\Cognex.VisionPro.dll"
/r:"$assemblies\Cognex.VisionPro.Core.dll"
/out:"$out\g04-visionpro-probe.exe"
"$root\tests\automated\g04_visionpro_probe.cs"
"@
$response | Set-Content "$out/visionpro.rsp" -Encoding UTF8
& C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe "@$out/visionpro.rsp" 2>&1 | Tee-Object "$evidence/probe-build.txt"
if($LASTEXITCODE -ne 0) {throw 'G04 Cognex x64 probe compilation failed'}
Add-Content "$evidence/probe-build.txt" 'CompilerExitCode=0'
Write-Output 'PASS: G04 Cognex x64 probe compiled'
