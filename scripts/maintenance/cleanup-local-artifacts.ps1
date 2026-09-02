param(
    [switch]$Apply,
    [string]$BackupRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
if (-not $BackupRoot) {
    $BackupRoot = Join-Path $repoRoot "_local-backup\local-artifacts-$stamp"
}

$allowedRelativeTargets = @(
    '.codex-artifacts',
    '.cache',
    '.pytest_cache',
    '_run',
    'backend\__pycache__',
    'backend\.pytest_cache',
    'backend\test-results',
    'backend\tmp',
    'enterprise-portal\dist',
    'enterprise-portal\node_modules',
    'frontend\dist',
    'frontend\node_modules',
    'miniapp\dist',
    'miniapp\node_modules',
    'student-portal\dist',
    'student-portal\node_modules'
)

function Assert-RepoChild([string]$PathValue) {
    $full = [IO.Path]::GetFullPath($PathValue)
    $prefix = $repoRoot.TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside repository: $full"
    }
    return $full
}

$found = @()
foreach ($relative in $allowedRelativeTargets) {
    $candidate = Assert-RepoChild (Join-Path $repoRoot $relative)
    if (Test-Path -LiteralPath $candidate) {
        $measure = Get-ChildItem -LiteralPath $candidate -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum
        $found += [pscustomobject]@{
            RelativePath = $relative
            FullPath = $candidate
            Files = $measure.Count
            SizeMB = [math]::Round(($measure.Sum / 1MB), 2)
        }
    }
}

if (-not $Apply) {
    Write-Host 'PREVIEW ONLY. Nothing was changed.' -ForegroundColor Yellow
    $found | Format-Table RelativePath, Files, SizeMB -AutoSize
    exit 0
}

$backupFull = [IO.Path]::GetFullPath($BackupRoot)
$backupParent = [IO.Path]::GetFullPath((Join-Path $repoRoot '_local-backup'))
if (-not $backupFull.StartsWith($backupParent.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "BackupRoot must stay below _local-backup: $backupFull"
}
New-Item -ItemType Directory -Force -Path $backupFull | Out-Null

foreach ($item in $found) {
    $destination = Join-Path $backupFull $item.RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $item.FullPath -Destination $destination -Recurse -Force
    $resolvedTarget = Assert-RepoChild $item.FullPath
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    Write-Host "Backed up and removed $($item.RelativePath)" -ForegroundColor Green
}

$found | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupFull 'cleanup-manifest.json') -Encoding UTF8
Write-Host "Backup: $backupFull" -ForegroundColor Cyan
