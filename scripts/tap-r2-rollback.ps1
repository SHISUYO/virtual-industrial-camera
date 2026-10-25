param([Parameter(Mandatory=$true)][string]$DeploymentEvidence)
# Explicit user-invoked cleanup only; exact recorded new device, no driver deletion.
$ErrorActionPreference='Stop'
$ev=[IO.Path]::GetFullPath($DeploymentEvidence)
if(!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Run from an administrator PowerShell'}
if(Get-Process VICTapPoC -ErrorAction SilentlyContinue){throw 'Close VICTapPoC before removing its dedicated device'}
$id=Get-Content (Join-Path $ev 'identity.json') -Raw | ConvertFrom-Json
$before=Get-Content (Join-Path $ev 'before-adapters.json') -Raw | ConvertFrom-Json
if($id.guid -in @($before.InterfaceGuid) -or $id.pnp_id -in @($before.PnPDeviceID)){throw 'Device existed before R2; removal refused'}
$nic=@(Get-NetAdapter -IncludeHidden | Where-Object {[string]$_.InterfaceGuid -eq $id.guid})
if($nic.Count -ne 1 -or $nic[0].ifIndex -ne $id.ifIndex -or $nic[0].PnPDeviceID -ne $id.pnp_id -or $nic[0].InterfaceDescription -ne 'TAP-Windows Adapter V9'){throw 'Exact new device identity mismatch; removal refused'}
Start-Transcript -Path (Join-Path $ev ('rollback-'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.txt')) | Out-Null
try {
    $address=Get-NetIPAddress -InterfaceIndex $id.ifIndex -IPAddress 10.203.0.1 -ErrorAction SilentlyContinue
    if($address){$address | Remove-NetIPAddress -Confirm:$false}
    & pnputil.exe /remove-device $id.pnp_id
    if($LASTEXITCODE -ne 0){throw "Removal failed/reboot required: $LASTEXITCODE; STOP"}
    Write-Output 'New dedicated device removed. Driver package deliberately retained; no existing adapter or VPN driver removed.'
} finally {Stop-Transcript | Out-Null}
