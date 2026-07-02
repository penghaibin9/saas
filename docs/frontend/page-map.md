# P5 页面清单冻结（前端）

> 阶段定位：P5 仅做页面清单冻结，不开发页面，不新增真实路由代码。

## 字段补充（商业化补强）

在原有字段基础上，补充以下控制字段：

- `saleMode`：`suite` / `standalone` / `addon` / `internal`
- `licenseRequired`：是否需要授权（`yes`/`no`）
- `moduleCode`：模块编码占位（如 `internship`、`graduation`、`platform`）
- `packageTier`：`free` / `basic` / `standard` / `professional` / `flagship` / `standalone`
- `authEffect`：未授权时页面表现（隐藏 / 不可访问 / 只读 / 升级提示）

## 当前真实页面（active / frozen）

| module | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | dashboardRelation | saleMode | licenseRequired | moduleCode | packageTier | authEffect | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dashboard | Dashboard 工作台首页 | `/` | active | PC管理端 | admin/teacher | BasePortalLayout（现状） | frozen | `modules/dashboard/provider` | 是 | suite | yes | dashboard | basic+ | 未授权模块数据隐藏 | 当前主链路页面，P5 不改代码 |
| dev | 组件预览页 | `/dev/components` | active | PC管理端 | admin/dev | BasePortalLayout（现状） | frozen | 本地组件与样式 | 否 | internal | no | dev | free | 始终可访问 | P3 冻结成果，P5 不改代码 |

## 未来 planned 页面（仅规划，不开发）

| module | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | dashboardRelation | saleMode | licenseRequired | moduleCode | packageTier | authEffect | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 06 岗位实习 | 我的实习 | `/student/internship` | planned | 学生PC | student | StudentPortalLayout | P6-1 | `modules/internship/provider#getMyInternship` | 是 | standalone | yes | internship | standalone/standard+ | 未授权隐藏菜单与页面 | 展示实习主状态卡、今日任务、退回提醒 |
| 06 岗位实习 | 周报提交 | `/student/internship/reports` | planned | 学生PC | student | StudentPortalLayout | P6-1 | `modules/internship/provider#getMyReports/submitReport` | 是 | standalone | yes | internship | standalone/standard+ | 到期只读、写操作禁用 | 学生提交周报，查看通过/退回 |
| 06 岗位实习 | 周报批阅 | `/admin/internship/report-review` | planned | PC管理端 | admin/teacher | BasePortalLayout | P6-1 | `modules/internship/provider#reviewReport` | 是 | standalone | yes | internship | standalone/standard+ | 到期只读、审批按钮禁用 | 教师批阅、通过、退回 |
| 06 岗位实习 | 实习打卡 | `/student/internship/checkins` | planned | 学生PC | student | StudentPortalLayout | P6-2 | `modules/internship/provider#getCheckins/submitCheckin` | 是 | addon | yes | internship | professional+ | 未购模块不显示入口 | 实习打卡记录 |
| 05 毕业设计 | 我的毕业设计 | `/student/graduation` | planned | 学生PC | student | StudentPortalLayout | P6-2 | `modules/graduation/provider#getMyGraduation` | 是 | standalone | yes | graduation | standalone/standard+ | 未授权隐藏菜单与页面 | 展示毕设主状态 |
| 05 毕业设计 | 毕设材料提交 | `/student/graduation/submissions` | planned | 学生PC | student | StudentPortalLayout | P6-2 | `modules/graduation/provider#getSubmissions/submitAchievement` | 是 | standalone | yes | graduation | standalone/standard+ | 到期只读，提交按钮禁用 | 学生提交阶段材料 |
| 05 毕业设计 | 毕设材料批阅 | `/admin/graduation/review` | planned | PC管理端 | admin/teacher | BasePortalLayout | P6-2 | `modules/graduation/provider#reviewAchievement` | 是 | standalone | yes | graduation | standalone/standard+ | 到期只读，批阅按钮禁用 | 教师批阅材料 |
| 05 毕业设计 | 学生选题 | `/student/graduation/topics` | planned | 学生PC | student | StudentPortalLayout | P6-3 | `modules/graduation/provider#fetchTopics/submitTopicChoice` | 是 | addon | yes | graduation | professional+ | 未授权不显示 | 学生选题流程 |
| 05 毕业设计 | 课题管理 | `/admin/graduation/topics` | planned | PC管理端 | admin/teacher | BasePortalLayout | P6-3 | `modules/graduation/provider#reviewTopic/confirmTopic` | 是 | addon | yes | graduation | professional+ | 高级功能置灰+升级提示 | 教师课题管理 |
| 05 毕业设计 | 成绩汇总 | `/admin/graduation/grades` | planned | PC管理端 | admin | BasePortalLayout | P6-3 | `modules/graduation/provider#getGrades` | 否 | addon | yes | graduation | professional+ | 高级功能置灰+升级提示 | 成绩汇总与归档 |
| 06 岗位实习 | 实习申请 | `/student/internship/apply` | planned | 学生PC | student | StudentPortalLayout | P6-3 | `modules/internship/provider#submitApply` | 否 | addon | yes | internship | professional+ | 高级功能置灰+升级提示 | 学生实习申请 |
| enterprise | 企业导师门户 | `/enterprise` | planned | 企业端 | enterpriseMentor | EnterprisePortalLayout | postponed | `modules/enterprise/provider` | 否 | addon | yes | enterprise | flagship | 未授权不开放入口 | 企业端后期启用 |

