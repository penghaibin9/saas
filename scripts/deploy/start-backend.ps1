# ==========================================================
#  本地部署预演：用 Docker Compose 启动 backend（自动带上 postgres + redis 依赖）
#  默认只起 backend/postgres/redis，不起 nginx（PC/miniapp 静态站点未必已 build）。
#  如需连 nginx 一起起（需先跑 build-pc.ps1 / build-miniapp.ps1）：
#    powershell -ExecutionPolicy Bypass -File scripts\deploy\start-backend.ps1 -All
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\deploy\start-backend.ps1
# ==========================================================
param(
    [switch]$All   # 加此参数：连 nginx 一起启动完整预演栈
)

$Root       = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$ComposeDir = Join-Path $Root 'deploy\docker'
$ComposeFile = Join-Path $ComposeDir 'docker-compose.local.yml'
$EnvExample  = Join-Path $Root 'deploy\env\backend.env.example'
$EnvFile     = Join-Path $Root 'deploy\env\backend.env'

Write-Host ''
Write-Host '================ [本地部署预演] 启动 backend ================' -ForegroundColor Cyan

# 1. 检查 compose 文件
if (-not (Test-Path $ComposeFile)) {
    Write-Host "[X] 没有找到 $ComposeFile" -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

# 2. 检查 Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host '[X] 电脑上没有安装 Docker（找不到 docker 命令）。请安装 Docker Desktop 并启动它。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[X] 找不到 docker compose 子命令（需要 Docker Desktop 自带的 Compose V2）。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

# 3. 准备 backend.env（不存在则从示例自动复制，方便本地预演第一次运行）
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "[!] 首次运行：已自动从 backend.env.example 复制出 backend.env（本地预演默认值）。" -ForegroundColor Yellow
        Write-Host "     如需修改密钥/连接串，编辑：$EnvFile" -ForegroundColor Yellow
    } else {
        Write-Host "[X] 缺少 $EnvExample，无法自动生成 backend.env。" -ForegroundColor Red
        Read-Host '按回车键关闭'
        exit 1
    }
}

# 4. 启动
Set-Location $ComposeDir
Write-Host ''
if ($All) {
    Write-Host '[..] 正在启动完整预演栈（backend + postgres + redis + nginx）...' -ForegroundColor Cyan
    docker compose -f docker-compose.local.yml up -d --build
} else {
    Write-Host '[..] 正在启动 backend（自动带上 postgres + redis 依赖，不含 nginx）...' -ForegroundColor Cyan
    docker compose -f docker-compose.local.yml up -d --build backend
}
$upCode = $LASTEXITCODE
if ($upCode -ne 0) {
    Write-Host '[X] 启动失败，往上翻红字看第一条报错。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit $upCode
}

# 5. 轮询健康检查（最多等 ~20 秒，仅提示，不影响退出码）
Write-Host ''
Write-Host '[..] 正在等待 backend 健康检查（/health）...' -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
}

Write-Host ''
if ($healthy) {
    Write-Host '[OK] backend 已就绪：http://localhost:8000/health' -ForegroundColor Green
} else {
    Write-Host '[!] 暂时还没探测到 /health 200（可能还在启动/装依赖），稍等几秒后自行刷新看看：' -ForegroundColor Yellow
    Write-Host '     http://localhost:8000/health'
    Write-Host '     排查：docker compose -f deploy\docker\docker-compose.local.yml logs -f backend'
}
Write-Host '     接口文档：http://localhost:8000/docs'
Write-Host ''
Write-Host '[提醒] 若要让 backend 真正连上 Postgres（首次，建表）：' -ForegroundColor Yellow
Write-Host '     docker compose -f deploy\docker\docker-compose.local.yml exec backend alembic upgrade head'
Write-Host ''
Write-Host '停止服务：docker compose -f deploy\docker\docker-compose.local.yml down'
Write-Host ''
Read-Host '按回车键关闭'
exit 0
