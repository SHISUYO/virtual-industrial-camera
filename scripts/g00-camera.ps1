param([Parameter(Mandatory=$true)][System.Net.IPAddress]$BindIP)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$oldPath = $env:PATH
try {
    if (!(Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -eq $BindIP.IPAddressToString)) {
        throw 'BindIP must be an IPv4 address assigned to this computer'
    }
    $env:PATH = "$root/out/g00/msys64/ucrt64/bin;$oldPath"
    & "$root/out/g00/build/src/arv-fake-gv-camera-0.8.exe" -i $BindIP.IPAddressToString -s VICG00 -d all:2
    if ($LASTEXITCODE -ne 0) { throw "Camera exited: $LASTEXITCODE" }
} finally { $env:PATH = $oldPath }
