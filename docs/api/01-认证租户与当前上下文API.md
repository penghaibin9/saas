# 01 · 认证 · 租户 · 当前上下文 API

> 属 P0 底座。全端登录、身份、品牌、权限、菜单、按钮、数据范围都从这里来。
> 通用规则见 [00-API契约冻结总册](00-API契约冻结总册.md)（响应/错误码/分页/审计/切换）。
> 前缀：`/api/v1/authz`（全端共用）。

---

## 模块一览

| # | 接口 | 方法 | 路径 | 一期 |
|---|---|---|---|---|
| 1.1 | 登录 | POST | /authz/login | P0 |
| 1.2 | 登出 | POST | /authz/logout | P0 |
| 1.3 | 刷新 Token | POST | /authz/token/refresh | P0 |
| 1.4 | 当前用户 | GET | /authz/me | P0 |
| 1.5 | 当前租户品牌 | GET | /authz/tenant/brand | P0 |
| 1.6 | 我的身份列表 | GET | /authz/contexts | P0 |
| 1.7 | 当前身份 | GET | /authz/contexts/active | P0 |
| 1.8 | 切换身份 | POST | /authz/contexts/{contextId}/activate | P0 |
| 1.9 | 我的数据范围 | GET | /authz/me/data-scope | P0 |
| 1.10 | 我的菜单 | GET | /authz/me/menus | P0 |
| 1.11 | 我的按钮权限 | GET | /authz/me/buttons | P0 |
| 1.12 | 我的模块授权 | GET | /authz/modules | P0 |
| 1.13 | 权限校验（内部） | POST | /authz/check | P0 |
| 1.14 | 微信登录（小程序） | POST | /authz/wechat/login | P1 |

---

### 1.1 登录

- **方法/路径**：`POST /api/v1/authz/login`
- **用途**：账号密码登录，返回 Token 与最小用户上下文。
- **使用页面**：PC 登录页、学生小程序登录、教师移动端登录。
- **请求体**：
  ```json
  { "tenantCode": "hnsh", "loginName": "20230101", "password": "***", "clientType": "PC|STUDENT_MINI|TEACHER_MINI" }
  ```
  > tenantCode 用于定位学校（也可由域名/小程序 appid 反解）。
- **响应字段**：
  ```json
  { "accessToken":"...", "refreshToken":"...", "expiresIn":7200,
    "user": { "userId":"...", "realName":"张三", "userType":"TEACHER", "mustChangePassword":false },
    "contexts": [ { "contextId":"...", "contextType":"COUNSELOR", "contextName":"软件2401辅导员", "dataScope":"COUNSELOR_CLASSES" } ],
    "activeContextId": "..." }
  ```
- **权限**：公开（登录前）。**数据范围**：—。**审计**：是（登录成功/失败写 t_user_login_log + t_security_audit）。**分页**：否。**mock**：是。
- **对应表**：t_user、t_tenant、t_user_login_log、t_user_context、t_user_active_context。
- **备注**：只有一个身份时自动激活；多身份返回列表由前端进身份选择。`mustChangePassword=true` 强制改密后才放行业务。

### 1.2 登出
- `POST /api/v1/authz/logout`。用途：注销当前会话。权限：登录态。审计：是。mock：是。表：t_user_login_log。一期 P0。

### 1.3 刷新 Token
- `POST /api/v1/authz/token/refresh`，请求体 `{ "refreshToken": "..." }`。用途：Token 续期。审计：否。mock：是。一期 P0。

### 1.4 当前用户
- **方法/路径**：`GET /api/v1/authz/me`
- **用途**：拉取当前登录用户基础信息（刷新页面/重进用）。
- **使用页面**：所有端顶栏。
- **响应字段**：`{ userId, realName, userType, avatarFileId, phoneMasked, activeContextId }`（手机号脱敏）。
- **权限**：登录态。**数据范围**：SELF。**审计**：否。**分页**：否。**mock**：是。**表**：t_user。**一期**：P0。

### 1.5 当前租户品牌（tenantBrandConfig）
- **方法/路径**：`GET /api/v1/authz/tenant/brand`
- **用途**：返回学校品牌配置，**登录页与全端顶栏品牌全部来自这里，禁止前端硬编码学校名**。
- **使用页面**：登录页、PC 顶栏、小程序首页、浏览器标题/favicon。
- **响应字段**：
  ```json
  { "tenantId":"...", "platformName":"职校全生命周期平台", "platformSubtitle":"学生成长管理平台",
    "browserTitle":"...", "logoLightUrl":"...", "logoDarkUrl":"...", "faviconUrl":"...", "badgeUrl":"...",
    "loginBgUrl":"...", "campusLineUrl":"...", "primaryColor":"#2563EB", "secondaryColor":"...",
    "defaultTheme":"academy_blue", "motto":"厚德 精技 笃行", "watermarkText":"..." }
  ```
