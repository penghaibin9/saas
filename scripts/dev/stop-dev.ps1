# ==========================================================
#  停止开发服务：释放常用开发端口（5173 / 5174 / 5188 / 8000 / 3000）
#  会先列出将要停止的进程，回车确认后才动手。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\dev\stop-dev.ps1
# ==========================================================
$Ports = @(5173, 5174, 5188, 8000, 3000)

Write-Host ''
Write-Host '=============== 停止开发服务 ===============' -ForegroundColor Cyan
Write-Host ''

# 1. 收集占用这些端口的进程
$targets = @()
foreach ($port in $Ports) {
    $conns = $null
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    } catch { $conns = $null }
    if ($conns) {
        foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
            if ($procId -le 4) { continue }   # 跳过系统进程
            $pname = '(未知进程)'
            try { $pname = (Get-Process -Id $procId -ErrorAction Stop).ProcessName } catch {}
            $targets += [pscustomobject]@{ Port = $port; ProcId = $procId; Name = $pname }
        }
    }
}

# 2. 没有可停的
if ($targets.Count -eq 0) {
    Write-Host '[OK] 端口 5173 / 5174 / 5188 / 8000 / 3000 都没有被占用，没有需要停止的服务。' -ForegroundColor Green
    Read-Host '按回车键关闭'
    exit 0
}

# 3. 先显示将要停止什么
Write-Host '将要停止以下进程：' -ForegroundColor Yellow
foreach ($t in $targets) {
    Write-Host ("  端口 {0}  → 进程 {1} (PID={2})" -f $t.Port, $t.Name, $t.ProcId) -ForegroundColor Yellow
}
Write-Host ''
$ans = Read-Host '确认全部停止请直接按回车；不想停请输入 N 再回车'
if ($ans -match '^[Nn]') {
    Write-Host '已取消，什么都没动。' -ForegroundColor Green
    exit 0
}

# 4. 动手停止（同一 PID 只停一次）
$done = @{}
foreach ($t in $targets) {
    if ($done.ContainsKey($t.ProcId)) { continue }
    try {
        Stop-Process -Id $t.ProcId -Force -ErrorAction Stop
        Write-Host ("[OK] 已停止 {0} (PID={1})，端口 {2} 已释放" -f $t.Name, $t.ProcId, $t.Port) -ForegroundColor Green
    } catch {
        Write-Host ("[X] 停止 PID={0} 失败：{1}" -f $t.ProcId, $_.Exception.Message) -ForegroundColor Red
    }
    $done[$t.ProcId] = $true
}

Write-Host ''
Write-Host '完成。可以再运行 scripts\dev\check-ports.ps1 确认端口已空闲。'
Read-Host '按回车键关闭'
