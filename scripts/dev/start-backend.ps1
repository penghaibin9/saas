param([switch]$Restart)
& (Join-Path $PSScriptRoot 'start-sandbox.ps1') -Service backend -NoBrowser -Restart:$Restart
