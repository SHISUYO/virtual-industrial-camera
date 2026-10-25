$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root 'out/g05/venv/Scripts/python.exe'
$folder=Join-Path $root 'out/g05'
Push-Location $root
try {
    & $python -m PyInstaller --noconfirm --clean --windowed --onedir --name VICControl --paths control --distpath out/g05/Release --workpath out/g05/pyinstaller --specpath out/g05 control/main.py
    if($LASTEXITCODE -ne 0){throw 'PyInstaller failed'}
    $release=Join-Path $folder 'Release/VICControl'
    $backend=Join-Path $release 'backend'
    New-Item -ItemType Directory -Force $backend | Out-Null
    foreach($name in @('VICGigEControl.exe','opencv_world4120.dll','opencv_videoio_ffmpeg4120_64.dll')) {
        Copy-Item -LiteralPath (Join-Path $folder "build/$name") -Destination $backend
    }
    $crt='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Redist/MSVC'
    $version=Get-ChildItem -LiteralPath $crt -Directory | Where-Object {Test-Path -LiteralPath (Join-Path $_.FullName 'x64/Microsoft.VC143.CRT')} | Sort-Object Name -Descending | Select-Object -First 1
    if(!$version){throw 'MSVC x64 runtime directory not found'}
    Get-ChildItem -LiteralPath (Join-Path $version.FullName 'x64/Microsoft.VC143.CRT') -Filter '*.dll' | Copy-Item -Destination $backend
    Copy-Item -LiteralPath (Join-Path $root 'control/THIRD_PARTY_NOTICES.md') -Destination $release
    Copy-Item -LiteralPath (Join-Path $root 'tests/manual/G05_control.md') -Destination $release
    $licenses=Join-Path $release 'licenses'
    New-Item -ItemType Directory -Force $licenses | Out-Null
    Get-ChildItem (Join-Path $root 'out/g05/venv/Lib/site-packages') -Directory -Filter '*dist-info' | ForEach-Object {
        $metadata=$_
        Get-ChildItem -LiteralPath $metadata.FullName -File | Where-Object {$_.Name -match '(?i)license|copying|metadata'} | ForEach-Object {
            $destination=Join-Path $licenses $metadata.Name
            New-Item -ItemType Directory -Force $destination | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination
        }
    }
    Get-ChildItem -LiteralPath $release -Recurse -File | ForEach-Object {
        [pscustomobject]@{path=$_.FullName.Substring($release.Length+1);bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}
    } | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $folder 'Release/sha256-manifest.json') -Encoding UTF8
    Write-Output "RELEASE: $release/VICControl.exe"
} finally {Pop-Location}
