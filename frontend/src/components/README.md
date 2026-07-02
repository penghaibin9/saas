# 前端组件规范（Dashboard / UI）

## 命名规则

| 层级 | 前缀 | 示例 |
|------|------|------|
| 基础 UI | `App` | AppCard、AppButton、AppBadge、AppIcon、AppDrawer |
| Dashboard 业务 | 业务名 | MetricCard、RiskAlertCard、TaskCard、LifecycleTimeline |

## Props / Emit

1. 组件只接收 props，通过 emit 向上通知。
2. 禁止 import mock / provider。
3. 禁止直接修改 store 或父级状态。
4. 颜色、圆角、阴影使用 `tokens.css` 变量。

## 表现层映射

- 数据转换与聚合：`modules/dashboard/adapter`
- UI 配色、状态文案、accent：`components/dashboard/presentation.js`
- adapter **不得** 承担颜色/样式映射。

## 图标

- 导航与通用图标统一使用 `AppIcon`（内置 SVG map）。
- 禁止在导航使用 Unicode 占位符。

## 新页面复用

```vue
import { AppCard, AppButton, AppBadge, AppIcon } from '@/components/ui'
import { MetricCard, RiskAlertCard } from '@/components/dashboard'
```

## Dashboard 数据

- 页面使用 `useDashboardStore`，不直接读 mock。
- 状态流转经 store actions。
