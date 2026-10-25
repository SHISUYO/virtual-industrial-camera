$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=Join-Path $root 'out/g02'
$evidence=Join-Path $root 'tests/evidence/G02'
New-Item -ItemType Directory -Force $out,$evidence | Out-Null
$oldPath=$env:PATH
if(Test-Path V:/) {throw 'V: must be free for the temporary Aravis dependency path'}
& subst.exe V: (Join-Path $root 'out/g00')
if($LASTEXITCODE -ne 0) {throw 'Cannot map temporary V:'}
try {
    $env:PATH="V:/msys64/ucrt64/bin;$root/out/g00/build/src;$oldPath"
    $flags=& V:/msys64/ucrt64/bin/pkg-config.exe --cflags --libs gio-2.0 gobject-2.0 glib-2.0
    if($LASTEXITCODE -ne 0) {throw 'pkg-config failed'}
    Set-Content "$evidence/consumer-build.txt" 'External Aravis 0.8.36 consumer compilation'
    & V:/msys64/ucrt64/bin/gcc.exe -Wall -Wextra -O2 "-I$root/out/g00/aravis/src" "-I$root/out/g00/build/src" "$root/tests/automated/g02_aravis_consumer.c" "-L$root/out/g00/build/src" '-laravis-0.8' ($flags -split ' ') -o "$out/g02-aravis-consumer.exe" 2>&1 | Tee-Object "$evidence/consumer-build.txt" -Append
    if($LASTEXITCODE -ne 0) {throw 'External Aravis consumer build failed'}
    Add-Content "$evidence/consumer-build.txt" 'CompilerExitCode=0'
} finally {$env:PATH=$oldPath;& subst.exe V: /D}
