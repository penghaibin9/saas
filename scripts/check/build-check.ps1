# ==========================================================
#  构建自检：依次尝试所有构建命令，最后给一张汇总表
#  只检查，不修改任何代码。整个过程可能要几分钟。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\check\build-check.ps1
# ==========================================================
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Results = @()

# 跑一个 npm 构建步骤（要求目录和 node_modules 都在）
function Run-Step {
    param([string]$Name, [string]$Dir, [scriptblock]$Cmd)
    Write-Host ''
    Write-Host ">>> 正在检查：$Name" -ForegroundColor Cyan
    if (-not (Test-Path $Dir)) {
        Write-Host "[--] 目录不存在，跳过：$Dir" -ForegroundColor Yellow
        return [pscustomobject]@{ 项目 = $Name; 结果 = '跳过(目录不存在)' }
    }
    if (-not (Test-Path (Join-Path $Dir 'node_modules'))) {
        Write-Host '[--] 依赖未安装（没有 node_modules），跳过。先运行对应的 start 脚本装依赖。' -ForegroundColor Yellow
        return [pscustomobject]@{ 项目 = $Name; 结果 = '跳过(依赖未安装)' }
    }
    Push-Location $Dir
    try {
        & $Cmd
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($code -eq 0) {
        Write-Host "[OK] $Name 通过" -ForegroundColor Green
        return [pscustomobject]@{ 项目 = $Name; 结果 = '通过' }
    } else {
        Write-Host "[X] $Name 失败（往上翻红字看第一条报错）" -ForegroundColor Red
        return [pscustomobject]@{ 项目 = $Name; 结果 = '失败' }
    }
}

# 同 Run-Step，但不检查 node_modules（给 Python 等非 npm 步骤用）
function Run-StepRaw {
    param([string]$Name, [string]$Dir, [scriptblock]$Cmd)
    Write-Host ''
    Write-Host ">>> 正在检查：$Name" -ForegroundColor Cyan
    Push-Location $Dir
    try {
        & $Cmd
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($code -eq 0) {
        Write-Host "[OK] $Name 通过" -ForegroundColor Green
        return [pscustomobject]@{ 项目 = $Name; 结果 = '通过' }
    } else {
        Write-Host "[X] $Name 失败（往上翻红字看第一条报错）" -ForegroundColor Red
        return [pscustomobject]@{ 项目 = $Name; 结果 = '失败' }
    }
}

Write-Host ''
Write-Host '=============== 构建自检 build-check ===============' -ForegroundColor Cyan
Write-Host '（只检查能不能构建，不改任何代码，可能要几分钟）'

# 1. PC 前端构建
$Results += Run-Step 'PC 前端 npm run build' (Join-Path $Root 'frontend') { npm run build }

# 2. 小程序 H5 构建
$Results += Run-Step '小程序 npm run build:h5' (Join-Path $Root 'miniapp') { npm run build:h5 }

# 3. 小程序微信端构建
$Results += Run-Step '小程序 npm run build:mp-weixin' (Join-Path $Root 'miniapp') { npm run build:mp-weixin }

# 4. 后端最小检查（Python/FastAPI 优先，其次 Node；只检查，不改代码）
$B = Join-Path $Root 'backend'
if (-not (Test-Path $B)) {
    Write-Host ''
    Write-Host '>>> 后端：未创建，跳过' -ForegroundColor Yellow
    $Results += [pscustomobject]@{ 项目 = '后端检查'; 结果 = '跳过(未创建)' }
} elseif (Test-Path (Join-Path $B 'requirements.txt')) {
    # Python 后端
    $VPy = Join-Path $B '.venv\Scripts\python.exe'
    if (-not (Test-Path $VPy)) {
        Write-Host ''
        Write-Host '>>> 后端(Python)：.venv 还没创建，跳过（先运行 scripts\dev\start-backend.ps1 会自动创建）' -ForegroundColor Yellow
        $Results += [pscustomobject]@{ 项目 = '后端检查(Python)'; 结果 = '跳过(.venv 未创建)' }
    } else {
        if (Test-Path (Join-Path $B 'app\main.py')) {
            $Results += Run-StepRaw '后端 Python 导入检查(app.main)' $B { & $VPy -c 'import app.main' }
        } elseif (Test-Path (Join-Path $B 'main.py')) {
            $Results += Run-StepRaw '后端 Python 导入检查(main)' $B { & $VPy -c 'import main' }
        } else {
            $Results += [pscustomobject]@{ 项目 = '后端检查(Python)'; 结果 = '跳过(无入口 main.py)' }
        }
        # 有 pytest 测试就跑，没装 pytest 就跳过
        $hasPytest = $false
        try { & $VPy -m pytest --version *> $null; $hasPytest = ($LASTEXITCODE -eq 0) } catch { $hasPytest = $false }
        if ((Test-Path (Join-Path $B 'tests')) -and $hasPytest) {
            $Results += Run-StepRaw '后端 pytest' $B { & $VPy -m pytest -q }
        }
    }
} elseif (Test-Path (Join-Path $B 'package.json')) {
    if (Test-Path (Join-Path $B 'app.js')) {
        $Results += Run-Step '后端 node --check app.js' $B { node --check app.js }
    } else {
        Write-Host ''
        Write-Host '>>> 后端(Node)：只是底座（没有 app.js 入口），跳过' -ForegroundColor Yellow
        $Results += [pscustomobject]@{ 项目 = '后端检查(Node)'; 结果 = '跳过(底座无入口)' }
    }
} else {
    $Results += [pscustomobject]@{ 项目 = '后端检查'; 结果 = '跳过(无法识别类型)' }
}

# 汇总
Write-Host ''
Write-Host '=================== 汇总 ===================' -ForegroundColor Cyan
foreach ($r in $Results) {
    $color = 'Yellow'
    if ($r.结果 -eq '通过') { $color = 'Green' }
    if ($r.结果 -eq '失败') { $color = 'Red' }
    Write-Host ("  {0}  →  {1}" -f $r.项目.PadRight(32), $r.结果) -ForegroundColor $color
}
$failed = @($Results | Where-Object { $_.结果 -eq '失败' }).Count
Write-Host ''
if ($failed -eq 0) {
    Write-Host '结论：没有失败项。' -ForegroundColor Green
} else {
    Write-Host "结论：有 $failed 项失败。往上翻对应部分的红字，先看第一条报错，再对照 docs\dev-run\02-常见启动失败处理.md" -ForegroundColor Red
}
Read-Host '按回车键关闭'
exit $failed
