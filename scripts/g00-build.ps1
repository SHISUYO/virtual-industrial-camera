param([switch]$Setup)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$tools = 'V:/msys64/ucrt64/bin'
$source = Join-Path $root 'out/g00/aravis'
$build = Join-Path $root 'out/g00/build'
$evidence = Join-Path $root 'tests/evidence/G00'
New-Item -ItemType Directory -Force $evidence | Out-Null
$oldPath = $env:PATH
if (Test-Path V:/) { throw 'V: must be free for the temporary space-free dependency path' }
& subst.exe V: (Join-Path $root 'out/g00')
if ($LASTEXITCODE -ne 0) { throw 'Cannot create temporary V: mapping' }
try {
    $env:PATH = "$tools;$oldPath"
    if ($Setup) {
        & "$tools/meson.exe" setup $build $source --buildtype=release -Dviewer=disabled -Dgst-plugin=disabled -Dintrospection=disabled -Dusb=disabled -Ddocumentation=disabled -Dpacket-socket=disabled 2>&1 | Tee-Object "$evidence/configure.txt"
        if ($LASTEXITCODE -ne 0) { throw 'Meson configuration failed' }
    }
    & "$tools/meson.exe" compile -C $build 2>&1 | Tee-Object "$evidence/build.txt"
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
    & "$tools/meson.exe" test -C $build --print-errorlogs 2>&1 | Tee-Object "$evidence/tests.txt"
    $testExit = $LASTEXITCODE
    Copy-Item "$build/meson-logs/testlog.txt" "$evidence/upstream-testlog.txt" -Force
    Copy-Item "$build/meson-logs/meson-log.txt" "$evidence/meson-log.txt" -Force
    if ($testExit -ne 0) { throw "Upstream tests failed: $testExit" }
} finally { $env:PATH = $oldPath; & subst.exe V: /D }
