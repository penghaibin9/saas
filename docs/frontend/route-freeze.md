# P5 路由冻结（前端）

> 本文档冻结“未来路由规划”，不修改真实路由代码。

## 1) 当前真实路由（active / frozen）

| path | name | component | title | module | permissionKey | menuVisible | layout | status | phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | `ui-preview` | `src/views/UiPreview.vue` | Dashboard 工作台首页 | dashboard | `dashboard:view` | 是 | BasePortalLayout（现状） | active | frozen |
| `/dev/components` | `component-dev` | `src/views/ComponentDevPreview.vue` | 组件预览 | dev | `dev:components:view` | 否 | BasePortalLayout（现状） | active | frozen |

## 2) 未来路由域（planned）

- `/admin/*`：PC 管理端业务页面（planned）
- `/student/*`：学生 PC 门户（planned）
- `/platform/*`：SaaS 厂商平台运营后台（planned）
- `/enterprise/*`：企业导师门户（planned，后期启用）
- `/dashboard`：未来驾驶舱独立域（planned，当前不启用）

## 2.1) 路由域边界表（商业化补强）

| 路由域 | 当前状态 | 未来用途 | Layout | 启用阶段 | 不能做什么 |
| --- | --- | --- | --- | --- | --- |
| `/` | active/frozen | 当前 Dashboard 工作台首页 | 当前首页布局（BasePortalLayout 现状） | 已启用 | P5 不改 |
| `/dev/components` | active/frozen | P3 组件预览页 | Dev/Layout（现状） | 已启用 | P5 不改 |
| `/student/*` | planned | 学生 PC 门户 | StudentPortalLayout | P6-1 后逐步启用 | 不一次性铺开 |
| `/admin/*` | planned | 学校 PC 管理端 | BasePortalLayout | P6-1 后逐步启用 | 不混入学生页 |
| `/platform/*` | planned | SaaS 厂商平台运营后台 | PlatformLayout | P5.5/P6-2 规划后启用 | 当前不写代码 |
| `/enterprise/*` | postponed | 企业导师门户 | EnterprisePortalLayout | 后期 | 当前不启用 |
| `/dashboard` | planned | 未来独立驾驶舱域 | DashboardLayout | P9 或后期 | 当前 Dashboard 仍在 `/` |

补充说明：

- `/platform/*` 属于 SaaS 厂商后台，不是学校后台。
- `/admin/*` 是学校自己的管理端。
- 两者不能混用。
- 当前阶段不新增真实 router 代码。

## 3) Planned 路由清单（仅规划）

