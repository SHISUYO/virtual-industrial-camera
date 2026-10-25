param([Parameter(Mandatory=$true)][System.Net.IPAddress]$CameraIP)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$oldPath = $env:PATH
if (Test-Path V:/) { throw 'V: must be free' }
& subst.exe V: (Join-Path $root 'out/g00')
if ($LASTEXITCODE -ne 0) { throw 'Cannot map V:' }
try {
    $env:PATH = "V:/msys64/ucrt64/bin;$root/out/g00/build/src;$oldPath"
    $flags = & V:/msys64/ucrt64/bin/pkg-config.exe --cflags --libs gio-2.0 gobject-2.0 glib-2.0
    if ($LASTEXITCODE -ne 0) { throw 'pkg-config failed' }
    Set-Content "$root/tests/evidence/G00/consumer-build.txt" 'Compiling g00-consumer.c'
    & V:/msys64/ucrt64/bin/gcc.exe -Wall -Wextra -O2 "-I$root/out/g00/aravis/src" "-I$root/out/g00/build/src" "$root/tests/automated/g00-consumer.c" "-L$root/out/g00/build/src" '-laravis-0.8' ($flags -split ' ') -o "$root/out/g00/g00-consumer.exe" 2>&1 | Tee-Object "$root/tests/evidence/G00/consumer-build.txt" -Append
    if ($LASTEXITCODE -ne 0) { throw 'Consumer compilation failed' }
    Add-Content "$root/tests/evidence/G00/consumer-build.txt" 'CompilerExitCode=0'
    & "$root/out/g00/g00-consumer.exe" $CameraIP.IPAddressToString 2>&1 | Tee-Object "$root/tests/evidence/G00/consumer-$($CameraIP.IPAddressToString).txt"
    if ($LASTEXITCODE -ne 0) { throw "Consumer failed: $LASTEXITCODE" }
} finally { $env:PATH = $oldPath; & subst.exe V: /D }
