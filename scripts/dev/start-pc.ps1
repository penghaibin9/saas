param([switch]$Restart)
& (Join-Path $PSScriptRoot 'start-sandbox.ps1') -Service pc -NoBrowser -Restart:$Restart
