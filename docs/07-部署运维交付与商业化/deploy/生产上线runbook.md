# 生产上线 Runbook

> 本文只保留当前有效的正式上线口径。学校试点逐步执行版见同目录《学校试点部署Runbook.md》。历史 `init_mysql_db.py` / `metadata.create_all` / 演示 seed 不能作为正式建库或升级流程。

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
- HTTPS `CORS_ORIGINS`。

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

发布脚本负责：发布前数据库备份、独立 release 目录、三端构建、`alembic upgrade head`、动态单头/current 校验、原子 symlink 切换、backend/scheduler/file-scan 三服务重启、发布后验收。

**正式数据库只允许 Alembic 演进。** 不允许人工补表、`metadata.create_all`、跳过失败迁移或写死某个 Alembic revision 到发布脚本。

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
- 管理 PC、miniapp H5、学生 PC 都来自当前 release；
- production `/docs` 关闭；
- 未认证业务访问被拒绝。

文件扫描属于生产就绪依赖：required 时 ClamAV disabled/down 或 DEAD job 都会让 READY 降级，不能用“网页能打开”替代。

## 4. 真实学校数据准入

只有部署验收通过后才能导入真实学校数据。先小样本再扩大：平台建租户 → 品牌/组织 → 身份导入 dry-run → 修完错误行 → confirm → 教师/学生/辅导员/教务管理员真实角色 smoke → 跨租户负向验证 → 附件上传/扫描/绑定/下载 → Excel 导入导出 → 后台任务消费。

## 5. 备份、恢复与回滚

每日执行 `deploy/backup/backup-mysql.sh`。本地文件存储时必须同步备份 `UPLOAD_DIR`。真实大批数据导入前和每次重要升级前做一次恢复演练，验证：数据库可恢复、Alembic current 正确、敏感字段能解密、附件可读取、关键账号可登录。

应用发布失败时脚本会把 `/opt/school-lifecycle/current` 回退到上一个 release；**数据库迁移不会自动 downgrade**。因此任何迁移上线前必须先有可恢复备份，并保证向后兼容/可回滚方案。

## 6. 合规与安全

上线真实学生数据前仍需学校侧完成隐私告知、最小化授权、运维账号管理、日志留存与第三方安全评估/渗透测试等工作。代码闸门不能替代组织与合规流程。
