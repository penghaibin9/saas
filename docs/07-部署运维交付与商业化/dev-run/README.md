# 新手运行手册（docs/dev-run）

不用记命令，照着做就行。所有命令都在 **项目根目录**（就是有 `frontend`、`miniapp` 文件夹的那一层）的 PowerShell 里执行。

## 文档目录

| 文档 | 什么时候看 |
| --- | --- |
| [01-新手一键启动说明.md](01-新手一键启动说明.md) | 想把项目跑起来（最常用） |
| [02-常见启动失败处理.md](02-常见启动失败处理.md) | 启动时出现红字报错 |
| [03-端口占用处理.md](03-端口占用处理.md) | 提示端口被占用 / 想停服务 |
| [04-如何判断项目是否跑起来.md](04-如何判断项目是否跑起来.md) | 不确定有没有启动成功 |

## 速查表（背不下来就回来抄）

| 想干什么 | 在项目根目录执行 |
| --- | --- |
| 一键启动全部 | `powershell -ExecutionPolicy Bypass -File scripts\dev\start-all.ps1` |
| 只启动 PC 前端 | `powershell -ExecutionPolicy Bypass -File scripts\dev\start-pc.ps1` |
| 只启动小程序 H5 | `powershell -ExecutionPolicy Bypass -File scripts\dev\start-miniapp.ps1` |
| 只启动后端 | `powershell -ExecutionPolicy Bypass -File scripts\dev\start-backend.ps1` |
| 停掉所有服务 | `powershell -ExecutionPolicy Bypass -File scripts\dev\stop-dev.ps1` |
| 看端口占用 | `powershell -ExecutionPolicy Bypass -File scripts\dev\check-ports.ps1` |
| 看项目状态 | `powershell -ExecutionPolicy Bypass -File scripts\check\project-status.ps1` |
| 访问自检（服务通不通） | `node scripts\check\smoke-check.mjs` |
| 构建自检（代码能不能打包） | `powershell -ExecutionPolicy Bypass -File scripts\check\build-check.ps1` |

## 访问地址

| 服务 | 地址 |
| --- | --- |
| PC 前端 | http://localhost:5173/ |
| 小程序 H5 | http://localhost:5188/ |
| 后端（Python/FastAPI） | http://localhost:8000/docs （搭建完成后；入口没写好时启动脚本会自动跳过，不影响演示） |
