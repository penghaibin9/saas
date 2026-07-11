# 00 · API 契约冻结总册

> 文档性质：全端 API 契约冻结总册（唯一权威 API 基线）
> 适用项目：职校学生全生命周期 SaaS 平台
> 依据：`docs/database/00-数据库设计冻结总册.md`（DB 基线）+ UI 设计稿（PC/小程序）+ 业务深化文档 01–12 + 11 权限与流程 §12 + 08B 教师移动 §11
> 技术栈（已拍板）：PostgreSQL + Python FastAPI + SQLAlchemy + Alembic
> 冲突优先级：本册 > 各域 API 文档（01–10）> 深化文档零散接口
> 本轮边界：**只生成 API 契约与交接文档**。未写后端/前端代码、未写迁移、未连库、未改 router/provider/mock/security/workflow。
> 生成日期：2026-07-03

---

## 阅读指引（本册是给 AI 和开发的施工资料，用户本人不需要逐章阅读）

- 想懂**全局规则**（响应/错误码/分页/权限/租户/角色/审计/文件/切换）→ 本册
- 想找**某个业务的接口** → 看 01–07 各域文档
- 想知道**某个页面调哪些接口** → 看 08（小程序）、09（PC）映射文档
- 想知道**前端怎么从 mock 切真实后端** → 看 10

本套 API 文档共 **11 份**，覆盖 **PC 管理端 + 学生小程序 + 教师移动端** 全端。

---

## 一、API 总体原则

```text
1. REST 风格：资源用名词复数，动作用 HTTP 方法（GET 查 / POST 建 / PUT 全量改 / PATCH 局部改 / DELETE 删）。
   复杂动作用子资源动词：POST /xxx/{id}/approve、/return、/publish、/activate。
2. 统一版本前缀 /api/v1。
3. 分端前缀（对齐 V3.0 §15、路由隔离）：
   /api/v1/admin/*            PC 管理端
   /api/v1/student-pc/*       学生 PC 门户
   /api/v1/enterprise-portal/* 企业导师 PC 端（后期）
   /api/v1/student-mini/*     学生小程序
   /api/v1/teacher-mobile/*   教师移动工作台
   /api/v1/platform/*         SaaS 平台运营端
   /api/v1/authz/*            权限与身份底座（全端共用）
   /api/v1/files/*            文件中心（全端共用）
4. 所有业务 API 默认按 tenant_id 隔离；前端不传 tenant_id，后端从登录上下文解析（见 §六）。
5. 当前角色/身份通过 currentRoleCode + activeContextId 体现（见 §七）；数据范围通过 dataScope 体现（见 §八）。
6. 敏感字段默认脱敏返回；查看完整值需字段权限 + 写审计（见 §九、§十二）。
7. 所有列表接口分页（见 §四）；所有写操作支持 request_id 幂等；审批类写操作带 version 乐观锁。
8. 驳回/退回必须带 reject_reason（≥5 字，服务端校验）。
9. 文件上传只返回 file_id，业务写操作只提交 file_id，不把文件写进业务表（见 §十一）。
10. 空状态、无权限、无数据范围都必须有明确结构化返回，不返回裸 500 或空白。
```

## 二、统一响应结构

**成功：**
```json
{
  "code": "SUCCESS",
  "message": "success",
  "data": { },
  "traceId": "req-8f3a...",
  "timestamp": "2026-07-03T14:05:00+08:00"
}
```

**失败：**
```json
{
  "code": "NO_PERMISSION",
  "message": "无权限访问当前数据",
  "details": { "required": "gd:topic:review" },
  "traceId": "req-8f3a...",
  "timestamp": "2026-07-03T14:05:00+08:00"
}
```

**约定：**
- `code` 为业务码（见 §三），HTTP 状态码另用于传输层语义（200/400/401/403/404/409/413/429/500）。
- `traceId` = 请求链路 ID（= DB 审计表的 `request_id`），前端出错时展示给用户便于报障。
- `timestamp` 用 ISO8601 带时区。
- 成功恒 `data` 对象；列表放在 `data` 里的分页结构（见 §四）。

