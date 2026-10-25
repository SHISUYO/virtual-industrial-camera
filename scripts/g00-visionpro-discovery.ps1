param([switch]$Acquire)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$assemblies = 'C:/Program Files/Cognex/VisionPro/ReferencedAssemblies'
$response = @"
/nologo
/platform:x64
/r:"$assemblies/Cognex.VisionPro.dll"
/r:"$assemblies/Cognex.VisionPro.Core.dll"
/out:"$root/out/g00/g00-visionpro-discovery.exe"
"$root/tests/automated/g00-visionpro-discovery.cs"
"@
$response.Replace('/', '\').Replace('\nologo', '/nologo').Replace('\platform:', '/platform:').Replace('\r:', '/r:').Replace('\out:', '/out:') | Set-Content "$root/out/g00/visionpro.rsp"
$oldPassing = $PSNativeCommandArgumentPassing
$PSNativeCommandArgumentPassing = 'Legacy'
try {
    Set-Content "$root/tests/evidence/G00/visionpro-probe-build.txt" 'Compiling Cognex x64 SDK probe'
    & C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe "@$root/out/g00/visionpro.rsp" 2>&1 | Tee-Object "$root/tests/evidence/G00/visionpro-probe-build.txt" -Append
} finally { $PSNativeCommandArgumentPassing = $oldPassing }
if ($LASTEXITCODE -ne 0) { throw 'Cognex probe compilation failed' }
Add-Content "$root/tests/evidence/G00/visionpro-probe-build.txt" 'CompilerExitCode=0'
$processArgs = @{
    FilePath = "$root/out/g00/g00-visionpro-discovery.exe"
    WindowStyle = 'Hidden'
    PassThru = $true
    RedirectStandardOutput = "$root/tests/evidence/G00/visionpro-discovery.txt"
    RedirectStandardError = "$root/tests/evidence/G00/visionpro-error.txt"
}
if ($Acquire) { $processArgs.ArgumentList = '--acquire' }
$probe = Start-Process @processArgs
if (!$probe.WaitForExit(30000)) {
    $probe.Kill()
    throw 'Cognex probe exceeded 30 seconds; owned probe process terminated'
}
$probe.Refresh()
$probeExit = $probe.ExitCode
Get-Content "$root/tests/evidence/G00/visionpro-discovery.txt"
Get-Content "$root/tests/evidence/G00/visionpro-error.txt"
if ($probeExit -eq 2) { throw 'Cognex enumeration did not find serial VICG00 (discovery FAIL)' }
if ($probeExit -ne 0) { throw "Cognex probe execution failed: $probeExit" }
