# CI 工作流治理说明

> 更新：2026-08-31
> 机器清单：`docs/00-项目入口与总控/ci-workflow-inventory.json`

当前 106 个工作流已经逐个登记名称、负责人、用途、触发配置、最后配置分支、生命周期和替代关系。分类结果由 `python scripts/maintenance/generate-workflow-inventory.py` 生成：

- `stable`：核心 CI、后端稳定分片、备份恢复、容量、安全和主要发布门禁。
- `domain-candidate`：仍需业务域负责人确认是否并入稳定族群。
- `legacy-wave`：包含 `w1/w2/final/one-shot/exact-head` 等阶段语义，候选替代为 `main-canonical-release-gate.yml`。

本轮没有直接删除工作流。原因是当前机器未登录 GitHub CLI，无法读取 `main` 的 branch protection required checks；在无法证明检查名称未被保护规则引用时删除 YAML，可能让合并请求永久等待。该保护性延期不影响现有 CI 运行。

后续删除 `legacy-wave` 必须同时满足：

1. 读取 GitHub branch protection 和 ruleset，保存 required check contexts。
2. 确认替代工作流已在候选 commit 成功运行，并保持必需检查名称兼容。
3. 把最后运行时间和最后使用分支补入机器清单。
4. 单批删除、单批验证，禁止一次删除全部 57 个历史波次。

仓库卫生门禁已接入现有 `ci.yml`，禁止受控临时目录、构建产物、未登记大文件和未豁免完全重复文件。
