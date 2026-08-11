# UI 展示层 V3 销号台账

基线：`main@a40b419a6f8bddd07e817e3c78f715e1ef8967d7`。本台账只记录本轮已施工或已明确收口的卡片，不替代运行态截图验收。

| Card | File | Evidence | Fix | Test | Status |
|---|---|---|---|---|---|
| ROOT-13 | `AppImportPreviewTable.vue` | 任意对象 JSON fallback | schema/安全字段白名单，未知对象不渲染 | `ui-presentation-safety.test.mjs` | DONE |
| ROOT-14 | `presentationSafety.js`, `client.js`, `toast.js`, `ErrorState.vue` | 技术错误可穿透 | 统一错误归一化，403/409/5xx 安全语义 | `ui-presentation-safety.test.mjs` | DONE |
| ROOT-15 | `AppAuditTrail.vue` | action/result/role/IP raw fallback | 审计记录统一展示映射，IP 默认隐藏 | `ui-presentation-safety.test.mjs` | DONE |
| ROOT-16 | `studentAffairs/pickerAdapters.js` | 名称缺失显示 DB ID、raw status/type | 名称缺失禁选并提示待同步，枚举安全映射 | `message-and-picker-presentation-contract.test.mjs` | DONE |
| ROOT-17 | `MessageComposeView.vue` | actionKey/JSON 参数编辑器 | 改为业务字段表单，内部参数不显示 | `message-and-picker-presentation-contract.test.mjs` | DONE |
| ROOT-18 | 教务归档、工作台、学期页、移动规则卡 | ruleCode/trace 默认展示 | 主层业务标签；技术信息仅二次展开 | `ui-presentation-v3-contract.test.mjs`, miniapp contract | DONE |
| ROOT-19 | 消息发布/发件箱 | demo/sandbox/账号实现细节 | 正式业务提示与空态 | `message-and-picker-presentation-contract.test.mjs` | DONE |
| ROOT-20 | StatusTag/dashboard/message mapper | unknown raw fallback | unknown-safe 中文 fallback | 三端 presentation tests | DONE |
| MSG-01—06 | MessageCompose/MessageOutbox | 沙箱、JSON、raw category/status | 业务化发布与安全枚举 | message contract | DONE |
| MSG-07 | 多端消息深链 | actionKey 旁路需运行态补查 | 发布端已禁止 raw actionKey；消费端待运行态矩阵 | — | PARTIAL |
| MSG-08 | `MessageComposeView.vue` | Snowflake/BIGINT 深链参数被 JS `Number` 舍入 | 业务 ID 全程按不透明字符串传递 | `message-deep-link-id-contract.test.mjs` | DONE |
| AA-NEW-01—09 | ArchivePrecheck/AaDashboard/AaTerm*/AaScheduling | 后端话术、规则码、JSON、批次 ID、raw level | 业务文案、结构化证据、安全映射、ID 隐藏 | V3 contract + 原 Stage D tests | DONE |
| PORTAL-DATA-01 | `EmploymentView.vue` | 就业回访列名与真实 `{way, content, time}` DTO 不一致 | 绑定真实字段并把跟进方式中文业务化 | `ui-presentation-v3-data-contract.test.mjs` | DONE |
| PORTAL-DATA-02 | `AcademicView.vue` | 专业分流表读取不存在的 batch/name 字段 | 改用 `choices/gpa/status/resultChoiceRank/adjustReason`，结果不暴露 DB ID | `ui-presentation-v3-data-contract.test.mjs` | DONE |
| SYS-NEW-01—02 | SystemJobCenterView | kind/jobId/status 与授权 JSON | 业务任务摘要、中文状态、结构化授权依据 | V3 contract | DONE |
| SYS-NEW-03—06 | SystemAccessGovernanceView | permission/org/user/role code 手填与 raw 列表 | 权限/组织/人员/角色选择器与安全展示 | build + V3 contract | DONE |
| SYS-NEW-07 | SystemMasterDataView | table/userId/ruleCode/raw status | 中文来源、人员选择器、质量规则/状态映射 | build + V3 contract | DONE |
| SYS-NEW-08—10 | SystemSecurityChangeView | JSON fallback、raw mapper、targetId/traceId | 结构化影响摘要、安全 mapper、主层隐藏 ID | build + V3 contract | DONE |
| SYS-NEW-11—12 | SensitiveAudit + public error layer | result raw 与 ErrorState 穿透 | 审计展示记录映射 + 公共错误归一化 | presentation tests | DONE |
| PL-NEW-01—03 | StudentPortalConfigPanel.vue | 手填 tenant DB ID、开发话术、JSON/raw key | 租户上下文驱动、结构化预览、unknown-safe 标签 | V3 contract | DONE |
| GD-NEW-01 | Graduation*DetailView | audit action 未传 label | 优先传 `actionLabel`，公共审计层兜底 | build | DONE |
| MOB-NEW-01 | MobileAcademicDecisionCard.vue | 教师端默认 ruleCode/trace/version | 主层规则依据；高级角色二次展开技术详情 | miniapp contract | DONE |
| DASH-NEW-01 | dashboard/presentation.js | riskLevel raw fallback | unknown-safe 风险等级 | `ui-presentation-safety.test.mjs` | DONE |
| PORTAL-DATE-01 | AppDatePicker/AffairsFourEndView/InternshipView | 业务页直接使用原生日期输入 | 学生门户公共日期组件、起止约束与扫描门禁 | `date-picker-contract.test.mjs` | DONE |

## 尚需运行态验收

- 真实角色登录、403/409/5xx、旧数据 unknown 枚举注入。
- Excel 导入、打印/PDF、消息深链和各端弹窗交互截图。
- 审计文档中的 PATTERN-HIT 长尾页面逐页截图确认；公共门禁已经覆盖 raw error/status 的默认路径。
