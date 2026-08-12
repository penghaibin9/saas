# 05 · token 与会话安全真值（SECURITY-P0）

> 更新：2026-08-12。本文记录当前生产实现，不再描述早期 mock 阶段。

## 一、浏览器端当前真值

管理 PC 与学生 PC 门户统一采用：

- **accessToken：仅驻留 JavaScript 内存**，页面脚本不写入 `localStorage`、`sessionStorage` 或 IndexedDB。
- **refreshToken：仅由后端通过 HttpOnly Cookie 持有**，浏览器 JavaScript 无法读取。
- Cookie 使用 `SameSite=Strict`；生产环境同时设置 `Secure`，路径限制在 `/api/v1/auth`。
- F5 / 新页面内存 accessToken 丢失后，私有路由先通过 `/api/v1/auth/browser-refresh` 静默恢复，再执行角色、权限和强制改密守卫；无有效 Cookie 才跳登录页。
- 浏览器登录、刷新、身份切换、登出分别走 `browser-login` / `browser-refresh` / `browser-switch-role` / `browser-logout`，refreshToken 不进入 JSON 响应。
- 历史版本遗留的 Web Storage token key 会在客户端初始化时主动清除。

后端原 `/auth/login`、`/auth/refresh` 等 JSON token 接口仍保留给微信小程序等**非浏览器客户端**；不能因为 Web 安全模型升级而把 HttpOnly Cookie 强行套到微信运行时。

## 二、边界与威胁模型

1. HttpOnly 主要降低 XSS 直接窃取长期 refreshToken 的风险；它**不能替代 XSS 防护本身**，CSP、输出编码、依赖治理仍必须保持。
2. accessToken 仍会被当前页面 JavaScript 使用 Bearer 方式发送，因此 XSS 发生时仍可能在当前会话内滥用权限；其风险窗口受 accessToken 短时有效期和后端授权门禁约束。
3. refresh Cookie 使用 `SameSite=Strict`，浏览器端敏感写接口仍必须继续遵守 Origin/同源、CORS 和业务权限规则；若未来放宽 SameSite 或引入跨站登录，必须同步引入并验证显式 CSRF token 合同。
4. 登出、本人改密、管理员重置、角色回收继续以后端 refresh 吊销 / access JTI / permissionVersion 等服务端真值为准，前端清理状态不能被当作安全边界。
5. production 不允许 mock-login 作为认证兜底；浏览器 refresh 失败必须回登录，不能回退演示身份。

## 三、禁止回退的门禁

以下行为视为 SECURITY-P0 回归：

- 将浏览器 accessToken / refreshToken 重新写入 `localStorage`、`sessionStorage` 或 IndexedDB；
- 在浏览器 JSON 登录/刷新响应中重新暴露 refreshToken；
- F5 后为了“保持登录”而恢复持久化 JS token；
- 生产环境取消 HttpOnly / Secure（生产）/ SameSite 约束；
- 让管理 PC / 学生 PC 绕过真实 `/auth/*` 后端认证；
- 通过降低 401/403、强制改密、角色/租户权限断言制造前端绿灯。

权威测试由 `backend/tests/test_production_truth_hardening.py`、浏览器客户端测试和 `Main / production security truth` 共同承担；`Main / canonical release gate` 必须直接依赖该安全真值。
