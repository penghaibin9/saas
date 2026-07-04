# ==========================================================
#  部署构建：PC 前端（frontend / Vite + Vue3）→ frontend/dist/
#  只构建静态产物，供 Nginx（本地 docker-compose 或传统 Nginx）挂载使用。
#  不改 frontend/src 任何源码。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\deploy\build-pc.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dir  = Join-Path $Root 'frontend'

Write-Host ''
Write-Host '================ [部署构建] PC 前端 ================' -ForegroundColor Cyan

# 1. 检查工程是否存在
if (-not (Test-Path (Join-Path $Dir 'package.json'))) {
    Write-Host "[X] 没有找到 PC 前端工程：$Dir" -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

# 2. 检查 Node / npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host '[X] 电脑上没有安装 Node.js（找不到 npm 命令）。请到 https://nodejs.org 安装 LTS 版。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

Set-Location $Dir

# 3. 依赖
if (-not (Test-Path (Join-Path $Dir 'node_modules'))) {
    Write-Host '[!] 依赖还没安装，正在自动执行 npm install（可能需要几分钟）...' -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[X] npm install 失败。请看 docs\dev-run\02-常见启动失败处理.md' -ForegroundColor Red
        Read-Host '按回车键关闭'
        exit 1
    }
    Write-Host '[OK] 依赖安装完成。' -ForegroundColor Green
}

# 4. 构建
Write-Host ''
Write-Host '[..] 正在执行 npm run build ...' -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host '[X] 构建失败，往上翻红字看第一条报错。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

# 5. 校验产物
$DistIndex = Join-Path $Dir 'dist\index.html'
if (-not (Test-Path $DistIndex)) {
    Write-Host '[X] 构建命令返回成功，但没有找到 dist\index.html，产物异常。' -ForegroundColor Red
    Read-Host '按回车键关闭'
    exit 1
}

Write-Host ''
Write-Host '[OK] PC 前端构建完成。' -ForegroundColor Green
Write-Host "     产物目录：$Dir\dist" -ForegroundColor Green
Write-Host '     本地 docker-compose 预演：nginx 已按 deploy/docker/docker-compose.local.yml' -ForegroundColor Green
Write-Host '       只读挂载 frontend/dist → /usr/share/nginx/html/pc，构建完成后直接生效。'
Write-Host '     传统 Nginx 部署：把 dist\ 内容拷到服务器 root 指向的目录（见 docs/deploy/03、09）。'
Write-Host ''
Read-Host '按回车键关闭'
exit 0
