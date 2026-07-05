# ==========================================================
#  一键启动：PC 前端（frontend / Vite + Vue3）
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\dev\start-pc.ps1
#  或：右键本文件 → 使用 PowerShell 运行
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dir  = Join-Path $Root 'frontend'

Write-Host ''
Write-Host '================ [PC 前端] 启动 ================' -ForegroundColor Cyan

# 1. 检查工程是否存在
if (-not (Test-Path (Join-Path $Dir 'package.json'))) {
    Write-Host "[X] 没有找到 PC 前端工程：$Dir" -ForegroundColor Red
    Write-Host '    请确认 frontend 目录存在。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

# 2. 检查 Node / npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host '[X] 电脑上没有安装 Node.js（找不到 npm 命令）。' -ForegroundColor Red
    Write-Host '    请到 https://nodejs.org 下载安装 LTS 版本，装完重开本窗口。' -ForegroundColor Yellow
    Read-Host '按回车键关闭'
    exit 1
}

Set-Location $Dir

# 3. 检查依赖 node_modules
if (-not (Test-Path (Join-Path $Dir 'node_modules'))) {
    Write-Host '[!] 第一次运行：依赖还没安装（没有 node_modules）。' -ForegroundColor Yellow
    Write-Host '    正在自动执行 npm install，可能需要几分钟，请不要关窗口...' -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[X] npm install 失败。请看 docs\dev-run\02-常见启动失败处理.md' -ForegroundColor Red
        Read-Host '按回车键关闭'
        exit 1
    }
    Write-Host '[OK] 依赖安装完成。' -ForegroundColor Green
}

# 4. 启动
Write-Host ''
Write-Host '[OK] 正在启动 PC 前端开发服务器...' -ForegroundColor Green
Write-Host '     启动成功后，用浏览器打开：http://localhost:5173/' -ForegroundColor Green
Write-Host '     （如果 5173 被占用，vite 会自动换端口，以下面的输出为准）'
Write-Host '     停止服务：直接关掉本窗口，或按 Ctrl+C'
Write-Host ''
npm run dev
