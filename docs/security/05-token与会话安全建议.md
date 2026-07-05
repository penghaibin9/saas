# 05 · token 与会话安全建议（SECURITY-P0）

## 一、现状（本次检查结论）

- 当前登录态为**纯内存 mock**（`security/auth/auth.context.js`），token 未写入 localStorage / sessionStorage。✔
- localStorage 仅存放 `themePreference`（主题偏好，非敏感）。✔
- 会话策略常量已定义（PC 30 分钟无操作超时 / 并发 3 / 首登改密预留）。✔
- 请求封装 `secure-request.client.js` 已带 Authorization 预留 + CSRF 头 + X-Request-Id + X-Trace-Id。

## 二、风险声明（mock 阶段）

mock 阶段无真实 token，无实际泄露面；风险在于**接真实后端时的实现选择**。禁止届时图省事把 token 落 localStorage。

## 三、生产环境要求（P11+ 接真实认证时）

1. 首选 HttpOnly + Secure + SameSite=Lax/Strict Cookie 承载会话，JS 不可读，配合 CSRF Token（封装已预留）。
2. 若必须前端持有 accessToken：仅存内存；有效期 ≤30 分钟；refresh token 走 HttpOnly Cookie 静默续期。
3. 禁止 token / refreshToken 入 localStorage、sessionStorage、IndexedDB。
4. 401/419 与登出必须清空内存态（`clearAuthContext` 已提供）并跳安全错误页。
5. 会话并发、强制下线、首登改密由后端会话服务实现，前端仅消费。

对应 TODO 已写入 `auth.context.js` 头注释。
