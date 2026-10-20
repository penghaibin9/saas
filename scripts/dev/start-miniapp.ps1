param([switch]$Restart)
& (Join-Path $PSScriptRoot 'start-sandbox.ps1') -Service miniapp -NoBrowser -Restart:$Restart
