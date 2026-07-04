# ==========================================================
#  部署配置自检（只读检查，不改任何文件，不启动/不停止任何服务）
#  检查内容：
#    1) P5 部署准备的 10 个文件是否都在
#    2) docker-compose.local.yml 语法（有 docker 才检查；docker compose config）
#    3) nginx.conf 语法（有 docker 才检查；临时容器跑 nginx -t，不常驻）
#    4) 端口规划 80/8080/8000/5432/6379 当前占用情况
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\deploy\check-deploy.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

Write-Host ''
Write-Host '=============== 部署配置自检 check-deploy ===============' -ForegroundColor Cyan

$Results = @()

function Add-Result([string]$Item, [string]$Status) {
    $script:Results += [pscustomobject]@{ 项目 = $Item; 结果 = $Status }
}

# ---------- 1. 文件是否都在 ----------
Write-Host ''
Write-Host '--- 1. 部署文件是否齐全 ---' -ForegroundColor Cyan

$Files = [ordered]@{
    'backend/Dockerfile'                          = 'backend\Dockerfile'
    'deploy/docker/docker-compose.local.yml'      = 'deploy\docker\docker-compose.local.yml'
    'deploy/nginx/nginx.conf'                     = 'deploy\nginx\nginx.conf'
    'deploy/env/backend.env.example'              = 'deploy\env\backend.env.example'
    'deploy/env/frontend.env.example'             = 'deploy\env\frontend.env.example'
    'deploy/env/miniapp.env.example'               = 'deploy\env\miniapp.env.example'
    'scripts/deploy/build-pc.ps1'                 = 'scripts\deploy\build-pc.ps1'
    'scripts/deploy/build-miniapp.ps1'            = 'scripts\deploy\build-miniapp.ps1'
    'scripts/deploy/start-backend.ps1'            = 'scripts\deploy\start-backend.ps1'
    'scripts/deploy/check-deploy.ps1'              = 'scripts\deploy\check-deploy.ps1'
}
foreach ($label in $Files.Keys) {
    $p = Join-Path $Root $Files[$label]
    if (Test-Path $p) {
        Write-Host "  [有] $label" -ForegroundColor Green
        Add-Result $label '存在'
    } else {
        Write-Host "  [无] $label" -ForegroundColor Red
        Add-Result $label '缺失'
    }
}

# ---------- 2. docker-compose 语法 ----------
Write-Host ''
Write-Host '--- 2. docker-compose.local.yml 语法 ---' -ForegroundColor Cyan
$ComposeFile = Join-Path $Root 'deploy\docker\docker-compose.local.yml'
$hasDocker = [bool](Get-Command docker -ErrorAction SilentlyContinue)
if (-not $hasDocker) {
    Write-Host '  [--] 电脑上没有 docker 命令，跳过语法检查（文件本身已确认存在）。' -ForegroundColor Yellow
    Add-Result 'docker-compose 语法' '跳过(无 docker)'
} elseif (-not (Test-Path $ComposeFile)) {
    Write-Host '  [--] 文件不存在，跳过。' -ForegroundColor Yellow
    Add-Result 'docker-compose 语法' '跳过(文件缺失)'
} else {
    Push-Location (Join-Path $Root 'deploy\docker')
    docker compose -f docker-compose.local.yml config *> $null
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -eq 0) {
        Write-Host '  [OK] docker compose config 通过（YAML 与字段语法正确）。' -ForegroundColor Green
        Add-Result 'docker-compose 语法' '通过'
    } else {
        Write-Host '  [X] docker compose config 报错，运行以下命令看详情：' -ForegroundColor Red
        Write-Host '      docker compose -f deploy\docker\docker-compose.local.yml config'
        Add-Result 'docker-compose 语法' '失败'
    }
}

# ---------- 3. nginx.conf 语法 ----------
Write-Host ''
Write-Host '--- 3. nginx.conf 语法 ---' -ForegroundColor Cyan
$NginxConf = Join-Path $Root 'deploy\nginx\nginx.conf'
if (-not $hasDocker) {
    Write-Host '  [--] 电脑上没有 docker 命令，跳过语法检查（文件本身已确认存在）。' -ForegroundColor Yellow
    Add-Result 'nginx.conf 语法' '跳过(无 docker)'
} elseif (-not (Test-Path $NginxConf)) {
    Write-Host '  [--] 文件不存在，跳过。' -ForegroundColor Yellow
    Add-Result 'nginx.conf 语法' '跳过(文件缺失)'
} else {
    # 用一次性临时容器测语法，不常驻、不占端口、检查完自动删除（--rm）
    $mount = "$NginxConf`:/etc/nginx/nginx.conf:ro"
    docker run --rm -v $mount nginx:1.27-alpine nginx -t *> $null
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host '  [OK] nginx -t 通过（临时容器测试，未常驻）。' -ForegroundColor Green
        Add-Result 'nginx.conf 语法' '通过'
    } else {
        Write-Host '  [X] nginx -t 报错，运行以下命令看详情：' -ForegroundColor Red
        Write-Host "      docker run --rm -v `"$NginxConf`:/etc/nginx/nginx.conf:ro`" nginx:1.27-alpine nginx -t"
        Add-Result 'nginx.conf 语法' '失败'
    }
}

# ---------- 4. 端口规划占用情况 ----------
Write-Host ''
Write-Host '--- 4. 端口规划占用情况（只看，不动进程）---' -ForegroundColor Cyan
$PortMap = [ordered]@{
    80   = 'nginx：PC 管理端静态站点'
    8080 = 'nginx：miniapp H5 静态站点'
    8000 = 'backend：FastAPI'
    5432 = 'postgres'
    6379 = 'redis（预留）'
}
foreach ($port in $PortMap.Keys) {
    $desc = $PortMap[$port]
    $listening = $false
    try {
        $listening = [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    } catch { $listening = $false }
    if ($listening) {
        Write-Host ("  [占用] 端口 {0}   {1}" -f $port, $desc) -ForegroundColor Yellow
        Add-Result ("端口 $port ($desc)") '占用中'
    } else {
        Write-Host ("  [空闲] 端口 {0}   {1}" -f $port, $desc) -ForegroundColor Green
        Add-Result ("端口 $port ($desc)") '空闲'
    }
}

# ---------- 汇总 ----------
Write-Host ''
Write-Host '=================== 汇总 ===================' -ForegroundColor Cyan
foreach ($r in $Results) {
    $color = 'Yellow'
    if ($r.结果 -in @('存在', '通过', '空闲')) { $color = 'Green' }
    if ($r.结果 -in @('缺失', '失败')) { $color = 'Red' }
    Write-Host ("  {0}  →  {1}" -f $r.项目.PadRight(34), $r.结果) -ForegroundColor $color
}

$failed = @($Results | Where-Object { $_.结果 -in @('缺失', '失败') }).Count
Write-Host ''
if ($failed -eq 0) {
    Write-Host '结论：部署配置文件齐全，语法检查（如跑了）均通过。' -ForegroundColor Green
    Write-Host '下一步：scripts\deploy\build-pc.ps1 → build-miniapp.ps1 → start-backend.ps1'
} else {
    Write-Host "结论：有 $failed 项需要处理，见上方红字。" -ForegroundColor Red
}
Write-Host ''
Read-Host '按回车键关闭'
exit $failed