## SaaS 平台后台候选页面（commercial planned）

| module | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | dashboardRelation | saleMode | licenseRequired | moduleCode | packageTier | authEffect | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SaaS Platform | 平台运营首页 | `/platform` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchTenants+fetchSubscriptions` | 否 | internal | yes | platform | internal | 未授权不可访问 | 查看租户、收入、试用、到期、模块开通情况 |
| SaaS Platform | 学校租户管理 | `/platform/tenants` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchTenants` | 否 | internal | yes | platform | internal | 未授权不可访问 | 管理学校客户 |
| SaaS Platform | 租户详情 | `/platform/tenants/:id` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchTenantDetail` | 否 | internal | yes | platform | internal | 未授权不可访问 | 查看学校套餐、模块、账号、用量 |
| SaaS Platform | 套餐管理 | `/platform/packages` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchPackages` | 否 | internal | yes | platform | internal | 未授权不可访问 | 配置基础版、标准版、专业版等 |
| SaaS Platform | 模块商品管理 | `/platform/modules` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchModules` | 否 | internal | yes | platform | internal | 未授权不可访问 | 定义哪些模块可单卖 |
| SaaS Platform | 模块授权中心 | `/platform/licenses` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchLicenses+updateTenantLicense` | 否 | internal | yes | platform | internal | 未授权不可访问 | 给学校开通/关闭模块 |
| SaaS Platform | 权限模板管理 | `/platform/permission-templates` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchPermissionTemplates` | 否 | internal | yes | platform | internal | 未授权不可访问 | 配置角色权限模板 |
| SaaS Platform | 菜单模板管理 | `/platform/menu-templates` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchMenuTemplates` | 否 | internal | yes | platform | internal | 未授权不可访问 | 控制学校端菜单显示 |
| SaaS Platform | 试用与到期管理 | `/platform/subscriptions` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchSubscriptions` | 否 | internal | yes | platform | internal | 未授权不可访问 | 控制试用、续费、到期只读 |
| SaaS Platform | 订单与合同管理 | `/platform/orders` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchOrders` | 否 | internal | yes | platform | internal | 未授权不可访问 | 管理订单、合同、续费 |
| SaaS Platform | 操作审计日志 | `/platform/audit-logs` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider#fetchAuditLogs` | 否 | internal | yes | platform | internal | 未授权不可访问 | 记录平台级操作 |

## P5 口径修正

- P5 是文档冻结，不是页面开发。
- “9+1 页面”仅作为候选清单，不是 P6 一次性范围。
- P6-1 首批开发建议仅 3 个页面：`/student/internship`、`/student/internship/reports`、`/admin/internship/report-review`。
- `/dashboard` 目前不是真实路由，当前 Dashboard 首页仍在 `/`。
