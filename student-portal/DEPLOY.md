# 学生 PC 门户（student-portal）部署说明（/portal/）

面向学校试点服务器，把学生 PC 门户部署到主站的 `/portal/` 子路径，与 PC 管理端（`/`）、
miniapp H5（`/miniapp/`）、后端（`/api/`）并存。**不 hardcode 服务器 IP、不 hardcode localhost。**

## 1. 构建（在开发机 / CI）

```bash
cd student-portal
npm install
# 关键：以 /portal/ 子路径构建；API 走服务器同源，经 Nginx /api/ 反代
#   - VITE_BASE=/portal/            → 静态资源与 history base
#   - VITE_API_BASE_URL 留空        → 同源，请求形如 /api/v1/...（推荐）
#     或填「源」域名（勿带 /api、勿带 /api/v1）：VITE_API_BASE_URL=https://你的学校域名
npm run build
```

产物在 `student-portal/dist/`。把 `dist/` 的内容部署到服务器 `/usr/share/nginx/html/student-portal/`。

> 注意：`VITE_API_BASE_URL` 只填「源」，前缀 `/api/v1` 由代码自动拼接。**切勿**写成
> `https://域名/api` 或 `https://域名/api/v1`（会多拼成 `/api/api/v1`）。

## 2. Nginx（history 刷新不 404）

把 `deploy/nginx/nginx.portal.conf.example` 的 `location /portal/` 块加入主站 `server{}`：

```nginx
location /portal/ {
    alias /usr/share/nginx/html/student-portal/;
    index index.html;
    try_files $uri $uri/ /portal/index.html;   # 刷新 /portal/home 不 404
}
```

后端接口复用主站已有的 `location /api/`（见 `deploy/nginx/nginx.mysql.conf`）。

## 3. 安全与账号

- 生产 `APP_ENV=prod` 时后端强制：`mock-login` 返回 **403**、`DEBUG=false`、`CORS` 非 `*`、`JWT` 非弱值（`assert_*` 启动校验）。门户本身**从不调用** mock-login、无免密。
- 门户仅 `STUDENT` 可进入；同一套后端账号与小程序共用，token key 独立 `sp_token_v1`。
- 演示学生账号（需先入库，见 `backend/scripts/seed_student_portal_demo_accounts.py`）：
  - `student / 123456`（demo-school 租户）
  - `student2 / 123456`（其独立租户，与 demo-school 数据隔离）
  登录页仅**展示并填充**这两个账号，不自动登录、不绕过 `/api/v1/auth/login`。

## 4. 数据库

学生门户配置表 `t_tenant_portal_config` 通过 Alembic 迁移创建：

```bash
cd backend
# 连接串来自 .env（DATABASE_URL 或 DB_DRIVER=mysql + DB_*）
alembic upgrade head
```

## 5. 部署自检

- 打开 `http://<主站>/portal/` → 登录页出现，可用 student/123456 登录。
- 刷新 `http://<主站>/portal/home` → 不 404（history 兜底生效）。
- 关闭某租户门户（平台端「学生PC门户」标签保存 enabled=false）→ 该校学生刷新变「未开通」页。
