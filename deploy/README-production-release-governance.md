# 生产发布治理与灾备运行手册

本手册只覆盖发布治理、供应链、备份恢复和仓库设置，不替代业务模块验收。

## 1. 发布裁决

正式发布必须同时满足：

1. PR 合并前主 `CI` 全绿；
2. 业务专项门禁按变更范围全绿；
3. 合并到 `main` 后 `Main post-merge acceptance` 必须针对最终 main HEAD 再跑并全绿；
4. `Main / canonical release gate` 失败时禁止部署；
5. `Release governance contracts` 必须通过，不允许一次性 repair/patch/closeout workflow 或旧 Node runtime 回流；
6. 生产数据库只允许通过正式迁移链升级，禁止直接 create_all 或手工改表替代 Alembic。

## 2. main 分支保护（仓库所有者必须在 GitHub Settings 配置）

当前 GitHub App 连接没有修改 Ruleset/Branch Protection 的权限，因此该部分不能由代码提交代替。

对 `main` 建议启用以下规则：

- Require a pull request before merging；
- 禁止 direct push；
- 禁止 force push；
- 禁止删除 main；
- Require branches to be up to date before merging；
- Require status checks to pass before merging；
- 不允许绕过规则（管理员也应尽量受规则约束）。

建议至少把当前始终运行的主 CI job 设为 required checks：

- `控制面合同检查`
- `岗位实习生产闸门`
- `毕业设计生产闸门`
- `后端 pytest（PR:变更感知 / 定时:全量）`
- `PC 管理端 lint + test + build`
- `学生 PC 门户 lint + test + build`
- `小程序生产 build`
- `禁止文件检查`
- `迁移库门禁（真实 alembic schema）`
- `Permanent release governance contracts`

`Main post-merge acceptance` 是合并后的最终 main 证明，不是 PR 合并前的替代品。

## 3. 供应链安全

仓库已提供 `.github/dependabot.yml`，覆盖：

- backend/pip；
- frontend/npm；
- student-portal/npm；
- miniapp/npm；
- GitHub Actions。

GitHub Settings 中仍必须人工确认开启：

- Dependency graph；
- Dependabot alerts；
- Dependabot security updates；
- Secret scanning；
- Push protection；
- Code scanning / CodeQL（当前套餐支持时）。

如果这些开关未开启，不得把“已有 dependabot.yml”描述为供应链安全已经闭环。

## 4. 备份目标

当前单机部署的最低灾备目标：

- **RPO ≤ 6 小时**：systemd timer 每天 01:15 / 07:15 / 13:15 / 19:15 执行全量一致性备份；
- **RTO ≤ 2 小时**：要求值班人员能取得最近一份通过 SHA-256 校验的异地副本并完成恢复、迁移状态、readiness、登录和租户隔离验证。

如果学校合同要求分钟级 RPO，应升级到托管 MySQL/PITR 或 binlog 连续备份；当前全量备份不能虚构成分钟级恢复能力。

## 5. 安装备份 timer

```bash
sudo install -m 600 deploy/env/backup.env.example /etc/school-lifecycle/backup.env
# 编辑 /etc/school-lifecycle/backup.env：配置 BACKUP_RCLONE_REMOTE 和告警地址。
# rclone 的 COS/S3 凭据必须保存在受保护的 rclone 配置或系统 Secret 中，不得提交 Git。

sudo cp deploy/systemd/school-lifecycle-backup.service /etc/systemd/system/
sudo cp deploy/systemd/school-lifecycle-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now school-lifecycle-backup.timer
sudo systemctl list-timers school-lifecycle-backup.timer
```

正式上线推荐保持：

```text
BACKUP_REQUIRE_OFFSITE=true
```

这样异地复制失败时整次备份任务会失败并进入告警，而不会把“只有本机副本”误判为成功灾备。

## 6. 手工演练

正式服务器禁止直接运行 `restore-drill.sh` 指向远程或生产数据库。该脚本只允许 localhost，并要求目标库名以 `_drill`、`_restore_test` 或 `_e2e` 结尾。

仓库的 `Backup restore drill` GitHub Actions 每周在隔离 MySQL/Redis 中执行：

1. 全新 MySQL 跑 Alembic；
2. 写入最小真实登录账号；
3. 调用正式备份脚本生成并校验备份；
4. 恢复到本地 disposable drill DB；
5. 核验 Alembic 与租户数据；
6. 从恢复库启动 FastAPI；
7. 检查 `/health/ready`；
8. 使用真实账号密码登录；
9. 验证跨租户错误登录被拒绝；
10. 保存演练日志和 SHA-256 Artifact。

## 7. Workflow 分类

长期永久门禁应保留，例如：主 CI、文件中心 final acceptance、真实登录 Redis、容量/可观测性、Playwright、教务/学工/实习/毕设正式验收。

已完成使命的一次性脚本不得留在 main，例如：

- 自修改代码并 push 的 package closeout patch；
- 只服务某个旧 PR/旧施工分支的 final merge closeout；
- 临时 sync/repair trigger。

任何新的一次性施工工具必须在合并前删除，最终 PR 只能保留长期运行能力。
