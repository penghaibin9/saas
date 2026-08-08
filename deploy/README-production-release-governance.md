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

当前 GitHub App 连接只有 Administration read 权限，没有 Ruleset/Branch Protection 写权限，因此该部分不能由代码提交代替。

推荐使用 GitHub Ruleset 对 `main` 启用以下规则：

- **Target branches 必须包含 Default branch 或明确 `main`**；创建 active Ruleset 但目标分支为空并不会保护任何分支；
- Require a pull request before merging；
- Restrict deletions；
- Block force pushes / non-fast-forward；
- Require status checks to pass before merging；
- Required check 至少包含 `Main / canonical release gate`；
- **Require branches to be up to date before merging**（对应 required status checks 的 strict policy）；
- 不允许 bypass（管理员也应尽量受规则约束）。

平台配置完成后，不以“Ruleset 页面显示 Active”作为验收，而要检查 GitHub 的 effective-rules API：

```text
GET /repos/penghaibin9/saas/rules/branches/main
```

该接口必须真实返回作用于 `main` 的 `deletion`、`non_fast_forward`、`pull_request`、`required_status_checks`，并且 required status checks 必须包含 `Main / canonical release gate`，strict policy 必须为 true。

仓库内 `Main / protected branch contract` 已按这个 effective-rules 结果 fail-closed；只有在没有 effective Ruleset 时才回退接受传统 Branch Protection 的 `protected=true`。禁止通过修改 workflow 条件绕过平台治理。

建议其他长期 required checks 仍由 `Main / canonical release gate` 内部汇总，避免 Ruleset 直接绑定大量会随变更范围跳过的专项 job 造成不可合并；canonical gate 自身必须唯一命名并永久存在。

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

- **RPO ≤ 6 小时（21600 秒）**：systemd timer 每天 01:15 / 07:15 / 13:15 / 19:15 执行全量一致性备份；
- **RTO ≤ 2 小时（7200 秒）**：要求值班人员能取得最近一份通过 SHA-256 回读校验的异地副本并完成恢复、迁移状态、readiness、登录和租户隔离验证。

`restore-drill.sh` 默认使用上述生产基线并把备份年龄、恢复耗时、Alembic 版本、表/索引/FK/租户数量写入证据文件；CI 针对小型测试库可覆盖为更严格阈值。

如果学校合同要求分钟级 RPO，应升级到托管 MySQL/PITR 或 binlog 连续备份；当前全量备份不能虚构成分钟级恢复能力。

## 5. 安装备份 timer

```bash
sudo install -o root -g schoolapp -m 640 deploy/env/backup.env.example /etc/school-lifecycle/backup.env
sudo install -o root -g schoolapp -m 640 /path/to/your/rclone.conf /etc/school-lifecycle/rclone.conf

# 编辑 /etc/school-lifecycle/backup.env：
# 1) BACKUP_RCLONE_REMOTE 指向专用异地备份桶/路径；
# 2) 配置告警地址；
# 3) 在云端真正启用并验证版本控制 + 生命周期 + 不可变保留/Object Lock 后，
#    才把 BACKUP_IMMUTABLE_REMOTE_CONFIRMED 改成 true。
# rclone 的 COS/S3 凭据必须只放在 /etc/school-lifecycle/rclone.conf 或系统 Secret 中，不得提交 Git。

sudo cp deploy/systemd/school-lifecycle-backup.service /etc/systemd/system/
sudo cp deploy/systemd/school-lifecycle-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now school-lifecycle-backup.timer
sudo systemctl list-timers school-lifecycle-backup.timer
```

正式上线应保持：

```text
REQUIRE_UPLOAD_BACKUP=1
BACKUP_REQUIRE_OFFSITE=true
RCLONE_CONFIG=/etc/school-lifecycle/rclone.conf
BACKUP_REQUIRE_IMMUTABLE_REMOTE=true
BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true
MAX_BACKUP_AGE_SECONDS=21600
MAX_RESTORE_SECONDS=7200
```

注意：`BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true` 不是“打开保护”的开关，它只是上线证明。必须先在 COS/S3 提供商侧真正配置并验证版本控制、保留/对象锁和生命周期策略。未确认时生产 backup runner 会 fail-closed。

异地复制成功也不只看文件大小：backup runner 会把远端对象重新读回并计算 SHA-256，与本地文件逐字节内容哈希一致后才判定本轮异地备份成功。

## 6. 手工演练

正式服务器禁止直接运行 `restore-drill.sh` 指向远程或生产数据库。该脚本只允许 localhost，并要求目标库名以 `_drill`、`_restore_test` 或 `_e2e` 结尾。

仓库的 `Backup restore drill` GitHub Actions 每周在隔离 MySQL/Redis 中执行：

1. 全新 MySQL 跑完整 Alembic 链，并记录当前精确 `alembic_version`；
2. 写入最小真实登录账号和至少两个租户哨兵；
3. 先证明必需上传目录缺失会 fail-closed；
4. 再证明未配置异地目标时生产 runner 不会把本地备份误判为成功；
5. 调用正式备份脚本生成数据库 + 上传附件备份及 SHA-256；
6. 复制到隔离异地目标并回读比对内容哈希；
7. 恢复到本地 disposable drill DB；
8. 核验精确 Alembic 版本、关键表、索引、外键和租户哨兵；
9. 从恢复库启动 FastAPI 并检查 `/health/ready`；
10. 使用真实账号密码登录并验证跨租户错误登录被拒绝；
11. 校验备份年龄不超过 RPO、恢复耗时不超过 RTO；
12. 保存 readiness、恢复证据、日志和 SHA-256 Artifact。

## 7. Workflow 分类

长期永久门禁应保留，例如：主 CI、文件中心 final acceptance、真实登录 Redis、容量/可观测性、Playwright、教务/学工/实习/毕设正式验收。

已完成使命的一次性脚本不得留在 main，例如：

- 自修改代码并 push 的 package closeout patch；
- 只服务某个旧 PR/旧施工分支的 final merge closeout；
- 临时 sync/repair trigger。

任何新的一次性施工工具必须在合并前删除，最终 PR 只能保留长期运行能力。
