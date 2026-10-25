param([string]$Destination = 'out/github-public-snapshot')

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outRoot = [IO.Path]::GetFullPath((Join-Path $root 'out'))
$destinationPath = [IO.Path]::GetFullPath((Join-Path $root $Destination))
if (!$destinationPath.StartsWith($outRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Snapshot destination must stay inside out/'
}
if (Test-Path -LiteralPath $destinationPath) { throw "Snapshot directory already exists: $destinationPath" }

$prefixes = @('src/', 'control/', 'poc/tap-camera/', 'assets/', 'installer/', 'scripts/', 'tests/automated/')
$exact = @('.gitignore', '.gitattributes', 'AGENTS.md', 'CMakeLists.txt', 'README.md', 'LICENSE',
    'CHANGELOG.md', 'docs/SPEC.md', 'docs/GIGE.md', 'docs/PUBLISHING.md')
$tracked = & git -C $root ls-files
if ($LASTEXITCODE -ne 0) { throw 'Unable to read tracked files' }
$candidates = @($tracked) + $exact + @('scripts/prepare-github-snapshot.ps1')
$selected = @($candidates | Sort-Object -Unique | Where-Object {
    $name = $_.Replace('\', '/')
    ($exact -contains $name) -or [bool](@($prefixes | Where-Object { $name.StartsWith($_, [StringComparison]::Ordinal) }).Count)
})

$textExtensions = @('.md', '.ps1', '.py', '.cpp', '.hpp', '.h', '.cs', '.xaml', '.xml', '.json', '.ini', '.txt', '.iss', '.cmake', '.yml', '.yaml')
$privateUser = [regex]::Escape($env:USERNAME)
$credentialPattern = '(?i)' + ('github_' + 'pat_') + '[A-Za-z0-9_]+' + '|' + ('gh' + 'p_') + '[A-Za-z0-9]{20,}'
$files = @()
foreach ($name in $selected) {
    $relative = $name.Replace('/', [IO.Path]::DirectorySeparatorChar)
    $source = Join-Path $root $relative
    if (!(Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing source file: $name" }
    $file = Get-Item -LiteralPath $source
    if ($file.Length -gt 50MB) { throw "File exceeds snapshot limit: $name" }
    if (($textExtensions -contains $file.Extension.ToLowerInvariant()) -or $name -in @('.gitignore', '.gitattributes', 'CMakeLists.txt')) {
        $content = Get-Content -LiteralPath $source -Raw
        if ($content -match $privateUser -or $content -match '(?i)[A-Z]:[\\/]Users[\\/]' -or $content -match $credentialPattern) {
            throw "Private machine path or credential-like string found in: $name"
        }
    }
    $files += [pscustomobject]@{ Name = $relative; Source = $source; Bytes = $file.Length }
}

New-Item -ItemType Directory -Path $destinationPath | Out-Null
foreach ($file in $files) {
    $target = Join-Path $destinationPath $file.Name
    $parent = Split-Path $target -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Copy-Item -LiteralPath $file.Source -Destination $target
}
$commit = (& git -C $root rev-parse --short HEAD).Trim()
@(
    '# Public source snapshot',
    '',
    "Exported from development commit: $commit",
    "Files: $($files.Count)",
    '',
    'This directory intentionally omits Git history, local logs, packet captures,',
    'diagnostic ZIPs, tests/evidence, user-specific manual records and build outputs.',
    'Review licensing, dependencies and the build limitations in docs/PUBLISHING.md',
    'before creating a public GitHub repository.'
) | Set-Content -LiteralPath (Join-Path $destinationPath 'SOURCE_SNAPSHOT.md') -Encoding utf8
Write-Host "SNAPSHOT: $destinationPath"
Write-Host "FILES: $($files.Count)"
Write-Host "BYTES: $(($files | Measure-Object Bytes -Sum).Sum)"
Write-Host "SOURCE_COMMIT: $commit"
