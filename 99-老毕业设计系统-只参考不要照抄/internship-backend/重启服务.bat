@echo off
chcp 65001 >nul
cd /d %~dp0
echo [1/4] 停止占用 3000 端口的旧服务...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo [2/4] 等待端口释放...
:waitport
netstat -ano | findstr :3000 | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
  timeout /t 1 >nul
  goto waitport
)
echo [3/4] 启动后端服务...
start "internship-backend" cmd /k npm start
echo [4/4] 等待服务就绪后打开管理平台...
timeout /t 5 >nul
start http://localhost:3000/
echo 完成！浏览器若显示旧页面请按 Ctrl+F5 强制刷新。
pause
