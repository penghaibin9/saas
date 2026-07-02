# V2：规模化运营（SSE 跨实例 + 计费对账 + 监管局跨校驾驶舱 + 读写分离/分片预留）

> 承接 V1（P0 运营面 / P1 工程化 / P2 配置化流程）。V2 解决「100+ 校规模化」蓝图四项：
> 多实例实时一致、用量计费自动对账、监管局跨校视角、读写分离与分片预留。
> 单元测试 **71 全过**（+SSE 隔离 3 例、计费对账 4 例）；新接口在多租户(2 校)环境冲烟通过。

---

## 一、SSE 跨实例广播（Redis Pub/Sub）
**问题**：PM2 cluster / 多实例下，用户连在 A 实例，事件在 B 实例产生 → 推送丢失（原 SSE 仅推本进程连接）。

**方案**（[`utils/sse.js`](../../internship-backend/utils/sse.js)）：
- **多租户隔离**：连接按 `租户#用户` 复合键登记，杜绝不同学校同号用户串推；[`routes/realtimeRoutes.js`](../../internship-backend/routes/realtimeRoutes.js) 用 JWT 的 `tid` 显式隔离。
- **跨实例广播**：配置 `REDIS_URL` 后，推送经 Redis 频道 `sse:push` 广播，每个实例订阅后推给本地连接；**发布端只发不直推**（由各实例订阅回调统一本地推），保证「单次送达、不重复」。
- **回退**：未配置 Redis / Redis 异常 → 回退单进程本地推送（fail-open，不因缓存故障丢实时、更不拖垮业务）。
- 与限流（`rateLimit.js`）共用 `REDIS_URL`，同款懒加载 + 容错风格。

## 二、计费对账自动化
**问题**：30+ 校用量靠人工核对，超配额无台账，收入口径不清。

**方案**：
- **纯对账函数**（可单测，[`services/billingService.js`](../../internship-backend/services/billingService.js) `reconcileUsage`）：用量 vs 配额 → 各维度利用率% + 超限标记 + 状态（`ok`/`warn` 任一≥90%/`over` 超配额）。
- **全租户用量聚合** `refreshAll`：逐校切库统计在册学生/当月 AI 调用，写回控制面 `t_tenant_usage`（按月）；单校失败不影响其余。
- **对账报告** `report`：用量 vs 配额逐校对账 + 按套餐年费汇总 **ARR/MRR** + 超配额校清单。
- **定时聚合**（[`utils/scheduler.js`](../../internship-backend/utils/scheduler.js) `runBillingAggregate`）：每日一次，分布式锁保证集群只跑一份；single 模式自动跳过。
- **接口**：`GET /api/platform/billing`（对账报告）、`POST /api/platform/billing/refresh`（即时聚合）。
- **控制台**：「💰 计费对账」页——用量进度条 + 套餐年费 + ARR/MRR 汇总 + 正常/临界/超配额徽标。

## 三、监管局版·跨校驾驶舱
**问题**：单校大屏是「校长视角」；教育局/督导要「跨所有学校」的实习规模与风险总账。

**方案**（[`services/supervisionService.js`](../../internship-backend/services/supervisionService.js)）：
- 经 `tenancy.forEachTenant` 逐校切上下文聚合，复用 [`models/bigscreenModel`](../../internship-backend/models/bigscreenModel.js) 风险雷达；单校失败标 `ok=false` 不阻断整体。
- 输出：全局总账（在用学校/实习生总数/在岗/风险合计）+ 跨校风险维度求和 + **风险最高学校榜**（督导约谈优先级）+ 各校明细。
- **接口** `GET /api/platform/supervision`（平台/监管管理员令牌）。
- **控制台**：「🛰️ 跨校监管驾驶舱」页——KPI 卡 + 全局风险总账 + 风险榜。

## 四、读写分离 / 租户分片（抽象 + 预留）
> 真分片需多 MySQL 实例（基础设施）；本期落地**零风险抽象 + 预留钩子**，配置即启用、不配置行为无差。

- **读副本路由**（[`config/tenancy.js`](../../internship-backend/config/tenancy.js)）：配置 `DB_READ_HOST` 后，`getReadPoolForCurrentRequest()` 路由到只读副本；未配置则回主库。
- **只读句柄**（[`config/db.js`](../../internship-backend/config/db.js)）：`require('../config/db').read.query(...)` 即走只读副本。读多写少的监管聚合（`supervisionService`）已接入示范；其余读密集接口可渐进采用，写路径不变。
- **分片预留**：`poolFor(dbName, host)` 接受按租户 `db_host`；控制面 `t_tenant` 增 `db_host` 预留列。租户分片到不同实例时，按 `db_host` 建独立池（db_name 全局唯一，空闲回收逻辑不变）。
- `pool-stats` 增 `readReplica`/`readPools` 字段便于排障。

---

## 验证
```bash
npm run test:unit     # 71 全过（含 SSE 隔离/计费对账新增 7 例）
npm run gen:types     # 前端类型随 OpenAPI 重生成
# 多租户冲烟（2 校）：
#   GET  /api/platform/billing            → ARR/MRR + 逐校对账
#   POST /api/platform/billing/refresh    → 全租户用量聚合
#   GET  /api/platform/supervision        → 跨校实习规模 + 风险总账
#   GET  /api/platform/pool-stats         → readReplica/readPools 状态
# 控制台 /platform → 三视图：租户管理 / 计费对账 / 跨校监管
```

## 部署开关（生产）
| 能力 | 开关 | 不配置时 |
|---|---|---|
| SSE 跨实例广播 | `REDIS_URL` | 单进程本地推送 |
| 限流共享配额 | `REDIS_URL` | 内存计数 |
| 读写分离 | `DB_READ_HOST` | 读走主库 |
| 租户分片 | `t_tenant.db_host` | 同主库 host |
| 用量聚合频率 | 每日（启动 90s 后首次） | — |

## 至此 V1 + V2 蓝图
- **V1**：平台运营面 + 配置化流程引擎 + Service 层/契约/OpenAPI + 连接池治理/全租户迁移。
- **V2**：SSE 跨实例 + 计费对账自动化 + 监管局跨校驾驶舱 + 读写分离/分片预留。
- 后续 V3（生态/智能化）：统一身份服务、企业端独立子站、AI 深度、开放 API、信创全栈认证。
