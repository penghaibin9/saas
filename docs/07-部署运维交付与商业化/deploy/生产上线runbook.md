# 生产上线 Runbook（从演示到"敢跑真实客户数据"）

面向：把当前演示服务器升级为可承接真实学校、真实学生数据的生产环境。
标注约定：🟩 = 我（代码/配置）已备好，你执行即可；🟦 = 必须你/运维执行；🟥 = 需第三方或专业人员（无法由代码完成）。

> **数据备份与恢复的权威口径：`deploy/README-data-governance.md`。** 本文如有历史备份描述与其冲突，以该文件和 PR #66 的 systemd/backup/watchdog 合同为准。生产环境不要直接用 cron 调 `backup-mysql.sh` 绕过异地校验与 watchdog。

---

## 阶段 0 · 上线前必做（安全底线，缺一不可）

| # | 事项 | 标注 | 说明 |
|---|---|---|---|
| 0.1 | 设置强 `JWT_SECRET` | 🟦 | `openssl rand -hex 32` 生成，写入 backend/.env。**不设后端会拒绝启动**（已内置保护）。 |
| 0.2 | `APP_ENV=production` | 🟦 | 生产环境会自动关闭 /docs、/openapi.json、精简 /health（已内置）。 |
| 0.3 | 关闭 mock-login | 🟥→🟩 | 正式接入真实客户数据前必须禁用 `/auth/mock-login`（当前演示保留）。改动很小，需要时告诉我加一个 `MOCK_LOGIN_ENABLED=false` 开关。 |
| 0.4 | 收敛 CORS | 🟦 | `CORS_ORIGINS` 设为真实域名，勿留空（留空会回退 `*`）。 |
| 0.5 | 数据库密码 | 🟦 | MySQL 用强密码，只经 .env / 环境变量注入，不进仓库。 |
| 0.6 | HTTPS | 🟦 | 用 deploy/nginx/nginx.https.conf.example，配 Let's Encrypt 或云厂商免费证书。**真实学生身份证/手机号必须走 HTTPS 传输。** |

---

## 阶段 1 · 部署（每次发版）

1. 🟦 同步最新代码到服务器。
2. 🟦 确认 backend/.env：`APP_ENV=production` + 强 `JWT_SECRET` + `DB_*` + `CORS_ORIGINS`。
3. 🟦 数据库初始化 / 迁移：
   - 首次：`python scripts/init_mysql_db.py` 建表 → `python scripts/seed_mysql_demo_data.py` 灌演示数据（**含 6 大业务域**，种子链已打通）。
   - 后续加表：本项目新增表通过 `metadata.create_all` 建缺失表；如上正式生产建议改用 Alembic 迁移（`alembic upgrade head`）。
4. 🟦 前端构建部署：`cd frontend && npm ci && npm run build` → dist 传到 nginx 的 PC 根目录；miniapp 同理 build:h5。
5. 🟦 重启后端：`systemctl restart school-backend`（或 docker compose restart backend）。
6. 🟦 `nginx -t && systemctl reload nginx`。

---

## 阶段 2 · 部署后验证（每次必跑）

- 🟩 `curl https://<域名>/health` → `{"status":"UP"}`
- 🟩 `curl https://<域名>/docs` → 404（生产已关）
- 🟩 platform_owner 登录 → 进 /admin/platform/overview；陌生浏览器进该页 → 跳登录
- 🟩 6 大业务域看板均可打开（迎新/在校服务/学业/实习/毕业/就业）
- 🟩 demo 账号仍只见 5 名学生（多租户隔离）
- 🟩 后端日志无 "生产环境必须设置 JWT_SECRET" 报错

---

## 阶段 3 · 数据安全与运维（真实数据必备）

| # | 事项 | 标注 | 说明 |
|---|---|---|---|
| 3.1 | 自动治理备份 | 🟩 | 正式生产安装 `school-lifecycle-backup.service/.timer`，每天 4 次生成 **MySQL + uploads 同一 manifest 备份集**，完成 SHA-256 与异地回读校验；不要直接 cron 调底层 `backup-mysql.sh`。 |
| 3.2 | 备份失效监测与恢复演练 | 🟩→🟦 | `school-lifecycle-backup-watchdog.timer` 每小时检查 RPO/本地完整性/异地 commit marker；GitHub 定时跑完整恢复演练。首次生产部署仍须人工跑 1 次真实备份 + 隔离恢复，确认真实 COS/rclone 配置。 |
| 3.3 | 敏感字段加密恢复材料 | 🟩→🟦 | 当前后端已有敏感字段静态加密与密钥轮换能力。上线时只需把生产 `FIELD_ENCRYPTION_KEY`、历史 key（如有）及固定搜索 HMAC key 的**受保护恢复副本**保存在应用服务器/Git 之外，防止灾难恢复后密文无法解开。 |
| 3.4 | 日志与监控 | 🟦 | 接入服务器监控（CPU/内存/磁盘/端口存活）、后端访问日志留存 ≥6 个月。 |
| 3.5 | 限流/防爆破 | 🟩 | 已内置：登录失败 5 次锁 15 分钟、登录/上传/导出限流。 |

生产数据治理基线：**RPO ≤ 6 小时、RTO ≤ 2 小时**。本地默认至少保留 8 个完整恢复点；异地对象存储必须启用版本化/不可变保留和存储侧加密。具体配置只认 `deploy/README-data-governance.md`。

---

## 阶段 4 · 合规与安全评估（上线为真实学校前）

| # | 事项 | 标注 | 说明 |
|---|---|---|---|
| 4.1 | 等保三级自查 | 🟩 | 见 `docs/05-数据接口权限与安全/security/合规与等保附录.md`，逐项对照。 |
| 4.2 | 正式渗透测试 | 🟥 | 需具备资质的安全公司做一次黑盒+白盒渗透，出报告。代码层已过基础自查（无注入/无算法混淆/异常不泄露）。 |
| 4.3 | 等保测评备案 | 🟥 | 涉及学生个人信息的教育系统通常需过等保测评（三级）+ 公安备案，由测评机构出具。 |
| 4.4 | 隐私合规 | 🟥 | 《个人信息保护法》：明示收集范围、告知同意、数据最小化。需法务/合规参与出隐私政策。 |
| 4.5 | 数据处理协议 | 🟦 | 与学校签订数据处理协议（DPA），明确数据归属、留存、销毁。 |

---

## 一句话总结

**生产数据治理代码侧已经统一到自动化入口**：完整备份集、异地回读校验、watchdog、RPO/RTO、隔离恢复演练和恢复证据由脚本/CI/systemd 承担；你上线时只做一次性真实环境配置，不需要日常手工跑备份。
**部署与运维（🟦）** 仍需在真实服务器完成首次配置与验收。
**合规与渗透（🟥）** 必须由第三方/专业人员完成——这部分不是写代码能替代的，是"敢卖给真实学校"的最后一道人工关。
