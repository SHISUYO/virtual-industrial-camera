$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$python=Join-Path $root 'out/g05/venv/Scripts/python.exe'
Push-Location $root
try {
    $ErrorActionPreference='Continue'
    & $python -m PyInstaller --noconfirm --clean --windowed --onedir --name VICControl06 --paths control --distpath out/06-tap-address/Release --workpath out/06-tap-address/pyinstaller --specpath out/06-tap-address control/control06.py 2>&1 | ForEach-Object {$_.ToString()} | Tee-Object -FilePath out/06-tap-address/package.txt
    $code=$LASTEXITCODE;$ErrorActionPreference='Stop'
    if($code -ne 0){throw '06 source package failed'}
    $release=Join-Path $root 'out/06-tap-address/Release/VICControl06'
    foreach($sub in @('backend','gige06')) {
        $target=Join-Path $release $sub
        New-Item -ItemType Directory -Force $target | Out-Null
        Get-ChildItem -LiteralPath (Join-Path $root 'out/g05/Release-combobox/VICControl/backend') -File | Where-Object {$_.Extension -eq '.dll'} | Copy-Item -Destination $target
    }
    Copy-Item -LiteralPath (Join-Path $root 'out/06-resolution/build/VICEngine.exe') -Destination (Join-Path $release 'backend')
    Copy-Item -LiteralPath (Join-Path $root 'out/06-resolution/build/gige06/VICGigEControl.exe') -Destination (Join-Path $release 'gige06')
    Copy-Item -LiteralPath (Join-Path $root 'control/THIRD_PARTY_NOTICES.md'),(Join-Path $root 'tests/manual/06_tap_address.md') -Destination $release
    $samples=Join-Path $release 'samples'
    New-Item -ItemType Directory -Force $samples | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $root 'tests/evidence/06-source-fix/live-02/fixtures') | Copy-Item -Destination $samples -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $root 'out/06-resolution/fixtures/industrial.png'),(Join-Path $root 'out/06-resolution/fixtures/square.png') -Destination $samples -Force
    Write-Output "RELEASE: $release/VICControl06.exe"
} finally {Pop-Location}
