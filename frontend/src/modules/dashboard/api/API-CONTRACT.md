# Dashboard API 契约文档

> P4 冻结版本 · 不涉及 SQL / 数据库实现 · 后端按本文档返回 JSON 即可

## 1. Dashboard API 总览

| # | Method | Path | Mock 函数 |
|---|--------|------|-----------|
| 1 | GET | `/api/dashboard/overview` | `fetchDashboardOverview()` |
| 2 | GET | `/api/dashboard/risks` | `fetchDashboardRisks(params)` |
| 3 | POST | `/api/dashboard/risks/:riskId/remind` | `remindRisk(riskId, payload)` |
| 4 | POST | `/api/dashboard/risks/:riskId/follow-up` | `followUpRisk(riskId, payload)` |
| 5 | POST | `/api/dashboard/risks/:riskId/resolve` | `resolveRisk(riskId, payload)` |
| 6 | POST | `/api/dashboard/tasks/:taskId/complete` | `completeDashboardTask(taskId, payload)` |
| 7 | GET | `/api/dashboard/operation-logs` | `fetchOperationLogs(params)` |

代码常量见 `dashboard.contract.js` 中的 `DASHBOARD_API_PATHS`。

## 2. 统一响应格式

### 成功

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 失败

```json
{
  "code": "DASHBOARD_RISK_NOT_FOUND",
  "message": "风险记录不存在",
  "data": null
}
```

### 错误码

| code | 说明 |
|------|------|
| `DASHBOARD_RISK_NOT_FOUND` | 风险记录不存在 |
| `DASHBOARD_TASK_NOT_FOUND` | 待办任务不存在 |
| `DASHBOARD_STUDENT_NOT_FOUND` | 学生不存在 |
| `DASHBOARD_INVALID_STATUS` | 状态不允许当前操作 |
| `DASHBOARD_PERMISSION_DENIED` | 无操作权限 |
| `DASHBOARD_VALIDATION_ERROR` | 请求参数校验失败 |
| `DASHBOARD_SERVER_ERROR` | 服务端异常 |

## 3. 接口详情

### 3.1 获取首页总览

- **Method:** `GET`
- **Path:** `/api/dashboard/overview`
- **Params:** `teacherId`（query，可选，默认当前登录教师）

**Response `data`（经 adapter 转换后的领域字段）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `teacher` | object | 当前教师信息 |
| `students` | array | 学生列表 |
| `risks` | array | 风险事件 |
| `tasks` | array | 教师待办 |
| `operationLogs` | array | 处理记录 |
| `lifecycleStages` | array | 生命周期阶段卡片 |
| `lifecycleBannerStages` | array | Banner 时间轴 |
| `overviewMetrics` | array | 实践教学指标 |
| `gdMetrics` | array | 毕业设计指标 |
| `internshipMetrics` | array | 岗位实习指标 |
| `dataQuality` | object | 数据口径说明 |
| `today` | string | 数据基准日 `YYYY-MM-DD` |

> **当前 mock 说明：** `fetchDashboardOverview` 返回 `data/dashboard.mock.js` 的原始 bundle（含 `todos`、`workbench`、`overview` 等），由 `adapter/normalizeDashboardData` 转换为上表字段。接真实后端时，可返回已归一化结构，或在 adapter 中增加映射分支。

**Error Codes:** `DASHBOARD_SERVER_ERROR`

---

### 3.2 获取风险列表

