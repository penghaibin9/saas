# P5 页面清单冻结（前端）— 正式版

> **阶段定位**：P5 商业化页面清单与路由冻结。不开发页面，不新增真实路由代码。
> **上位文档**：`docs/commercialization/00-商业化SaaS总控作战手册V1.0.md`（冲突时以 commercialization 为准）

## 商业化主线冻结

| 优先级 | moduleCode | 模块 | 说明 |
| --- | --- | --- | --- |
| 第一主攻 | `INTERNSHIP` | 岗位实习中心 | P6-1 首批 3 页闭环 |
| 第二主攻 | `GD` | 毕业设计中心 | P6-3 复制范式 |
| 厂商后台 | `PLATFORM` | SaaS 平台运营后台 | 路由域 `/platform`，P6-2 首批 2 页壳 |
| 基础件 | `DASHBOARD` | 数据驾驶舱（轻量） | 当前首页在 `/`，指标受模块授权过滤 |

## 字段定义（冻结）

| 字段 | 说明 |
| --- | --- |
| `saleMode` | `suite` / `standalone` / `addon` / `internal` |
| `licenseRequired` | `yes` / `no` |
| `moduleCode` | 与总册 §3.2 一致：`INTERNSHIP`、`GD`、`DASHBOARD`、`PLATFORM` 等 |
| `packageTier` | `free` / `basic` / `standard` / `professional` / `flagship` / `standalone` |
| `authEffect` | 未授权：隐藏；到期：只读不隐藏；高级功能：升级提示 |
| `dataSource` | 页面只调 `modules/*/provider`，禁止直引 mock、禁止拼 API path |

## 当前真实页面（active / frozen）

| moduleCode | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | dashboardRelation | saleMode | licenseRequired | packageTier | authEffect | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DASHBOARD | Dashboard 工作台首页 | `/` | active | PC管理端 | admin/teacher | BasePortalLayout（现状） | frozen | `modules/dashboard/provider` | 是 | suite | yes | basic+ | 未授权模块指标/风险/待办不渲染 | **当前真实路由**，P5 不改代码 |
| dev | 组件预览页 | `/dev/components` | active | PC管理端 | admin/dev | BasePortalLayout（现状） | frozen | 本地组件 | 否 | internal | no | free | 始终可访问 | **当前真实路由**，P3 冻结 |

## 未来 planned 页面 — 业务模块

| moduleCode | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | dashboardRelation | saleMode | licenseRequired | packageTier | authEffect | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INTERNSHIP | 我的实习 | `/student/internship` | planned | 学生PC | student | StudentPortalLayout | **P6-1** | `modules/internship/provider` | 是 | standalone | yes | standalone/standard+ | 未购买：菜单隐藏 | **第一主攻** · 实习主状态卡、今日任务、退回提醒 |
| INTERNSHIP | 周报提交 | `/student/internship/reports` | planned | 学生PC | student | StudentPortalLayout | **P6-1** | `modules/internship/provider` | 是 | standalone | yes | standalone/standard+ | 到期：只读、写禁用 | **第一主攻** · 学生提交/查看退回 |
| INTERNSHIP | 周报批阅 | `/admin/internship/report-review` | planned | PC管理端 | admin/teacher | BasePortalLayout | **P6-1** | `modules/internship/provider` | 是 | standalone | yes | standalone/standard+ | 到期：只读、批阅禁用 | **第一主攻** · 教师批阅/退回 |
| INTERNSHIP | 实习打卡 | `/student/internship/checkins` | planned | 学生PC | student | StudentPortalLayout | P6-3 | `modules/internship/provider` | 是 | addon | yes | professional+ | 未购买：菜单隐藏 | 第二批实习扩展 |
| INTERNSHIP | 实习申请 | `/student/internship/apply` | planned | 学生PC | student | StudentPortalLayout | P6-3 | `modules/internship/provider` | 否 | addon | yes | professional+ | 高级功能升级提示 | 五级申请流暂缓细化 |
| GD | 我的毕业设计 | `/student/graduation` | planned | 学生PC | student | StudentPortalLayout | **P6-3** | `modules/graduation/provider` | 是 | standalone | yes | standalone/standard+ | 未购买：菜单隐藏 | **第二主攻** |
| GD | 毕设材料提交 | `/student/graduation/submissions` | planned | 学生PC | student | StudentPortalLayout | **P6-3** | `modules/graduation/provider` | 是 | standalone | yes | standalone/standard+ | 到期：只读 | **第二主攻** |
| GD | 毕设材料批阅 | `/admin/graduation/review` | planned | PC管理端 | admin/teacher | BasePortalLayout | **P6-3** | `modules/graduation/provider` | 是 | standalone | yes | standalone/standard+ | 到期：只读 | **第二主攻** |
| GD | 学生选题 | `/student/graduation/topics` | planned | 学生PC | student | StudentPortalLayout | P6-3 | `modules/graduation/provider` | 是 | addon | yes | professional+ | 未购买：隐藏 | 毕设扩展 |
| GD | 课题管理 | `/admin/graduation/topics` | planned | PC管理端 | admin/teacher | BasePortalLayout | P6-3 | `modules/graduation/provider` | 是 | addon | yes | professional+ | 升级提示 | 毕设扩展 |
| GD | 成绩汇总 | `/admin/graduation/grades` | planned | PC管理端 | admin | BasePortalLayout | postponed | `modules/graduation/provider` | 否 | addon | yes | professional+ | 升级提示 | 依赖评阅链，暂缓 |
| enterprise | 企业导师门户 | `/enterprise` | planned | 企业端 | enterpriseMentor | EnterprisePortalLayout | **postponed** | `modules/enterprise/provider` | 否 | addon | yes | flagship | 未授权：不开放 | P9 后评估 |

