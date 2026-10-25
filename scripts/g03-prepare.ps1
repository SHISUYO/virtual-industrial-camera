$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$archive=Join-Path $root 'out/g03/opencv-4.12.0-windows.exe'
$destination=Join-Path $root 'out/g03/opencv-sdk'
New-Item -ItemType Directory -Force (Join-Path $root 'out/g03') | Out-Null
if(!(Test-Path $archive)) {
    & curl.exe -L --fail --retry 2 --output $archive 'https://github.com/opencv/opencv/releases/download/4.12.0/opencv-4.12.0-windows.exe'
    if($LASTEXITCODE -ne 0) {throw 'OpenCV download failed'}
}
# Pinned SHA256 of the official release artifact downloaded for this build.
if((Get-FileHash $archive -Algorithm SHA256).Hash -ne 'B753B14D880B9BC8D89D6ACD3B665C040BAEC0211078435432FCAE117DB707AF') {throw 'OpenCV archive hash mismatch'}
if(!(Test-Path "$destination/opencv/build/OpenCVConfig.cmake")) {
    $extract=Start-Process -FilePath $archive -ArgumentList @('-y',('-o"'+$destination+'"')) -WindowStyle Hidden -Wait -PassThru
    if($extract.ExitCode -ne 0) {throw 'OpenCV extraction failed'}
}
if(!(Test-Path "$destination/opencv/build/x64/vc16/bin/opencv_world4120.dll")) {throw 'OpenCV x64 runtime missing'}
Write-Output 'PASS: project-local OpenCV 4.12.0 x64 prepared'
