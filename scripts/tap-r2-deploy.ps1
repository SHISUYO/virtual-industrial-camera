param([Parameter(Mandatory=$true)][string]$Evidence)
# Approved R2 only. Never updates an existing TAP, changes bindings or reboots.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$Evidence=[IO.Path]::GetFullPath($Evidence)
New-Item -ItemType Directory -Path $Evidence -ErrorAction Stop | Out-Null
Start-Transcript -Path (Join-Path $Evidence 'deployment.txt') | Out-Null
function Save-Json($name,$value) { ConvertTo-Json -InputObject $value -Depth 8 | Set-Content (Join-Path $Evidence $name) -Encoding UTF8 }
function Snapshot($prefix) {
    Save-Json "$prefix-adapters.json" @(Get-NetAdapter -IncludeHidden | Select-Object Name,InterfaceGuid,ifIndex,InterfaceDescription,Status,MacAddress,PnPDeviceID,DriverVersion,DriverInformation)
    Save-Json "$prefix-addresses.json" @(Get-NetIPAddress | Select-Object InterfaceIndex,IPAddress,PrefixLength,AddressFamily,AddressState,SkipAsSource,PrefixOrigin)
    Save-Json "$prefix-routes.json" @(Get-NetRoute | Select-Object InterfaceIndex,DestinationPrefix,NextHop,RouteMetric,Protocol)
    Save-Json "$prefix-dns.json" @(Get-DnsClientServerAddress | Select-Object InterfaceIndex,AddressFamily,ServerAddresses)
    Save-Json "$prefix-bindings.json" @(Get-NetAdapterBinding -Name '*' -AllBindings | Select-Object Name,ComponentID,Enabled)
    Save-Json "$prefix-firewall.json" @(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction)
    Save-Json "$prefix-drivers.json" @(Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceClass -eq 'NET' | Select-Object DeviceID,InfName,DriverVersion,IsSigned,Signer)
}
$phase='preflight'
try {
    $admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if(!$admin){throw 'Administrator token required; no installation attempted'}
    Snapshot 'before'
    & pnputil.exe /enum-drivers /class Net | Out-File (Join-Path $Evidence 'before-driver-store.txt') -Encoding utf8
    if($LASTEXITCODE -ne 0){throw 'Cannot inventory Driver Store'}
    try { Save-Json 'secure-boot.json' (Confirm-SecureBootUEFI) } catch { Save-Json 'secure-boot.json' $_.Exception.Message }
    Save-Json 'device-guard.json' @(Get-CimInstance -Namespace root/Microsoft/Windows/DeviceGuard -ClassName Win32_DeviceGuard)
    $old=@(Get-NetAdapter -IncludeHidden)
    $oldDevices=@(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='Net'")
    if(@($old | Where-Object {$_.Name -eq 'VIC-PoC-TAP' -or $_.InterfaceDescription -match 'TAP-Windows'}).Count -or @($oldDevices | Where-Object {($_.HardwareID -join ',') -match 'tap0901'}).Count){throw 'Existing TAP found; refusing install/update'}
    if(Get-Process VICGigE,VICTapPoC,CogQuickBuild,WindowsSandbox -ErrorAction SilentlyContinue){throw 'Close the existing camera/consumer/Sandbox before deployment'}
    # Include all IPv4 interface prefixes, even disconnected interfaces, plus non-default routes.
    $prefixes=@(Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" }) + @(Get-NetRoute -AddressFamily IPv4 | Where-Object DestinationPrefix -ne '0.0.0.0/0' | ForEach-Object DestinationPrefix)
    Save-Json 'checked-prefixes.json' $prefixes
    foreach($prefix in $prefixes) {
        $parts=$prefix.Split('/');$bytes=[Net.IPAddress]::Parse($parts[0]).GetAddressBytes()
        [uint64]$addr=[uint64]$bytes[0]*16777216+[uint64]$bytes[1]*65536+[uint64]$bytes[2]*256+$bytes[3]
        [uint64]$block=[math]::Pow(2,32-[int]$parts[1]);[uint64]$lo=[math]::Floor($addr/$block)*$block;[uint64]$hi=$lo+$block-1
        # 10.203.0.0..10.203.0.255
        if($lo -le 181076223 -and $hi -ge 181075968){throw "Address/route overlap: $prefix"}
    }
    $drv=Join-Path $root 'out/tap-research/tap-signed/dist.win10/amd64'
    $zip=Get-FileHash (Join-Path $root 'out/tap-research/dist.win10.zip') -Algorithm SHA256
    if($zip.Hash -ne '36E2609B7CEEFEDCB978CE5C48CAF9E0E5AF83423717C4E2E3C1D7EBCA8F62A5'){throw 'Official ZIP hash mismatch'}
    $sigs=@(Get-AuthenticodeSignature (Join-Path $drv 'devcon.exe'),(Join-Path $drv 'tap0901.cat'))
    Save-Json 'signatures.json' @($sigs | Select-Object Path,Status,@{n='Signer';e={$_.SignerCertificate.Subject}})
    if(@($sigs | Where-Object {$_.Status -ne 'Valid' -or $_.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation'}).Count){throw 'Signature validation failed'}
    $sign=Join-Path $root 'out/g01/sdk-cpp/c/bin/10.0.26100.0/x64/signtool.exe'
    & $sign verify /kp /c (Join-Path $drv 'tap0901.cat') (Join-Path $drv 'tap0901.sys')
    if($LASTEXITCODE -ne 0){throw 'Kernel-policy/catalog verification failed'}
    & $sign verify /pa /c (Join-Path $drv 'tap0901.cat') (Join-Path $drv 'OemVista.inf')
    if($LASTEXITCODE -ne 0){throw 'INF catalog verification failed'}
    Save-Json 'package-hashes.json' @(Get-ChildItem $drv -File | Get-FileHash -Algorithm SHA256)
    $phase='install'
    Save-Json 'journal.json' @{phase=$phase;command='devcon install OemVista.inf tap0901';automatic_reboot=$false}
    & (Join-Path $drv 'devcon.exe') install (Join-Path $drv 'OemVista.inf') tap0901
    $code=$LASTEXITCODE
    Save-Json 'install-exit.json' @{exit_code=$code}
    if($code -ne 0){throw "Driver install failed or needs reboot (exit $code); STOP, no retry"}
    $phase='identify'
    $new=@()
    for($i=0;$i -lt 20;$i++) {
        $new=@(Get-NetAdapter -IncludeHidden | Where-Object { $_.InterfaceGuid -notin $old.InterfaceGuid -and $_.InterfaceDescription -match 'TAP-Windows' })
        if($new.Count){break};Start-Sleep -Seconds 1
    }
    $added=@(Get-CimInstance Win32_PnPEntity -Filter "PNPClass='Net'" | Where-Object DeviceID -notin $oldDevices.DeviceID)
    Save-Json 'added-pnp.json' @($added | Select-Object DeviceID,Name,HardwareID,ConfigManagerErrorCode,Status)
    if($new.Count -ne 1 -or $added.Count -ne 1){throw 'Expected exactly one new TAP adapter/PnP instance; STOP'}
    $nic=$new[0];$pnp=$added[0]
    # Win32_PnPSignedDriver can omit a freshly installed device on this OS.
    # Use the PnP property store, loaded service and verified installed binary instead.
    $version=(Get-PnpDeviceProperty -InstanceId $pnp.DeviceID -KeyName DEVPKEY_Device_DriverVersion).Data
    $inf=(Get-PnpDeviceProperty -InstanceId $pnp.DeviceID -KeyName DEVPKEY_Device_DriverInfPath).Data
    $identity=@{guid=[string]$nic.InterfaceGuid;ifIndex=[int]$nic.ifIndex;pnp_id=$pnp.DeviceID;driver_version=$version;inf_name=$inf;host_ip='10.203.0.1';camera_ip='10.203.0.2';original_name=$nic.Name}
    Save-Json 'identity.json' $identity
    $service=Get-CimInstance Win32_SystemDriver -Filter "Name='tap0901'"
    $nodeStatus=(Get-PnpDeviceProperty -InstanceId $pnp.DeviceID -KeyName DEVPKEY_Device_DevNodeStatus).Data
    if(($nodeStatus -band 0x100) -ne 0){throw 'New device requires reboot; STOP'}
    if($nic.PnPDeviceID -ne $pnp.DeviceID -or $pnp.ConfigManagerErrorCode -ne 0 -or $version -ne '9.27.0.0' -or $service.State -ne 'Running'){throw 'New device not healthy/running TAP9.27; STOP'}
    if((Get-FileHash "$env:SystemRoot/System32/drivers/tap0901.sys").Hash -ne (Get-FileHash (Join-Path $drv 'tap0901.sys')).Hash){throw 'Loaded driver file differs from the verified package; STOP'}
    $phase='configure-new-tap'
    Save-Json 'journal.json' @{phase=$phase;identity=$identity}
    $nic | Rename-NetAdapter -NewName 'VIC-PoC-TAP' -Confirm:$false
    New-NetIPAddress -InterfaceIndex $nic.ifIndex -IPAddress 10.203.0.1 -PrefixLength 24 -SkipAsSource $true -PolicyStore ActiveStore | Out-Null
    if(Get-NetIPAddress -IPAddress 10.203.0.2 -ErrorAction SilentlyContinue){throw 'Camera IP is Windows-owned; STOP'}
    $post=@(Get-NetAdapter -IncludeHidden)
    foreach($previous in $old) {
        $current=$post | Where-Object InterfaceGuid -eq $previous.InterfaceGuid
        if(!$current -or $current.Status -ne $previous.Status){throw "Existing adapter state changed: $($previous.Name); STOP"}
    }
    Snapshot 'after'
    $phase='complete'
    Save-Json 'result.json' @{status='PASS';phase=$phase;identity=$identity;note='Driver loaded and new host address configured; ARP and VisionPro NOT TESTED'}
    Write-Output 'PASS: R2 deployment complete; no existing adapter configuration modified by this script.'
} catch {
    Save-Json 'result.json' @{status='FAIL';phase=$phase;error=$_.Exception.Message;action='STOP; no retry or automatic rollback; inspect evidence'}
    try { Snapshot 'stopped' } catch { Write-Output $_ }
    Write-Output "STOP: $($_.Exception.Message)"
    exit 1
} finally { Stop-Transcript | Out-Null }
