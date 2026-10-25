param([string]$BindIP)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if(!$BindIP) {
    $addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object InterfaceAlias -eq 'vEthernet (Default Switch)')
    if($addresses.Count -ne 1) {throw 'Cannot select the test adapter automatically. Send this message back for help.'}
    $BindIP=$addresses[0].IPAddress
}
$evidence=Join-Path $root ('tests/evidence/G02/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $root
try {
    New-Item -ItemType Directory -Force $evidence | Out-Null
    $binaryHash=(Get-FileHash "$root/out/g02/build/VICGigE.exe" -Algorithm SHA256).Hash
    [pscustomobject]@{Build='G02-0.2.0';BindIP=$BindIP;ExecutableSHA256=$binaryHash} | ConvertTo-Json | Set-Content "$evidence/build.json"
    Write-Output "正在测试虚拟相机：$BindIP，约需1分钟。无需实体相机。"
    & python tests/automated/g02_aravis_run.py --ip $BindIP --out $evidence 2>&1 | Tee-Object "$evidence/run.txt"
    if($LASTEXITCODE -ne 0) {throw "测试失败，请把窗口最后一屏截图发回。日志：$evidence"}
    Write-Output '测试通过：1000帧连续采集和20帧重连采集，全部像素正确。'
    Write-Output '请把本窗口最后一屏截图发给我。'
} finally {Pop-Location}
