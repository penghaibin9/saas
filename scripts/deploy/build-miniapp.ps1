# ==========================================================
#  部署构建：小程序端（miniapp / uni-app + Vue3）
#    → H5：miniapp/dist/build/h5/       （必须成功，供 Nginx 挂载）
#    → 微信小程序：miniapp/dist/build/mp-weixin/ （尽量构建，供微信开发者工具上传体验版）
#  不改 miniapp 任何源码。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\deploy\build-miniapp.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Dir  = Join-Path $Root 'miniapp'

Write-Host ''
Write-Host '================ [部署构建] 小程序端 ================' -ForegroundColor Cyan

# 1. 检查工程是否存在
if (-not (Test-Path (Join-Path $Dir 'package.json'))) {
    Write-Host "[X] 没有找到小程序工程：$Dir" -ForegroundColor Red
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

$h5Ok = $false
$mpOk = $false

# 4. 构建 H5（必须成功，Nginx 部署依赖这个产物）
Write-Host ''
Write-Host '[..] 正在执行 npm run build:h5 ...' -ForegroundColor Cyan
npm run build:h5
if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $Dir 'dist\build\h5\index.html'))) {
    Write-Host '[OK] H5 构建完成。' -ForegroundColor Green
    $h5Ok = $true
} else {
    Write-Host '[X] H5 构建失败或产物缺失（dist\build\h5\index.html 不存在），往上翻红字看第一条报错。' -ForegroundColor Red
}

# 5. 构建微信小程序（尽量做，不影响 H5 部署结论）
Write-Host ''
Write-Host '[..] 正在执行 npm run build:mp-weixin ...' -ForegroundColor Cyan
npm run build:mp-weixin
if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $Dir 'dist\build\mp-weixin\app.json'))) {
    Write-Host '[OK] 微信小程序构建完成。' -ForegroundColor Green
    $mpOk = $true
} else {
    Write-Host '[--] 微信小程序构建失败或产物缺失，不影响 H5 站点部署，可稍后单独排查。' -ForegroundColor Yellow
}

# 6. 汇总
Write-Host ''
Write-Host '=================== 汇总 ===================' -ForegroundColor Cyan
Write-Host ("  H5（Nginx 用）        →  {0}" -f $(if ($h5Ok) { '通过' } else { '失败' })) -ForegroundColor $(if ($h5Ok) { 'Green' } else { 'Red' })
Write-Host ("  微信小程序（开发者工具用）→  {0}" -f $(if ($mpOk) { '通过' } else { '失败/跳过' })) -ForegroundColor $(if ($mpOk) { 'Green' } else { 'Yellow' })

if ($h5Ok) {
    Write-Host ''
    Write-Host "     H5 产物目录：$Dir\dist\build\h5" -ForegroundColor Green
    Write-Host '     本地 docker-compose 预演：nginx 已按 deploy/docker/docker-compose.local.yml' -ForegroundColor Green
    Write-Host '       只读挂载 miniapp/dist/build/h5 → /usr/share/nginx/html/miniapp，构建完成后直接生效。'
    Write-Host '     传统 Nginx 部署：把 dist\build\h5\ 内容拷到服务器 root 指向的目录（见 docs/07-部署运维交付与商业化/deploy/04、09）。'
}
if ($mpOk) {
    Write-Host "     微信小程序产物目录：$Dir\dist\build\mp-weixin（用微信开发者工具打开上传体验版，见 docs/07-部署运维交付与商业化/deploy/04）" -ForegroundColor Green
}
Write-Host ''
Read-Host '按回车键关闭'

if ($h5Ok) { exit 0 } else { exit 1 }
