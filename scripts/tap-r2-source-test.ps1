param([Parameter(Mandatory=$true)][string]$DeploymentEvidence)
# Controlled A/B change of the approved NEW host IP only, never an existing NIC.
$ErrorActionPreference='Stop'
$ev=[IO.Path]::GetFullPath($DeploymentEvidence)
if(Test-Path (Join-Path $ev 'source-test-result.json')){throw 'Source selection experiment already attempted'}
Start-Transcript -Path (Join-Path $ev 'source-test.txt') | Out-Null
try {
    if(!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator token required'}
    if(Get-Process VICTapPoC -ErrorAction SilentlyContinue){throw 'Stop PoC before the controlled source selection test'}
    $config=Get-Content (Join-Path $ev 'configure-result.json') -Raw | ConvertFrom-Json
    if($config.status -ne 'PASS'){throw 'R2 configuration not confirmed'}
    $id=$config.identity
    $nic=@(Get-NetAdapter -IncludeHidden | Where-Object {[string]$_.InterfaceGuid -eq $id.guid})
    if($nic.Count -ne 1 -or $nic[0].Name -ne 'VIC-PoC-TAP' -or $nic[0].ifIndex -ne $id.ifIndex -or $nic[0].PnPDeviceID -ne $id.pnp_id){throw 'Dedicated new adapter identity mismatch'}
    $address=Get-NetIPAddress -InterfaceIndex $id.ifIndex -IPAddress 10.203.0.1
    if($address.PrefixLength -ne 24 -or !$address.SkipAsSource){throw 'Unexpected source address state'}
    @{ifIndex=$id.ifIndex;guid=$id.guid;address='10.203.0.1';before_skip_as_source=$true;after_skip_as_source=$false;rollback=('Set-NetIPAddress -InterfaceIndex '+$id.ifIndex+' -IPAddress 10.203.0.1 -SkipAsSource $true')} | ConvertTo-Json | Set-Content (Join-Path $ev 'source-test-journal.json') -Encoding UTF8
    $address | Set-NetIPAddress -SkipAsSource $false
    Get-NetIPAddress -InterfaceIndex $id.ifIndex -IPAddress 10.203.0.1 | Select-Object InterfaceIndex,IPAddress,PrefixLength,SkipAsSource | ConvertTo-Json | Set-Content (Join-Path $ev 'source-test-result.json') -Encoding UTF8
} catch {@{status='FAIL';error=$_.Exception.Message;action='STOP'} | ConvertTo-Json | Set-Content (Join-Path $ev 'source-test-result.json') -Encoding UTF8;exit 1} finally {Stop-Transcript | Out-Null}
