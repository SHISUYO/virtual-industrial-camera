param([Parameter(Mandatory=$true)][string]$DeploymentEvidence)
# Resume ONLY the one recorded new device after the read-only diagnosis.
# Does not install/retry a driver. No other network configuration is changed.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$ev=[IO.Path]::GetFullPath($DeploymentEvidence)
if(Test-Path (Join-Path $ev 'configure-result.json')){throw 'Configuration already attempted; inspect its result, do not retry'}
Start-Transcript -Path (Join-Path $ev 'configure.txt') | Out-Null
function Save($name,$value){ConvertTo-Json -InputObject $value -Depth 6 | Set-Content (Join-Path $ev $name) -Encoding UTF8}
try {
    if(!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator token required'}
    $id=Get-Content (Join-Path $ev 'identity.json') -Raw | ConvertFrom-Json
    $before=Get-Content (Join-Path $ev 'before-adapters.json') -Raw | ConvertFrom-Json
    $new=@(Get-NetAdapter -IncludeHidden | Where-Object { [string]$_.InterfaceGuid -notin @($before.InterfaceGuid) })
    if($new.Count -ne 1 -or [string]$new[0].InterfaceGuid -ne $id.guid -or $new[0].PnPDeviceID -ne $id.pnp_id -or $new[0].ifIndex -ne $id.ifIndex){throw 'Recorded unique new adapter identity does not match'}
    $nic=$new[0]
    if($nic.Name -ne $id.original_name -or $nic.InterfaceDescription -ne 'TAP-Windows Adapter V9'){throw 'Adapter has been changed since installation'}
    foreach($old in $before){$now=Get-NetAdapter -IncludeHidden | Where-Object {[string]$_.InterfaceGuid -eq $old.InterfaceGuid};if(!$now -or [string]$now.Status -ne [string]$old.Status){throw "Existing adapter changed: $($old.Name)"}}
    $properties=@(Get-PnpDeviceProperty -InstanceId $id.pnp_id -KeyName DEVPKEY_Device_DriverVersion,DEVPKEY_Device_DriverInfPath,DEVPKEY_Device_ProblemCode,DEVPKEY_Device_DevNodeStatus)
    Save 'confirmed-properties.json' @($properties | Select-Object KeyName,Data)
    $version=($properties | Where-Object KeyName -eq 'DEVPKEY_Device_DriverVersion').Data
    $inf=($properties | Where-Object KeyName -eq 'DEVPKEY_Device_DriverInfPath').Data
    $problem=($properties | Where-Object KeyName -eq 'DEVPKEY_Device_ProblemCode').Data
    $state=($properties | Where-Object KeyName -eq 'DEVPKEY_Device_DevNodeStatus').Data
    if($version -ne '9.27.0.0' -or $problem -ne 0 -or ($state -band 0x100) -ne 0){throw 'Driver unhealthy or requires reboot'}
    $service=Get-CimInstance Win32_SystemDriver -Filter "Name='tap0901'"
    if($service.State -ne 'Running'){throw 'Driver is not running'}
    $drv=Join-Path $root 'out/tap-research/tap-signed/dist.win10/amd64'
    if((Get-FileHash "$env:SystemRoot/System32/drivers/tap0901.sys").Hash -ne (Get-FileHash (Join-Path $drv 'tap0901.sys')).Hash){throw 'Installed SYS hash differs'}
    & (Join-Path $root 'out/g01/sdk-cpp/c/bin/10.0.26100.0/x64/signtool.exe') verify /kp /c (Join-Path $drv 'tap0901.cat') "$env:SystemRoot/System32/drivers/tap0901.sys"
    if($LASTEXITCODE -ne 0){throw 'Installed SYS signature/catalog verification failed'}
    $prefixes=@(Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object {"$($_.IPAddress)/$($_.PrefixLength)"})+@(Get-NetRoute -AddressFamily IPv4 | Where-Object DestinationPrefix -ne '0.0.0.0/0' | ForEach-Object DestinationPrefix)
    foreach($prefix in $prefixes){$p=$prefix.Split('/');$b=[Net.IPAddress]::Parse($p[0]).GetAddressBytes();[uint64]$a=[uint64]$b[0]*16777216+[uint64]$b[1]*65536+[uint64]$b[2]*256+$b[3];[uint64]$size=[math]::Pow(2,32-[int]$p[1]);[uint64]$lo=[math]::Floor($a/$size)*$size;if($lo -le 181076223 -and ($lo+$size-1) -ge 181075968){throw "Subnet conflict: $prefix"}}
    $id.driver_version=$version;$id.inf_name=$inf;Save 'confirmed-identity.json' $id
    Save 'configure-journal.json' @{phase='rename-and-host-address';identity=$id}
    $nic | Rename-NetAdapter -NewName 'VIC-PoC-TAP' -Confirm:$false
    New-NetIPAddress -InterfaceIndex $id.ifIndex -IPAddress 10.203.0.1 -PrefixLength 24 -SkipAsSource $true -PolicyStore ActiveStore | Out-Null
    if(Get-NetIPAddress -IPAddress 10.203.0.2 -ErrorAction SilentlyContinue){throw 'Camera IP must not be Windows-owned'}
    Save 'configured-addresses.json' @(Get-NetIPAddress | Select-Object InterfaceIndex,IPAddress,PrefixLength,AddressFamily,AddressState,SkipAsSource,PrefixOrigin)
    Save 'configured-routes.json' @(Get-NetRoute | Select-Object InterfaceIndex,DestinationPrefix,NextHop,RouteMetric,Protocol)
    Save 'configured-dns.json' @(Get-DnsClientServerAddress | Select-Object InterfaceIndex,AddressFamily,ServerAddresses)
    Save 'configured-bindings.json' @(Get-NetAdapterBinding -Name '*' -AllBindings | Select-Object Name,ComponentID,Enabled)
    Save 'configured-firewall.json' @(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction)
    Save 'configure-result.json' @{status='PASS';identity=$id;driver='PASS';arp='NOT TESTED';visionpro='NOT TESTED'}
    Write-Output 'PASS: confirmed driver running; only the recorded new TAP renamed/configured.'
} catch {Save 'configure-result.json' @{status='FAIL';error=$_.Exception.Message;action='STOP'};Write-Output "STOP: $($_.Exception.Message)";exit 1} finally {Stop-Transcript | Out-Null}
