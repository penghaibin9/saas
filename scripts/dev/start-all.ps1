# ==========================================================
#  一键启动全部：PC 前端 + 小程序 H5 + 后端
#  每个服务各开一个独立窗口，互不影响，本窗口不会被卡住。
#  用法（在项目根目录的 PowerShell 里执行）：
#    powershell -ExecutionPolicy Bypass -File scripts\dev\start-all.ps1
#  或：右键本文件 → 使用 PowerShell 运行
# ==========================================================
$DevDir = $PSScriptRoot

Write-Host ''
Write-Host '=========== 一键启动全部开发服务 ===========' -ForegroundColor Cyan
Write-Host ''

Write-Host '[1/3] 打开新窗口：PC 前端 (http://localhost:5173/)' -ForegroundColor Green
Start-Process powershell -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-File',(Join-Path $DevDir 'start-pc.ps1'))
Start-Sleep -Seconds 2

Write-Host '[2/3] 打开新窗口：小程序 H5 (http://localhost:5188/)' -ForegroundColor Green
Start-Process powershell -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-File',(Join-Path $DevDir 'start-miniapp.ps1'))
Start-Sleep -Seconds 2

Write-Host '[3/3] 打开新窗口：后端（入口没写好时会自动提示并跳过）' -ForegroundColor Green
Start-Process powershell -ArgumentList @('-NoExit','-ExecutionPolicy','Bypass','-File',(Join-Path $DevDir 'start-backend.ps1'))

Write-Host ''
Write-Host '=============== 已全部拉起 ===============' -ForegroundColor Cyan
Write-Host '等 1-2 分钟编译完成后，用浏览器打开：'
Write-Host '  PC 前端   ： http://localhost:5173/'
Write-Host '  小程序 H5 ： http://localhost:5188/'
Write-Host ''
Write-Host '想确认是否真的跑起来了？在项目根目录执行：'
Write-Host '  node scripts\check\smoke-check.mjs' -ForegroundColor Yellow
Write-Host ''
Write-Host '想全部停止？执行：'
Write-Host '  powershell -ExecutionPolicy Bypass -File scripts\dev\stop-dev.ps1' -ForegroundColor Yellow
Write-Host ''
Read-Host '本窗口可以关了，按回车键关闭'
