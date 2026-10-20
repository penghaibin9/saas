$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$RuntimeDir = Join-Path $Root '.codex-temp/daily-sandbox'
foreach ($Name in @('enterprise','miniapp','student','pc','backend')) {
    $StatePath = Join-Path $RuntimeDir ($Name + '.json')
    if (-not (Test-Path -LiteralPath $StatePath)) { continue }
    $Saved = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
    $Running = Get-CimInstance Win32_Process -Filter "ProcessId=$($Saved.pid)"
    if (-not $Running) { continue }
    if ($Saved.root -ne $Root -or -not $Running.CommandLine.Contains($Saved.entry) -or $Running.CreationDate.ToUniversalTime().ToString('o') -ne $Saved.created) {
        Write-Warning "Skipping unverified process for $Name."
        continue
    }
    $ProcessTree = @(Get-CimInstance Win32_Process)
    $StopIds = @([int]$Saved.pid)
    do {
        $Children = @($ProcessTree | Where-Object { $_.ParentProcessId -in $StopIds -and $_.ProcessId -notin $StopIds } | Select-Object -ExpandProperty ProcessId)
        $StopIds += $Children
    } while ($Children.Count)
    foreach ($StopId in $StopIds) { Stop-Process -Id $StopId -ErrorAction SilentlyContinue }
    Write-Host "[OK] Stopped managed $Name."
}
Write-Host 'Sandbox database and Redis remain running; saved business records are retained.'