## 三、统一错误码

| code | HTTP | 含义 | 前端处理 |
|---|---|---|---|
| SUCCESS | 200 | 成功 | 正常渲染 |
| VALIDATION_ERROR | 400 | 参数校验失败 | 表单标红，details 给字段级原因 |
| UNAUTHORIZED | 401 | 未登录/Token 失效 | 跳登录（安全页 /security/401） |
| NO_PERMISSION | 403 | 无角色权限（缺权限码） | 无权限页 /security/403 |
| NO_DATA_SCOPE | 403 | 有菜单权限但无数据范围 | 空列表 + "当前身份范围暂无数据" |
| TENANT_NOT_FOUND | 404 | 租户不存在/停用 | 提示联系管理员 |
| ROLE_NOT_FOUND | 404 | 角色/身份不存在 | 引导切换身份 |
| DATA_NOT_FOUND | 404 | 资源不存在 | 空态 |
| DATA_CONFLICT | 409 | 数据冲突（重复/状态不允许） | 提示原因 |
| APPROVAL_VERSION_CONFLICT | 409 | 乐观锁冲突（别人先改了） | 提示刷新后重试 |
| REJECT_REASON_REQUIRED | 400 | 驳回未填原因或<5字 | 强制填写 |
| MODULE_NOT_AUTHORIZED | 403 | 模块未授权 | 菜单隐藏/未开通页 |
| MODULE_EXPIRED_READONLY | 403 | 模块到期只读 | 只读横幅 + 续费提示 |
| FILE_TOO_LARGE | 413 | 文件超限 | 提示压缩 |
| FILE_TYPE_NOT_ALLOWED | 400 | 文件类型不允许 | 提示允许类型 |
| UPLOAD_FAILED | 500 | 上传失败 | 允许重试 |
| WECHAT_AUTH_REQUIRED | 401 | 需微信授权 | 拉起微信授权 |
| LOCATION_PERMISSION_REQUIRED | 400 | 需定位权限（打卡） | 引导开定位 |
| IDEMPOTENCY_CONFLICT | 409 | 相同 request_id 不同 payload | 提示重复提交 |
| RATE_LIMITED | 429 | 触发限流 | 稍后重试 |
| SERVER_ERROR | 500 | 服务异常 | 安全页 /security/500 + traceId |

> 各域可扩展专用码（如 `TEACHER_MOBILE_SCOPE_DENIED`、`SOD_VIOLATION`、`LOCATION_OUT_OF_RANGE`），但必须挂靠上表大类，不得新造与上表语义重复的码。

## 四、分页结构

**请求（二选一，全站统一其一）：**
- 页码分页（PC 列表默认）：`?page=1&pageSize=20&sort=createdAt,desc`
- 游标分页（小程序滚动加载）：`?cursor=xxx&pageSize=20`

**响应（放在 `data` 内）：**
```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 100,
  "nextCursor": null
}
```
- `total` 在游标模式可为 null（不强制算总数）。
- 单次 `pageSize` 上限 100，默认 20。

## 五、权限校验（服务端强制链，前端只做体验）

每个业务接口后端按固定链路校验（对齐 11 §13.1）：
```text
authMiddleware(登录) → tenantMiddleware(租户) → moduleEntitlementMiddleware(模块授权)
→ featureFlagMiddleware(功能开关) → permissionMiddleware(权限码) → dataScopeMiddleware(数据范围)
→ sodMiddleware(职责互斥) → auditMiddleware(留痕)
```
- 前端隐藏菜单/按钮/字段只是体验，**后端必须重新校验**。
- 每个接口在本套文档里都标注：`权限要求`（权限码）+ `数据范围要求`（scope 枚举）。

## 六、tenant_id 隔离

