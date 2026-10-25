param([string]$BindIP)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'invoke-python-logged.ps1')
$root=Split-Path $PSScriptRoot -Parent
if(!$BindIP) {
    $addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object InterfaceAlias -eq 'vEthernet (Default Switch)')
    if($addresses.Count -ne 1) {throw 'Cannot select the test adapter automatically. Send this message back for help.'}
    $BindIP=$addresses[0].IPAddress
}
$evidence=Join-Path $root ('tests/evidence/G03/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $root
try {
    New-Item -ItemType Directory -Force $evidence | Out-Null
    $binaryHash=(Get-FileHash "$root/out/g03/build/VICGigE.exe" -Algorithm SHA256).Hash
    [pscustomobject]@{Build='G03-0.3.0';BindIP=$BindIP;ExecutableSHA256=$binaryHash} | ConvertTo-Json | Set-Content "$evidence/build.json"
    Write-Output "正在测试虚拟相机：$BindIP，约需3分钟。无需实体相机。"
    try {
        Invoke-PythonLogged -Arguments @('-u','tests/automated/g03_aravis_run.py','--ip',$BindIP,'--out',(Join-Path $evidence 'checks')) -LogPath "$evidence/run.txt"
    } catch {
        Write-Output $_.Exception.Message
        throw "测试失败，请把窗口最后一屏截图发回。日志：$evidence"
    }
    Write-Output '测试通过：图片、序列、视频、Mono8/RGB8、帧率、软件触发及停止重启均正确，G02回归通过。'
    Write-Output '请把本窗口最后一屏截图发给我。'
} finally {Pop-Location}
