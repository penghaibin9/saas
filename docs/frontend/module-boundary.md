# P5 模块边界冻结（前端）

> 本文档冻结模块边界与数据调用约束，不新增运行代码。

## 1) Dashboard 模块边界（已冻结）

Dashboard 已完成 P4.1 契约收口。P5 阶段禁止修改以下目录：

```text
frontend/src/modules/dashboard/api/
frontend/src/modules/dashboard/provider/
frontend/src/modules/dashboard/store/
frontend/src/modules/dashboard/adapter/
```

P5 仅允许在文档中引用其能力（指标、风险、待办、下钻关系），不改实现。

## 2) Graduation 模块边界（规划）

未来建议模块目录（P5 不创建）：

```text
frontend/src/modules/graduation/
```

未来 provider 能力（规划）：

```text
fetchMyGraduation
fetchTopics
submitTopicChoice
fetchSubmissions
submitAchievement
reviewAchievement
reviewTopic
confirmTopic
```

## 3) Internship 模块边界（规划）

未来建议模块目录（P5 不创建）：

```text
frontend/src/modules/internship/
```

未来 provider 能力（规划）：

```text
fetchMyInternship
fetchMyReports
submitReport
reviewReport
fetchCheckins
submitCheckin
```

## 4) SaaS Platform 模块边界（规划）

未来建议模块目录（P5 不创建）：

```text
frontend/src/modules/platform/
```

边界定义：

- Platform 模块是 SaaS 厂商后台模块，不属于学校 PC 管理端。
- 负责租户、套餐、模块授权、菜单模板、权限模板、订单、到期、审计等能力。
- 后续开发必须独立于 `/admin/*` 学校端。

未来 provider 能力（规划）：

```text
fetchTenants
fetchTenantDetail
fetchPackages
fetchModules
fetchLicenses
updateTenantLicense
fetchPermissionTemplates
fetchMenuTemplates
fetchSubscriptions
fetchOrders
fetchAuditLogs
```

## 5) Layout 边界冻结

| 路径域 | Layout | 状态 | 说明 |
| --- | --- | --- | --- |
| `/` | BasePortalLayout（现状） | active / frozen | 当前 Dashboard 首页（不改） |
| `/dev/components` | BasePortalLayout（现状） | active / frozen | 组件预览页（不改） |
| `/student/*` | StudentPortalLayout | planned | 学生门户 P6 启用 |
| `/admin/*` | BasePortalLayout | planned | 管理端业务页 P6 启用 |
| `/enterprise/*` | EnterprisePortalLayout | postponed | 企业门户后置 |
| `/dashboard` | BasePortalLayout（独立域预留） | planned | 当前不启用，首页仍在 `/` |
| `/platform/*` | PlatformLayout | planned | SaaS 厂商平台后台，后续启用 |

## 6) 授权上下文边界（规划）

统一上下文命名（P5 只冻结）：

```text
authzContext
licenseContext
moduleAccessContext
```

边界规则：

1. 页面不得直接判断套餐字符串。
2. 页面不得直接写死模块开关。
3. 页面通过统一授权上下文判断：
   - 模块是否可见
   - 功能是否可用
   - 按钮是否可点击
   - 页面是否只读
4. 授权上下文在 P7/P8 阶段实现，P5 只冻结边界。

## 7) mock/provider 边界冻结

P5 只写原则，不写代码：

1. 业务页面不得直接 import mock。
2. 业务页面不得直接拼 API path。
3. 页面只调用 provider。
4. provider 对齐 contract。
5. mock 数据集中管理。
6. 当前工程已有 Dashboard mock 数据源，后续模块沿用该分层模式。
7. Graduation / Internship 的 mock/provider 运行代码在 P6/P7 再建立，P5 不提前创建。

## 8) 模块单卖候选（商业化草案）

| 模块 | 是否适合单卖 | 最小交付页面 | 依赖 |
| --- | --- | --- | --- |
| 岗位实习中心 | 是 | 我的实习、周报提交、周报批阅、实习打卡 | 学生主档、权限基础 |
| 毕业设计中心 | 是 | 我的毕业设计、材料提交、材料批阅、选题管理 | 学生主档、权限基础 |
| 数字迎新中心 | 是 | 迎新办理、资料审核、报到进度 | 学生主档 |
| 数据驾驶舱中心 | 适合增值 | 指标总览、风险下钻、报表入口 | 业务模块数据 |
| 学生 PC 门户 | 不建议单独卖 | 首页、待办、消息、材料 | 至少一个业务模块 |
| 教师移动工作台 | 适合增值 | 待办、批阅、学生查看 | 实习/毕设模块 |
| 权限与流程中心 | 不直接单卖 | 权限模板、流程配置 | 平台基础能力 |

## 9) P5 纠偏声明

- P5 是文档冻结，不是页面开发。
- P6-1 首批仅建议 3 页面闭环，不是 9+1 一次性开发。
- `/dashboard` 当前为 planned，不是当前真实路由。
- P4.1 已通过 commit 冻结，不以 tag 作为前置条件。
- P5 不以“补测试脚本”为阻塞条件。