## 未来 planned — SaaS 平台后台（`/platform`）

> 厂商后台：管租户、套餐、模块授权、到期、审计。**永不显示学生业务明细**（总册红线）。
> 与 `/admin/*` 学校端严格隔离。

| moduleCode | pageName | routePath | routeStatus | client | roles | layout | phase | dataSource | saleMode | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PLATFORM | 平台运营首页 | `/platform` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | P6-2+ | `modules/platform/provider` | internal | 租户/试用/到期总览 |
| PLATFORM | 学校租户管理 | `/platform/tenants` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | **P6-2** | `modules/platform/provider` | internal | **首批壳 #1** |
| PLATFORM | 模块授权中心 | `/platform/tenants/:id/licenses` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | **P6-2** | `modules/platform/provider` | internal | **首批壳 #2** · 开关翻转影响学校端 licenseContext |
| PLATFORM | 租户详情 | `/platform/tenants/:id` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | P6-2+ | `modules/platform/provider` | internal | 套餐/模块/账号/用量 |
| PLATFORM | 套餐管理 | `/platform/packages` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | P2 后台页 |
| PLATFORM | 模块商品管理 | `/platform/modules` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | 可单卖模块目录 |
| PLATFORM | 权限模板管理 | `/platform/permission-templates` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | P3 冻结结构 |
| PLATFORM | 菜单模板管理 | `/platform/menu-templates` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | 控制学校端菜单 |
| PLATFORM | 试用与到期管理 | `/platform/subscriptions` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | 试用/续费/只读 |
| PLATFORM | 订单与合同管理 | `/platform/orders` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | P2 后台页 |
| PLATFORM | 操作审计日志 | `/platform/audit-logs` | planned | SaaS平台后台 | platformAdmin | PlatformLayout | postponed | `modules/platform/provider` | internal | 开关操作留痕 |

## P6-1 最小闭环（冻结，仅 3 页）

```
学生 /student/internship → 提交周报 /student/internship/reports
    → 教师批阅 /admin/internship/report-review → 退回/通过 → 学生看到结果
```

## P6-2 规划（冻结，不写业务页）

- `licenseContext` mock（`modules/platform/`）
- 动态菜单过滤（`licenseContext` + `permissionContext`）
- `/platform` 首批 2 页壳：租户列表 + 模块授权中心

## 冻结口径

1. 当前**真实路由**仅 `/`、`/dev/components`。
2. `/dashboard` 为 planned 独立域；**当前 Dashboard 仍在 `/`**。
3. `/student/*`、`/admin/*`、`/platform/*` 均为 planned，本阶段不写 router 代码。
4. `/enterprise/*`：**postponed**。
5. “9+1 页面”为候选清单，**不是** P6 一次性开发范围。
6. 未购买模块：**菜单隐藏**；到期：**只读不隐藏**。
7. Dashboard 指标、风险、待办必须按 `moduleCode` 受 `licenseContext` 过滤。
