# 毕业设计 8 工作区 / 50 叶子机器审计记录

## 审计目标

验证毕业设计 HTML 原型的工作区投影是否仍与生产单一事实源一致，避免再次把生命周期概念分组误写成生产导航结构。

## 事实源

- 生产工作区：`frontend/src/modules/graduation/config/graduationWorkspaces.js`
- 当前读取 Blob SHA：`3dedbf5c3332b014d85472f225c8888fe7b607a1`
- 原型契约：`manifest-parts/320-graduation.json`
- 审计工具：`tools/check-graduation-workspace-audit.mjs`

## 当前生产投影

| 项目 | 当前事实 |
|---|---:|
| 工作区 | 8 |
| 三级叶子 | 50 |
| 唯一 URL | 48 |
| 显式共享 URL | 2 |
| 独立 HTML owner | 8 |

两个共享 URL：

1. `/admin/graduation/defense-scoring`
   - `gd-workbench`
   - `gd-defense`
2. `/admin/graduation/stats-report`
   - `gd-workbench`
   - `gd-risk-archive`

## 工具检查项

脚本直接解析生产 `GRADUATION_WORKSPACES`，并逐项核对 320 Manifest：

- 工作区数量、key、名称与主入口；
- 三级叶子总数与唯一 URL 数量；
- 每个工作区 `coveredRoutes` 与生产叶子集合完全一致；
- 每个工作区权限候选覆盖全部生产权限；
- 两个共享 URL 及其 owner 完全一致；
- 8 个 HTML 均存在，且一页只属于一个工作区；
- 每个工作区均具备字段、状态和业务边界契约；
- 无漏工作区、过时工作区、漏 URL、过时 URL或错误共享关系。

## 已完成验证

### 1. JavaScript 语法

```text
node --check tools/check-graduation-workspace-audit.mjs
PASS
```

### 2. 隔离同构夹具

已使用当前生产工作区投影和 320 Manifest 构造与真实仓库相同相对目录关系的隔离夹具，并执行审计工具：

```text
productionWorkspaces: 8
productionLeaves: 50
productionUniqueUrls: 48
productionSharedUrls: 2
manifestEntries: 8
manifestHtmlFiles: 8
errors: 0
```

结果：**PASS**。

该结果证明脚本本身能够解析当前生产结构并识别 320 Manifest 的预期投影，不等价于“当前完整 GitHub 分支已执行通过”。

## 当前未完成

当前执行容器无法解析 GitHub 域名，尚不能克隆或下载完整 PR 分支，因此还没有在真实完整分支快照中执行：

```bash
node tools/check-graduation-workspace-audit.mjs \
  --report=/tmp/teacher-pc-v2-freeze/graduation-workspace-audit.json
```

最终冻结候选 HEAD 必须重新读取生产 `graduationWorkspaces.js` 并真实执行，要求：

- 8 / 8 工作区 PASS；
- 50 / 50 叶子 PASS；
- 48 / 48 唯一 URL PASS；
- 2 / 2 共享 URL 与 owner PASS；
- 8 / 8 HTML owner PASS；
- 权限、字段、状态、边界缺失为 0；
- 漏项、过时项和重复 owner 为 0。

## 结论边界

当前可确认：

- 生产结构已经重新投影为现行 8 工作区；
- 320 Manifest 静态登记为 8 / 50 / 48 / 2；
- 审计脚本语法通过；
- 审计脚本在隔离同构夹具中 0 error。

当前不可宣称：

- 当前完整 PR HEAD 的毕业设计机器审计已经通过；
- 8 个 HTML 的 24 次浏览器回归已经通过；
- 毕业设计中心已经冻结；
- PR 可以转 Ready 或合并。

因此 PR #27 继续保持 Draft，最终候选 HEAD 的真实脚本执行和 24 次浏览器回归仍是冻结阻断。
