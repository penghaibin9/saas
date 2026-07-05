# ==========================================================
#  检查开发端口占用情况（只看，不动任何进程）
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\dev\check-ports.ps1
# ==========================================================

# 端口 → 一般是谁在用
$PortMap = [ordered]@{
    5173 = 'PC 前端（vite 默认）'
    5174 = '备用（5173 被占时 vite 自动用）'
    5188 = '小程序 H5（manifest 里配置的端口）'
    8000 = '后端 Python/FastAPI（uvicorn）'
    3000 = '后端 Node 旧底座（.env 默认 PORT）'
}

Write-Host ''
Write-Host '=============== 开发端口检查 ===============' -ForegroundColor Cyan
Write-Host ''

$busy = 0
foreach ($port in $PortMap.Keys) {
    $desc = $PortMap[$port]
    $conns = $null
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    } catch { $conns = $null }

    if ($conns) {
        $busy++
        $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            $pname = '(未知进程)'
            try { $pname = (Get-Process -Id $procId -ErrorAction Stop).ProcessName } catch {}
            Write-Host ("[占用] 端口 {0}  ← 进程 {1} (PID={2})   一般是：{3}" -f $port, $pname, $procId, $desc) -ForegroundColor Yellow
        }
    } else {
        Write-Host ("[空闲] 端口 {0}   一般是：{1}" -f $port, $desc) -ForegroundColor Green
    }
}

Write-Host ''
if ($busy -eq 0) {
    Write-Host '结论：所有开发端口都是空闲的，现在没有服务在跑。' -ForegroundColor Green
    Write-Host '想启动？运行 scripts\dev\start-all.ps1'
} else {
    Write-Host "结论：有 $busy 个端口被占用。" -ForegroundColor Yellow
    Write-Host '  - 如果就是你自己启动的服务在跑：正常，不用管。'
    Write-Host '  - 如果想全部停掉：运行 scripts\dev\stop-dev.ps1'
}
Write-Host ''
Read-Host '按回车键关闭'
