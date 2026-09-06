# 系统管理 UI · 第一批实际实施记录

## 冻结输入与并行边界

- PR：#262；唯一施工分支 `codex/system-management-ui-20260906`。
- 审计/视觉基线：`6810bd6284b4d5c69a78947560f808cd7738327e`。
- 本批集成起点：`9f14e9cf08932585376fb7b397119276ed7fad79`，已包含 `main@bafc9db2f48e98a1ac906a4f88cf37fce39915ce`。
- 用户批准依据：2026-09-06《19页离线预览》及《16个关键交互状态》。采用其角色上下文、双列权限矩阵、独立预览、底部保存条和失败态；合成数据/场景切换/源码说明不进入生产页面。
- 与 #261 并行，但不改它的生产后端、账号变更回执、品牌页面或商业授权。它合并后须重新核对同名接口的处理函数、版本与缓存回执。
- 不改 `BasePortalLayout.vue`、`navPlan.js`、共享权限、路由定义、依赖锁和数据库迁移；这些由其他既有施工线持有。

## 已接入生产入口的本批范围

| 入口 | 实际实现 |
| --- | --- |
| `/admin/system/iam?surface=roles` | 服务端分页角色卡片；创建、复制、名称修改、停用、导出继续使用原接口 |
| `?surface=permissions` / `/admin/system/roles?tab=permissions` | 左侧角色选择 + 菜单与操作/默认范围/成员/留痕/维护；不再要求再点中转入口 |
| `?surface=templates` | 已发布模板、来源版本、本校影响；通配治理初始化改为显式确认 |
| `?surface=members`、角色工作区成员页 | 独立成员分页、候选搜索、最多100人追加授权；不替换账号全部角色 |
| `?surface=access` / `#access-explain` | 姓名与工号选人、稳定主档选对象、服务端最终判定；选择变化后旧结论失效 |
| `/admin/system/module-entitlements` | 四态卡片、只读门、停用影响成功且对象一致才能确认、未知统计不显示零 |
| `/admin/system/scopes` | 本批仅修影响名单/显式策略错误态、受限200条口径与迟到响应；完整布局重构尚未完成 |

原 IAM 治理概览整文件移入 `components/workspace/SystemIamGovernancePanel.vue`，原 blob `0b6d7c10a0faaf04e019fcc9d4192ccad06286e3` 不变；可通过治理概览入口继续访问。没有删除企业权限边界、模板来源/漂移和分页证据功能。

## 关键行为合同

权限保存沿用 `systemApi.saveRolePermissions(menuKeys/buttonKeys/expectedVersion/reason/requestId)`，最终HTTP转换仍由现有适配器完成。具体目标未改动时省略 `scopeTarget`。只读/预设角色不调用只允许配置者读取的权限树；可写角色必须详情与目录双成功、角色和上下文一致。网络结果未知或版本冲突先重新读取、保留选择与原因，不自动重放；缓存警告显示已提交待核对，不再保存同一变更来清缓存。

成员读取使用 `items/total/page/pageSize`；不会用当前页长度冒充总数。成员追加接口没有每人的范围目标，因此保存后仍需核对任职和指导关系。学生业务对象使用 `studentId`，不拿账号 `id` 替代主档编号。所有高风险确认继续由后端逐请求校验。

## 已运行的本地验证（不是学校数据库验收）

- 34项 Node 测试通过：7项既有合同 + 27项新契约/生产 Vue 编译测试。
- 修改的前端文件 ESLint 通过。
- 6项纯文件型后端静态合同通过；仅运行 `test_control_plane_frontend_workspaces.py`，未运行数据库测试。
- 编译后的真实 Vue 组件：15项 Chromium 浏览器检查通过，接口是明确合成夹具，不是实际 HTTP/MySQL。包括读取失败禁止保存、只读不调用权限树、缓存警告不重放、跨页成员、稳定主档ID、迟到结果失效及1440/1280/768三档溢出检查。
- 原有安全变更 E2E 不变；新增实际浏览器流程附在 `e2e/specs/system-role-security-change.spec.mjs`，通过既有 School IAM MySQL 工作流运行。提交前只完成语法检查，实际结果以此提交对应的 CI 工件为准。

```sh
cd frontend
node --test tests/systemAdmin.governance.test.mjs tests/system-role-scope-target-preservation.test.mjs tests/system-user-role-assignment-contract.test.mjs tests/system-ui-workspace.test.mjs
```

## 尚未通过的验收门

本记录不将组件夹具通过换算为真实身份、权限、数据库和公共壳视觉验收。原前端完整构建、School IAM 新增真实创建/保存/成员/审计回读流程、真实多角色和上游分支集成，以精确提交的后续运行结果为准。19个页面族未全部重构；账号、导入、组织、品牌、学期、任务、安全变更等后续页面不得从此记录标为完成。

PR 保持 Draft，不自动合并 main、不部署。后续继续在原分支小批串行提交与复审，不新开同模块分支。
