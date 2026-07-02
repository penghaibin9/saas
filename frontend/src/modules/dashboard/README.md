# Dashboard 模块

首页 Dashboard 的前端生产级架构层，负责数据获取、转换、状态管理与业务流转。

## 分层职责

```
provider/          → 数据与变更 API 入口（当前 mock，未来 HTTP）
data/              → mock 原始数据实现（仅 provider 引用）
adapter/           → 原始数据 → 领域模型转换与聚合计算
types/             → JSDoc 领域类型定义
store/             → Pinia 状态、getters、actions
```

**页面与组件**只依赖 `store` 和 `types` 输出的结构，**不得**直接 `import` mock 或 provider。

## 状态边界

| 类型 | 存放位置 | 示例 |
|------|----------|------|
| 原始/初始化数据 | `state` | students, risks, tasks, operationLogs, lifecycleStages, overviewMetrics, dataQuality, teacher |
| UI 选中态 | `state` | selectedRiskId, selectedTaskId, drawerVisible |
| 派生口径 | `getters` | dashboardMetrics, riskAlerts, taskGroups, focusStudents, bannerCapsules, taskCompletionRate |

`taskCompletionMetric`、`dashboardMetrics` 由 getters 从 `tasks` / `overviewMetrics` 派生，`resolveRisk` 后自动重算。

## 状态流转

```
initDashboard()
  → provider.fetchDashboardRaw()
  → adapter.normalizeDashboardData()
  → 写入 state

remindStudent:  pending → processing + operationLog + toast
addFollowUp:    pending → processing + operationLog + toast
resolveRisk:    → resolved + 关联待办 done + operationLog + toast
completeTask:   → done + operationLog（不自动 resolveRisk）
```

## 接真实后端

1. 在 `provider/dashboard.provider.js` 中将 mock 调用替换为 HTTP 请求。
2. 在 `adapter/dashboard.adapter.js` 中调整字段映射。
3. 如有新字段，先改 `types/dashboard.types.js`。
4. **不要**修改 `UiPreview.vue` 与 dashboard 展示组件。

## 新增字段规范

1. `types` — 定义字段与关联 ID
2. `data/dashboard.mock.js` — 补充 mock 原始数据
3. `adapter` — 转换与聚合
4. `store` — 如需新 action/getter 再改 store

## 导出

```js
import { useDashboardStore } from '@/modules/dashboard'
```
