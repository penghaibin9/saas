# P1 工程化：统一异常 / Service 层 / 契约校验 / API 版本化 / OpenAPI

> SaaS V1 蓝图 P1 落地（招投标"代码质量+接口规范"必备）。增量式，不破坏现有 55 控制器与前端。
> 测试 60 全过；/api/v1、旧 /api 过渡、OpenAPI、Swagger UI、zod 校验拦截均启动冒烟通过。

---

## 一、统一异常体系
- [`utils/errors.js`](../../internship-backend/utils/errors.js)：`AppError(code,message,status,data)` + 便捷构造（`AppError.forbidden/notFound/conflict/badState...`）。
- 全局错误中间件（`app.js`）升级：识别 `AppError` → 按其 `status` 出 `{success:false,code,message}`（属预期错误记 warn、不触发 Sentry/告警）；非业务错误仍 500 脱敏。
- controller 改为 `try/catch → next(e)`，不再各自手写状态判断。`platformService` 异常已统一到 `AppError`。

## 二、事务助手
- [`utils/tx.js`](../../internship-backend/utils/tx.js) `withTransaction(fn)`：多租户感知（按当前租户库取连接），自动 begin/commit/rollback/release，供 Service 层编排事务。

## 三、契约校验层（zod）
- 新依赖 `zod`；[`validators/schemas.js`](../../internship-backend/validators/schemas.js) 定义入参契约（login/register/stipend/provision），[`middlewares/validate.js`](../../internship-backend/middlewares/validate.js) `validate(schema, source)` 前置校验、失败抛 `AppError(400)`。
- 已接代表性路由：`users/login`、`users/register`、`stipends`(POST)、`platform/tenants`(POST)。
- 收益：入参在进 controller 前即被强类型校验/强转/剥离未知字段（注册顺带挡 role 注入），错误信息统一。

## 四、Service 层样例
- [`services/stipendService.js`](../../internship-backend/services/stipendService.js)：`complianceInfo()`（报酬≥试用期80%合规域规则，**纯函数可单测**）+ `create()` 编排。
- `stipendController.create` 瘦身为：角色判断 + 调 service + `next(e)`。
- 模式确立：**controller(HTTP适配) → service(业务/事务) → model(SQL) + domain(纯规则)**，其余模块按此渐进迁移（不必一次重排全部）。

## 五、API 版本化
- `/api/v1` 为规范版本；旧 `/api` 并存过渡，响应带 `Deprecation: true` + `Warning` + `Link: </api/v1>; rel="successor-version"`。未来不兼容变更走 `/api/v2`。
- 前端现用 `/api` 继续可用，新对接用 `/api/v1`。平台运营接口 `/api/platform/*` 不变。

## 六、OpenAPI + Swagger UI（招投标交付）
- [`openapi/spec.js`](../../internship-backend/openapi/spec.js)：curated OpenAPI 3.0 契约（认证/用户/报酬/AI/监管大屏/平台运营/系统），字段与 zod 契约一致；含 `bearerAuth`(JWT) 与 `platformAuth`(平台令牌) 安全方案。
- `GET /api/openapi.json` 输出规范；`GET /api/docs` 提供 **Swagger UI**（CDN 加载，零额外依赖，可在线“Try it out”）。
- 全量接口可在 `spec.js` 持续补充。

---

## 验证
```bash
npm run test:unit                 # 60 全过（+stipend-service / 既有 saas-platform 等）
npm start
# 浏览器：http://localhost:3000/api/docs   （Swagger UI）
curl localhost:3000/api/v1/health           # 200
curl -i localhost:3000/api/health | grep -i deprecation   # Deprecation: true
curl -X POST localhost:3000/api/v1/users/login -d '{"username":"x"}' -H 'Content-Type: application/json'
# → 400 VALIDATION  参数校验失败：password: Required
```

## 下一步（蓝图 P2）
配置化流程引擎（实习申请/报告/请假 3 条）、validator 全量铺开 + 前端类型生成。
