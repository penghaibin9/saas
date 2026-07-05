# ==========================================================
#  一键启动：后端（backend）
#  自动识别后端类型：
#    1) 有 requirements.txt → Python/FastAPI，用 uvicorn 启动（端口 8000）
#    2) 只有 package.json   → Node/Express（端口 3000）
#  入口文件还没写好时会友好提示并跳过，不会报崩。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\dev\start-backend.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dir  = Join-Path $Root 'backend'

Write-Host ''
Write-Host '================ [后端] 启动 ================' -ForegroundColor Cyan

# 情况 1：backend 目录不存在
if (-not (Test-Path $Dir)) {
    Write-Host '[--] 后台工程未创建，跳过。' -ForegroundColor Yellow
    Write-Host '     这不影响 PC 前端和小程序（它们目前用 mock 数据）。'
    Read-Host '按回车键关闭'
    exit 0
}

Set-Location $Dir

# ---------- 情况 2：Python 后端（FastAPI / uvicorn，优先识别） ----------
if (Test-Path (Join-Path $Dir 'requirements.txt')) {

    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host '[X] 电脑上没有安装 Python。请到 https://www.python.org 安装（勾选 Add to PATH）。' -ForegroundColor Red
        Read-Host '按回车键关闭'
        exit 1
    }

    # 找入口：app/main.py（uvicorn app.main:app）或 main.py（uvicorn main:app）
    $Entry = $null
    if (Test-Path (Join-Path $Dir 'app\main.py')) { $Entry = 'app.main:app' }
    elseif (Test-Path (Join-Path $Dir 'main.py')) { $Entry = 'main:app' }

    if (-not $Entry) {
        Write-Host '[--] 后端（Python/FastAPI）还在搭建中：缺少入口 main.py，暂时无法启动，跳过。' -ForegroundColor Yellow
        Write-Host '     这不影响 PC 前端和小程序（它们目前用 mock 数据）。'
        Read-Host '按回车键关闭'
        exit 0
    }

    # 检查虚拟环境 .venv，没有就自动创建并装依赖
    $Venv = Join-Path $Dir '.venv'
    $VPy  = Join-Path $Venv 'Scripts\python.exe'
    if (-not (Test-Path $VPy)) {
        Write-Host '[!] 还没有虚拟环境 .venv，正在自动创建并安装依赖（要几分钟）...' -ForegroundColor Yellow
        python -m venv .venv
        & $VPy -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host '[X] 依赖安装失败。请看 docs\dev-run\02-常见启动失败处理.md' -ForegroundColor Red
            Read-Host '按回车键关闭'
            exit 1
        }
        Write-Host '[OK] 虚拟环境和依赖已就绪。' -ForegroundColor Green
    }

    Write-Host ''
    Write-Host "[OK] 正在启动后端（uvicorn $Entry，端口 8000）..." -ForegroundColor Green
    Write-Host '     健康检查：http://localhost:8000/health'
    Write-Host '     接口文档：http://localhost:8000/docs'
    Write-Host '     停止服务：直接关掉本窗口，或按 Ctrl+C'
    Write-Host ''
    & $VPy -m uvicorn $Entry --reload --port 8000
    exit $LASTEXITCODE
}

# ---------- 情况 3：Node.js 后端（Express） ----------
if (Test-Path (Join-Path $Dir 'package.json')) {

    if (-not (Test-Path (Join-Path $Dir 'app.js'))) {
        Write-Host '[--] 后端（Node）只是底座（缺少入口 app.js），暂时无法启动，跳过。' -ForegroundColor Yellow
        Write-Host '     这不影响 PC 前端和小程序（它们目前用 mock 数据）。'
        Read-Host '按回车键关闭'
        exit 0
    }

    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host '[X] 电脑上没有安装 Node.js（找不到 npm 命令）。请到 https://nodejs.org 安装 LTS 版。' -ForegroundColor Red
        Read-Host '按回车键关闭'
        exit 1
    }

    if (-not (Test-Path (Join-Path $Dir 'node_modules'))) {
        Write-Host '[!] 依赖还没安装，正在自动执行 npm install...' -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host '[X] npm install 失败。请看 docs\dev-run\02-常见启动失败处理.md' -ForegroundColor Red
            Read-Host '按回车键关闭'
            exit 1
        }
    }

    if (-not (Test-Path (Join-Path $Dir '.env'))) {
        Write-Host '[!] 提示：backend 还没有 .env 配置文件，可复制模板：copy .env.example .env' -ForegroundColor Yellow
    }

    Write-Host ''
    Write-Host '[OK] 正在启动后端（Express，默认端口 3000）...' -ForegroundColor Green
    Write-Host '     停止服务：直接关掉本窗口，或按 Ctrl+C'
    Write-Host ''
    npm run dev
    exit $LASTEXITCODE
}

# ---------- 情况 4：目录存在但认不出类型 ----------
Write-Host '[--] backend 目录存在，但既没有 requirements.txt 也没有 package.json，无法识别，跳过。' -ForegroundColor Yellow
Read-Host '按回车键关闭'
exit 0