- **Method:** `GET`
- **Path:** `/api/dashboard/risks`
- **Params:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | `pending` / `processing` / `resolved` / `ignored` |
| `riskLevel` | string | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` |
| `studentId` | string | 按学生筛选 |
| `module` | string | 按业务模块筛选 |

**Response `data`:**

```json
{
  "risks": [],
  "total": 0
}
```

---

### 3.3 发起提醒

- **Method:** `POST`
- **Path:** `/api/dashboard/risks/:riskId/remind`

**Request Body:**

```json
{
  "channel": "sms",
  "message": "请尽快补交周报",
  "operatorId": "t-002"
}
```

**Response `data`:**

```json
{
  "risk": {},
  "operationLog": {}
}
```

**Error Codes:** `DASHBOARD_RISK_NOT_FOUND`, `DASHBOARD_INVALID_STATUS`, `DASHBOARD_VALIDATION_ERROR`

---

### 3.4 添加跟进

- **Method:** `POST`
- **Path:** `/api/dashboard/risks/:riskId/follow-up`

**Request Body:**

```json
{
  "content": "已电话联系学生，承诺今日补交",
  "nextAction": "明日复查",
  "operatorId": "t-002"
}
```

**Response `data`:**

```json
{
  "risk": {},
  "operationLog": {}
}
```

**Error Codes:** `DASHBOARD_RISK_NOT_FOUND`, `DASHBOARD_INVALID_STATUS`, `DASHBOARD_VALIDATION_ERROR`

---

### 3.5 处理完成风险

- **Method:** `POST`
- **Path:** `/api/dashboard/risks/:riskId/resolve`

**Request Body:**

```json
{
  "result": "已跟进",
  "remark": "学生已补交材料",
  "operatorId": "t-002"
}
```

**Response `data`:**

```json
{
  "risk": {},
  "updatedTasks": [],
  "operationLog": {}
}
```

**Error Codes:** `DASHBOARD_RISK_NOT_FOUND`, `DASHBOARD_INVALID_STATUS`, `DASHBOARD_VALIDATION_ERROR`

---

### 3.6 完成待办

- **Method:** `POST`
- **Path:** `/api/dashboard/tasks/:taskId/complete`

**Request Body:**

```json
{
  "result": "已跟进",
  "remark": "",
  "operatorId": "t-002"
}
```

**Response `data`:**

```json
{
  "task": {},
  "operationLog": {}
}
```

**Error Codes:** `DASHBOARD_TASK_NOT_FOUND`, `DASHBOARD_INVALID_STATUS`, `DASHBOARD_VALIDATION_ERROR`

---

### 3.7 获取处理记录

- **Method:** `GET`
- **Path:** `/api/dashboard/operation-logs`
- **Params:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `studentId` | string | 按学生筛选 |
| `riskId` | string | 按风险筛选 |
| `taskId` | string | 按待办筛选 |
| `limit` | number | 返回条数上限 |

**Response `data`:**

```json
{
  "logs": [],
  "total": 0
}
```

## 4. 状态流转说明

### 风险（risk）

```
pending → processing → resolved
                ↘ ignored（预留，当前前端未启用 ignoreRisk action）
```

| 操作 | 状态变化 |
|------|----------|
| `remind` | `pending` → `processing` |
| `follow-up` | `pending` → `processing` |
| `resolve` | `*` → `resolved`（`resolved` / `ignored` 不可再操作） |

### 待办（task）

```
todo / doing → done
```

| 操作 | 说明 |
|------|------|
| `complete` | 单独完成待办，**不自动** resolve 关联风险 |
| `resolve`（风险） | 同步将关联处理类待办标记为 `done` |

## 5. 前端接后端替换步骤

```
store
  ↓ 调用 provider 中性函数名
provider/dashboard.provider.js
  ↓ 将 import 从 dashboard.api.mock.js 改为真实 http client
api/dashboard.api.real.example.js（参考实现）
  ↓ HTTP
后端服务
```

1. **provider** — 把 `import ... from '../api/dashboard.api.mock.js'` 换成真实 API 模块；保持 `fetchDashboardRaw`、`remindRisk`、`followUpRisk`、`resolveRisk`、`completeTask` 等对外函数名不变。
2. **adapter** — 若后端字段名与契约不一致，在 `normalizeDashboardData` 及子函数中统一转换；页面和组件不得直接依赖后端原始字段。
3. **store / page / component** — **不应重写**；仅当新增接口字段需要展示时，按 `types → adapter → store getter` 顺序扩展。

## 6. 数据库说明

本文档**不涉及 SQL**。后端按接口契约组装 JSON 响应即可；表结构由后端团队自行设计，只要满足 `data` 字段语义与状态流转规则。

## 7. 相关文件

| 文件 | 职责 |
|------|------|
| `dashboard.contract.js` | 路径、错误码、响应信封、JSDoc 类型 |
| `dashboard.api.mock.js` | 当前运行的 mock API 实现 |
| `dashboard.api.real.example.js` | 真实 HTTP 示例（不启用） |
| `provider/dashboard.provider.js` | store 唯一数据入口 |
| `adapter/dashboard.adapter.js` | 字段映射与聚合 |
| `data/dashboard.mock.js` | mock 原始数据源 |
