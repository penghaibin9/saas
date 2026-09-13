param(
    [ValidateSet('all','backend','pc','student','miniapp','enterprise')][string]$Service = 'all',
    [switch]$NoBrowser,
    [switch]$Restart
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$RuntimeDir = Join-Path $Root '.codex-temp/daily-sandbox'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
try {
    $StartupLock = [System.IO.File]::Open((Join-Path $RuntimeDir 'startup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
} catch { throw 'The sandbox launcher is already running. Wait for its current startup to finish.' }
try {
$Python = Join-Path $Root 'backend/.venv/Scripts/python.exe'
$Node = (Get-Command node -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $Python)) { throw 'The existing backend virtual environment is required.' }

# One explicit backend target for every local client, regardless of inherited task variables.
$env:VITE_PROXY_TARGET = 'http://127.0.0.1:8000'
$env:VITE_DEV_API_PROXY_TARGET = 'http://127.0.0.1:8000'
$env:VITE_API_BASE_URL = ''
$env:VITE_USE_MOCK = 'false'
$env:VITE_ALLOW_MOCK_FALLBACK = 'false'
$env:VITE_PORTAL_TEACHER_LOGIN_URL = '/login?tenant=sandbox-school'
$env:VITE_PORTAL_STUDENT_LOGIN_URL = 'http://localhost:5199/portal/login?tenant=sandbox-school'
$env:VITE_PORTAL_ENTERPRISE_LOGIN_URL = 'http://localhost:5202/enterprise/login?tenant=sandbox-school'
$env:VITE_PORTAL_TEACHER_H5_LOGIN_URL = 'http://localhost:5188/#/pages/login/teacher/index?tenant=sandbox-school'
$env:VITE_PORTAL_STUDENT_H5_LOGIN_URL = 'http://localhost:5188/#/pages/login/student/index?tenant=sandbox-school'
$env:PYTHONUTF8 = '1'

    Write-Host '[1/4] Checking Docker Desktop...' -ForegroundColor Cyan
    function Test-SandboxDockerReady {
        # PowerShell 5 turns native stderr into a terminating error under Stop.
        # A starting engine is an expected failed probe, not a launcher crash.
        try { & docker info --format '{{.ServerVersion}}' *> $null; return $LASTEXITCODE -eq 0 }
        catch { return $false }
    }
    if (-not (Test-SandboxDockerReady)) {
        $DockerExe = (Get-Command docker -ErrorAction Stop).Source
        $DockerDesktop = Join-Path (Split-Path (Split-Path (Split-Path $DockerExe -Parent) -Parent) -Parent) 'Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $DockerDesktop)) { throw 'Docker Desktop is required to start the existing sandbox containers.' }
        Start-Process -FilePath $DockerDesktop -WindowStyle Hidden
        $DockerDeadline = (Get-Date).AddSeconds(60)
        do {
            Start-Sleep -Milliseconds 1000
            $DockerReady = Test-SandboxDockerReady
        } while (-not $DockerReady -and (Get-Date) -lt $DockerDeadline)
        if (-not $DockerReady) { throw 'Docker Desktop is still starting. Wait for Docker to finish, then run this launcher again.' }
    }
    Write-Host '[2/4] Starting the original sandbox MySQL and Redis containers...' -ForegroundColor Cyan
    foreach ($Container in @('student-lifecycle-v8-mysql','codex-phone-local-redis-1')) {
        & docker start $Container | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Cannot start existing container $Container. Start Docker Desktop first." }
    }
Write-Host '[3/4] Waiting for MySQL; verifying the original school and database (up to 5 minutes)...' -ForegroundColor Cyan
& $Python (Join-Path $PSScriptRoot 'check-sandbox-runtime.py') wait
if ($LASTEXITCODE -ne 0) { throw 'Sandbox identity/version verification failed. No application service was started.' }

$Services = @(
    @{ Name='backend'; Port=8000; Dir='backend'; Exe=$Python; Entry=(Join-Path $PSScriptRoot 'check-sandbox-runtime.py'); Args='serve'; Url='http://127.0.0.1:8000/health' },
    @{ Name='pc'; Port=5173; Dir='frontend'; Exe=$Node; Entry=(Join-Path $Root 'frontend/node_modules/vite/bin/vite.js'); Args='--host 127.0.0.1 --port 5173 --strictPort'; Url='http://127.0.0.1:5173/login' },
    @{ Name='student'; Port=5199; Dir='student-portal'; Exe=$Node; Entry=(Join-Path $Root 'student-portal/node_modules/vite/bin/vite.js'); Args='--host 127.0.0.1 --port 5199 --strictPort'; Url='http://127.0.0.1:5199/portal/login' },
    @{ Name='miniapp'; Port=5188; Dir='miniapp'; Exe=$Node; Entry=(Join-Path $Root 'miniapp/node_modules/@dcloudio/vite-plugin-uni/bin/uni.js'); Args='--host 127.0.0.1 --port 5188 --strictPort'; Url='http://127.0.0.1:5188/' },
    @{ Name='enterprise'; Port=5202; Dir='enterprise-portal'; Exe=$Node; Entry=(Join-Path $Root 'enterprise-portal/node_modules/vite/bin/vite.js'); Args='--host 127.0.0.1 --port 5202 --strictPort'; Url='http://127.0.0.1:5202/enterprise/login' }
)
if ($Service -ne 'all') { $Services = @($Services | Where-Object { $_.Name -in @('backend', $Service) }) }

Write-Host '[4/4] Starting application services...' -ForegroundColor Cyan
foreach ($Item in $Services) {
    Write-Host "[START] $($Item.Name), port $($Item.Port)" -ForegroundColor Cyan
    $StatePath = Join-Path $RuntimeDir ($Item.Name + '.json')
    $Saved = if (Test-Path -LiteralPath $StatePath) { Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json } else { $null }
    $SavedProcess = if ($Saved) { Get-CimInstance Win32_Process -Filter "ProcessId=$($Saved.pid)" } else { $null }
    # PowerShell 7 converts ISO timestamps in JSON back to DateTime and its string
    # formatting drops fractional seconds. Compare DateTime values so a process
    # started by this launcher is still recognised after the state file is read.
    $SavedCreatedUtc = if ($Saved -and $Saved.created) { ([datetime]$Saved.created).ToUniversalTime() } else { $null }
    $CreatedMatches = $SavedProcess -and $SavedCreatedUtc -and `
        [Math]::Abs(($SavedProcess.CreationDate.ToUniversalTime() - $SavedCreatedUtc).TotalSeconds) -lt 1
    $Owned = $SavedProcess -and $SavedProcess.CommandLine.Contains($Item.Entry) -and $CreatedMatches
    $Changed = $false
    if ($Owned) {
        $Inputs = @(Get-ChildItem -LiteralPath (Join-Path $Root $Item.Dir) -File -Force | Where-Object { $_.Name -like '.env*' -or $_.Name -like 'vite.config.*' })
        $Inputs += Get-Item -LiteralPath $PSCommandPath
        if ($Item.Name -eq 'backend') {
            $Inputs += Get-Item -LiteralPath $Item.Entry
            $Inputs += Get-ChildItem -LiteralPath (Join-Path $Root 'backend/app') -Recurse -File -Filter '*.py'
        }
        $Changed = @($Inputs | Where-Object { $_.LastWriteTimeUtc -gt $SavedProcess.CreationDate.ToUniversalTime() }).Count -gt 0
    }
    if ($Owned -and ($Restart -or $Changed)) {
        # Stop only this launcher's verified process and descendants, never arbitrary port owners.
        $ProcessTree = @(Get-CimInstance Win32_Process)
        $StopIds = @([int]$Saved.pid)
        do {
            $Children = @($ProcessTree | Where-Object { $_.ParentProcessId -in $StopIds -and $_.ProcessId -notin $StopIds } | Select-Object -ExpandProperty ProcessId)
            $StopIds += $Children
        } while ($Children.Count)
        foreach ($StopId in $StopIds) { Stop-Process -Id $StopId -ErrorAction SilentlyContinue }
        $StopDeadline = (Get-Date).AddSeconds(10)
        while ((Get-NetTCPConnection -State Listen -LocalPort $Item.Port -ErrorAction SilentlyContinue) -and (Get-Date) -lt $StopDeadline) {
            Start-Sleep -Milliseconds 200
        }
        $Owned = $false
    }
    if (-not $Owned) {
        $Listener = Get-NetTCPConnection -State Listen -LocalPort $Item.Port -ErrorAction SilentlyContinue
        if ($Listener) { throw "Port $($Item.Port) belongs to an unverified process. Refusing to reuse it or silently change ports." }
        if (-not (Test-Path -LiteralPath $Item.Entry)) { throw "Missing installed dependency for $($Item.Name)." }
        $env:VITE_API_BASE_URL = if ($Item.Name -eq 'miniapp') { 'http://127.0.0.1:8000' } else { '' }
        $Process = Start-Process -FilePath $Item.Exe -WorkingDirectory (Join-Path $Root $Item.Dir) -WindowStyle Hidden -PassThru `
            -ArgumentList ('"' + $Item.Entry + '" ' + $Item.Args) `
            -RedirectStandardOutput (Join-Path $RuntimeDir ($Item.Name + '.out.log')) `
            -RedirectStandardError (Join-Path $RuntimeDir ($Item.Name + '.err.log'))
        $Started = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
        @{ pid=$Process.Id; created=$Started.CreationDate.ToUniversalTime().ToString('o'); root=$Root; entry=$Item.Entry; port=$Item.Port } |
            ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
    }
    $Ready = $false
    $Deadline = (Get-Date).AddSeconds(60)
    do {
        try { $Response = Invoke-WebRequest -UseBasicParsing -Uri $Item.Url -TimeoutSec 3; $Ready = $Response.StatusCode -eq 200 } catch { }
        if (-not $Ready) { Start-Sleep -Milliseconds 500 }
    } while (-not $Ready -and (Get-Date) -lt $Deadline)
    if (-not $Ready) { throw "$($Item.Name) did not become ready. See .codex-temp/daily-sandbox logs." }
    Write-Host "[OK] $($Item.Name) $($Item.Url) -> sandbox-school" -ForegroundColor Green
}
if (-not $NoBrowser -and $Service -in @('all','pc')) { Start-Process 'http://localhost:5173/login?tenant=sandbox-school' }
} finally { $StartupLock.Dispose() }
