# ==========================================================
#  项目状态一览：目录、文件、git、端口，一眼看清现状
#  只读检查，不改任何东西。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\check\project-status.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

function Check-Item {
    param([string]$Label, [string]$Path, [string]$Hint = '')
    if (Test-Path (Join-Path $Root $Path)) {
        Write-Host ("  [有] {0}" -f $Label) -ForegroundColor Green
        return $true
    } else {
        $msg = "  [无] {0}" -f $Label
        if ($Hint) { $msg += "   （$Hint）" }
        Write-Host $msg -ForegroundColor Yellow
        return $false
    }
}

Write-Host ''
Write-Host '=============== 项目状态 project-status ===============' -ForegroundColor Cyan

# 1. 关键目录 / 文件
Write-Host ''
Write-Host '--- 1. 关键目录和文件 ---' -ForegroundColor Cyan
$null = Check-Item 'frontend/（PC 前端，Vite+Vue3，端口 5173）'        'frontend\package.json'
$null = Check-Item 'frontend/node_modules（PC 依赖）'                  'frontend\node_modules' '首次启动会自动 npm install'
$null = Check-Item 'miniapp/（小程序端，uni-app，H5 端口 5188）'        'miniapp\package.json'
$null = Check-Item 'miniapp/node_modules（小程序依赖）'                 'miniapp\node_modules' '首次启动会自动 npm install'
$null = Check-Item 'backend/requirements.txt（Python/FastAPI 后端）'    'backend\requirements.txt' '存在则后端走 uvicorn，端口 8000'
$null = Check-Item 'backend/app/main.py（FastAPI 入口）'                'backend\app\main.py' '还没写好入口时后端脚本会自动跳过'
$null = Check-Item 'backend/package.json（Node 底座，旧）'              'backend\package.json'
$null = Check-Item 'AI执行状态.md（AI 交接文件）'                       'AI执行状态.md'
$null = Check-Item 'scripts/dev/（一键启动脚本）'                       'scripts\dev\start-all.ps1'
$null = Check-Item 'scripts/check/（自检脚本）'                         'scripts\check\smoke-check.mjs'
$null = Check-Item 'docs/dev-run/（新手运行文档）'                      'docs\dev-run\README.md'

# 2. miniapp manifest 完整性（预防性检查，正常时显示完整）
$Manifest = Join-Path $Root 'miniapp\src\manifest.json'
if (Test-Path $Manifest) {
    $tail = (Get-Content $Manifest -Raw).TrimEnd()
    if (-not $tail.EndsWith('}')) {
        Write-Host '  [!] miniapp\src\manifest.json 不完整（文件被截断），小程序会启动失败！' -ForegroundColor Red
        Write-Host '      修复（在项目根目录执行）：git checkout -- miniapp/src/manifest.json' -ForegroundColor Red
    } else {
        Write-Host '  [有] miniapp\src\manifest.json 文件完整' -ForegroundColor Green
    }
}

# 3. git 状态
Write-Host ''
Write-Host '--- 2. git 状态（git status --short）---' -ForegroundColor Cyan
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gs = git status --short 2>$null
    if ($gs) {
        $arr = @($gs)
        Write-Host ("  有 {0} 个文件有改动（未提交）。前 15 条：" -f $arr.Count)
        $arr | Select-Object -First 15 | ForEach-Object { Write-Host "    $_" }
        if ($arr.Count -gt 15) { Write-Host ("    ...（还有 {0} 条）" -f ($arr.Count - 15)) }
    } else {
        Write-Host '  工作区干净，没有未提交的改动。' -ForegroundColor Green
    }
} else {
    Write-Host '  [--] 没有安装 git，跳过。' -ForegroundColor Yellow
}

# 4. 哪些服务可能正在运行（看端口）
Write-Host ''
Write-Host '--- 3. 哪些服务可能正在运行 ---' -ForegroundColor Cyan
$PortMap = [ordered]@{
    5173 = 'PC 前端'
    5174 = '备用前端端口'
    5188 = '小程序 H5'
    8000 = '后端(FastAPI/uvicorn)'
    3000 = '后端(Node 旧底座)'
}
$anyRunning = $false
foreach ($port in $PortMap.Keys) {
    $listening = $false
    try {
        $listening = [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        # 旧系统退回 TCP 连接探测
        try {
            $c = New-Object Net.Sockets.TcpClient
            $r = $c.BeginConnect('127.0.0.1', $port, $null, $null)
            $listening = $r.AsyncWaitHandle.WaitOne(300) -and $c.Connected
            $c.Close()
        } catch { $listening = $false }
    }
    if ($listening) {
        $anyRunning = $true
        Write-Host ("  [在跑] 端口 {0}（{1}）有服务在监听" -f $port, $PortMap[$port]) -ForegroundColor Green
    }
}
if (-not $anyRunning) {
    Write-Host '  现在没有任何开发服务在跑。想启动：scripts\dev\start-all.ps1' -ForegroundColor Yellow
}

Write-Host ''
Write-Host '========================================================' -ForegroundColor Cyan
Write-Host '下一步建议：'
Write-Host '  启动服务 → powershell -ExecutionPolicy Bypass -File scripts\dev\start-all.ps1'
Write-Host '  访问自检 → node scripts\check\smoke-check.mjs'
Write-Host '  构建自检 → powershell -ExecutionPolicy Bypass -File scripts\check\build-check.ps1'
Write-Host ''
Read-Host '按回车键关闭'