- 前端**永不**传 tenant_id。后端从 Token/会话解析当前租户，SQLAlchemy 会话级注入 `WHERE tenant_id = :currentTenant`。
- 跨租户访问一律拒绝（TENANT_NOT_FOUND / NO_PERMISSION）。
- 平台运营端（/platform）查看多租户是唯一例外，且必须走平台权限 + 写 `t_security_audit`。

## 七、currentRole 当前角色 / active_context

- 用户可有多个身份（辅导员/毕设导师/实习导师/企业导师/学院管理员…）。
- 登录后返回可用身份列表；每客户端激活一个 `activeContextId`。
- 切换身份接口：`POST /api/v1/authz/contexts/{contextId}/activate`（教师移动端：`/api/v1/teacher-mobile/contexts/{id}/activate`）。
- 切换后：菜单/待办/数据范围/按钮/首页全部按新身份重载；写上下文切换审计。
- 接口层通过请求头或会话携带 `activeContextId`；后端据此定 `currentRoleCode` 与 `dataScope`。**权限不合并多身份**。

## 八、dataScope 数据范围（12 种）

`SELF / CLASS / COUNSELOR_CLASSES / GD_STUDENTS / INTERN_STUDENTS / ENTERPRISE_AUTH_STUDENTS / MAJOR / COLLEGE / SCHOOL / DEPARTMENT / TEMP_AUTH / CUSTOM`

- 由当前 active_context 决定；后端在 `dataScopeMiddleware` 翻译为 SQL 过滤，前端不参与计算。
- 有权限但范围内无数据 → 返回 `NO_DATA_SCOPE` 或空 `items`（列表接口用空 items + 提示；明确越权用 NO_DATA_SCOPE）。
- 企业导师 `ENTERPRISE_AUTH_STUDENTS` 对毕设成果/家庭/心理/处分**硬隔离**，查询默认排除。

## 九、审计留痕

以下操作接口必须写审计（`t_security_audit` / `t_operation_audit_log` / `t_file_access_log` / `t_permission_audit`）：
```text
登录/登出、身份切换、审批/批阅/退回/驳回、发布成绩、归档、
导入、导出、查看敏感字段、下载/预览敏感材料、越权尝试、权限变更、模块授权变更、代打卡拦截。
```
- 每份文档里接口标 `是否审计：是/否`。审计写入异步、不阻塞主流程，但审批/导出/敏感访问必须成功落审计。

## 十、文件上传

统一两步（对齐 DB 冻结 §14）：
1. `POST /api/v1/files`（multipart）上传 → 返回 `{ fileId, fileName, size, mimeType, hash }`。
2. 业务写接口只提交 `fileId`（或 fileId 数组），后端把 file_id 存业务表。
- 预览/下载：`GET /api/v1/files/{fileId}/url` → 返回短期签名 URL。
- 敏感材料下载写 `t_file_access_log`。
- 上传限制：默认单文件 ≤50MB（可按类型配置），类型白名单；超限 `FILE_TOO_LARGE` / `FILE_TYPE_NOT_ALLOWED`。

## 十一、审批流

- 审批/批阅统一走 11 权限流程中心的流程引擎：业务提交 → `startWorkflow` → 生成 `t_workflow_task` + `t_unified_todo` + 消息 → 处理人 approve/return → 回写业务状态。
- 审批类接口通用约定：
  - 请求体含 `version`（乐观锁）、`requestId`（幂等）、`comment`；退回/驳回含 `rejectReason`（≥5字）。
  - 通过 = `.../approve`；退回可改 = `.../return`；驳回不可改 = `.../reject`。
- SoD：申请人≠审批人、导师≠自己学生答辩评分人等，违反返回 `SOD_VIOLATION`。

## 十二、mock 到真实 API 的切换原则

