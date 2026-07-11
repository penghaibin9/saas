# 学校试点部署 Runbook

> 面向：把系统部署到一台服务器供一所学校试点。按步骤执行；🟦=运维执行，🟩=脚本/模板已备。
> 配套：`scripts/check/preflight-school-trial.*`（上线前预检）、`scripts/check/smoke-school-trial.*`（部署后冒烟）、`docs/07-部署运维交付与商业化/deploy/生产环境变量清单.md`、`nginx部署检查清单.md`、`HTTPS证书配置说明.md`。

## 阶段 0 · 准备
1. 🟦 服务器：2C4G 起、Ubuntu 22 / 同类；开放 80/443（8000/3306 不对公网）。
2. 🟦 域名：解析到服务器。
3. 🟦 数据库：安装 MySQL 8，建库 `saas_lifecycle`、建账号（强密码，仅 .env 注入）。
4. 🟩 证书：见《HTTPS证书配置说明》。

## 阶段 1 · 配置 .env.production
5. 🟦 复制 `backend/.env.example` → `backend/.env`，按《生产环境变量清单》填：
   - `APP_ENV=production`、`DEBUG=false`
   - 强 `JWT_SECRET`（`openssl rand -hex 32`）
   - `DB_ENABLED=true` + `DB_*`（密码仅此注入）
   - `CORS_ORIGINS=https://你的域名`（勿留空/勿 `*`）
   - `MOCK_LOGIN_ENABLED=false`（正式客户前）
   - `SMS_ENABLED=false`（未配密钥时保持关闭）
6. 🟩 **预检**：`bash scripts/check/preflight-school-trial.sh backend/.env` → 必须无 FAIL。

## 阶段 2 · 初始化数据库
7. 🟦 首次建表 + 演示/初始数据：
   - `cd backend && python scripts/init_mysql_db.py`
   - 用《新学校开局向导》导入该校院系/学生/教师（validate → confirm）。

## 阶段 3 · 构建与启动
8. 🟦 后端：`pip install -r backend/requirements.txt` → `systemctl restart school-backend`（或 `uvicorn app.main:app --host 127.0.0.1 --port 8000`）。
9. 🟦 PC 管理端：`cd frontend && npm ci && npm run build` → `dist/` 传到 nginx 站点根。
10. 🟦 学生/教师小程序 H5：`cd miniapp && npm ci && npm run build:h5` → 传到 nginx（或小程序发行微信版另走审核）。
11. 🟦 nginx：套用 `deploy/nginx/nginx.https.conf.example`，见《nginx部署检查清单》→ `nginx -t && systemctl reload nginx`。

## 阶段 4 · 部署后验证
12. 🟩 冒烟：`BASE_URL=https://你的域名 bash scripts/check/smoke-school-trial.sh` → 无 FAIL。
13. 🟩 人工确认：`/docs` 404、mock-login 关闭、demo 隔离、六域可打开、学生只看本人。
14. 🟩 就绪：`curl https://你的域名/health/ready` → `READY`。

## 阶段 5 · 运维
15. 🟦 部署每日备份（`deploy/backup/backup-mysql.sh` + crontab 02:00）；每月做一次恢复演练（见运维手册）。
16. 🟦 配监控告警（见《商用就绪度评估》建议）。

## 回滚
17. 🟦 版本回滚：切回上一个稳定 tag → 重新 build → 重启；**改表前必先备份**，出问题优先恢复备份（见备份恢复演练手册）。
18. 🟦 部署失败：保留旧 `dist/` 与旧后端进程，nginx 指回旧站点，先恢复可用再排查。
