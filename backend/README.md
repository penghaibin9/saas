# backend/ · 高校学生全生命周期管理平台 后端

## 技术栈（唯一主线）

**FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + Uvicorn + Pytest**（Python 3.12）。
生产与正式验收为 **MySQL-only**（utf8mb4）。

## 快速启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# 开发：复制 .env.example，按需设 DB_ENABLED / DATABASE_URL
uvicorn app.main:app --reload --port 8000
```

验收：
- http://localhost:8000/health
- 非生产：http://localhost:8000/docs

## 环境与部署模式

| 配置 | 说明 |
|---|---|
| `APP_ENV` | `development` / `test` / `staging` / `production`（非法值拒绝启动） |
| `DEPLOYMENT_MODE` | `local` / `staging` / `production`；`production` 时强制 `APP_ENV=production` |
| `DB_ENABLED` | 生产必须 `true`；开发可关（部分链路走内存演示） |
| `SCHEDULER_MODE` | `web`（单进程开发）/ `external`（独立 scheduler；生产默认） |
| `INTERNAL_OPS_TOKEN` | 保护 `/health/ready`、`/internal/metrics` |

主配置名：`JWT_SECRET`、`JWT_ALG`、`DATABASE_URL`。兼容旧名：`JWT_SECRET_KEY`、`JWT_ALGORITHM`、`ENV`/`ENVIRONMENT`（冲突拒绝启动）。

## 测试

```bash
.venv\Scripts\python.exe -m pytest tests/test_p1_*.py -q
```

全量 MySQL 测试请在 CI 或专用测试库执行，勿用 SQLite 冒充验收。

## 版本

与 `app.core.config.Settings.APP_VERSION` 对齐（当前 `1.0.0`）。
