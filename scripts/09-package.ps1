param([string]$Output = 'out/09-winui/Release/VICControlWinUI')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$python = Join-Path $root 'out/g05/venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw "Missing Python environment: $python" }
$engine = Join-Path $root 'out/06-sequence/build/VICEngine.exe'
$camera = Join-Path $root 'out/06-sequence/build/gige06/VICGigEControl.exe'
foreach ($item in @($engine,$camera)) { if (!(Test-Path -LiteralPath $item)) { throw "Missing preserved backend: $item" } }
$release = [IO.Path]::GetFullPath((Join-Path $root $Output))
if (!$release.StartsWith((Join-Path $root 'out') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Release path must stay inside out/' }
dotnet publish control/winui09/VICControl.WinUI.csproj -c Release -p:Platform=x64 --no-restore -o $release -v:q
if ($LASTEXITCODE -ne 0) { throw 'WinUI publish failed' }
# Unpackaged WinUI's dotnet publish omits compiled XAML and PRI in this SDK setup.
$compiled = Join-Path $root 'control/winui09/bin/x64/Release/net9.0-windows10.0.26100.0/win-x64'
foreach ($name in @('App.xbf','MainWindow.xbf','VICControl.WinUI.pri')) {
    $source = Join-Path $compiled $name
    if (!(Test-Path -LiteralPath $source)) { throw "Missing compiled WinUI resource: $source" }
    Copy-Item -LiteralPath $source -Destination (Join-Path $release $name) -Force
}
$bridgeDist = Join-Path $root 'out/09-winui/bridge-dist'
& $python -m PyInstaller --noconfirm --clean --console --onedir --name VICBridge --paths control --distpath $bridgeDist --workpath out/09-winui/bridge-build --specpath out/09-winui control/winui_bridge09.py
if ($LASTEXITCODE -ne 0) { throw 'Bridge packaging failed' }
$bridge = Join-Path $release 'bridge'
New-Item -ItemType Directory -Force -Path $bridge | Out-Null
Copy-Item -Path (Join-Path $bridgeDist 'VICBridge/*') -Destination $bridge -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $bridge 'backend'),(Join-Path $bridge 'gige06') | Out-Null
Copy-Item -LiteralPath $engine -Destination (Join-Path $bridge 'backend/VICEngine.exe') -Force
Copy-Item -LiteralPath $camera -Destination (Join-Path $bridge 'gige06/VICGigEControl.exe') -Force
$runtime = Join-Path $root 'out/06-dashboard/Release/VICControl06/backend'
if (!(Test-Path -LiteralPath (Join-Path $runtime 'opencv_world4120.dll'))) { throw "Missing preserved native dependencies: $runtime" }
foreach ($dll in Get-ChildItem -LiteralPath $runtime -Filter '*.dll' -File) {
    Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $bridge 'backend' $dll.Name) -Force
    Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $bridge 'gige06' $dll.Name) -Force
}
Write-Host "RELEASE: $(Join-Path $release 'VICControl.WinUI.exe')"
Write-Host "ENGINE_SHA256: $((Get-FileHash -LiteralPath (Join-Path $bridge 'backend/VICEngine.exe') -Algorithm SHA256).Hash)"
Write-Host "GIGE_SHA256: $((Get-FileHash -LiteralPath (Join-Path $bridge 'gige06/VICGigEControl.exe') -Algorithm SHA256).Hash)"
