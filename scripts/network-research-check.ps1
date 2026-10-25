param([string]$BindIP)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'invoke-python-logged.ps1')
$root=Split-Path $PSScriptRoot -Parent
if(!$BindIP) {
    $addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object InterfaceAlias -eq 'vEthernet (Default Switch)')
    if($addresses.Count -ne 1) {throw 'Cannot choose one existing IPv4. Use -BindIP with an already configured local address.'}
    $BindIP=$addresses[0].IPAddress
}
if(Get-Process WindowsSandboxRemoteSession,VICGigE,Cognex.VisionPro.QuickBuild -ErrorAction SilentlyContinue) {
    throw 'Close the previous Sandbox/camera/QuickBuild test first. No process was stopped.'
}
$evidence=Join-Path $root ('tests/evidence/network-research/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force $evidence | Out-Null
Push-Location $root
try {
    Write-Output '开始网络调查，约2分钟。只运行临时测试，不修改网卡、IP、路由、DNS、防火墙或Hyper-V。'
    Invoke-PythonLogged -Arguments @('-u','tests/automated/network_research.py','--ip',$BindIP,'--out',(Join-Path $evidence 'checks')) -LogPath (Join-Path $evidence 'run.txt')
    Write-Output '调查结束。当前同IP下Cognex取图预期仍可能FAIL；这不是兼容通过声明。'
    Write-Output "证据：$evidence"
    Write-Output '请把最后一屏截图发回。'
} finally {Pop-Location}