- **权限**：可公开（登录页需要，按 tenantCode 取）。**数据范围**：—。**审计**：否。**mock**：是。**表**：t_tenant、t_tenant_brand_config、t_file_object（图 URL 由 file_id 转签名 URL）。**一期**：P0。
- **备注**：这是 UI 文档强调的 `tenantBrandConfig` 唯一来源。前端所有品牌位（logo/校训/主色/背景/标题）绑定此接口。

### 1.6 我的身份列表
- **方法/路径**：`GET /api/v1/authz/contexts`
- **用途**：列出当前用户所有可用身份（多身份工作台的身份选择页）。
- **使用页面**：PC 顶栏角色切换器、教师移动端身份选择页(T2)。
- **响应字段**：`items[] { contextId, contextType, contextName, orgName, dataScope, todoCount, riskCount, enabled }`。
- **权限**：登录态。**数据范围**：SELF。**审计**：否。**分页**：否（数量少）。**mock**：是。**表**：t_user_context / t_teacher_context、t_student_org_relation。**一期**：P0。

### 1.7 当前身份
- `GET /api/v1/authz/contexts/active` → `{ contextId, contextType, contextName, dataScope, moduleScope }`。一期 P0。

### 1.8 切换身份
- **方法/路径**：`POST /api/v1/authz/contexts/{contextId}/activate`
- **用途**：切换当前工作身份，切换后菜单/待办/数据范围/按钮全部改变。
- **使用页面**：角色切换器、教师端 T2。
- **请求体**：`{ "clientType":"PC", "deviceId":"..." }`
- **响应字段**：`{ activeContextId, contextType, dataScope, menusChanged:true }`。
- **权限**：登录态 + 该身份属于本人且 enabled。**数据范围**：SELF。**审计**：是（上下文切换）。**mock**：是。**表**：t_user_active_context。**一期**：P0。
- **备注**：身份过期/禁用返回 `ROLE_NOT_FOUND` 或 `CONTEXT_EXPIRED`。切换后前端须重新拉 1.9/1.10/1.11。

### 1.9 我的数据范围
- **方法/路径**：`GET /api/v1/authz/me/data-scope`
- **用途**：当前身份的数据范围（顶栏"数据范围：本人指导学生 18 人"）。
- **响应字段**：`{ scopeType:"INTERN_STUDENTS", scopeLabel:"本人指导实习学生", studentCount:18 }`。
- **权限**：登录态。**审计**：否。**mock**：是。**表**：t_data_scope_rule、t_user_context。**一期**：P0。

### 1.10 我的菜单
- **方法/路径**：`GET /api/v1/authz/me/menus`
- **用途**：返回当前身份 + 已授权模块下的菜单树（未授权模块不返回，到期模块带只读标）。
- **使用页面**：PC 左侧菜单、小程序服务入口。
- **响应字段**：`items[] { menuCode, title, path, icon, moduleCode, readonly:false, children[] }`。
- **权限**：登录态。**审计**：否。**mock**：是。**表**：t_module_def、t_tenant_module_entitlement、t_role_permission、t_permission。**一期**：P0。
- **备注**：菜单过滤 = 已购模块 ∩ 角色权限 ∩（学生端再 ∩ 学生阶段）。到期模块 `readonly:true`，不隐藏。

### 1.11 我的按钮权限
- **方法/路径**：`GET /api/v1/authz/me/buttons?page=studentList`
- **用途**：返回某页面当前身份可见/可用的按钮权限码集合（前端据此显隐按钮，后端仍二次校验）。
- **响应字段**：`{ buttons: ["student.import","student.export","student.field.view_full"] }`。
- **权限**：登录态。**审计**：否。**mock**：是。**表**：t_role_permission。**一期**：P0。

### 1.12 我的模块授权
- **方法/路径**：`GET /api/v1/authz/modules`
- **用途**：当前租户各模块授权状态（控制菜单/路由/写操作/只读）。
- **响应字段**：`items[] { moduleCode, status:"ACTIVE|TRIAL|EXPIRING|EXPIRED_READONLY|SUSPENDED", expireAt, features:{...} }`。
- **权限**：登录态。**审计**：否。**mock**：是。**表**：t_tenant_module_entitlement、t_feature_flag。**一期**：P0。

### 1.13 权限校验（内部/前端可选）
- `POST /api/v1/authz/check`，体 `{ permissionCode, resourceId? }` → `{ allowed:true }`。用途：前端个别按钮点击前校验。审计：否。一期 P0。

### 1.14 微信登录（小程序）
- **方法/路径**：`POST /api/v1/authz/wechat/login`
- **用途**：小程序 wx.login code 换取绑定 → 登录。
- **请求体**：`{ "code":"...", "clientType":"STUDENT_MINI" }`
- **响应字段**：同 1.1；未绑定返回 `WECHAT_AUTH_REQUIRED` + 绑定引导。
- **权限**：公开。**审计**：是。**依赖微信能力**：是。**mock**：是（mock 直接返回登录态）。**表**：t_wechat_binding、t_user。**一期**：P1。

---

## 一期范围小结（本文档）
全部 P0（除 1.14 微信登录 P1）。这是所有其它文档的前置：任何业务接口都假定 1.1/1.4/1.8/1.9/1.10 已就绪。
