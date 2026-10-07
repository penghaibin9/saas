# 学生全生命周期 SaaS 发布运行手册

## 日常命令

在 Linux 发布主机、仓库根目录运行：

```bash
sudo ./deploy.sh /path/to/school-lifecycle-release.tar.gz
sudo ./rollback.sh
sudo ./backup.sh
sudo ./health-check.sh
```

`deploy.sh` 只接受两类输入：携带 `.release-commit` 的可信离线发布包，或干净的 Git checkout。它拒绝脏工作区、缺少前后端目录、缺少生产配置、缺少受治理备份配置和并行发布。

## 发布顺序与失败处理

统一发布入口使用现有 `scripts/deploy/install-systemd-release.sh` 的受治理内核。它会建立发布锁、记录旧版本、物化不可变 release、检查 Python/Node 依赖并构建四个前端、暂停后台写入者、执行 MySQL 与上传文件的已校验备份、执行 Alembic 增量迁移、原子切换 `current`、安装 systemd 单元、重启服务并执行 Nginx、健康、数据库迁移和运行时验收。

任一步失败都会退出且不会静默继续。迁移已经开始后的失败，会由内核恢复发布前受治理备份后再恢复旧代码；不会调用 Alembic downgrade。

## 数据库红线

- 不在发布脚本中执行 `DROP DATABASE`、`DROP TABLE`、清空业务表或初始化正式库。
- 结构变更只能运行候选 release 自带的 Alembic 增量迁移。
- `rollback.sh` 仅回滚代码和静态资源，明确输出 `database_action=NONE`；它不回滚数据库。
- 若某个 release 的迁移与旧代码不兼容，停止使用自动回滚，按备份恢复演练和人工变更流程处理。

## 目录与保留策略

- 程序根目录：`/opt/school-lifecycle`
- 不可变版本：`/opt/school-lifecycle/releases/<release-id>`
- 当前版本：`/opt/school-lifecycle/current`（符号链接）
- 上传/导出共享目录：`/opt/school-lifecycle/shared/uploads`、`/opt/school-lifecycle/shared/exports`
- 备份目录：由 `/etc/school-lifecycle/backup.env` 的 `BACKUP_DIR` 决定，默认 `/var/lib/school-lifecycle-backup`

发布脚本不自动删除 release，因而始终保留至少 5 个可回滚版本。需要清理旧版本时，先确认当前与最近 5 个健康版本，再由管理员单独执行并记录。

## 配置与备份

生产密钥只保留在 `/etc/school-lifecycle/backend.env` 和受保护的备份/对象存储配置中，发布包不会携带或覆盖这些文件。`backup.sh` 生成数据库、上传文件、版本标记以及 root-only 配置快照，并为新增文件生成 SHA-256 校验文件；底层受治理备份还要求异地只读回读验证。

## 发布后验收

`health-check.sh` 验证 systemd 服务、Nginx 语法、`/health`、受令牌保护的 `/health/ready`、数据库/Alembic 状态、文件扫描与静态入口。核心业务登录、读取、Excel 和文件操作必须在隔离的演练环境使用真实测试账号验收；不得用生产租户、测试数据覆盖或直改正式库代替验收。

## 当前服务器核验（2026-09-16）

腾讯云主机已有 `/opt/school-lifecycle`、受保护的 `/etc/school-lifecycle/backend.env` 和名为 `saas_lifecycle` 的 MySQL schema；但没有 `current` release、没有 `school-lifecycle` systemd 单元、没有对应 Nginx 路由，且该 schema 当前没有业务表。因此它尚不是可做“升级/回滚”的已运行正式学生系统。先在隔离演练环境完成一次完整发布，再由负责人确认正式首次发布窗口。
