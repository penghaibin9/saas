# 学校试点部署 Runbook

> 面向：把系统部署到一台服务器供一所学校试点。按步骤执行；🟦=运维执行，🟩=脚本/模板已备。
> 配套：`scripts/check/preflight-school-trial.*`（上线前预检）、`scripts/check/smoke-school-trial.*`（部署后冒烟）、`docs/07-部署运维交付与商业化/deploy/生产环境变量清单.md`、`nginx部署检查清单.md`、`HTTPS证书配置说明.md`。
>
> **备份/恢复只认 `deploy/README-data-governance.md`。** 正式 Linux 生产不要再用“单独 cron 调 `backup-mysql.sh`”作为上线方案。

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
15. 🟦 **一次性安装生产数据治理**：按 `deploy/README-data-governance.md` 配置 `backup.env` 与 rclone 异地目标，开启对象存储版本化/不可变保留/存储侧加密；安装 `school-lifecycle-backup.service/.timer` 和 `school-lifecycle-backup-watchdog.service/.timer`。正式基线为每 6 小时一个恢复点、watchdog 每小时检查。
16. 🟦 首次上线只需人工验证一次：手动触发 1 次正式备份 → watchdog 通过 → 在隔离库执行 1 次恢复演练。之后由 systemd/CI 自动运行。生产字段加密密钥的受保护恢复副本必须放在应用服务器与 Git 之外。
17. 🟦 配监控告警（见《商用就绪度评估》建议），并把 backup/watchdog systemd 失败纳入告警。

## 回滚
18. 🟦 版本回滚：切回上一个稳定 tag → 重新 build → 重启；**改表前必须确认存在最新的 manifest-committed 完整恢复点**，数据库恢复只在隔离验证后按恢复流程执行。
19. 🟦 部署失败：保留旧 `dist/` 与旧后端进程，nginx 指回旧站点，先恢复可用再排查。
