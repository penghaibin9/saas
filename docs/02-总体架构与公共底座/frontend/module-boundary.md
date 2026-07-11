# P5 模块边界冻结（前端）— 正式版

> 本文档冻结前端模块目录、数据流与授权边界，**不修改** `frontend/src`。
> **上位文档**：`docs/01-产品需求与范围/commercialization/00-商业化SaaS总控作战手册V1.0.md`、`docs/08-历史记录与归档/source-design/00-职校学生全生命周期SaaS平台开发冻结总册 V3.0-增强版.md`

## 1) 模块优先级（商业化冻结）

| 顺序 | moduleCode | 目录 | 主攻阶段 | 说明 |
| --- | --- | --- | --- | --- |
| 基础 | `DASHBOARD` | `modules/dashboard/` | 已 frozen | 当前 `/`，P4.1 契约已冻结 |
| **第一主攻** | `INTERNSHIP` | `modules/internship/` | **P6-1** | 岗位实习中心 |
| **第二主攻** | `GD` | `modules/graduation/` | **P6-3** | 毕业设计中心 |
| 厂商后台 | `PLATFORM` | `modules/platform/` | **P6-2** | SaaS 运营后台 |
| 暂缓 | `enterprise` | `modules/enterprise/` | postponed | 企业导师 |

## 2) 标准模块内结构（冻结）

```
modules/<name>/
├── api/           # 契约 + mock 实现（唯一 mock 入口）
├── provider/      # 页面唯一数据门面
├── store/         # 可选，经 provider 取数
├── types/         # 领域类型
└── components/    # 模块内 UI（可选）
```

### 数据流铁律

```
页面/组件 → provider → api（mock|real） → 后端
```

| 禁止项 | 说明 |
| --- | --- |
| 页面直引 `data/mock` | 必须经 provider |
| 页面拼 API path | path 封装在 `api/` |
| store 直调 mock | store 只调 provider |
| 跨模块直 import 业务 store | 经共享 context 或事件 |

## 3) 授权上下文边界（冻结）

| 上下文 | 路径（规划） | 职责 | 阶段 |
| --- | --- | --- | --- |
| `licenseContext` | `src/contexts/licenseContext.js` | 租户模块授权、到期、套餐档位、`useModule`/`useFeature`/`useQuota` | **P6-2** mock |
| `permissionContext` | `src/contexts/permissionContext.js` | 角色、功能点、数据范围 | P6-2 占位，P8 实装 |

**统一口径**：权限、菜单、模块开关后续统一通过 **`licenseContext` + `permissionContext`**（不用分散的 `authzContext` / `moduleAccessContext` 命名）。

### 授权效果（对齐商业化）

| 状态 | 菜单 | 页面 | Dashboard |
| --- | --- | --- | --- |
| 未购买 | 隐藏 | 不可达 | 该模块指标/风险/待办不渲染 |
| 已购正常 | 显示 | 读写 | 正常聚合 |
| 已购到期 | 显示 | 只读 | 可展示历史，写入口禁用 |

## 4) 路由域与模块映射

| 路由域 | 模块 | 数据可见性 |
| --- | --- | --- |
| `/` | DASHBOARD | 本校汇总；**按 license 过滤各模块指标** |
| `/student/*` | INTERNSHIP、GD 等 | 当前学生本人数据 |
| `/admin/*` | INTERNSHIP、GD 等 | 本校师生业务数据 |
| `/platform/*` | PLATFORM | **仅租户/套餐/授权/审计元数据；禁止学生业务明细** |
| `/enterprise/*` | enterprise | postponed |

### `/platform` 红线

- 可展示：租户名、套餐、模块开关、到期日、用量统计、审计日志。
- **禁止**：学生姓名列表、周报正文、毕设材料、成绩明细等业务数据。
- 与 `/admin` 的 provider、store、菜单完全隔离。

## 5) 各模块边界摘要

### DASHBOARD（frozen）

- 已落地：`modules/dashboard/`（P4.1）。
- 真实路由：`/`。
- P6-2 起：metrics/risks/todos provider 增加 `moduleCode` 过滤参数，消费 `licenseContext`。

### INTERNSHIP（P6-1）

- 页面：3 页闭环（见 `page-map.md`）。
- provider 负责：实习状态、周报 CRUD、批阅状态机。
- 不依赖 GD 模块；可被 Dashboard 聚合引用。

### GD（P6-3）

- 复制 INTERNSHIP 范式：学生提交 + 教师批阅 + 状态回写。
- 与 INTERNSHIP 菜单并列，互不硬依赖。

### PLATFORM（P6-2）

- 首批 2 页壳：`/platform/tenants`、`/platform/tenants/:id/licenses`。
- `licenseContext` mock 数据源；开关变更影响学校端菜单与 Dashboard 过滤。
- Layout：`PlatformLayout`（与 BasePortalLayout 分离）。

### enterprise（postponed）

- 路由域 `/enterprise/*` 暂不启用。
- 目录可预留，P9 前不写业务代码。

## 6) P6 阶段边界（不写代码，仅冻结）

| 阶段 | 范围 | 禁止 |
| --- | --- | --- |
| **P6-1** | 3 页：实习主态、周报提交、周报批阅 | 不铺毕设、不做 platform 全量 |
| **P6-2** | licenseContext mock、动态菜单、platform 2 页壳 | 不做真实后端、不铺 GD 页 |
| **P6-3** | GD 4 页 + 实习扩展 | 不做 enterprise |

## 7) 与 source-design 关系

- 业务字段、状态机、审批流以 `docs/08-历史记录与归档/source-design/` 为准。
- 商业化售卖、套餐、授权以 `docs/01-产品需求与范围/commercialization/` 为准。
- 冲突时：**commercialization > source-design > 本文档**。

## 8) 冻结声明

- P5 仅更新本文档及 `page-map` / `route-freeze` / `menu-freeze`。
- **未修改** `frontend/src` 运行代码。
- **未新增**真实路由。
