# 生产上线 Runbook

> 本文只保留当前有效的正式上线口径。学校试点逐步执行版见同目录《学校试点部署Runbook.md》。历史 `init_mysql_db.py` / `metadata.create_all` / 演示 seed 不能作为正式建库或升级流程。
> **数据备份与恢复的唯一权威口径是 `deploy/README-data-governance.md`。** 不得另建 cron 直接调用底层备份脚本形成第二套生产流程。

## 1. 上线前准入

正式环境必须满足：MySQL 8、Redis、Nginx/HTTPS、ClamAV clamd、独立 scheduler、独立 file-scan worker；管理 PC、miniapp H5、学生 PC 三端同一次 release 发布。

环境文件以 `deploy/env/backend.systemd.env.example` 为唯一示例，关键红线包括：

- `APP_ENV=production`、`DEPLOYMENT_MODE=production`、`DEBUG=false`；
- `MOCK_LOGIN_ENABLED=false`；
- `DB_ENABLED=true`、`DB_DRIVER=mysql`；
- 强随机 `JWT_SECRET`；
- 与 JWT 独立的 `FIELD_ENCRYPTION_KEY`；
- `REDIS_URL`；
- `INTERNAL_OPS_TOKEN`；
- `SCHEDULER_MODE=external`；
- `CLAMAV_ENABLED=true`；
- HTTPS `CORS_ORIGINS` 与 `PUBLIC_BASE_URL`。

先运行：

```bash
bash scripts/check/preflight-school-trial.sh /etc/school-lifecycle/backend.env
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --check
```

任何 FAIL 都不允许上线。

## 2. 正式发布

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --apply
```

发布脚本使用排他锁串行执行，负责：创建独立 release、在维护窗口前完成依赖与三端构建、短暂静默 Web/后台写入者、迁移前一致性备份、`alembic upgrade head`、动态单头/current 校验、原子 symlink 切换、backend/scheduler/file-scan 三服务启动和发布后验收。miniapp H5 必须由当前 release 注入正式 `PUBLIC_BASE_URL`，正式产物不得包含 localhost/127.0.0.1 API origin。

**正式数据库只允许 Alembic 演进。** 不允许人工补表、`metadata.create_all`、跳过失败迁移或写死某个 Alembic revision 到发布脚本。数据库 migration 不自动 downgrade，因此 migration 必须遵守 expand/contract、向后兼容原则。

## 3. 发布后验收

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/verify-systemd-release.sh
```

必须 `FAIL=0`。重点包括：

- backend、scheduler、file-scan active；
- Nginx `/portal/` 已启用且 `/uploads/`、`/exports/` 禁止静态直读；
- `/health` UP；
- 携带运维令牌的 `/health/ready` READY；
- 数据库 current == 仓库动态唯一 Alembic head；
- ClamAV 可用；
- COS 模式完成真实小对象 write/delete，或 local 存储合同可用；
- 管理 PC、miniapp H5、学生 PC 都来自当前 release；
- 真实 443/TLS/server_name 路径返回 HSTS、CSP、X-Frame-Options、X-Content-Type-Options；
- production `/docs` 关闭；
- 未认证业务访问被拒绝。

文件扫描属于生产就绪依赖：required 时 ClamAV disabled/down 或 DEAD job 都会让 READY 降级，不能用“网页能打开”替代。

## 4. 真实学校数据准入

只有部署验收通过后才能导入真实学校数据。先小样本再扩大：平台建租户 → 品牌/组织 → 身份导入 dry-run → 修完错误行 → confirm → 教师/学生/辅导员/教务管理员真实角色 smoke → 跨租户负向验证 → 附件上传/扫描/绑定/下载 → Excel 导入导出 → 后台任务消费。

禁止用演示 seed 作为真实学校初始化方式。

## 5. 备份、恢复与回滚

生产备份统一按 `deploy/README-data-governance.md` 落地：

- 配置正式 `backup.env` 与 rclone 异地目标，异地对象存储启用版本化/不可变保留/存储侧加密；
- 启用 `school-lifecycle-backup.service/.timer`，每天 4 次生成恢复点；local 文件存储必须把 `UPLOAD_DIR` 与 MySQL 纳入同一恢复集；
- 启用 `school-lifecycle-backup-watchdog.service/.timer`，每小时检查 RPO、本地完整性、异地 commit/回读证据；
- GitHub 定时恢复演练继续作为独立灾备证据；首次生产部署必须人工跑一次真实备份 + watchdog + 隔离恢复，确认真实环境配置；
- 生产 `FIELD_ENCRYPTION_KEY`、历史 key（如有）及固定搜索 HMAC key 的受保护恢复副本保存在应用服务器与 Git 之外；
- 生产基线：**RPO ≤ 6 小时、RTO ≤ 2 小时**，本地保留策略和异地保留按数据治理合同执行。

应用发布失败时脚本会把 `/opt/school-lifecycle/current` 回退到上一个 release 并恢复服务；**数据库迁移不会自动 downgrade**。任何迁移上线前都必须存在最新、完整、可验证的恢复点，并保证旧应用在必要时仍可读取迁移后的兼容结构。只有经过隔离验证的灾难恢复流程才允许恢复数据库，不把 downgrade 当成常规发布回滚手段。

## 6. 合规与安全

上线真实学生数据前仍需学校侧完成隐私告知、最小化授权、运维账号管理、日志留存与第三方安全评估/渗透测试等工作。代码闸门不能替代组织与合规流程。
