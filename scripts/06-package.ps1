$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root 'out/g05/venv/Scripts/python.exe'
Push-Location $root
try {
    $ErrorActionPreference='Continue'
    & $python -m PyInstaller --noconfirm --clean --windowed --onedir --name VICControl06 --paths control --distpath out/06/Release --workpath out/06/pyinstaller --specpath out/06 control/control06.py 2>&1 | ForEach-Object {$_.ToString()} | Tee-Object -FilePath out/06/package.txt
    $code=$LASTEXITCODE;$ErrorActionPreference='Stop'
    if($code -ne 0){throw '06 PyInstaller build failed'}
    $release=Join-Path $root 'out/06/Release/VICControl06'
    $backend=Join-Path $release 'backend'
    New-Item -ItemType Directory -Force $backend | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $root 'out/g05/Release-combobox/VICControl/backend') -File | Where-Object {$_.Extension -eq '.dll'} | Copy-Item -Destination $backend
    Copy-Item -LiteralPath (Join-Path $root 'out/06/build/VICEngine.exe') -Destination $backend
    if(!(Test-Path (Join-Path $release 'G05'))){Copy-Item -LiteralPath (Join-Path $root 'out/g05/Release-combobox/VICControl') -Destination (Join-Path $release 'G05') -Recurse}
    Copy-Item -LiteralPath (Join-Path $root 'control/THIRD_PARTY_NOTICES.md') -Destination $release
    Copy-Item -LiteralPath (Join-Path $root 'tests/manual/06_control.md') -Destination $release
    $fixtures=Join-Path $root 'tests/evidence/06/pixels-final/fixtures'
    $samples=Join-Path $release 'samples'
    New-Item -ItemType Directory -Force $samples | Out-Null
    Get-ChildItem -LiteralPath $fixtures -Recurse | ForEach-Object {
        $target=Join-Path $samples $_.FullName.Substring($fixtures.Length+1)
        if($_.PSIsContainer){New-Item -ItemType Directory -Force $target | Out-Null}
        else {Copy-Item -LiteralPath $_.FullName -Destination $target -Force}
    }
    Get-ChildItem -LiteralPath $release -Recurse -File | ForEach-Object {[pscustomobject]@{path=$_.FullName.Substring($release.Length+1);bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash}} | ConvertTo-Json -Depth 5 | Set-Content out/06/Release/sha256-manifest.json -Encoding UTF8
    Write-Output "RELEASE: $release/VICControl06.exe"
} finally {Pop-Location}
