param([switch]$NoBrowser, [switch]$Restart)
& (Join-Path $PSScriptRoot 'start-sandbox.ps1') -NoBrowser:$NoBrowser -Restart:$Restart
