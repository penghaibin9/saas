# Control Plane V2 合并前审计收口记录（2026-08-18）

## 审计基线

- 目标分支：`agent/control-plane-v2-hardening-20260817`
- 审计起点 exact HEAD：`10b41fb82b1a02433fd4191bc656801bdb63474a`
- 目标基线：`main@4b706f392bd4213edcf4fbf81e4c292f90028c12`
- 起点关系：branch ahead 35 / behind 0；不需要 rebase、merge-main 或 force。

本记录只覆盖本轮合并前发现的剩余生产缺口，不重写既有 Control Plane 总册，也不把未执行的测试写成 GREEN。

## P-09 Product IAM provenance

最终口径：Product IAM 的 `sourceCommitSha` 必须来自服务器可验证的部署 provenance，浏览器只能提交 expectation，不能成为真值来源。

生产取值顺序：

1. 如果显式配置 `DEPLOYED_COMMIT_SHA`，必须是 40 位 Git SHA；显式值非法时直接 fail-closed，不允许静默回退。
2. 未显式配置时，读取不可变发布 marker：优先 `DEPLOYED_COMMIT_FILE` 指定路径；正式 systemd 发布默认读取 release 根目录的 `.release-commit`。
3. 两者均无法证明有效 SHA 时返回 `PRODUCT_IAM_PROVENANCE_UNAVAILABLE`，禁止创建或发布 Product IAM 版本。

该口径与 `scripts/deploy/install-systemd-release.sh` 已有发布链一致：正式 release 从受信 commit tree 物化，并在 release 根目录生成只读 `.release-commit`。不再要求运维重复手填同一个 SHA 才能使用 Product IAM。

## P-10 Access Review scale guard

最终口径：访问复核创建不得先通过通用 `list_records().all()` 全量水化平台访问记录，再在 Python 中判断是否超过 campaign 上限。

本轮收口后：

- 复核快照仍只由服务器生成；客户端 `items / recordIds / snapshot(s)` 继续拒绝。
- 数据库查询先约束 `config_type`、`is_deleted=false`、`enabled=true`。
- 指定 `tenantIds` 时在 SQL 层做 exact tenant filter，不自动混入 `tenantId=0` 的全局记录。
- 每一类记录最多只读取“当前剩余额度 + 1”条，即 `LIMIT(remaining + 1)`；发现第 `max+1` 项立即 `ACCESS_REVIEW_SCOPE_TOO_LARGE`，且 campaign 不落库。
- close 仍要求冻结快照逐项、无重复、无遗漏地提交 `KEEP / REVOKE`。

因此 P-10 的上限现在既是事务写入保护，也是数据库读取规模保护。

## P-05(D) normalized PAM migration 判定

本轮结论：**NO-GO / 不在本 PR 施工。**

当前 canonical PAM 明确仍以 `PlatformConfig` 作为 storage adapter，normalized PAM tables 尚未形成独立、冻结、可回滚的迁移合同。临合并新增表、数据搬迁或双写会扩大 blast radius，也无法在本分支现有 35 个提交的验收范围内证明 N-1 / rollback / writer ownership。

因此本 PR 只收紧现有 canonical adapter 的生产语义；P-05(D) 后续必须作为独立 migration change set 施工。该 NO-GO 不构成本 PR 合并阻断，因为本分支没有宣称或依赖 normalized PAM schema。

## 合并判据

只有最终 exact HEAD 同时满足以下条件才允许合并：

- branch 相对 main 可合并且无竞态前移；
- P-09 / P-10 targeted contracts 无真实红灯；
- PR required checks 无失败；
- 没有未解决 review blocker；
- 不使用 force、skip、xfail 或修改测试标准制造假绿。

本记录不得被用作“测试已经执行”的替代证据；最终结果以 GitHub 同一 HEAD 的真实检查为准。
