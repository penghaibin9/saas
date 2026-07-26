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
    APP_ENV: str = "development"
    ENV: str = ""
    ENVIRONMENT: str = ""
    DEPLOYMENT_MODE: str = "local"
    APP_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    TIMEZONE_OFFSET_HOURS: int = 8
    TENANT_TIMEZONE: str = "Asia/Shanghai"
    APP_VERSION: str = "1.0.0"
    # 家长门户公网根地址，例如 https://school.example.com；岗位实习监护人确认短信用。
    # 生产未配置时不会伪装成已发送，任务保持待送达并在管理工作台明确提示。
    GUARDIAN_PORTAL_BASE_URL: str = ""

    # ── 认证 ──
    JWT_SECRET: str = "school-lifecycle-dev-secret-change-me-please-32"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_IN: int = 7200
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MOCK_LOGIN_ENABLED: str = ""
    DEMO_TENANT_READONLY: str = ""
    SANDBOX_AUTO_RESET: str = "false"
    INTERNSHIP_OVERDUE_AUTO_SCAN: bool = True
    AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN: bool = True
    AFFAIRS_RISK_TIMEOUT_AUTO_SCAN: bool = True
    AFFAIRS_COUNSELOR_TEMP_AUTO_SCAN: bool = True
    AFFAIRS_RISK_NEW_ASSIGN_HOURS: float = 4
    AFFAIRS_RISK_ASSIGNED_PROCESS_HOURS: float = 72
    AFFAIRS_RISK_SLA_JSON: str = ""
    AFFAIRS_LEAVE_SLA_JSON: str = ""
    INTERNAL_OPS_TOKEN: str = ""
    SUPPORT_CONTACT: str = ""

    # ── 反向代理 ──
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"

    # ── 多租户 ──
    TENANCY_MODE: str = "single"
    DEFAULT_TENANT_CODE: str = "demo"

    # ── 微信小程序一键登录 ──
    WX_APPID: str = ""
    WX_SECRET: str = ""

    # ── 数据库 ──
    DB_ENABLED: bool = False
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    MULTI_INSTANCE: bool = False
    WEB_CONCURRENCY: int = 1
    REDIS_KEY_PREFIX: str = "school-lifecycle"
    REDIS_CONNECT_TIMEOUT: float = 0.3
    REDIS_SOCKET_TIMEOUT: float = 0.5
    AUTH_SUBJECT_CACHE_TTL: int = 30
    HOME_CACHE_TTL: int = 20
    TENANT_API_RATE_LIMIT_PER_SECOND: int = 500
    USER_API_RATE_LIMIT_PER_SECOND: int = 120
    FILE_STORAGE_ENDPOINT: str = ""

    DB_DRIVER: str = "mysql"
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "student_lifecycle_dev"
    DB_USER: str = "saas_user"
    DB_PASSWORD: str = ""
    DB_SQLITE_PATH: str = "./data/dev.db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_TIMEOUT: int = 5
    DB_CONNECT_TIMEOUT: int = 5
    DB_READ_TIMEOUT: int = 30
    DB_WRITE_TIMEOUT: int = 30
    SLOW_QUERY_MS: int = 500
    HTTP_SLOW_REQUEST_MS: int = 1000
    SCHEDULER_MODE: str = "web"

    CORS_ORIGINS: str = (
        "http://localhost:5173,http://localhost:5174,http://localhost:5188,http://localhost:5189,http://localhost:5190,http://localhost:5199,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5188,http://127.0.0.1:5189,http://127.0.0.1:5190,http://127.0.0.1:5199"
    )

    TEST_DATABASE_URL: str = "mysql+pymysql://saas_user:@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4"
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = ""
    FIELD_ENCRYPTION_KEY: str = "jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"
    AUDIT_ENABLED: bool = True
    FILE_ALLOW_ZIP: bool = False
    FILE_ZIP_MAX_ENTRIES: int = 200
    FILE_ZIP_MAX_UNCOMPRESSED_MB: int = 100
    FILE_ZIP_MAX_RATIO: int = 100

    FILE_STORAGE_BACKEND: str = "local"
    COS_REGION: str = ""
    COS_BUCKET: str = ""
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""

    # ── 短信/通知 ──
    SMS_ENABLED: str = "false"
    SMS_PROVIDER: str = "mock"
    SMS_ACCESS_KEY_ID: str = ""
    SMS_ACCESS_KEY_SECRET: str = ""
    SMS_SIGN_NAME: str = ""
    SMS_TEMPLATE_TODO: str = ""
    SMS_TEMPLATE_REJECTED: str = ""
    SMS_TEMPLATE_WARNING: str = ""
    SMS_TEMPLATE_GUARDIAN_CONSENT: str = ""
    SMS_RATE_LIMIT_PER_MINUTE: int = 30
    SMS_MAX_RETRY: int = 2

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
            raise ValueError("SCHEDULER_MODE 仅允许 web/external")
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
            if self.APP_ENV not in ("development", norm):
                raise ValueError(f"APP_ENV 与 {legacy_name} 冲突")
            self.APP_ENV = norm
        if self.DEPLOYMENT_MODE == "production" and self.APP_ENV != "production":
            raise ValueError("DEPLOYMENT_MODE=production 时 APP_ENV 必须为 production")
        if self.APP_ENV == "production" and self.DEPLOYMENT_MODE != "production":
            raise ValueError("APP_ENV=production 时 DEPLOYMENT_MODE 必须为 production")
        return self

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "production" or self.DEPLOYMENT_MODE == "production"

    @property
    def db_enabled(self) -> bool:
        return bool(self.DB_ENABLED)

    @property
    def mock_login_enabled(self) -> bool:
        raw = (self.MOCK_LOGIN_ENABLED or "").strip().lower()
        if raw:
            return raw in ("true", "1", "yes", "on")
        return not self.is_prod

    @property
    def demo_tenant_readonly(self) -> bool:
        raw = (self.DEMO_TENANT_READONLY or "").strip().lower()
        if raw:
            return raw in ("true", "1", "yes", "on")
        return self.is_prod


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
