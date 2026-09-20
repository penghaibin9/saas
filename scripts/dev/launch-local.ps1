param([switch]$NoBrowser, [switch]$Restart, [switch]$PauseOnError)
$ErrorActionPreference = 'Stop'
try {
    & (Join-Path $PSScriptRoot 'start-sandbox.ps1') -NoBrowser:$NoBrowser -Restart:$Restart
    exit 0
} catch {
    Write-Host ''
    Write-Host '[FAILED] Startup did not finish. The original sandbox has not been reset.' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    Write-Host 'Logs: .codex-temp/daily-sandbox'
    if ($PauseOnError) { Read-Host 'Press Enter to close this window' | Out-Null }
    exit 1
}
