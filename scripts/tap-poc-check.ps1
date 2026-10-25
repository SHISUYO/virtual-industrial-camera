$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'invoke-python-logged.ps1')
$root=Split-Path $PSScriptRoot -Parent
$folder=Join-Path $root ('tests/evidence/tap-research/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force $folder | Out-Null
Push-Location $root
try {
    Write-Output '只做离线帧验证，不安装驱动、不打开网卡、不修改网络。'
    Invoke-PythonLogged -Arguments @('-u','tests/automated/tap_poc_verify.py','--out',(Join-Path $folder 'checks')) -LogPath (Join-Path $folder 'run.txt')
    Write-Output '离线通过不代表VisionPro兼容。真实取图尚未测试。请把最后一屏截图发回。'
} finally {Pop-Location}
