# 学生 PC 门户（student-portal）部署说明（/portal/）

学校试点的 **systemd 正式部署不再单独手工发布 student-portal**。它已经与管理 PC、miniapp H5、后端代码一起进入 `scripts/deploy/install-systemd-release.sh` 的同一 release：三端构建任一失败，整次发布不切换。

## 1. 正式试点推荐方式

先按 `deploy/env/backend.systemd.env.example` 配置 `/etc/school-lifecycle/backend.env`，并把 `deploy/nginx/school-lifecycle.systemd.conf.example` 替换域名/证书后装入 Nginx。

```bash
# 只读预检
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --check

# 预检全过后才执行
sudo ENV_FILE=/etc/school-lifecycle/backend.env \
  bash scripts/deploy/install-systemd-release.sh --apply
```

发布脚本会自动执行：

- `frontend` → 管理 PC；
- `miniapp` → H5 `/miniapp/`；
- `student-portal` → 学生 PC `/portal/`；
- `alembic upgrade head` 后动态核对数据库 current 与仓库唯一 head；
- 原子切换 `/opt/school-lifecycle/current`；
- 原子更新 `/var/www/school-lifecycle/pc|miniapp|portal` 三个静态链接；
- 启动/校验 backend、scheduler、file-scan 三个 systemd 服务；
- 最后跑 `verify-systemd-release.sh`，任何红灯回退应用 symlink（数据库迁移不自动 downgrade）。

`student-portal` 构建时固定：

```text
VITE_BASE=/portal/
VITE_API_BASE_URL=
```

即静态资源走 `/portal/`，API 使用同源 `/api/v1/*`，不 hardcode 服务器 IP。

## 2. Nginx

正式 systemd 模板已经包含：

```nginx
location ^~ /portal/ {
    root /var/www/school-lifecycle;
    try_files $uri $uri/ /portal/index.html;
}
```

因此 `/portal/home` 等 history 子路由刷新不会 404。`/uploads/`、`/exports/` 仍显式 404，附件必须经过后端鉴权与租户/业务关系校验。

## 3. 单独本地构建（仅开发/排障）

```bash
cd student-portal
npm ci
VITE_BASE=/portal/ VITE_API_BASE_URL= npm run build
```

产物为 `student-portal/dist/`。正式服务器不要再手工覆盖旧目录；应交给统一 release 脚本切换，避免管理端、小程序与学生 PC 版本漂移。

## 4. 试点发布后必验

- `/portal/` 打开登录页；
- `/portal/home` 直接刷新不 404；
- 学生账号只能进入 STUDENT 门户；
- 管理 PC、小程序 H5、学生 PC 三端均来自同一个 `/opt/school-lifecycle/current` release；
- `scripts/deploy/verify-systemd-release.sh` 返回 `FAIL=0` 后才允许导入真实学校数据。
