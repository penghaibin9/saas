# P5 菜单冻结（前端）— 正式版

> 本文档冻结菜单结构与授权策略，**不修改** `frontend/src` 菜单实现。
> **上位文档**：`docs/commercialization/03-模块开关权限菜单控制模型.md`

## 1) 菜单域划分（冻结）

| 菜单域 | 路由前缀 | 用户 | Layout | 当前状态 |
| --- | --- | --- | --- | --- |
| 学校管理端 | `/`、`/admin/*` | 教师/管理员 | BasePortalLayout | `/` 下 Dashboard 已 active |
| 学生门户 | `/student/*` | 学生 | StudentPortalLayout | planned |
| 厂商后台 | `/platform/*` | 平台管理员 | PlatformLayout | planned（P6-2 首批） |
| 企业端 | `/enterprise/*` | 企业导师 | EnterprisePortalLayout | **postponed** |

**铁律**：`/platform` 菜单与 `/admin` 菜单**不得混排**；厂商后台不出现学生业务明细入口。

## 2) 授权消费模型（冻结）

菜单可见性由两层上下文联合决定：

| 上下文 | 职责 | 启用阶段 |
| --- | --- | --- |
| `licenseContext` | 模块是否购买、是否到期、套餐档位 | P6-2 mock |
| `permissionContext` | 角色/功能点权限 | P6-2 占位，P8 实装 |

### 策略表（对齐商业化总控）

| 场景 | 菜单行为 | 页面行为 |
| --- | --- | --- |
| 未购买模块 | **隐藏**（不灰显） | 路由守卫 → noLicense |
| 已购买未到期 | 正常显示 | 正常读写 |
| 已购买已到期 | **仍显示** | **只读**，写操作禁用 |
| 高级功能未购 | 隐藏或升级提示 | 按 `authEffect` 字段 |

## 3) 学校管理端菜单（BasePortalLayout）

### 3.1 当前 active

| menuKey | label | routePath | moduleCode | licenseRequired | status |
| --- | --- | --- | --- | --- | --- |
| `dashboard` | 工作台 | `/` | DASHBOARD | yes | **active** |

> Dashboard 子指标/风险/待办按 `moduleCode` 受 `licenseContext` 过滤（P6-2 起）。

### 3.2 planned — P6-1（INTERNSHIP 第一主攻）

| menuKey | label | routePath | moduleCode | permissionKey | phase | authEffect |
| --- | --- | --- | --- | --- | --- | --- |
| `internship` | 岗位实习 | `/student/internship` | INTERNSHIP | `student:internship:view` | P6-1 | 未购：隐藏 |
| `internship-reports` | 周报提交 | `/student/internship/reports` | INTERNSHIP | `student:internship:report:submit` | P6-1 | 到期：只读 |
| `internship-report-review` | 周报批阅 | `/admin/internship/report-review` | INTERNSHIP | `admin:internship:report:review` | P6-1 | 到期：只读 |

> 学生端菜单挂 StudentPortalLayout；教师批阅挂学校管理端菜单。

### 3.3 planned — P6-3（GD 第二主攻）

| menuKey | label | routePath | moduleCode | phase | authEffect |
| --- | --- | --- | --- | --- | --- |
| `graduation` | 毕业设计 | `/student/graduation` | GD | P6-3 | 未购：隐藏 |
| `graduation-submissions` | 材料提交 | `/student/graduation/submissions` | GD | P6-3 | 到期：只读 |
| `graduation-review` | 材料批阅 | `/admin/graduation/review` | GD | P6-3 | 到期：只读 |

### 3.4 postponed

| menuKey | label | routePath | moduleCode | status |
| --- | --- | --- | --- | --- |
| `enterprise` | 企业导师 | `/enterprise` | enterprise | **postponed** |
| `graduation-grades` | 成绩汇总 | `/admin/graduation/grades` | GD | postponed |

## 4) 厂商后台菜单（PlatformLayout）— `/platform`

### 4.1 P6-2 首批（2 项）

| menuKey | label | routePath | moduleCode | phase |
| --- | --- | --- | --- | --- |
| `platform-tenants` | 学校租户 | `/platform/tenants` | PLATFORM | **P6-2** |
| `platform-licenses` | 模块授权 | `/platform/tenants/:id/licenses` | PLATFORM | **P6-2** |

### 4.2 postponed（P2 后台页）

| menuKey | label | routePath | phase |
| --- | --- | --- | --- |
| `platform-home` | 运营首页 | `/platform` | P6-2+ |
| `platform-packages` | 套餐管理 | `/platform/packages` | postponed |
| `platform-modules` | 模块商品 | `/platform/modules` | postponed |
| `platform-permission-templates` | 权限模板 | `/platform/permission-templates` | postponed |
| `platform-menu-templates` | 菜单模板 | `/platform/menu-templates` | postponed |
| `platform-subscriptions` | 试用与到期 | `/platform/subscriptions` | postponed |
| `platform-orders` | 订单与合同 | `/platform/orders` | postponed |
| `platform-audit-logs` | 操作审计 | `/platform/audit-logs` | postponed |

## 5) P6-2 动态菜单过滤（规划冻结）

1. 菜单配置源：静态 JSON + `moduleCode` / `permissionKey` 元数据。
2. 渲染前过滤：`filterMenus(menus, licenseContext, permissionContext)`。
3. 未购买 → 剔除节点；到期 → 保留节点、标记 `readonly`。
4. Dashboard 工作台卡片/风险/待办同源过滤，不单开例外。

## 6) 冻结口径

- 本阶段不写菜单组件代码。
- 权限、菜单、模块开关后续统一通过 **`licenseContext` + `permissionContext`**。
- `/dashboard` 独立域菜单 postponed；当前工作台菜单在 `/`。
