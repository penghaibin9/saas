param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

function Test-LocalPort {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

$Services = @(
    @{ Name = 'PC frontend'; Port = 5173; Script = 'start-pc.ps1' },
    @{ Name = 'Miniapp H5'; Port = 5188; Script = 'start-miniapp.ps1' },
    @{ Name = 'Backend API'; Port = 8000; Script = 'start-backend.ps1' }
)

Write-Host ''
Write-Host 'Starting local student lifecycle system...' -ForegroundColor Cyan

foreach ($Service in $Services) {
    if (Test-LocalPort -Port $Service.Port) {
        Write-Host ("[READY] {0} is already running on port {1}." -f $Service.Name, $Service.Port) -ForegroundColor Green
        continue
    }

    $ServiceScript = Join-Path $PSScriptRoot $Service.Script
    Start-Process -FilePath 'powershell.exe' `
        -WindowStyle Hidden `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $ServiceScript))
    Write-Host ("[START] {0} is starting on port {1}." -f $Service.Name, $Service.Port) -ForegroundColor Yellow
}

$Deadline = (Get-Date).AddSeconds(45)
do {
    $Pending = @($Services | Where-Object { -not (Test-LocalPort -Port $_.Port) })
    if ($Pending.Count -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 750
} while ((Get-Date) -lt $Deadline)

Write-Host ''
foreach ($Service in $Services) {
    if (Test-LocalPort -Port $Service.Port) {
        Write-Host ("[OK] {0}: http://localhost:{1}/" -f $Service.Name, $Service.Port) -ForegroundColor Green
    }
    else {
        Write-Host ("[WAIT] {0} has not opened port {1} yet." -f $Service.Name, $Service.Port) -ForegroundColor Yellow
    }
}

if (-not $NoBrowser -and (Test-LocalPort -Port 5173)) {
    Start-Process 'http://localhost:5173/'
}

Write-Host ''
Write-Host 'Done. This window will close automatically.' -ForegroundColor Cyan
Start-Sleep -Seconds 2
