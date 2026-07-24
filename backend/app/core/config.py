"""
应用配置（pydantic-settings）

从 .env / 环境变量读取。正式部署必须显式声明 DEPLOYMENT_MODE=production 与 APP_ENV=production，
不得依赖「未写 production 即当开发」上线。DB_ENABLED 控制是否连接真实数据库（生产强制 true）。
主配置名：APP_ENV、DEPLOYMENT_MODE、JWT_SECRET、JWT_ALG、DATABASE_URL。
兼容旧名：ENV / ENVIRONMENT、JWT_SECRET_KEY、JWT_ALGORITHM（冲突时拒绝启动）。
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_APP_ENV = frozenset({"development", "test", "staging", "production"})
_APP_ENV_ALIASES = {
    "dev": "development", "develop": "development", "local": "development",
    "prod": "production", "production": "production",
    "test": "test", "testing": "test",
    "staging": "staging", "stage": "staging",
}
_ALLOWED_DEPLOYMENT = frozenset({"local", "staging", "production"})


class Settings(BaseSettings):
    # ── 应用 ──
    APP_NAME: str = "高校学生全生命周期管理平台 · 后端"
    APP_ENV: str = "development"         # development / test / staging / production
    ENV: str = ""                        # 兼容旧部署脚本 ENV=production（弃用，冲突拒绝）
    ENVIRONMENT: str = ""                # 兼容 ENVIRONMENT=production（弃用，冲突拒绝）
    # local=本机；staging=预发；production=正式。正式部署必须显式 production。
    DEPLOYMENT_MODE: str = "local"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    TIMEZONE_OFFSET_HOURS: int = 8
    TENANT_TIMEZONE: str = "Asia/Shanghai"  # IANA；API 无偏移时间按此解释
    APP_VERSION: str = "1.0.0"

    # ── 认证（开发可用安全默认 JWT；生产由 assert_* 强制强密钥 + 关 mock-login）──
    JWT_SECRET: str = "school-lifecycle-dev-secret-change-me-please-32"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_IN: int = 7200           # 秒
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # 演示登录（/auth/mock-login）。留空时按 is_prod 推断（production 关、其余开）。
    MOCK_LOGIN_ENABLED: str = ""
    DEMO_TENANT_READONLY: str = ""
    SANDBOX_AUTO_RESET: str = "false"
    INTERNSHIP_OVERDUE_AUTO_SCAN: bool = True
    AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN: bool = True
    AFFAIRS_RISK_TIMEOUT_AUTO_SCAN: bool = True
    AFFAIRS_RISK_NEW_ASSIGN_HOURS: float = 4
    AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS: float = 72
    # 学工 SLA JSON 覆盖；解析失败或字段非法时由 affairs_sla 回退内置默认。
    AFFAIRS_RISK_SLA_JSON: str = ""
    AFFAIRS_LEAVE_SLA_JSON: str = ""
    # 运维探针令牌：/health/ready、/internal/metrics（生产建议必填）
    INTERNAL_OPS_TOKEN: str = ""
    # 对外联系方式；错误提示用配置而非硬编码个人电话
    SUPPORT_CONTACT: str = ""

    # ── 反向代理 ──
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"

    # ── 多租户（对齐 DB 冻结册：单库/单 schema + tenant_id 行级隔离）──
    TENANCY_MODE: str = "single"         # single(私有化单校) / multi(SaaS 多校)
    DEFAULT_TENANT_CODE: str = "demo"

    # ── 微信小程序一键登录（jscode2session）──
    WX_APPID: str = ""                   # 小程序 AppID；未配置则微信登录端点返回"未配置"错误，不影响账号密码登录
    WX_SECRET: str = ""                  # 小程序 AppSecret；仅经 .env/环境变量注入，禁止写进仓库

    # ── 数据库 ──
    DB_ENABLED: bool = False             # False 时部分链路可走内存/演示；生产强制 True
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    MULTI_INSTANCE: bool = False
    WEB_CONCURRENCY: int = 1             # >1 或 MULTI_INSTANCE 时禁止 SCHEDULER_MODE=web
    REDIS_KEY_PREFIX: str = "school-lifecycle"
    REDIS_CONNECT_TIMEOUT: float = 0.3
    REDIS_SOCKET_TIMEOUT: float = 0.5
    AUTH_SUBJECT_CACHE_TTL: int = 30
    HOME_CACHE_TTL: int = 20
    TENANT_API_RATE_LIMIT_PER_SECOND: int = 500
    USER_API_RATE_LIMIT_PER_SECOND: int = 120
    FILE_STORAGE_ENDPOINT: str = ""

    # ── 数据库分项配置（DATABASE_URL 留空时按此组装）──
    # MySQL-only 收口（2026-07-07）：正式开发/测试/部署统一 MySQL(utf8mb4)。
    #   mysql       → 正式（默认）
    #   sqlite      → legacy · 仅历史临时演示（保留不删）
    #   postgresql  → legacy · 仅历史兼容（保留不删）
    DB_DRIVER: str = "mysql"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "student_lifecycle_dev"   # 开发库标准名（utf8mb4 / utf8mb4_unicode_ci）
    DB_USER: str = "saas_user"
    DB_PASSWORD: str = ""               # 禁止写进仓库 / AI执行状态；仅经 .env / 环境变量注入
    DB_SQLITE_PATH: str = "./data/dev.db"  # DB_DRIVER=sqlite 时的库文件（保留 SQLite dev 模式）
    DB_POOL_SIZE: int = 10              # MySQL / PG 连接池大小
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600         # 秒；规避 MySQL wait_timeout 断连
    DB_POOL_TIMEOUT: int = 5            # 秒；池耗尽快速失败，避免请求无限堆积
    DB_CONNECT_TIMEOUT: int = 5         # 秒；数据库网络故障快速失败
    DB_READ_TIMEOUT: int = 30
    DB_WRITE_TIMEOUT: int = 30
    SLOW_QUERY_MS: int = 500              # 仅记录耗时与 SQL 动词，不记录敏感参数
    HTTP_SLOW_REQUEST_MS: int = 1000
    # web=单进程开发内嵌定时；external=独立 scheduler 进程（production 默认应 external）
    SCHEDULER_MODE: str = "web"

    # ── CORS（逗号分隔白名单；留空开发放开）──
    # 5173=管理端 Vite；5188=历史兼容；5199=学生 PC 门户（student-portal）
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:5188,http://localhost:5189,http://localhost:5190,http://localhost:5199,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5188,http://127.0.0.1:5189,http://127.0.0.1:5190,http://127.0.0.1:5199"
    )

    # ── 任务 BACKEND-OVERNIGHT 追加（与旧键并存，旧键继续生效）──
    # MySQL-only 收口：测试库标准 = MySQL student_lifecycle_test（utf8mb4）。
    # 密码经 .env / 环境变量注入，禁止写死；无本机 MySQL 时可临时置 sqlite（legacy 演示，不得当 MySQL 验收）。
    TEST_DATABASE_URL: str = "mysql+pymysql://saas_user:@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4"
    JWT_SECRET_KEY: str = ""            # 优先级高于 JWT_SECRET；生产必须改
    JWT_ALGORITHM: str = ""             # 优先级高于 JWT_ALG
    # 强敏感字段静态加密密钥（家庭经济收入/负债、手机号等 _encrypted 列，Fernet urlsafe-base64
    # 32 字节）。此为开发默认值，生产必须经 .env / 环境变量覆盖为独立密钥且妥善保管——
    # 密钥一旦轮换，此前密文将无法解密（需先用旧密钥读出、用新密钥重新写入）。
    FIELD_ENCRYPTION_KEY: str = "jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # legacy 配置名；正式令牌统一读取 JWT_EXPIRES_IN
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    AUDIT_ENABLED: bool = True
    FILE_ALLOW_ZIP: bool = False
    FILE_ZIP_MAX_ENTRIES: int = 200
    FILE_ZIP_MAX_UNCOMPRESSED_MB: int = 100
    FILE_ZIP_MAX_RATIO: int = 100

    # local / cos；字节存本地或腾讯云 COS（t_file_object.file_key 语义一致）
    FILE_STORAGE_BACKEND: str = "local"
    COS_REGION: str = ""                # 如 ap-guangzhou（COS 桶所在地域）
    COS_BUCKET: str = ""                # 如 student-files-1250000000（含 APPID 后缀）
    COS_SECRET_ID: str = ""             # 腾讯云访问密钥 SecretId；仅经 .env / 环境变量注入，禁止进仓库
    COS_SECRET_KEY: str = ""            # 腾讯云访问密钥 SecretKey；仅经 .env / 环境变量注入，禁止进仓库

    # ── 短信/通知（P13-B；默认关闭，测试环境永不真实发送）──
    SMS_ENABLED: str = "false"          # "true" 才真实发送；否则记录 SKIPPED
    SMS_PROVIDER: str = "mock"          # mock / aliyun / tencent
    SMS_ACCESS_KEY_ID: str = ""         # 真实密钥仅经 .env 注入，禁止进仓库
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = ""             # 短信签名
    SMS_TEMPLATE_TODO: str = ""         # 待办提醒模板ID
    SMS_TEMPLATE_REJECTED: str = ""     # 退回提醒模板ID
    SMS_TEMPLATE_WARNING: str = ""      # 预警提醒模板ID
    SMS_RATE_LIMIT_PER_MINUTE: int = 30 # 每租户每分钟发送上限
    SMS_MAX_RETRY: int = 2              # 发送失败重试次数

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _normalize_app_env(cls, v):
        raw = (str(v or "")).strip().lower() or "development"
        norm = _APP_ENV_ALIASES.get(raw, raw)
        if norm not in _ALLOWED_APP_ENV:
            raise ValueError(f"APP_ENV 非法：{v}；允许 development/test/staging/production")
        return norm

    @field_validator("DEPLOYMENT_MODE", mode="before")
    @classmethod
    def _normalize_deployment(cls, v):
        raw = (str(v or "local")).strip().lower() or "local"
        if raw in ("dev", "development"):
            raw = "local"
        if raw not in _ALLOWED_DEPLOYMENT:
            raise ValueError(f"DEPLOYMENT_MODE 非法：{v}；允许 local/staging/production")
        return raw

    @field_validator("SCHEDULER_MODE", mode="before")
    @classmethod
    def _normalize_scheduler(cls, v):
        raw = (str(v or "web")).strip().lower() or "web"
        if raw not in ("web", "external"):
            raise ValueError(f"SCHEDULER_MODE 非法：{v}；允许 web/external")
        return raw

    @model_validator(mode="after")
    def _reconcile_aliases_and_deployment(self):
        for legacy_name, legacy_val in (("ENV", self.ENV), ("ENVIRONMENT", self.ENVIRONMENT)):
            raw = (legacy_val or "").strip().lower()
            if not raw:
                continue
            norm = _APP_ENV_ALIASES.get(raw, raw)
            if norm not in _ALLOWED_APP_ENV:
                raise ValueError(f"{legacy_name} 非法：{legacy_val}")
            if norm != self.APP_ENV:
                raise ValueError(
                    f"{legacy_name}={legacy_val} 与 APP_ENV={self.APP_ENV} 冲突，请统一后启动")
        # JWT 双名冲突：两键都非空且值不同 → 拒绝
        if (self.JWT_SECRET_KEY or "").strip() and (self.JWT_SECRET or "").strip():
            if self.JWT_SECRET_KEY.strip() != self.JWT_SECRET.strip():
                raise ValueError("JWT_SECRET 与 JWT_SECRET_KEY 同时存在且值冲突")
        if (self.JWT_ALGORITHM or "").strip() and (self.JWT_ALG or "").strip():
            if self.JWT_ALGORITHM.strip() != self.JWT_ALG.strip():
                raise ValueError("JWT_ALG 与 JWT_ALGORITHM 同时存在且值冲突")
        if self.DEPLOYMENT_MODE == "production" and self.APP_ENV != "production":
            raise ValueError("DEPLOYMENT_MODE=production 时必须 APP_ENV=production")
        # production 未显式指定 scheduler 时默认 external（仅当仍为默认 web 且部署正式）
        if self.DEPLOYMENT_MODE == "production" and self.SCHEDULER_MODE == "web":
            object.__setattr__(self, "SCHEDULER_MODE", "external")
        return self

    @property
    def is_prod(self) -> bool:
        if self.DEPLOYMENT_MODE == "production":
            return True
        return self.APP_ENV == "production"

    @property
    def mock_login_enabled(self) -> bool:
        v = (self.MOCK_LOGIN_ENABLED or "").strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
        return not self.is_prod

    @property
    def demo_tenant_readonly(self) -> bool:
        return (self.DEMO_TENANT_READONLY or "").strip().lower() not in ("false", "0", "no", "off")

    @property
    def sandbox_auto_reset(self) -> bool:
        return (self.SANDBOX_AUTO_RESET or "").strip().lower() not in ("false", "0", "no", "off")

    @property
    def field_encryption_key(self) -> str:
        return self.FIELD_ENCRYPTION_KEY

    @property
    def jwt_secret(self) -> str:
        return (self.JWT_SECRET_KEY or self.JWT_SECRET or "").strip()

    @property
    def jwt_algorithm(self) -> str:
        return (self.JWT_ALGORITHM or self.JWT_ALG or "HS256").strip()

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.CORS_ORIGINS.strip():
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def effective_database_url(self) -> str:
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
        return f"sqlite+pysqlite:///{self.DB_SQLITE_PATH}"

    @property
    def db_dialect(self) -> str:
        url = self.effective_database_url
        head = url.split(":", 1)[0].lower() if url else ""
        if head.startswith("mysql") or head.startswith("mariadb"):
            return "mysql"
        if head.startswith("postgresql") or head.startswith("postgres"):
            return "postgresql"
        return "sqlite"

    @property
    def support_contact_display(self) -> str:
        return (self.SUPPORT_CONTACT or "").strip() or "平台运营"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