- 前端严格 `页面 → provider → api → mock/后端` 分层：**页面不直连 mock、不拼 URL、不写死数据**。
- 每个模块一个 `provider`，内部一个 `api` 实现；`api` 有 `mock` 与 `real` 两版，靠开关切换（详见 [10-Mock数据结构与真实API切换说明](10-Mock数据结构与真实API切换说明.md)）。
- 切真实后端时**只改 api 实现（mock→real），页面与 store 一行不动**。
- mock 返回结构必须与本套契约 100% 一致（同 code/data/分页/字段名）；字段命名与 DB 冻结册对齐（camelCase 对外，snake_case 落库，由后端 DTO 转换）。
- `tenantBrandConfig`、`currentRole`、`dataScope` 三类上下文字段的来源见文档 10 专章。

## 十三、命名与类型约定（前后端一致）

- 对外 JSON 字段 **camelCase**；DB 列 snake_case，由后端 DTO 层转换。
- ID 一律字符串化返回（BIGINT 雪花值超出 JS 安全整数，`"1832..."` 字符串），前端不做数值运算。
- 时间返回 ISO8601 带时区字符串；金额返回字符串或数字两位小数（前端不做浮点运算）。
- 枚举返回英文码 + 可选 `xxxLabel` 中文（中文由后端字典翻译，前端不硬编码映射）。

## 十四、一期优先级（P0–P4）

| 期 | 范围 | 对应文档 |
|---|---|---|
| **P0** | 认证、当前用户、租户品牌、角色切换、数据范围、文件基础、审计基础、状态页基础 | 01 |
| **P1** | 学生首页/待办/提交材料/消息/我的、老师工作台/角色切换/审批列表/审批详情/学生简档 | 01、04、08 |
| **P2** | 数字迎新试点：报到清单、预报到、身份核验、报到码、未报到跟进 | 03、08 |
| **P3** | 岗位实习、毕业设计、就业服务核心流程 | 05、06、07、08、09 |
| **P4** | 导出、弱网草稿、统计洞察、平台运营、SaaS 授权 | 02（导入导出）、09、10 |

> 每个接口在各域文档标 `一期(P?)`，实现时按期推进，避免一次铺全量。

## 十五、本套文档索引

| 文档 | 覆盖 |
|---|---|
| [01-认证租户与当前上下文API](01-认证租户与当前上下文API.md) | 登录/当前用户/租户品牌/角色切换/数据范围/菜单/按钮 |
| [02-学生主档与学生360API](02-学生主档与学生360API.md) | 列表/详情/360/核验/学籍/更正/联系方式/家长授权/文件/导入导出 |
| [03-数字迎新API](03-数字迎新API.md) | 录取激活/批次/报到清单/预报到/核验/缴费绿通/报到码/扫码/未报到跟进 |
| [04-待办审批消息API](04-待办审批消息API.md) | 待办/审批列表详情/同意驳回/留痕/消息/已读回执 |
| [05-岗位实习API](05-岗位实习API.md) | 首页/学生/企业岗位/打卡/异常/周报/批阅/请假/巡访/风险/归档 |
| [06-毕业设计API](06-毕业设计API.md) | 首页/选题/开题/中期/成果/查重/答辩/批阅/退回/留痕 |
| [07-就业服务API](07-就业服务API.md) | 首页/状态/材料/审核/未就业/跟进/状态更新/提醒 |
| [08-小程序端页面到API映射](08-小程序端页面到API映射.md) | 学生端 S/D/P 屏 + 教师端 T1–T30 |
| [09-PC端页面到API映射](09-PC端页面到API映射.md) | 工作台/学生/360/数据中心/权限审批/迎新/实习/毕设/就业/导入导出/平台/授权 |
| [10-Mock数据结构与真实API切换说明](10-Mock数据结构与真实API切换说明.md) | mock 位置/分层/切换/上下文字段来源 |

---

> 本册及本套 11 份文档为纯契约设计，未写任何代码、未连库、未改 src。各接口的 DB 映射以 `docs/database/00-数据库设计冻结总册.md` 为准。
