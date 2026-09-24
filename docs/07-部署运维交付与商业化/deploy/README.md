# 部署与上线：当前唯一入口

> 更新：2026-08-31。当前系统已有 FastAPI、MySQL、Redis、Alembic、后台任务、备份恢复和四个客户端交付面；“后端预留”“只部署静态演示站”“固定迁移号 0111”等旧口径均已失效。

## 上线红线

先查看 [`../../00-项目入口与总控/project-status.json`](../../00-项目入口与总控/project-status.json)。只有 `deliverable=true` 才允许执行生产发布。`integration_candidate`、`pending`、`partial` 或 `blocked_environment` 都不等于可上线。

再运行只读检查：

```powershell
python scripts\check\check-release-readiness.py
```

任何 `BLOCK` 都必须先解决。检查不会部署、删除文件、重启服务或访问生产数据库。

## 当前权威文档

| 顺序 | 文档 | 用途 |
|---|---|---|
| 1 | [`上线候选版本检查.md`](./上线候选版本检查.md) | 确认正在看的 commit 能否进入生产流程 |
| 2 | [`生产环境变量清单.md`](./生产环境变量清单.md) | 准备生产配置，真实秘密不入 Git |
| 3 | [`生产上线runbook.md`](./生产上线runbook.md) | 正式发布、验收和失败处置 |
| 4 | [`../../../deploy/README-data-governance.md`](../../../deploy/README-data-governance.md) | MySQL、uploads、异地备份与恢复唯一口径 |
| 5 | [`学校试点部署Runbook.md`](./学校试点部署Runbook.md) | 第一所学校的分阶段执行顺序 |
| 6 | [`10-2U4G非容器部署准备与执行手册.md`](./10-2U4G非容器部署准备与执行手册.md) | 2U4G Linux/systemd 现场准备 |

实际执行脚本以仓库当前版本为准：

- `scripts/check/preflight-school-trial.sh`：环境静态预检。
- `scripts/deploy/install-systemd-release.sh --check`：发布前只读/检查模式。
- `scripts/deploy/install-systemd-release.sh --apply`：生产发布，仅在全部门禁通过后执行。
- `scripts/deploy/verify-systemd-release.sh`：发布后验证。
- `deploy/backup/restore-backup-set.sh`：受治理恢复点的恢复原语。

## 当前交付组成

- 后端服务：FastAPI + MySQL 8 + Redis。
- 管理 PC：`frontend/`。
- 学生 PC：`student-portal/`。
- 移动端 H5/微信构建：`miniapp/`。
- 企业协同 PC：`enterprise-portal/`。
- 后台进程：scheduler、file-scan worker、backup watchdog。

systemd 发布脚本必须构建并验证四个客户端目录，同时发布后端与后台进程。微信小程序审核/发布属于微信平台流程，不等于服务器 H5 发布。

## 旧文档怎么处理

本目录 `01`—`09` 是 2026-07 的新手阶段材料，其中多份仍描述“后端预留”或静态站点手工覆盖。为保留历史链接暂不删除，但已经在文档清单中标记为 `superseded`，不得用于正式上线。

若旧文档与本页、生产 Runbook、数据治理文档或当前脚本冲突，以后四者为准。不要手工覆盖 `dist`，不要用 `metadata.create_all` 建生产库，不要用固定迁移编号判断数据库状态，也不要用自动 `alembic downgrade` 代替受治理恢复。
