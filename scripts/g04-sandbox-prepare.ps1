$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$package=Join-Path $root 'out/g04/sandbox/runtime'
$logs=Join-Path $root 'tests/evidence/G04/sandbox'
New-Item -ItemType Directory -Force $package,$logs | Out-Null
foreach($name in @('VICGigE.exe','opencv_world4120.dll','opencv_videoio_ffmpeg4120_64.dll')) {
    Copy-Item -LiteralPath (Join-Path $root "out/g04/build/$name") -Destination $package
}
$crt='C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Redist/MSVC/14.44.35112/x64/Microsoft.VC143.CRT'
Get-ChildItem $crt -Filter '*.dll' | Copy-Item -Destination $package
Copy-Item -LiteralPath (Join-Path $root 'assets/g01-camera.ini') -Destination (Join-Path $package 'camera.ini')
# The firewall rule is confined to the disposable guest and this executable.
$startup=@'
@echo off
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { New-NetFirewallRule -DisplayName 'VIC G04 Guest UDP' -Direction Inbound -Program 'C:\VIC\VICGigE.exe' -Protocol UDP -Action Allow | Out-Null; $addresses=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' }); if($addresses.Count -ne 1){throw 'Expected one guest IPv4'}; $ip=$addresses[0].IPAddress; @{IPAddress=$ip;Computer=$env:COMPUTERNAME} | ConvertTo-Json | Set-Content 'C:\VICLogs\guest.json'; & 'C:\VIC\VICGigE.exe' --bind $ip --config 'C:\VIC\camera.ini' --duration-ms 1200000 --log 'C:\VICLogs\server.txt' --dump-xml 'C:\VICLogs\device.xml' *> 'C:\VICLogs\console.txt'; if($LASTEXITCODE -ne 0){throw ('Server exit '+$LASTEXITCODE)} } catch { $_ | Out-String | Set-Content 'C:\VICLogs\guest-error.txt' }"
'@
$startup | Set-Content (Join-Path $package 'guest-start.cmd') -Encoding ascii
$escapedPackage=[Security.SecurityElement]::Escape($package)
$escapedLogs=[Security.SecurityElement]::Escape($logs)
$config=@"
<Configuration>
 <vGPU>Disable</vGPU><Networking>Enable</Networking><MemoryInMB>4096</MemoryInMB>
 <AudioInput>Disable</AudioInput><VideoInput>Disable</VideoInput>
 <ClipboardRedirection>Disable</ClipboardRedirection><PrinterRedirection>Disable</PrinterRedirection>
 <MappedFolders>
  <MappedFolder><HostFolder>$escapedPackage</HostFolder><SandboxFolder>C:\VIC</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
  <MappedFolder><HostFolder>$escapedLogs</HostFolder><SandboxFolder>C:\VICLogs</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder>
 </MappedFolders>
 <LogonCommand><Command>cmd.exe /c C:\VIC\guest-start.cmd</Command></LogonCommand>
</Configuration>
"@
$config | Set-Content (Join-Path $root 'out/g04/sandbox/VIC-G04.wsb') -Encoding UTF8
Write-Output (Join-Path $root 'out/g04/sandbox/VIC-G04.wsb')
