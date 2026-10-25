param([string]$DeploymentEvidence,[string]$EvidenceRoot)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
if(!$DeploymentEvidence){
    $candidates=@(Get-ChildItem (Join-Path $root 'tests/evidence/tap-r2') -Filter configure-result.json -Recurse | Where-Object { (Get-Content $_.FullName -Raw | ConvertFrom-Json).status -eq 'PASS' })
    if($candidates.Count -ne 1){throw 'Supply -DeploymentEvidence for the one approved R2 deployment'}
    $DeploymentEvidence=$candidates[0].DirectoryName
}
$ev=[IO.Path]::GetFullPath($DeploymentEvidence)
$record=Get-Content (Join-Path $ev 'configure-result.json') -Raw | ConvertFrom-Json
if($record.status -ne 'PASS'){throw 'R2 deployment is not confirmed'}
$id=$record.identity
$nic=@(Get-NetAdapter -IncludeHidden | Where-Object {[string]$_.InterfaceGuid -eq $id.guid})
if($nic.Count -ne 1 -or $nic[0].Name -ne 'VIC-PoC-TAP' -or $nic[0].PnPDeviceID -ne $id.pnp_id){throw 'Recorded dedicated TAP does not match; no test started'}
$ip=Get-NetIPAddress -InterfaceIndex $id.ifIndex -IPAddress 10.203.0.1
if($ip.PrefixLength -ne 24 -or $ip.SkipAsSource){throw 'New TAP needs the approved 10.203.0.1/24 with SkipAsSource=false; no configuration changed'}
if(Get-Process VICGigE,VICTapPoC,CogQuickBuild,WindowsSandbox -ErrorAction SilentlyContinue){throw 'Close Sandbox, VICGigE, VICTapPoC and QuickBuild before this test'}
$capture=Join-Path $ev ('manual-capture-'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
if($EvidenceRoot){
    $EvidenceRoot=[IO.Path]::GetFullPath($EvidenceRoot)
    New-Item -ItemType Directory -Path $EvidenceRoot -ErrorAction Stop | Out-Null
    $capture=Join-Path $EvidenceRoot 'capture'
    # Read-only environment evidence. Never changes firewall policy or rules.
    @(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction) | ConvertTo-Json | Set-Content (Join-Path $EvidenceRoot 'firewall-observed.json') -Encoding UTF8
}
$admin=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
try {
    if($admin){& (Join-Path $PSScriptRoot 'tap-live-capture.ps1') -Evidence $capture -Action start}
    else {Write-Output 'NDIS capture NOT TESTED: use an administrator PowerShell for PktMon. TAP boundary capture remains enabled.'}
    $arguments=@('-u',(Join-Path $root 'tests/automated/tap_live_run.py'),'--deployment',$ev)
    if($EvidenceRoot){$arguments+=@('--out',(Join-Path $EvidenceRoot 'live'))}
    & python @arguments
    $code=$LASTEXITCODE
} finally {
    if(Test-Path (Join-Path $capture 'capture-owned.txt')){& (Join-Path $PSScriptRoot 'tap-live-capture.ps1') -Evidence $capture -Action stop}
}
Write-Output "CHECK FINISHED exit=$code. Discovery/FIFO are separate from valid images. Preserve all FAIL/NOT TESTED items."
Write-Output "DEPLOYMENT EVIDENCE: $ev"
if($EvidenceRoot){Write-Output "G04-D RUN EVIDENCE: $EvidenceRoot"}
exit $code
