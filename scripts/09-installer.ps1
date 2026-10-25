param(
    [string]$Release = 'out/09-winui/Release/VICControlWinUI',
    [string]$Output = 'out/09-winui/Installer'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$releasePath = (Resolve-Path (Join-Path $root $Release)).Path
$outputPath = [IO.Path]::GetFullPath((Join-Path $root $Output))
$outRoot = [IO.Path]::GetFullPath((Join-Path $root 'out'))
if (!$outputPath.StartsWith($outRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Installer output must stay inside out/'
}
$required = @('VICControl.WinUI.exe', 'App.xbf', 'MainWindow.xbf', 'VICControl.WinUI.pri',
    'bridge/VICBridge.exe', 'bridge/backend/VICEngine.exe', 'bridge/gige06/VICGigEControl.exe')
foreach ($name in $required) {
    if (!(Test-Path -LiteralPath (Join-Path $releasePath $name) -PathType Leaf)) { throw "Missing publish file: $name" }
}
$pairs = @(
    @('out/06-sequence/build/VICEngine.exe', 'bridge/backend/VICEngine.exe'),
    @('out/06-sequence/build/gige06/VICGigEControl.exe', 'bridge/gige06/VICGigEControl.exe')
)
foreach ($pair in $pairs) {
    $original = (Get-FileHash -LiteralPath (Join-Path $root $pair[0]) -Algorithm SHA256).Hash
    $packaged = (Get-FileHash -LiteralPath (Join-Path $releasePath $pair[1]) -Algorithm SHA256).Hash
    if ($original -ne $packaged) { throw "Backend differs from preserved build: $($pair[1])" }
}
$compiler = Join-Path $env:LOCALAPPDATA 'Programs/Inno Setup 6/ISCC.exe'
if (!(Test-Path -LiteralPath $compiler)) { $compiler = 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe' }
if (!(Test-Path -LiteralPath $compiler)) { throw 'Inno Setup 6 ISCC.exe is required' }
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
& $compiler "/DReleaseRoot=$releasePath" "/DInstallerOutput=$outputPath" (Join-Path $root 'installer/09-winui.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
$installer = Join-Path $outputPath 'VIC-Control-WinUI-09-Setup.exe'
if (!(Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Expected installer was not produced' }
$file = Get-Item -LiteralPath $installer
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash
Write-Host "INSTALLER: $($file.FullName)"
Write-Host "SIZE_BYTES: $($file.Length)"
Write-Host "SHA256: $hash"
