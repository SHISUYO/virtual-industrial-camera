$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'invoke-python-logged.ps1')
$root=Split-Path $PSScriptRoot -Parent
$guestFile=Join-Path $root 'tests/evidence/G04/sandbox/guest.json'
$evidence=Join-Path $root ('tests/evidence/G04/manual/'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $root
try {
    New-Item -ItemType Directory -Force $evidence | Out-Null
    if(!(Get-Process WindowsSandbox,WindowsSandboxClient,WindowsSandboxRemoteSession -ErrorAction SilentlyContinue)) {
        & (Join-Path $PSScriptRoot 'g04-sandbox-prepare.ps1') | Out-Null
        if(Test-Path $guestFile) {Remove-Item -LiteralPath $guestFile}
        $launcher=Start-Process "$env:WINDIR/System32/WindowsSandbox.exe" -ArgumentList ('"'+(Join-Path $root 'out/g04/sandbox/VIC-G04.wsb')+'"') -PassThru
        $launcher.Id | Set-Content 'tests/evidence/G04/sandbox/launcher.pid'
    }
    Write-Output '正在等待隔离相机启动。首次启动可能需要数分钟，请保留 Sandbox 窗口。'
    $deadline=(Get-Date).AddMinutes(8)
    while(!(Test-Path $guestFile)) {
        if((Get-Date) -gt $deadline) {throw 'Sandbox startup timeout; send the Sandbox window screenshot.'}
        Start-Sleep -Seconds 2
    }
    Write-Output '开始 VisionPro 测试，约需1分钟，无需实体相机。'
    Get-FileHash 'out/g04/build/VICGigE.exe' | ConvertTo-Json | Set-Content "$evidence/build.json"
    Invoke-PythonLogged -Arguments @('-u','tests/automated/g04_sandbox_run.py','--out',(Join-Path $evidence 'checks')) -LogPath "$evidence/run.txt"
    Write-Output '请把最后一屏截图发回。测试结束后关闭 Windows Sandbox 窗口即可。'
} finally {Pop-Location}
