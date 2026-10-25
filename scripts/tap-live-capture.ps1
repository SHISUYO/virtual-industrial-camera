param([Parameter(Mandatory=$true)][string]$Evidence,[Parameter(Mandatory=$true)][ValidateSet('start','stop')][string]$Action)
# Own capture session only. Does not add/remove filters or install capture drivers.
$ErrorActionPreference='Stop'
$Evidence=[IO.Path]::GetFullPath($Evidence)
New-Item -ItemType Directory -Force $Evidence | Out-Null
if($Action -eq 'start') {
    if(Test-Path (Join-Path $Evidence 'capture-owned.txt')){throw 'Capture already attempted here'}
    & pktmon.exe status | Out-File (Join-Path $Evidence 'pktmon-before.txt') -Encoding utf8
    & pktmon.exe filter list | Out-File (Join-Path $Evidence 'pktmon-filters.txt') -Encoding utf8
    & pktmon.exe list | Out-File (Join-Path $Evidence 'pktmon-components.txt') -Encoding utf8
    & pktmon.exe start --capture --comp all --pkt-size 0 --file-name (Join-Path $Evidence 'packets.etl') --file-size 128 --log-mode circular | Out-File (Join-Path $Evidence 'pktmon-start.txt') -Encoding utf8
    if($LASTEXITCODE -ne 0){$message='NOT TESTED: cannot start an independent capture; no existing session stopped';$message | Set-Content (Join-Path $Evidence 'capture-result.txt');Write-Output $message;exit 1}
    # Successful start means this invocation created the single PktMon session.
    (Join-Path $Evidence 'packets.etl') | Set-Content (Join-Path $Evidence 'capture-owned.txt')
} else {
    $owned=Join-Path $Evidence 'capture-owned.txt'
    if(!(Test-Path $owned)){throw 'No owned capture session recorded; refusing stop'}
    # Check status refers to our exact ETL before stopping, never stop another session.
    $status=(& pktmon.exe status | Out-String)
    $status | Set-Content (Join-Path $Evidence 'pktmon-before-stop.txt') -Encoding utf8
    if(!$status.Contains((Join-Path $Evidence 'packets.etl'))){throw 'Current capture path does not match the recorded owned session; refusing stop'}
    & pktmon.exe stop | Out-File (Join-Path $Evidence 'pktmon-stop.txt') -Encoding utf8
    if($LASTEXITCODE -ne 0){throw 'Capture stop failed; inspect status'}
    & pktmon.exe list --json | Out-File (Join-Path $Evidence 'pktmon-all-components.json') -Encoding utf8
    & pktmon.exe etl2pcap (Join-Path $Evidence 'packets.etl') --out (Join-Path $Evidence 'packets.pcapng') | Out-File (Join-Path $Evidence 'pktmon-convert.txt') -Encoding utf8
    & pktmon.exe etl2pcap (Join-Path $Evidence 'packets.etl') --drop-only --out (Join-Path $Evidence 'drops.pcapng') | Out-File (Join-Path $Evidence 'pktmon-drops.txt') -Encoding utf8
    & pktmon.exe etl2txt (Join-Path $Evidence 'packets.etl') --out (Join-Path $Evidence 'packets.txt') | Out-File (Join-Path $Evidence 'pktmon-text.txt') -Encoding utf8
    'Captured actual NDIS packets; inspect ETL/PCAPNG and filters for scope.' | Set-Content (Join-Path $Evidence 'capture-result.txt')
}
