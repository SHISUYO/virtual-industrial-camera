param([Parameter(Mandatory=$true)][string]$Evidence)
# Explicit user-approved repair only. Never invoked by the GUI.
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
Start-Transcript -Path (Join-Path $Evidence 'restore.txt') | Out-Null
try {
    if(!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Administrator required'}
    $nic=@(Get-NetAdapter -IncludeHidden | Where-Object {[string]$_.InterfaceGuid -eq '{FA1317AE-2D52-4DAA-A4EC-1D116C7C1504}'})
    if($nic.Count -ne 1 -or $nic[0].Name -ne 'VIC-PoC-TAP' -or $nic[0].DriverVersion -ne '9.27.0.0'){throw 'Approved adapter identity mismatch'}
    $idx=$nic[0].ifIndex
    if(Get-NetIPAddress -IPAddress 10.203.0.2 -ErrorAction SilentlyContinue){throw 'Camera address is Windows-owned'}
    $addresses=@(Get-NetIPAddress -AddressFamily IPv4)
    $routes=@(Get-NetRoute -AddressFamily IPv4)
    $prefixes=@($addresses | ForEach-Object {"$($_.IPAddress)/$($_.PrefixLength)"})+@($routes | Where-Object DestinationPrefix -ne '0.0.0.0/0' | ForEach-Object DestinationPrefix)
    foreach($prefix in $prefixes){
        $p=$prefix.Split('/');$b=[Net.IPAddress]::Parse($p[0]).GetAddressBytes()
        [uint64]$a=[uint64]$b[0]*16777216+[uint64]$b[1]*65536+[uint64]$b[2]*256+$b[3]
        [uint64]$size=[math]::Pow(2,32-[int]$p[1]);[uint64]$lo=[math]::Floor($a/$size)*$size
        if($lo -le 181076223 -and ($lo+$size-1) -ge 181075968){throw "Subnet overlap: $prefix; STOP, no changes"}
    }
    function Snapshot($name){
        $value=@{adapters=@(Get-NetAdapter -IncludeHidden | Select-Object Name,InterfaceGuid,ifIndex,DriverVersion,Status);addresses=@(Get-NetIPAddress | Select-Object InterfaceIndex,IPAddress,PrefixLength,SkipAsSource);routes=@(Get-NetRoute | Select-Object InterfaceIndex,DestinationPrefix,NextHop,RouteMetric);dns=@(Get-DnsClientServerAddress | Select-Object InterfaceIndex,AddressFamily,ServerAddresses);firewall=@(Get-NetFirewallProfile | Select-Object Name,Enabled);bindings=@(Get-NetAdapterBinding -Name '*' -AllBindings | Select-Object Name,ComponentID,Enabled)}
        $value | ConvertTo-Json -Depth 7 | Set-Content (Join-Path $Evidence $name) -Encoding UTF8
    }
    Snapshot 'before.json'
    # With no PolicyStore, Windows creates both ActiveStore and PersistentStore.
    New-NetIPAddress -InterfaceIndex $idx -IPAddress 10.203.0.1 -PrefixLength 24 -SkipAsSource $false | Out-Null
    foreach($store in @('ActiveStore','PersistentStore')){
        $ip=Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -PolicyStore $store | Where-Object IPAddress -eq '10.203.0.1'
        if(!$ip -or $ip.PrefixLength -ne 24 -or $ip.SkipAsSource){throw "Address verification failed: $store; STOP"}
    }
    Snapshot 'after.json'
    @{status='PASS';guid=[string]$nic[0].InterfaceGuid;index=$idx;address='10.203.0.1/24';active='PASS';persistent='PASS';reboot='NOT TESTED'} | ConvertTo-Json | Set-Content (Join-Path $Evidence 'result.json') -Encoding UTF8
} catch {
    @{status='FAIL';error=$_.Exception.Message;action='STOP'} | ConvertTo-Json | Set-Content (Join-Path $Evidence 'result.json') -Encoding UTF8
    throw
} finally {Stop-Transcript | Out-Null}