| path | name | component | title | module | permissionKey | menuVisible | layout | status | phase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/student/internship` | `student-internship` | `src/views/student/StudentInternshipPage.vue` | 我的实习 | 06 岗位实习 | `student:internship:view` | 是 | StudentPortalLayout | planned | P6-1 |
| `/student/internship/reports` | `student-internship-reports` | `src/views/student/StudentInternshipReportsPage.vue` | 周报提交 | 06 岗位实习 | `student:internship:report:submit` | 是 | StudentPortalLayout | planned | P6-1 |
| `/admin/internship/report-review` | `admin-internship-report-review` | `src/views/admin/AdminInternshipReportReviewPage.vue` | 周报批阅 | 06 岗位实习 | `admin:internship:report:review` | 是 | BasePortalLayout | planned | P6-1 |
| `/student/internship/checkins` | `student-internship-checkins` | `src/views/student/StudentInternshipCheckinsPage.vue` | 实习打卡 | 06 岗位实习 | `student:internship:checkin` | 是 | StudentPortalLayout | planned | P6-2 |
| `/student/graduation` | `student-graduation` | `src/views/student/StudentGraduationPage.vue` | 我的毕业设计 | 05 毕业设计 | `student:graduation:view` | 是 | StudentPortalLayout | planned | P6-2 |
| `/student/graduation/submissions` | `student-graduation-submissions` | `src/views/student/StudentGraduationSubmissionsPage.vue` | 毕设材料提交 | 05 毕业设计 | `student:graduation:submission` | 是 | StudentPortalLayout | planned | P6-2 |
| `/admin/graduation/review` | `admin-graduation-review` | `src/views/admin/AdminGraduationReviewPage.vue` | 毕设材料批阅 | 05 毕业设计 | `admin:graduation:review` | 是 | BasePortalLayout | planned | P6-2 |
| `/student/graduation/topics` | `student-graduation-topics` | `src/views/student/StudentGraduationTopicsPage.vue` | 学生选题 | 05 毕业设计 | `student:graduation:topic:choose` | 是 | StudentPortalLayout | planned | P6-3 |
| `/admin/graduation/topics` | `admin-graduation-topics` | `src/views/admin/AdminGraduationTopicsPage.vue` | 课题管理 | 05 毕业设计 | `admin:graduation:topic:manage` | 是 | BasePortalLayout | planned | P6-3 |
| `/admin/graduation/grades` | `admin-graduation-grades` | `src/views/admin/AdminGraduationGradesPage.vue` | 成绩汇总 | 05 毕业设计 | `admin:graduation:grade:view` | 是 | BasePortalLayout | planned | P6-3 |
| `/student/internship/apply` | `student-internship-apply` | `src/views/student/StudentInternshipApplyPage.vue` | 实习申请 | 06 岗位实习 | `student:internship:apply` | 是 | StudentPortalLayout | planned | P6-3 |
| `/enterprise` | `enterprise-home` | `src/views/enterprise/EnterpriseHomePage.vue` | 企业工作台 | enterprise | `enterprise:home:view` | 是 | EnterprisePortalLayout | planned | postponed |
| `/dashboard` | `dashboard-home` | `src/views/dashboard/DashboardHomePage.vue` | 驾驶舱独立域 | dashboard | `dashboard:domain:view` | 否 | BasePortalLayout | planned | postponed |
| `/platform` | `platform-home` | `src/views/platform/PlatformHomePage.vue` | 平台运营首页 | platform | `platform:home:view` | 是 | PlatformLayout | planned | postponed |
| `/platform/tenants` | `platform-tenants` | `src/views/platform/PlatformTenantsPage.vue` | 学校租户管理 | platform | `platform:tenants:view` | 是 | PlatformLayout | planned | postponed |
| `/platform/tenants/:id` | `platform-tenant-detail` | `src/views/platform/PlatformTenantDetailPage.vue` | 租户详情 | platform | `platform:tenants:detail` | 否 | PlatformLayout | planned | postponed |
| `/platform/packages` | `platform-packages` | `src/views/platform/PlatformPackagesPage.vue` | 套餐管理 | platform | `platform:packages:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/modules` | `platform-modules` | `src/views/platform/PlatformModulesPage.vue` | 模块商品管理 | platform | `platform:modules:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/licenses` | `platform-licenses` | `src/views/platform/PlatformLicensesPage.vue` | 模块授权中心 | platform | `platform:licenses:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/permission-templates` | `platform-permission-templates` | `src/views/platform/PlatformPermissionTemplatesPage.vue` | 权限模板管理 | platform | `platform:permission-template:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/menu-templates` | `platform-menu-templates` | `src/views/platform/PlatformMenuTemplatesPage.vue` | 菜单模板管理 | platform | `platform:menu-template:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/subscriptions` | `platform-subscriptions` | `src/views/platform/PlatformSubscriptionsPage.vue` | 试用与到期管理 | platform | `platform:subscription:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/orders` | `platform-orders` | `src/views/platform/PlatformOrdersPage.vue` | 订单与合同管理 | platform | `platform:orders:manage` | 是 | PlatformLayout | planned | postponed |
| `/platform/audit-logs` | `platform-audit-logs` | `src/views/platform/PlatformAuditLogsPage.vue` | 操作审计日志 | platform | `platform:audit:view` | 是 | PlatformLayout | planned | postponed |

## 4) 命名规则冻结

1. 路由全小写。
2. 学生端统一 `/student/...`。
3. 管理端统一 `/admin/...`。
4. 企业端统一 `/enterprise/...`。
5. 不使用 test/demo 临时业务路由。
6. 动作型词（submit/approve）不单独作为一级路由，仅可出现在业务页面名中。

## 5) 边界声明

- 本文档不代表已实现，仅为 P5 路由冻结合同。
- 本阶段未修改 `frontend/src/router/index.js`。
