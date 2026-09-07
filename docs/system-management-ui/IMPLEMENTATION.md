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

## 第二批续工：角色真实流程收口与师生导入工作区

本批起点为 `3c64a12`。`00f0407dbda19911728d2c5a98b860b66b184a6e` 已为角色创建表单的来源模板与默认范围补上稳定可访问名称；没有删除或放宽原浏览器断言。

精确 `00f0407` 的 School IAM 工作流 `34043291564` 已成功，包含新增 UI 创建角色、保存权限、追加成员、刷新回读、保留原角色及审计验证，以及原安全变更与角色投影测试。该成功不能推算为下面新增导入工作区已完成真实 Excel→worker→MySQL 的整链验收。

### P04/P05 逐控件接线

教师、学生两个既有 route entry 均使用 `IdentityImportWorkspace.vue`，仅固定 kind，不改正式路由、权限定义、API客户端、后端或worker。原共享 ImportDialog 保留供其他页面使用；此处改为页内五步办理。

| 控件 / 状态 | 生产调用与约束 |
| --- | --- |
| 下载标准模板 | 原 `systemApi.downloadTeacherImportTemplate` / `downloadStudentImportTemplate`，不在浏览器自建模板 |
| 上传名单 | 原 `dataExchangeApi.validateIdentity(kind, File)`；同一 File 对象显式重试继续由原API的WeakMap复用上传幂等标识 |
| 扫描与预检 | 原 `waitIdentityValidation` 纯GET轮询；处理态计数显示未取得；离开只Abort本地轮询，不取消服务器任务 |
| 刷新和任务深链 | 当前导入页 `?jobId=` 纯GET恢复；校验数字ID、IMPORT/SYSTEM、IDENTITY_TEACHER/STUDENT与服务器版本；错误类型任务不显示 |
| 错误明细 | 原 `getImportErrors`，20条分页；只投影行号/字段/消息，不渲染raw snapshot；读失败独立错误，不等于零错误 |
| 核对并继续 | 重新GET，冻结任务ID、文件ID、版本、身份、状态与数量摘要；填写确认勾选不自动代勾 |
| 确认导入 | 再次GET并比较核对摘要，仅调用原 `confirmImport(jobId, current.version)`；不提交rows/batchNo/tenantId；状态或版本变化重新核对 |
| 完成回执 | POST成功后再次GET；确认结果未知时阻止再次POST；只展示后台真实分类计数，缺失不补0 |
| 初始凭据 | 本页不存储/截图/自动下载凭据；沿原任务中心受控下载，不能将receiptFileId当exportJobId |

现有确认服务校验：`data_exchange_confirm_service.confirm_identity_import_job` → `data_exchange_confirm_legacy.confirm_import_job` → `_finish`；确认后持久状态为SUCCEEDED。结果计数沿 `school_onboarding_service` 的 `entities.teachers/students/studentAccounts` 与 `summary.studentsReused/accountsSkipped`，不按原型样例推导。

第二批本地：新增29项导入状态/请求生命周期/生产SFC测试；与已有测试合跑68项通过，修改文件ESLint通过。恢复快照全量Node为817项通过，但不是完整最新main的所有业务文件，不能代替精确HEAD CI。新增12项Chromium编译组件夹具检查通过，含1440/1280/768、教师/学生请求形状、扫描、错误分页、版本变化、只读与结果未知。

保留待验：精确新HEAD构建与School IAM回归；真实师生XLSX上传、扫描worker、确认持久化与凭据票据下载；仅viewOwn身份的父布局/路由权限仍需专门联调，不能仅凭组件夹具宣布全站已兼容。账号目录、组织、任务中心等剩余页面继续按批准稿施工。
