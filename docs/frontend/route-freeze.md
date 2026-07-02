# P5 路由冻结（前端）— 正式版

> 本文档冻结未来路由规划，**不修改** `frontend/src/router/index.js`。
> **上位文档**：`docs/commercialization/02-SaaS平台运营后台PC端蓝图.md`、`docs/commercialization/03-模块开关权限菜单控制模型.md`

## 1) 当前真实路由（active / frozen）

| path | name | component | title | moduleCode | permissionKey | layout | status | phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | `ui-preview` | `src/views/UiPreview.vue` | Dashboard 工作台首页 | DASHBOARD | `dashboard:view` | BasePortalLayout（现状） | **active** | frozen |
| `/dev/components` | `component-dev` | `src/views/ComponentDevPreview.vue` | 组件预览 | dev | `dev:components:view` | BasePortalLayout（现状） | **active** | frozen |

**仅此两条为当前真实路由。**

## 2) 路由域边界表（冻结）

| 路由域 | 当前状态 | 未来用途 | 用户 | Layout | 启用阶段 | 禁止事项 |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | active/frozen | Dashboard 工作台首页 | 教师/管理员 | BasePortalLayout（现状） | 已启用 | P5 不改 |
| `/dev/components` | active/frozen | P3 组件预览 | 开发者 | BasePortalLayout（现状） | 已启用 | P5 不改 |
| `/student/*` | **planned** | 学生 PC 门户 | 学生 | StudentPortalLayout | P6-1 起 | 不一次性铺开 |
| `/admin/*` | **planned** | 学校 PC 管理端（本校业务） | 教师/管理员 | BasePortalLayout | P6-1 起 | 不混入 `/platform` |
| `/platform/*` | **planned** | **SaaS 厂商运营后台** | 平台管理员 | PlatformLayout | **P6-2** 首批壳 | 不显示学生业务明细；不与 `/admin` 混用 |
| `/enterprise/*` | **postponed** | 企业导师门户 | 企业导师 | EnterprisePortalLayout | P9 后 | 当前不启用 |
| `/dashboard` | **planned** | 未来独立驾驶舱域 | 校领导 | 待定 | P10 后 | **当前 Dashboard 仍在 `/`** |

### `/platform` vs `/admin`（铁律）

- `/platform/*`：厂商管**学校们**（租户、套餐、授权、到期、审计）。
- `/admin/*`：学校管**学生们**（实习、毕设等业务）。
- 两者路由、Layout、菜单、数据边界**不得混用**。

## 3) Planned 路由清单 — P6-1（第一主攻 INTERNSHIP）

| path | name | component | title | moduleCode | permissionKey | layout | status | phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/student/internship` | `student-internship` | `src/views/student/StudentInternshipPage.vue` | 我的实习 | INTERNSHIP | `student:internship:view` | StudentPortalLayout | planned | **P6-1** |
| `/student/internship/reports` | `student-internship-reports` | `src/views/student/StudentInternshipReportsPage.vue` | 周报提交 | INTERNSHIP | `student:internship:report:submit` | StudentPortalLayout | planned | **P6-1** |
| `/admin/internship/report-review` | `admin-internship-report-review` | `src/views/admin/AdminInternshipReportReviewPage.vue` | 周报批阅 | INTERNSHIP | `admin:internship:report:review` | BasePortalLayout | planned | **P6-1** |

## 4) Planned 路由清单 — P6-2（授权壳 + 平台后台首批）

| path | name | component | title | moduleCode | layout | status | phase | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/platform` | `platform-home` | `src/views/platform/PlatformHomePage.vue` | 平台运营首页 | PLATFORM | PlatformLayout | planned | P6-2+ | 可选，首批可仅 2 子页 |
| `/platform/tenants` | `platform-tenants` | `src/views/platform/PlatformTenantsPage.vue` | 学校租户管理 | PLATFORM | PlatformLayout | planned | **P6-2** | 首批壳 #1 |
| `/platform/tenants/:id/licenses` | `platform-tenant-licenses` | `src/views/platform/PlatformTenantLicensesPage.vue` | 模块授权中心 | PLATFORM | PlatformLayout | planned | **P6-2** | 首批壳 #2 · 读写 licenseContext |

P6-2 同步规划（无新路由或守卫占位）：

- `licenseContext` mock + `useModule` / `useFeature` / `useQuota`
- 动态菜单过滤（消费 `licenseContext` + `permissionContext`）
- 路由守卫占位：未授权模块 → noLicense 页（P8 实装）

## 5) Planned 路由清单 — P6-3（第二主攻 GD + 实习扩展）

| path | name | moduleCode | layout | status | phase |
| --- | --- | --- | --- | --- | --- |
| `/student/graduation` | 我的毕业设计 | GD | StudentPortalLayout | planned | **P6-3** |
| `/student/graduation/submissions` | 毕设材料提交 | GD | StudentPortalLayout | planned | **P6-3** |
| `/admin/graduation/review` | 毕设材料批阅 | GD | BasePortalLayout | planned | **P6-3** |
| `/student/graduation/topics` | 学生选题 | GD | StudentPortalLayout | planned | P6-3 |
| `/admin/graduation/topics` | 课题管理 | GD | BasePortalLayout | planned | P6-3 |
| `/student/internship/checkins` | 实习打卡 | INTERNSHIP | StudentPortalLayout | planned | P6-3 |
| `/student/internship/apply` | 实习申请 | INTERNSHIP | StudentPortalLayout | planned | P6-3 |

## 6) Postponed 路由

| path | moduleCode | status | phase | 说明 |
| --- | --- | --- | --- | --- |
| `/enterprise` | enterprise | planned | **postponed** | 企业导师门户，P9 后 |
| `/dashboard` | DASHBOARD | planned | **postponed** | 独立驾驶舱域；轻量版已由 `/` 承担 |
| `/admin/graduation/grades` | GD | planned | postponed | 成绩汇总依赖链未完成 |
| `/platform/packages` 等其余平台页 | PLATFORM | planned | postponed | 见 `page-map.md` 平台后台表 |

## 7) 命名规则冻结

1. 全小写路径。
2. 学生端 `/student/*`；学校管理端 `/admin/*`；厂商后台 **`/platform/*`**（不用 `/console`）。
3. 企业端 `/enterprise/*`。
4. 禁止 test/demo 业务路由。
5. 动作词（submit/approve）不作为一级路由。

## 8) 边界声明

- 本文档为 P5 冻结合同，不代表已实现。
- 本阶段**未修改**真实 router 代码。
- 页面数据只经 `modules/*/provider`，禁止直引 mock、禁止拼 API path。
