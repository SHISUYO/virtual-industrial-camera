# PowerShell 5.1 turns native stderr into ErrorRecord objects. Convert them to
# plain text before Tee-Object, and decide success from the actual exit code.
function Invoke-PythonLogged {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$LogPath
    )
    $pythonCommand=Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $savedPreference=$ErrorActionPreference
    $pythonExitCode=$null
    try {
        $ErrorActionPreference='Continue'
        $global:LASTEXITCODE=$null
        & $pythonCommand.Source @Arguments 2>&1 |
            ForEach-Object { $_.ToString() } |
            Tee-Object -FilePath $LogPath -ErrorAction Stop
        $pythonExitCode=$LASTEXITCODE
    } finally {
        $ErrorActionPreference=$savedPreference
    }
    if($null -eq $pythonExitCode -or $pythonExitCode -ne 0) {
        throw "Python check failed (exit=$pythonExitCode). Full output: $LogPath"
    }
}
