# =============================================================================
# backend/Dockerfile —— FastAPI 后端 · 本地部署预演镜像
# -----------------------------------------------------------------------------
# 用途：配合 deploy/docker/docker-compose.local.yml 做「本地部署预演」，
#      不是真实生产镜像的最终定稿，只做部署准备（P5），不改 backend/app 任何业务代码。
#
# 技术栈对齐 backend/requirements.txt：FastAPI + SQLAlchemy 2.x + Alembic +
#      Uvicorn + psycopg[binary]（PostgreSQL 驱动）。入口：app/main.py → app.main:app。
#
# 只拷贝运行必需的目录，明确不拷贝（无需 .dockerignore，靠白名单 COPY 天然排除）：
#   - .venv/            本机 Windows 虚拟环境，体积大且平台不符，容器内会重新 pip install
#   - .env               真实环境变量/密钥，绝不应打进镜像，运行时用 docker-compose env_file 注入
#   - data/、uploads/     运行期数据，用 volume 挂载持久化，不打进镜像
#   - _legacy_node_express/  已归档的旧 Node 残留，不参与 FastAPI 运行
#   - tests/、.pytest_cache/、__pycache__/  测试与缓存，运行镜像不需要
# =============================================================================

FROM python:3.12-slim

# curl 仅用于容器 HEALTHCHECK 探活 /health；如不需要健康检查可整段移除
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先只拷贝依赖清单，能让 Docker 层缓存生效（依赖不变时不用重装）
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 按白名单拷贝运行所需代码（不拷 .venv / .env / data / uploads / _legacy_node_express / tests）
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

# 运行期数据目录（挂 volume 持久化，见 docker-compose.local.yml）
RUN mkdir -p /app/data /app/uploads

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_PORT=8000

EXPOSE 8000

# 健康检查：与 app/main.py 的 GET /health 对齐（统一响应结构，恒 200）
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# 生产/预演统一不带 --reload（--reload 仅用于本机开发，见 scripts/dev/start-backend.ps1）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
