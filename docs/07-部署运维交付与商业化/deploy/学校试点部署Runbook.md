# 学校试点部署 Runbook

> 目标：一所学校、真实账号、真实业务数据的受控试点。**任何 FAIL 都禁止导入真实学生数据。**
> 当前推荐部署：2C4G/2U4G Linux + systemd + MySQL 8 + Redis + Nginx + ClamAV。管理 PC、miniapp H5、学生 PC 必须来自同一个 release。

## 0. 服务器与外部依赖

1. 安装 MySQL 8、Redis、Nginx、Python 3、Node/npm（或准备好三端预构建产物）。
2. 安装并启动 `clamd`，确认 TCP `3310` 或 Unix Socket 可连接。正式环境 Office/Excel/ZIP/CSV 等高风险附件是 fail-closed；没有 ClamAV 会导致材料不能进入业务。
3. 域名解析到服务器，只对公网开放 80/443；8000、3306、6379、3310 不直接暴露公网。
4. 配置 HTTPS 证书，把 `deploy/nginx/school-lifecycle.systemd.conf.example` 替换真实域名/证书路径后放进 Nginx。该模板同时提供 `/`、`/miniapp/`、`/portal/`、`/api/`，并拒绝 `/uploads/`、`/exports/` 静态直读。
5. `nginx -t && systemctl reload nginx`。

## 1. 生产环境文件

复制 `deploy/env/backend.systemd.env.example` 到：

```text
/etc/school-lifecycle/backend.env
```

权限：

```bash
sudo chmod 600 /etc/school-lifecycle/backend.env
```

必须逐项替换：MySQL 密码、Redis、`JWT_SECRET`、独立 `FIELD_ENCRYPTION_KEY`、`INTERNAL_OPS_TOKEN`、正式域名、试点学校编码。`APP_ENV=production`、`DEPLOYMENT_MODE=production`、`DEBUG=false`、`MOCK_LOGIN_ENABLED=false`、`SCHEDULER_MODE=external`、`CLAMAV_ENABLED=true` 不得改变。

如果启用 COS，再填写 `FILE_STORAGE_BACKEND=cos` + COS 参数；单机试点暂用 local 时，`/opt/school-lifecycle/shared/uploads` 必须进入备份与恢复演练。

## 2. 两道只读预检

代码侧静态准入：

```bash
bash scripts/check/preflight-school-trial.sh /etc/school-lifecycle/backend.env
```

服务器侧真实依赖预检：

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --check
```

两者必须 `FAIL=0`。服务器预检会额外核验：实际 Nginx `/portal/`、ClamAV PING、动态 Alembic 单头、systemd 文件齐全等。

## 3. 原子发布

不要再手工分别复制管理端、小程序、学生门户，也不要运行 `metadata.create_all`/`init_mysql_db.py` 作为正式建库流程。正式数据库只走 Alembic：

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --apply
```

脚本会按顺序执行：

1. 发布前 MySQL 全备份 + gzip/sha256 校验；
2. 创建独立 release 目录和 Python venv；
3. 构建 `frontend`、`miniapp`、`student-portal`；
4. `alembic upgrade head`；
5. 动态核验“仓库唯一 head == 数据库 current”，不再写死任何 revision；
6. 原子切换 `/opt/school-lifecycle/current`；
7. 原子更新 `/var/www/school-lifecycle/pc|miniapp|portal`；
8. 安装并启动 `school-lifecycle-backend`、`school-lifecycle-scheduler`、`school-lifecycle-file-scan`；
9. 自动执行发布后验收；失败时回退应用 symlink，数据库迁移不自动 downgrade。

## 4. 发布后强制验收

可单独重跑：

```bash
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/verify-systemd-release.sh
```

必须看到 `FAIL=0`。它会验证：

- backend / scheduler / file-scan 三服务 active；
- Nginx 语法、`/portal/`、`/uploads/`、`/exports/` 保护；
- `/health` 为 UP；
- 携带 `INTERNAL_OPS_TOKEN` 的 `/health/ready` 为 READY；
- 数据库 current 等于动态 Alembic head；
- ClamAV PING/命令链正常；
- 管理 PC、miniapp H5、学生 PC 三端构建产物及原子链接存在；
- `/docs` 在 production 关闭；
- 未登录业务访问被拒绝。

`/health/ready` 已把文件扫描依赖纳入就绪判断：扫描 required 时，ClamAV disabled/down 或扫描任务进入 DEAD 都会返回 DEGRADED/503，禁止“附件全卡住但系统假绿”。

## 5. 新学校开局

只有前四阶段全绿后才创建/导入真实学校数据：

1. 平台创建试点租户；
2. 配品牌、院系、专业、班级；
3. 通过系统管理标准身份导入入口导入老师/学生；
4. 先 dry-run/预检，处理全部错误行，再 confirm；
5. 用最小真实样本做教师、学生、辅导员、教务管理员账号登录与权限验证。

禁止把演示 seed 作为真实学校初始化方式。

## 6. 试点业务冒烟

至少用真实试点角色验证：登录/刷新、学生本人数据、教师数据范围、跨租户负向 403、Excel 导入/导出、附件上传→隔离→ClamAV CLEAN→业务绑定/下载、消息/审批后台任务、学生 PC `/portal/` 刷新子路由、小程序 H5。

任何跨租户越权、文件扫描卡死、后台任务不消费、迁移不一致、READY 503 都是上线阻断，不以“页面能打开”替代。

## 7. 备份与恢复

部署每日 MySQL 备份：`deploy/backup/backup-mysql.sh`。使用本地文件存储时必须同时备份 `UPLOAD_DIR`。正式导入大批真实数据前做一次恢复演练：恢复到临时 MySQL → `alembic current`/动态检查 → 登录 → 抽查敏感字段可解密 → 抽查附件可下载。

**试点准入最终口径：静态预检 0 FAIL + 服务器预检 0 FAIL + 发布验收 0 FAIL + 真实角色冒烟通过 + 备份恢复实证通过，之后才允许扩大真实数据范围。**
