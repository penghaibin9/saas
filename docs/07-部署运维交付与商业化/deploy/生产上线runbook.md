# 生产上线 Runbook

> 更新：2026-08-12。本文只保留当前有效的正式上线口径。学校试点逐步执行版见同目录《学校试点部署Runbook.md》。历史 `init_mysql_db.py` / `metadata.create_all` / 演示 seed 不能作为正式建库或升级流程。
> **数据备份与恢复的唯一权威口径是 `deploy/README-data-governance.md`。** 发布前恢复点与日常灾备使用同一治理链，不再维护第二套 DB-only 发布备份。

## 1. 上线前准入

正式环境必须满足：MySQL 8、Redis、Nginx/HTTPS、ClamAV clamd、独立 scheduler、独立 file-scan worker；管理 PC、miniapp H5、学生 PC 三端同一次 release 发布。

环境文件以 `deploy/env/backend.systemd.env.example` 为后端示例，同时必须配置 `/etc/school-lifecycle/backup.env`（可用 `BACKUP_ENV_FILE` 显式覆盖）。关键红线包括：

- `APP_ENV=production`、`DEPLOYMENT_MODE=production`、`DEBUG=false`；
- `MOCK_LOGIN_ENABLED=false`；
- `DB_ENABLED=true`、`DB_DRIVER=mysql`；
- 强随机 `JWT_SECRET`；
- 与 JWT 独立的 `FIELD_ENCRYPTION_KEY`；
- `REDIS_URL`；
- `INTERNAL_OPS_TOKEN`；
- `SCHEDULER_MODE=external`；
- `CLAMAV_ENABLED=true`；
- HTTPS `CORS_ORIGINS` 与 `PUBLIC_BASE_URL`；
- backup.env 中正式 MySQL、`UPLOAD_DIR`、异地 rclone 与不可变存储确认均可用。

先运行：

```bash
bash scripts/check/preflight-school-trial.sh /etc/school-lifecycle/backend.env
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  BACKUP_ENV_FILE=/etc/school-lifecycle/backup.env \
  bash scripts/deploy/install-systemd-release.sh --check
```

任何 FAIL 都不允许上线。

## 2. 正式发布

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  BACKUP_ENV_FILE=/etc/school-lifecycle/backup.env \
  bash scripts/deploy/install-systemd-release.sh --apply
```

发布脚本使用排他锁串行执行，负责：创建独立 release、在维护窗口前完成冻结 Python 依赖与三端构建、短暂静默 Web/后台写入者、通过数据治理 backup runner 生成 **MySQL + uploads + manifest + SHA-256 + 异地回读** 的受治理恢复点、`alembic upgrade head`、动态单头/current 校验、原子 symlink 切换、backend/scheduler/file-scan 三服务启动和发布后验收。miniapp H5 必须由当前 release 注入正式 `PUBLIC_BASE_URL`，正式产物不得包含 localhost/127.0.0.1 API origin。

**正式数据库只允许 Alembic 演进。** `0001_init_core_tables` 已改为冻结 MySQL 8 DDL，不再在运行迁移时导入当前 ORM `metadata.create_all`。新增 migration 的 `upgrade()` 必须遵守 expand/contract：同一发布不得直接 drop/rename 旧结构、原位改变类型或直接收紧 `nullable=False` 破坏 N-1 代码兼容；收缩动作在旧代码退役后的后续 release 再做。

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

禁止用演示 seed 作为真实学校初始化方式。所有 well-known 演示/试用/沙箱身份以 `backend/app/core/tenant_identity.py` 为唯一代码真值；seed 必须按 tenant code/ID 双重核验目标后才能写入，不能在业务 seed 自行硬编码 Snowflake tenant ID。

## 5. 备份、恢复与发布失败回滚

生产备份统一按 `deploy/README-data-governance.md` 落地：

- 配置正式 `backup.env` 与 rclone 异地目标，异地对象存储启用版本化/不可变保留/存储侧加密；
- 启用 `school-lifecycle-backup.service/.timer`，每天 4 次生成恢复点；local 文件存储必须把 `UPLOAD_DIR` 与 MySQL 纳入同一恢复集；
- 启用 `school-lifecycle-backup-watchdog.service` 与 `school-lifecycle-backup-watchdog.timer`，后者每小时检查 RPO、本地完整性、异地 commit/回读证据；
- GitHub 定时恢复演练继续作为独立灾备证据；首次生产部署必须人工跑一次真实备份 + watchdog + 隔离恢复，确认真实环境配置；
- 生产 `FIELD_ENCRYPTION_KEY`、历史 key（如有）及固定搜索 HMAC key 的受保护恢复副本保存在应用服务器与 Git 之外；
- 生产基线：**RPO ≤ 6 小时、RTO ≤ 2 小时**，本地保留策略和异地保留按数据治理合同执行。

发布回滚现在分两段：

1. **迁移开始前失败**：数据库尚未改变，只清理/回退候选 release，不恢复数据库。
2. **`alembic upgrade head` 已开始后的任何失败**：脚本先停止所有候选写入者，必须用本次 `ROLLBACK_MANIFEST` 调用 `deploy/backup/restore-backup-set.sh` 恢复受治理的数据库与 uploads；恢复成功后才允许切回 previous symlink、恢复 previous systemd units 并重启旧服务。若 manifest 缺失、恢复失败或旧服务重启失败，脚本保持服务停止并以独立严重错误码退出，禁止把“旧代码 + 新 schema”伪装成回滚成功。

这里**不使用自动 `alembic downgrade`**作为生产事故恢复手段。rollback compatibility gate 仍要求新 migration 对 N-1 代码保持 expand/contract 兼容；受治理恢复是最后一道事故恢复保护，两者缺一不可。

`backend/tests/test_release_rollback_restore_integration.py` 会在隔离 MySQL 数据库中真实注入“候选 schema/数据/文件已改变”的失败场景，再执行同一 restore primitive，验证旧 schema、旧数据和旧 uploads 全部恢复。静态脚本存在不再等同于“回滚已被证明”。

## 6. 浏览器会话与租户生产真值

- 管理 PC 与学生 PC：accessToken 仅内存，refreshToken 仅 HttpOnly + SameSite Cookie；F5 后先通过 browser-refresh 恢复内存会话再做路由授权。
- 微信/非浏览器客户端继续使用自身 token transport，不强行套浏览器 Cookie 模型。
- production 租户解析只认 `t_tenant` 与已验证 Bearer token `tid`；显式未知 tenant 400，业务请求无法解析真实租户时 503 fail-closed，不回退 mock tenant。
- `/api/v1/auth` 与 `/api/v1/platform` 仅按**完整命名空间边界**作为 tenant-neutral 入口；`/api/v1/authz` 等业务授权路由绝不能被前缀误判为 tenant-neutral。

## 7. 合规与安全

上线真实学生数据前仍需学校侧完成隐私告知、最小化授权、运维账号管理、日志留存与第三方安全评估/渗透测试等工作。代码闸门不能替代组织与合规流程。
