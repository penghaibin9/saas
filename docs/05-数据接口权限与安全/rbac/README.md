# RBAC 权限体系文档目录导航

- **文档性质**：目录导航 / 权限模型总纲说明
- **适用端**：PC 管理端（frontend/）、miniapp（学生端 + 教师端）、后端权限设计参考
- **依据**：
  - `frontend/src/config/adminMenu.js`（PC 模块与角色-模块允许关系）
  - `frontend/src/modules/workflow/`（角色、数据范围、权限点 mock：`workflow.mock.js`）
  - `frontend/src/modules/workflow/context/permission.context.js`（权限判断入口）
  - `frontend/src/mocks/student/student.mock.js`（学生模块细粒度按钮 roleProfiles）
  - `miniapp/.../config/roles.config.js`（miniapp 角色与按钮键）
  - `frontend/src/security/constants/security.constants.js`
  - `docs/05-数据接口权限与安全/security/00-等保三级安全基线总册.md`（引用，不重写）
  - `docs/05-数据接口权限与安全/database/00-数据库设计冻结总册.md`（引用，不重写）
  - `docs/05-数据接口权限与安全/api/00-API契约冻结总册.md`（引用，不重写）
- **当前阶段声明**：本套文档中涉及的角色、权限点、数据范围、按钮键均来自前端 **mock 数据**（`ENV.useMock=true`）。PC 管理端与 miniapp 均未接入真实后端接口；文中所有"权限判断"当前仅在前端 `permission.context.js` 中生效，**后端接入后必须在服务端做二次权限校验**，不能仅依赖前端隐藏按钮/菜单来保证安全。
- **生成日期**：2026-07-04

---

## 一、本目录文件清单

| 文件 | 内容 | 一句话说明 |
|---|---|---|
| `README.md` | 本文件 | 目录导航 + 权限模型总纲 |
| `01-角色体系说明.md` | 角色定义 | 11 类业务角色 ↔ 系统角色码映射、定位、默认数据范围、主要工作台 |
| `02-PC端权限矩阵.md` | PC 权限矩阵 | 角色 × PC 模块 可见性矩阵 + 各模块关键按钮 |
| `03-miniapp权限矩阵.md` | miniapp 权限矩阵 | miniapp 角色 × 页面 可见性矩阵 + 按钮键 |
| `04-数据范围矩阵.md` | 数据范围矩阵 | 9 类数据范围定义、角色默认范围、生效方式、越权处理 |
| `05-角色切换规则.md` | 角色切换规则 | PC/miniapp 角色切换机制、切换后的联动、审计 |
| `06-权限按钮清单.md` | 权限点全清单 | 全部 `permissions[]` + 学生模块细粒度按钮台账 |
| `07-敏感操作权限清单.md` | 敏感操作专表 | 敏感数据/导出/审批/学籍异动等敏感操作的权限、脱敏、审计要求 |

---

## 二、权限模型三层结构

本平台权限模型分为三层，从粗到细依次生效，**任一层判定失败即拒绝**：

| 层级 | 名称 | 作用 | 当前实现 | 判断入口 |
|---|---|---|---|---|
| 第一层 | 模块授权（License）| 判断当前租户是否已购买/授权某业务模块（如是否开通"毕业设计"模块） | **预留**，`licenseContext` 尚未实现，对应错误码 `MODULE_NOT_AUTHORIZED`（未授权）/ `MODULE_EXPIRED_READONLY`（到期只读） | （待后端确认，`licenseContext` 待落地） |
| 第二层 | 角色权限（Permission） | 判断当前角色是否拥有某菜单/页面/按钮/数据操作的权限点 | 前端 mock 已实现：角色 ↔ 权限点绑定关系见 `workflow.mock.js roles[]` | `frontend/src/modules/workflow/context/permission.context.js` |
| 第三层 | 数据范围（Data Scope） | 判断当前角色在拥有操作权限的前提下，能看到/操作哪些数据行（本人/本班/本学院/本校/全平台等） | 权威为数据库冻结册 §10.2 的 **12 类** `data_scope`；前端当前实现 6 类简化枚举（是 12 类的聚合）；详见 `04-数据范围矩阵.md` | `permission.context.js` 的 `getDataScope()` |

判断顺序建议：**模块是否已授权 → 角色是否有该权限点 → 该权限点下数据范围过滤**。三层任一层不通过，均应返回对应错误码（`MODULE_NOT_AUTHORIZED` / `NO_PERMISSION` / `NO_DATA_SCOPE`）并在前端跳转安全错误页或隐藏按钮。

## 三、权限点命名规范

统一命名规范：**`module.resource.action`**

- `module`：模块简写，如 `workflow`、`student`、`internship`、`graduation`、`security`
- `resource`：资源/对象，如 `task`、`profile`、`export`、`apply`
- `action`：动作，如 `view`、`edit`、`approve`、`reject`、`export`、`toggle`

示例：`student.profile.view`（查看学生主档）、`internship.report.reject`（退回实习周报）、`security.export.desensitized`（脱敏导出）。

权限点类型 `PERMISSION_TYPE` 共 4 类：`MENU`（菜单）、`PAGE`（页面/路由）、`BUTTON`（按钮/操作）、`DATA`（数据级权限，如敏感字段查看）。

## 四、判断入口与安全底座

- **前端权限判断唯一入口**：`frontend/src/modules/workflow/context/permission.context.js`，暴露方法：`canAccessPage`、`canClickButton`、`canViewMenu`、`getDataScope`、`hasRole`、`hasAnyPermission`、`filterMenusByPermission`、`filterActionsByPermission`。所有页面/组件应通过该入口判断是否渲染菜单、路由、按钮，禁止在业务代码中硬编码角色码分支。
- **前端安全底座**：`frontend/src/security/`（含 `constants/security.constants.js`：会话策略、敏感分级、上传/导出策略、审计事件类型、CSRF 策略等），详见 `docs/05-数据接口权限与安全/security/00-等保三级安全基线总册.md`（本文档只引用，不重写）。
- **数据库层权限相关表结构**：以 `docs/05-数据接口权限与安全/database/00-数据库设计冻结总册.md` 为准，本文档不重写表结构。

## 五、当前阶段的重要声明（必读）

1. 当前 PC 端与 miniapp 的一切"角色/权限/数据范围"判断均为**前端 mock 实现**，数据来自 `workflow.mock.js`、`student.mock.js`、`roles.config.js` 等 mock 文件，尚未对接真实后端与数据库。
2. **前端隐藏按钮/菜单不等于安全控制**。真实后端接入后，`backend/`（PostgreSQL + FastAPI + SQLAlchemy + Alembic）必须在每一个写接口和敏感读接口上做服务端权限二次校验（角色权限 + 数据范围 + 模块授权三层），不能信任前端传来的 `currentRoleCode`/`dataScope`/`activeContextId`，这些应由后端根据登录会话解析，前端不传或仅作展示用途（见共享底稿第 5 节 API 契约基线：`tenant_id` 由后端从登录上下文解析）。
3. 文档中标注"（待后端确认）"的内容，表示底稿中未给出明确定义，需后端设计阶段补充，**本轮文档不得编造**。
