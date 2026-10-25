$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$out=Join-Path $root 'out/g01'
New-Item -ItemType Directory -Force $out | Out-Null
& python -m pip install --upgrade --target "$out/python-tools" cmake==4.4.4 ninja==1.13.2 lxml==6.1.3
if($LASTEXITCODE -ne 0) {throw 'Project-local Python tool installation failed'}
$packages=@(
    @{Id='microsoft.windows.sdk.cpp';File='sdk-cpp';Hash='475269434DCD808A67853773272F972C3229C0E10C3DDC821290E70CC0F6904D'},
    @{Id='microsoft.windows.sdk.cpp.x64';File='sdk-x64';Hash='DF6226A051E320942ABFBD57848B43D18772996ECD66BEADAD240F2A56ED2F7B'}
)
foreach($package in $packages) {
    $archive=Join-Path $out "$($package.File).nupkg"
    if(!(Test-Path $archive)) {
        & curl.exe --fail --location --retry 2 --output $archive "https://api.nuget.org/v3-flatcontainer/$($package.Id)/10.0.26100.9169/$($package.Id).10.0.26100.9169.nupkg"
        if($LASTEXITCODE -ne 0) {throw "SDK download failed: $($package.Id)"}
    }
    if((Get-FileHash $archive -Algorithm SHA256).Hash -ne $package.Hash) {throw "SDK hash mismatch: $($package.Id)"}
    & python -m zipfile -e $archive (Join-Path $out $package.File)
    if($LASTEXITCODE -ne 0) {throw "SDK extraction failed: $($package.Id)"}
}
Write-Output 'G01 tools prepared in out/g01; Visual Studio 2022 C++ x64 tools remain required.'
