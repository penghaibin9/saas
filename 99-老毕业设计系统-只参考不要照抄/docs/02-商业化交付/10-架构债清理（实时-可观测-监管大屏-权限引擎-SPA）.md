# 架构债清理（第五波）：实时 / 可观测 / 监管大屏 / 权限引擎 / SPA

> 针对「对标商业产品」剩余架构债逐项落地。后端四项做完做透并测试；前端单文件给出可运行的 SPA 迁移地基（诚实标注非全量迁移）。
> 测试 49 通过 + 1 跳过 + 0 失败；8 个新接口启动冒烟全部通过。

---

## 一、站内实时推送（SSE）
**债**：待办/通知靠轮询 + 微信，无实时。
**做法**：
- [`utils/sse.js`](../../internship-backend/utils/sse.js)：按 userId 维护连接、心跳保活、`pushToUser`。
- `GET /api/realtime/stream?token=<JWT>`（[`routes/realtimeRoutes.js`](../../internship-backend/routes/realtimeRoutes.js)）：EventSource 不能带 header，故令牌经查询串自校验，不挂标准守卫。
- `notify()` 落库后即时 `pushToUser(userId,'notification',…)`，在线即收。
- 前端：`new EventSource('/api/realtime/stream?token='+token)` 监听 `notification`（SPA 已接，见 `web/spa/src/realtime.js`）。

## 二、可观测（APM）
**债**：出问题事后才知道。
**做法**：
- **Prometheus**：[`utils/metrics.js`](../../internship-backend/utils/metrics.js) 零依赖采集（请求数/耗时直方图/5xx/SSE 连接/进程内存），`GET /metrics`（可用 `METRICS_TOKEN` 保护）。
- **Sentry**：[`utils/sentry.js`](../../internship-backend/utils/sentry.js) 懒加载 `@sentry/node`（配 `SENTRY_DSN` 启用），接入全局错误处理 + 未捕获异常。
- 与既有「结构化日志 + 错误告警群机器人」三件套联动，告警→采集→追溯闭环。

## 三、监管大屏：GIS 分布 + 风险雷达
**债**：报表/BI 偏浅，监管客户竞争力弱。
**做法**：[`models/bigscreenModel.js`](../../internship-backend/models/bigscreenModel.js) + `/api/bigscreen`：
- `GET /bigscreen/gis`：有坐标的实习企业点位 + 在册人数（地图打点）+ 学院汇总。
- `GET /bigscreen/risk-radar`：多维风险计数——打卡异常(30天) / 未处理投诉 / 未投保在册 / 3天未打卡 / 待审换岗终止。
- 分院管理员自动限本院；容错聚合（单维失败不阻断）。
- 前端大屏可直接消费这两个接口渲染地图与雷达图。

## 四、自定义角色 + 数据权限引擎
**债**：固定 5 角色，大机构/监管局权限不够灵活。
**做法**（**增量式，零破坏既有 requireRole**）：
- [`models/permModel.js`](../../internship-backend/models/permModel.js)：`t_perm_role`（含数据范围 all/college/class/self）+ `t_perm_grant`（角色→权限码）+ `t_user_perm_role`（用户→角色）；权限码目录可扩展。
- [`middlewares/perm.js`](../../internship-backend/middlewares/perm.js)：`requirePermission(code)`（role=1 超管放行）供**新接口**细粒度控权；`attachDataScope` 把数据范围解析到 `req.dataScope.filter` 供控制器过滤。
- 管理接口 `/api/perm`：角色 CRUD、授权、分配给用户、查看自身权限/目录。
- 纯逻辑（`hasPermission`/`scopeToFilter`/`widestScope`）已单测。
> 既有 5 角色与 `requireRole` 不动，新引擎叠加使用，平滑演进；大机构可在后台自定义岗位角色与可见范围，无需改代码。

## 五、PC 管理端 SPA（Vite + Vue3）—— 迁移地基
**债**：5000+ 行单文件 `管理平台.html` 迭代慢、XSS 面大、难审计。
**做法**：`web/spa/`（[README](../../web/spa/README.md)）提供**可运行的工程化骨架 + 完整迁移样例**：
- Vite+Vue3+router+Pinia；登录→token→路由守卫→401 登出闭环；统一 axios 客户端；SSE 实时通知；工作台(复用风险雷达)、用户管理样例页。
- **核心收益**：Vue 模板默认 HTML 转义，**存储型 XSS 天然消除**，不再手写 `esc()`。
> **诚实标注**：这是地基 + 模板，**非 120 页全量迁移**。团队按 `Users.vue` 同一模式逐页迁移、与单文件并存过渡，迁完再下线单文件。全量迁移属持续工程，不在一次提交内完成。

---

## 六、部署 / 升级
```bash
cd internship-backend && npm run migrate:up && npm start   # 含 t_perm_* 等新表（幂等）
# 可选：.env 配 SENTRY_DSN / METRICS_TOKEN
cd web/spa && npm install && npm run dev                    # SPA 开发（/api 代理到 :3000）
```
新增可选依赖：`@sentry/node`。全不配也能跑（metrics 零依赖、Sentry/SSE 不依赖外部）。

## 七、测试
- `test/perm.test.js`：权限判定/数据范围/最宽范围/目录。
- 合计 **49 通过 + 1 跳过 + 0 失败**；`/metrics`、`/bigscreen/*`、`/perm/*`、`/realtime/stream` 启动冒烟通过。
