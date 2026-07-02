# 实习管理平台 · PC 管理端 SPA（Vite + Vue3）

> **定位：渐进式迁移地基 + 模板，不是一次性全量迁移。**
> `web/管理平台.html`（5000+ 行单文件）维护慢、XSS 面大、难审计。本 SPA 提供
> 标准工程化骨架与一个完整的「用户管理」迁移样例，团队按同一模式逐页迁移即可。

## 已具备（可运行）
- **工程化**：Vite + Vue3 + vue-router + Pinia。
- **鉴权闭环**：登录（打后端 `/api/users/login`）→ token 持久化 → 路由守卫 → 401 自动登出。
- **统一 API 客户端**：`src/api/client.js`（自动带 token、解包 `{success,data}`、401 跳登录）。
- **实时通知**：`src/realtime.js` 连后端 SSE（`/api/realtime/stream`），收到通知即弹窗。
- **样例页**：
  - `views/Login.vue` 登录
  - `layouts/AdminLayout.vue` 后台骨架（侧栏/顶栏/SSE 弹窗）
  - `views/Dashboard.vue` 工作台（复用 `/bigscreen/risk-radar` + `/ai/status`）
  - `views/Users.vue` 用户管理（对照单文件同功能的迁移模板）

## 核心收益（迁移的理由）
- **XSS 天然消除**：Vue 模板 `{{ }}` 与属性绑定默认 HTML 转义，不再手写 `esc()`——这是单文件最大的安全债。
- **可维护/可审计**：按页面拆组件，迭代快、改一处不牵全身。
- **构建产物**：`npm run build` 出 `dist/`，可由后端/nginx 同源托管。

## 开发
```bash
cd web/spa
npm install
npm run dev      # http://localhost:5173 （已配 /api 代理到 :3000 后端）
```

## 怎么继续迁移
1. 在 `src/views/` 新建页面组件（参考 `Users.vue`：`onMounted` 调 `api.get(...)` → `v-for` 渲染）。
2. 在 `src/router/index.js` 加路由，`AdminLayout.vue` 的 `nav` 加入口。
3. 表单/弹窗用 Vue 受控组件替代原 `innerHTML` 拼接。
4. 逐页迁移、与单文件并存过渡，迁完再下线 `管理平台.html`。
