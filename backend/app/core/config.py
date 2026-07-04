"""
应用配置（pydantic-settings）
────────────────────────────────────────────────────────────
从 .env 读取，全部有安全默认值，缺 .env 也能起。

数据库仅做「预留」：DATABASE_URL 读进来但默认不连库、不建表、不迁移。
是否真正启用数据库由 DB_ENABLED 控制（默认 False）。
对齐冻结文档：docs/api/00-API契约冻结总册、docs/database/00-数据库设计冻结总册、
deploy/08-环境变量说明（APP_ENV / APP_PORT=8000 / DATABASE_URL / JWT_SECRET / REDIS_URL）。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = "高校学生全生命周期管理平台 · 后端"
    APP_ENV: str = "dev"                 # dev / test / prod
    APP_PORT: int = 8000                 # 与 deploy/05、08 预留端口一致
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    TIMEZONE_OFFSET_HOURS: int = 8       # 响应 timestamp 用 +08:00（固定偏移，跨平台无需 tz 库）

    # ── 认证（当前为 mock，仅用于签发演示令牌）──
    JWT_SECRET: str = "school-lifecycle-dev-secret-change-me-please-32"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_IN: int = 7200           # 秒

    # ── 多租户（对齐 DB 冻结册：单库/单 schema + tenant_id 行级隔离）──
    TENANCY_MODE: str = "single"         # single(私有化单校) / multi(SaaS 多校)
    DEFAULT_TENANT_CODE: str = "demo"

    # ── 平台运营控制面（跨租户，独立令牌，与学校角色边界隔离）──
    PLATFORM_ADMIN_TOKEN: str = ""       # 未配置则平台端接口默认关闭

    # ── 数据库 ──
    DB_ENABLED: bool = False             # 关闭时走 mock；开启后按 effective_database_url 连库
    DATABASE_URL: str = ""               # 显式连接串（最高优先级）：sqlite/mysql/postgresql 均可；留空则按 DB_DRIVER 组装
    REDIS_URL: str = ""                  # 预留（缓存）
    FILE_STORAGE_ENDPOINT: str = ""      # 预留（MinIO/对象存储）

    # ── 数据库分项配置（DATABASE_URL 留空时按此组装；部署演示用 MySQL）──
    DB_DRIVER: str = "sqlite"            # sqlite（本地 dev，默认，保留不删）/ mysql（部署演示）/ postgresql
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "saas_lifecycle"
    DB_USER: str = "saas_user"
    DB_PASSWORD: str = ""               # 禁止写进仓库 / AI执行状态；仅经 .env / 环境变量注入
    DB_SQLITE_PATH: str = "./data/dev.db"  # DB_DRIVER=sqlite 时的库文件（保留 SQLite dev 模式）
    DB_POOL_SIZE: int = 10              # MySQL / PG 连接池大小
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600         # 秒；规避 MySQL wait_timeout 断连

    # ── CORS（逗号分隔白名单；留空开发放开）──
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5188"

    # ── 任务 BACKEND-OVERNIGHT 追加（与旧键并存，旧键继续生效）──
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"   # pytest / 本地无 PG 时用
    JWT_SECRET_KEY: str = ""            # 优先级高于 JWT_SECRET；生产必须改
    JWT_ALGORITHM: str = ""             # 优先级高于 JWT_ALG
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    UPLOAD_DIR: str = "./uploads"       # 文件上传占位目录（不真正落对象存储）
    AUDIT_ENABLED: bool = True          # 审计开关（DB_ENABLED=False 时写内存列表）

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET_KEY or self.JWT_SECRET

    @property
    def jwt_algorithm(self) -> str:
        return self.JWT_ALGORITHM or self.JWT_ALG

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.CORS_ORIGINS.strip():
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def effective_database_url(self) -> str:
        """实际连接串。优先级：显式 DATABASE_URL > 按 DB_DRIVER 组装。
        - mysql   → mysql+pymysql://user:pwd@host:port/db?charset=utf8mb4
        - sqlite  → sqlite+pysqlite:///<DB_SQLITE_PATH>（保留本地 dev 模式）
        - postgresql → postgresql+psycopg://user:pwd@host:port/db
        密码经 URL 编码，不落仓库。"""
        if self.DATABASE_URL.strip():
            return self.DATABASE_URL.strip()
        drv = (self.DB_DRIVER or "sqlite").strip().lower()
        if drv in ("mysql", "mariadb"):
            from urllib.parse import quote_plus
            pwd = quote_plus(self.DB_PASSWORD or "")
            user = quote_plus(self.DB_USER or "root")
            return (f"mysql+pymysql://{user}:{pwd}@{self.DB_HOST}:{self.DB_PORT}"
                    f"/{self.DB_NAME}?charset=utf8mb4")
        if drv in ("postgresql", "postgres", "pg"):
            from urllib.parse import quote_plus
            pwd = quote_plus(self.DB_PASSWORD or "")
            user = quote_plus(self.DB_USER or "postgres")
            return (f"postgresql+psycopg://{user}:{pwd}@{self.DB_HOST}:{self.DB_PORT}"
                    f"/{self.DB_NAME}")
        # sqlite（默认）
        return f"sqlite+pysqlite:///{self.DB_SQLITE_PATH}"

    @property
    def db_dialect(self) -> str:
        """由 effective_database_url 推断方言：mysql / sqlite / postgresql。"""
        url = self.effective_database_url
        head = url.split(":", 1)[0].lower() if url else ""
        if head.startswith("mysql") or head.startswith("mariadb"):
            return "mysql"
        if head.startswith("postgresql") or head.startswith("postgres"):
            return "postgresql"
        return "sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
