# =============================================================================
# scripts/deploy/mysql-init.ps1 —— 一键把 MySQL 从空库带到「可演示」
#   顺序：check_mysql_connection → init_mysql_db（建库建表）→ seed_mysql_demo_data（灌数据）
# 前提：已在 backend/.env 填好 DB_DRIVER=mysql + DB_HOST/PORT/NAME/USER/DB_PASSWORD。
#      本脚本不打印、不索取密码；密码只从 backend/.env 读取。
# 用法（在仓库根目录）：
#   powershell -ExecutionPolicy Bypass -File scripts\deploy\mysql-init.ps1
# =============================================================================
$ErrorActionPreference = "Stop"
$RepoRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$BackendDir = Join-Path $RepoRoot "backend"

Write-Host "== MySQL 初始化 ==" -ForegroundColor Cyan
Write-Host "backend 目录: $BackendDir"

# 选择 python：优先 backend/.venv，其次 PATH
$py = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# 提示 .env 是否存在
$envFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "⚠️  未找到 backend\.env。请先复制并填写：" -ForegroundColor Yellow
    Write-Host "    copy backend\.env.example backend\.env"
    Write-Host "    然后在 .env 里设置 DB_ENABLED=true / DB_DRIVER=mysql / DB_* / DB_PASSWORD"
    Write-Host "    再重跑本脚本。"
    exit 2
}

Push-Location $BackendDir
try {
    Write-Host "`n[1/3] 检查 MySQL 连接 ..." -ForegroundColor Cyan
    & $py "scripts\check_mysql_connection.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 连接检查未通过（退出码 $LASTEXITCODE）。请按上面的提示修正 backend\.env 后重跑。" -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "`n[2/3] 建库 + 建表 ..." -ForegroundColor Cyan
    & $py "scripts\init_mysql_db.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "❌ 建库建表失败（退出码 $LASTEXITCODE）。" -ForegroundColor Red; exit $LASTEXITCODE }

    Write-Host "`n[3/3] 灌演示种子数据 ..." -ForegroundColor Cyan
    & $py "scripts\seed_mysql_demo_data.py"
    if ($LASTEXITCODE -ne 0) { Write-Host "❌ 种子数据失败（退出码 $LASTEXITCODE）。" -ForegroundColor Red; exit $LASTEXITCODE }

    Write-Host "`n✅ MySQL 就绪：库表已建、演示数据已灌。" -ForegroundColor Green
    Write-Host "   启动后端： uvicorn app.main:app --host 0.0.0.0 --port 8000"
    Write-Host "   验收：demo-school=5 学生 / 主租户=100 学生；演示账号密码 Demo@2026（库内 hash，不展示）"
}
finally {
    Pop-Location
}
