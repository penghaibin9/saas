# =============================================================================
# scripts/deploy/deploy-server-check.ps1 —— 上线前「服务器就绪自检」（只读，不改任何数据）
# 检查：前端/H5 是否已构建、部署配置是否齐、后端健康、MySQL 连接、演示数据规模。
# 用法（仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File scripts\deploy\deploy-server-check.ps1
#   可选参数： -ApiBase http://服务器IP  (默认 http://localhost:8000)
# =============================================================================
param(
    [string]$ApiBase = "http://localhost:8000"
)
$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RepoRoot "backend"
$pass = 0; $warn = 0; $fail = 0
function Ok($m){ Write-Host "  [OK]   $m" -ForegroundColor Green; $script:pass++ }
function Warn($m){ Write-Host "  [WARN] $m" -ForegroundColor Yellow; $script:warn++ }
function Fail($m){ Write-Host "  [FAIL] $m" -ForegroundColor Red; $script:fail++ }

Write-Host "== 部署就绪自检 ==" -ForegroundColor Cyan

# 1) 构建产物
Write-Host "`n[1] 前端 / H5 构建产物"
if (Test-Path (Join-Path $RepoRoot "frontend\dist\index.html")) { Ok "PC frontend/dist 已构建" }
else { Warn "未找到 frontend/dist —— 先跑 scripts\deploy\build-pc.ps1" }
if (Test-Path (Join-Path $RepoRoot "miniapp\dist\build\h5\index.html")) { Ok "miniapp H5 dist 已构建" }
else { Warn "未找到 miniapp/dist/build/h5 —— 先跑 scripts\deploy\build-miniapp.ps1" }

# 2) 部署配置
Write-Host "`n[2] MySQL 版部署配置"
foreach ($f in @(
    "deploy\docker\docker-compose.mysql.yml",
    "deploy\nginx\nginx.mysql.conf",
    "deploy\env\backend.mysql.env.example")) {
    if (Test-Path (Join-Path $RepoRoot $f)) { Ok $f } else { Fail "缺少 $f" }
}
if (Test-Path (Join-Path $BackendDir ".env")) { Ok "backend\.env 存在" }
else { Warn "backend\.env 不存在（本机直跑后端时需要；docker 用 backend.mysql.env）" }

# 3) 后端健康 + 关键接口
Write-Host "`n[3] 后端健康检查（$ApiBase）"
try {
    $h = Invoke-RestMethod -Uri "$ApiBase/health" -TimeoutSec 5
    Ok "GET /health 可达"
} catch { Warn "GET /health 不可达（后端可能未启动）：$($_.Exception.Message)" }
try {
    Invoke-RestMethod -Uri "$ApiBase/openapi.json" -TimeoutSec 5 | Out-Null
    Ok "GET /openapi.json 可达（Swagger: $ApiBase/api/v1/docs 或 /docs）"
} catch { Warn "GET /openapi.json 不可达" }

# 4) MySQL 连接 + 数据规模（调用后端只读脚本）
Write-Host "`n[4] MySQL 连接与演示数据规模"
$py = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Push-Location $BackendDir
try {
    & $py "scripts\check_mysql_connection.py"
    if ($LASTEXITCODE -eq 0) { Ok "MySQL 连接检查通过" }
    elseif ($LASTEXITCODE -eq 2) { Warn "MySQL 参数不全（多半是没填 DB_PASSWORD）——见上方提示" }
    else { Fail "MySQL 连接失败（退出码 $LASTEXITCODE）" }
} finally { Pop-Location }

# 汇总
Write-Host "`n== 自检结果：PASS=$pass WARN=$warn FAIL=$fail ==" -ForegroundColor Cyan
if ($fail -gt 0) { Write-Host "存在 FAIL，请先修复再上线。" -ForegroundColor Red; exit 1 }
if ($warn -gt 0) { Write-Host "有 WARN（多为未构建/未启动），按提示补齐即可。" -ForegroundColor Yellow; exit 0 }
Write-Host "全部通过，可以上服务器演示。" -ForegroundColor Green
exit 0
