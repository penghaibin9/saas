# 系统管理 UI · PR #262 最终施工记录

## 冻结输入与施工边界

- PR：#262；唯一施工分支 `codex/system-management-ui-20260906`。
- 用户批准依据：2026-09-06《19页离线预览》及《16个关键交互状态》。
- 生产实现原则：冻结稿提供信息架构、操作顺序和视觉目标；页面运行事实继续来自真实 API / MySQL / 权限 / 状态机，不把原型样例数据复制进生产。
- 继续使用既有 `BasePortalLayout`、真实路由、权限码、API 客户端和后端状态机；本轮没有新建第二套门户壳。
- 已经比冻结稿更深的页面不降级重写；统一通过系统管理内容区专属视觉层收口，保留真实能力与审计语义。
- PR 保持 Draft；代码完成不等于真实学校、多角色、跨分支兼容和部署验收完成。

## 19 个冻结页面族施工状态

| # | 页面族 | 生产入口 | 当前收口方式 |
| --- | --- | --- | --- |
| 01 | 系统总览 | `/admin/system/overview` | **已收口**：结论 → 高频任务 → 待办/风险 → 审计证据；高频入口按当前权限模式过滤 |
| 02 | 教职工账号 | `/admin/system/accounts/staff` | **已收口**：保留现有真实账号、角色、版本锁与批量能力；统一系统管理视觉层 |
| 03 | 学生账号 | `/admin/system/accounts/students` | **已收口**：保留稳定学生主档绑定、账号状态与批量能力；统一系统管理视觉层 |
| 04 | 教职工导入 | `/admin/system/identity-import/teachers` | **已收口**：页内五步办理，真实上传 → 扫描 → 预检 → 核对 → 确认 → 回读 |
| 05 | 学生导入 | `/admin/system/identity-import/students` | **已收口**：与教师导入共用真实工作区但固定身份类型，不混表 |
| 06 | 角色 | `/admin/system/roles` / IAM 工作区 | **已收口**：角色卡片、创建/复制/停用、来源与治理 |
| 07 | 权限 | `/admin/system/roles?tab=permissions` / IAM 工作区 | **已收口**：角色上下文、权限矩阵、默认范围、冲突/未知结果处理 |
| 08 | 成员 | `/admin/system/role-assignments` / IAM 工作区 | **已收口**：独立分页、候选搜索、追加授权，不把当前页长度冒充总数 |
| 09 | 数据范围 | `/admin/system/scopes` | **已收口**：左侧规则上下文 + 单规则工作区 + 引用角色 + 受限影响预览 + 显式 DENY |
| 10 | 访问排查 | `/admin/system/iam#access-explain` | **已收口**：稳定业务对象 + 服务端最终判定；选择变化后旧结论失效 |
| 11 | 组织 | `/admin/system/org` | **已收口**：保留既有学院/专业/班级/版本/任职深度；统一系统管理视觉层 |
| 12 | 模块开关 | `/admin/system/module-entitlements` | **已收口**：平台授权、学校开关、运行状态分离；未知统计不补 0 |
| 13 | 安全变更 | `/admin/system/security-changes` | **已收口**：保留版本、影响、激活流水；只有激活才改变权限事实 |
| 14 | 审计 | `/admin/system/logs?tab=operation` | **已收口**：保留操作/登录审计、筛选、只读详情与受控导出 |
| 15 | 数据交换任务 | `/admin/system/data-exchange` | **已收口**：任务上下文、版本、结果未知防重放、强敏感回执安全合同 |
| 16 | 实施与验收 | `/admin/system/implementation/overview` | **已收口**：未检查/未读运行时/未预览分别显示“待检查/待读取/待预览”，不伪造 0 |
| 17 | 学校品牌 | `/admin/system/config?tab=brand` | **已收口**：保留真实可编辑字段与实时预览；平台控制字段继续只读 |
| 18 | 学年学期 | `/admin/system/academic-calendar` | **已收口**：保留业务模块接线状态、影响对象与强制切换确认 |
| 19 | 接口与同步 | `/admin/system/integrations` | **已收口**：连接配置 / 凭证轮换 / 连通性测试 / 同步任务结果分开呈现 |

这里的“已收口”是**页面代码与冻结交互目标已经完成对应**，不是把未执行的真实环境验收标成通过。

## 本轮直接重构的关键页面

### 系统总览

`SystemDashboardView.vue` 改为任务优先：保留服务端运行指标；高频入口按 `permissionPatterns` 实时过滤；待办、安全提醒、最近操作都区分“服务端本次返回空”与“系统一定没有问题”。

### 数据范围

`SystemDataScopeView.vue` 改为左侧规则上下文 + 单规则工作区，显示结构化范围、引用角色、历史匹配口径；影响成员继续调用真实 `getScopeAffectedUsers`，最多 200 条并明确可能重复；显式 DENY / ALLOW 保留独立真实策略读取；读取失败不显示成 0。

### 实施与验收

`SystemImplementationWorkspaceView.vue` 修复误导上线判断的 UI 语义：没运行上线检查显示 **待检查**；运行时预设未成功读取显示 **待读取**；没生成安装预览显示 **待预览**；只有取得对应服务端证据后才显示实际数量；验收封板仍以不可变 `acceptanceDigest` 为事实。

### 接口与同步

`SystemIntegrationView.vue` 收口为学校能力与写权限、连接配置与脱敏凭证、连通性测试结果、同步任务结果四层事实。页面明确写出：**连通性测试通过不代表同步任务成功**。

## 统一视觉层

`AdminSystemLayout.vue` 仍只保留一个 `BasePortalLayout`，在系统管理内容区增加 `.system-ui-polish` 包装。`styles/system-ui-polish.css` 只作用于该包装下，统一 19 个页面族的标题、卡片、表单、表格、状态提示和响应式密度；不改全局导航或其他业务模块视觉。

## 关键生产合同继续保留

- 页面只展示真实后端返回结果，不硬编码冻结稿样例业务数据。
- 高风险写操作继续由服务端做权限、租户、版本与状态校验。
- 网络结果未知时不自动重放写请求。
- 师生导入确认仍是 `confirmImport(jobId, current.version)`，实现已迁到共享 `identityImportWorkspace.js`；两个路由 wrapper 只固定身份类型。
- 数据交换强敏感回执继续展示“强敏感、24 小时有效、一次性下载”，实际截止时间以服务端返回为准。
- 文件治理权限不能作为文件原文读取旁路。
- 审计日志不提供删除能力；受控导出仍需权限、水印与脱敏。

## Actions 合同同步

数据交换工作流原静态门仍在两个薄 wrapper 中搜索 `current.version`。第二批重构后，真实确认代码已经迁到共享 `identityImportWorkspace.js`，旧 grep 因此产生假红灯。本轮把门禁调整为验证 wrapper 确实引用共享工作区、共享控制器仍以 `confirmImport(jobId, current.version)` 提交、迁移页仍保留版本与 pendingJobId，同时不放宽租户隔离、`extra="forbid"` 和文件 RBAC-09 断言。

## 验收边界

提交前已对本轮新增/替换 Vue `<script>` 做 Node 语法检查，并新增 `system-ui-surface-completion.test.mjs` 静态合同。**仍必须以本提交对应的 GitHub Actions 精确 HEAD 结果为准。** 未执行的真实学校多角色浏览器验收、生产数据库、外部接口和跨 PR 集成不得从本文标成通过。
