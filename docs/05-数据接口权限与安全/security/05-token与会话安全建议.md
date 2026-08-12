# 05 · token 与会话安全真值（SECURITY-P0）

> 更新：2026-08-12。本文记录当前生产实现，不再描述早期 mock 阶段。

## 一、浏览器端当前真值

管理 PC、SaaS 平台运营 PC 与学生 PC 门户统一采用：

- **accessToken：仅驻留 JavaScript 内存**，页面脚本不写入 `localStorage`、`sessionStorage` 或 IndexedDB。
- **refreshToken：仅由后端通过 HttpOnly Cookie 持有**，浏览器 JavaScript 无法读取。
- 三个 PC 表面使用**互相独立**的 refresh Cookie：学校教师/管理 PC=`gx_staff_refresh_v1`、SaaS 平台运营 PC=`gx_platform_refresh_v1`、学生 PC=`gx_student_refresh_v1`；禁止重新合并成一个共享 Cookie。
- Cookie 使用 `SameSite=Strict`；生产环境同时设置 `Secure`，路径限制在 `/api/v1/auth`。历史共享 Cookie `gx_refresh_v1` 在新会话写入/清理时主动删除。
- F5 / 新页面内存 accessToken 丢失后，私有路由通过 `/api/v1/auth/browser-refresh` 静默恢复；客户端必须用 `X-Browser-Session: staff|platform|student` 指定当前入口，后端只读取该入口对应的 HttpOnly Cookie，再执行角色、权限和强制改密守卫；无有效 Cookie 才回登录页。
- 浏览器登录、刷新、身份切换、登出分别走 `browser-login` / `browser-refresh` / `browser-switch-role` / `browser-logout`，refreshToken 不进入 JSON 响应。
- 浏览器登录根据新签发 accessToken 的 `clientType/userType` 选择 Cookie 通道；刷新后若令牌身份与请求通道不一致，旧 refresh 已消费、新 refresh 也必须作废并拒绝会话切换。
- 登出只清理当前 PC 入口 Cookie，同时吊销已验证的 refresh 会话并尽可能拉黑仍有效的 access JTI；即使 accessToken 已过期，Cookie 会话也必须能够被清除。
- 历史版本遗留的 Web Storage token key 会在客户端初始化时主动清除。

后端原 `/auth/login`、`/auth/refresh` 等 JSON token 接口仍保留给微信小程序等**非浏览器客户端**；不能因为 Web 安全模型升级而把 HttpOnly Cookie 强行套到微信运行时。

## 二、边界与威胁模型

1. HttpOnly 主要降低 XSS 直接窃取长期 refreshToken 的风险；它**不能替代 XSS 防护本身**，CSP、输出编码、依赖治理仍必须保持。同源页面发生 XSS 时，恶意脚本仍可能以当前浏览器身份调用同源接口，因此平台运营端长期更适合独立域名/独立前端部署以进一步缩小爆炸半径。
2. accessToken 仍会被当前页面 JavaScript 使用 Bearer 方式发送，因此 XSS 发生时仍可能在当前会话内滥用权限；其风险窗口受 accessToken 短时有效期和后端授权门禁约束。
3. refresh Cookie 使用 `SameSite=Strict`，浏览器端敏感写接口仍必须继续遵守 Origin/同源、CORS 和业务权限规则；若未来放宽 SameSite 或引入跨站登录，必须同步引入并验证显式 CSRF token 合同。
4. 登出、本人改密、管理员重置、角色回收继续以后端 refresh 吊销 / access JTI / permissionVersion 等服务端真值为准，前端清理状态不能被当作安全边界。
5. production 不允许 mock-login 作为认证兜底；浏览器 refresh 失败必须回登录，不能回退演示身份。
6. 三 Cookie 隔离解决的是**同一浏览器多 PC 表面之间的会话覆盖/误刷新**；它不是浏览器同源安全隔离的替代品。平台控制面若与学校业务面长期共域，仍应按独立域名/独立构建的架构债继续治理。

## 三、禁止回退的门禁

以下行为视为 SECURITY-P0 回归：

- 将浏览器 accessToken / refreshToken 重新写入 `localStorage`、`sessionStorage` 或 IndexedDB；
- 在浏览器 JSON 登录/刷新响应中重新暴露 refreshToken；
- F5 后为了“保持登录”而恢复持久化 JS token；
- 将 staff / platform / student 三个 refresh 会话重新合并为一个共享 Cookie，或刷新时允许跨通道获得另一入口身份；
- 生产环境取消 HttpOnly / Secure（生产）/ SameSite 约束；
- 让管理 PC / 学生 PC 绕过真实 `/auth/*` 后端认证；
- 通过降低 401/403、强制改密、角色/租户权限断言制造前端绿灯。

权威测试由 `backend/tests/test_production_truth_hardening.py`、浏览器客户端测试和 `Main / production security truth` 共同承担；`Main / canonical release gate` 必须直接依赖该安全真值。
