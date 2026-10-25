param([ValidateSet('Debug','Release')][string]$Configuration='Release')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$cmakeRoot=$root.Replace('\','/')
$cmake=Join-Path $root 'out/g01/python-tools/cmake/data/bin/cmake.exe'
$ctest=Join-Path $root 'out/g01/python-tools/cmake/data/bin/ctest.exe'
$vcvars='C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
$build=Join-Path $root 'out/g03/build'
$evidence=Join-Path $root 'tests/evidence/G03'
New-Item -ItemType Directory -Force $evidence | Out-Null
if (!(Test-Path $cmake) -or !(Test-Path $vcvars)) {throw 'Install project-local CMake and VS2022 C++ x64 tools; see manual guide'}
$batch=@"
@echo off
set "VSLANG=1033"
call "$vcvars"
if errorlevel 1 exit /b 1
set "INCLUDE=$root\out\g01\sdk-cpp\c\Include\10.0.26100.0\ucrt;$root\out\g01\sdk-cpp\c\Include\10.0.26100.0\shared;$root\out\g01\sdk-cpp\c\Include\10.0.26100.0\um;%INCLUDE%"
set "LIB=$root\out\g01\sdk-x64\c\ucrt\x64;$root\out\g01\sdk-x64\c\um\x64;%LIB%"
set "PATH=$root\out\g01\sdk-cpp\c\bin\10.0.26100.0\x64;%PATH%"
"$cmake" -S "$root" -B "$build" -G Ninja -DCMAKE_MAKE_PROGRAM:FILEPATH="$cmakeRoot/out/g01/python-tools/bin/ninja.exe" -DCMAKE_BUILD_TYPE=$Configuration -DCMAKE_CXX_COMPILER=cl -DCMAKE_RC_COMPILER:FILEPATH="$cmakeRoot/out/g01/sdk-cpp/c/bin/10.0.26100.0/x64/rc.exe" -DCMAKE_MT:FILEPATH="$cmakeRoot/out/g01/sdk-cpp/c/bin/10.0.26100.0/x64/mt.exe"
if errorlevel 1 exit /b 1
"$cmake" --build "$build" --clean-first
if errorlevel 1 exit /b 1
"$ctest" --test-dir "$build" --output-on-failure
exit /b %errorlevel%
"@
$batch | Set-Content (Join-Path $root 'out/g03/build-msvc.cmd') -Encoding ascii
& $env:ComSpec /d /c (Join-Path $root 'out/g03/build-msvc.cmd') 2>&1 | Tee-Object "$evidence/build-$Configuration.txt"
if($LASTEXITCODE -ne 0) {throw "G03 configure/build/CTest failed: $LASTEXITCODE"}
