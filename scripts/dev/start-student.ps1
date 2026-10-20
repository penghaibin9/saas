param([switch]$Restart)
& (Join-Path $PSScriptRoot 'start-sandbox.ps1') -Service student -NoBrowser -Restart:$Restart
