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
    ENV: str = ""                        # 兼容部分部署脚本使用 ENV=production
    ENVIRONMENT: str = ""                # 兼容 ENVIRONMENT=production
    APP_PORT: int = 8000                 # 与 deploy/05、08 预留端口一致
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    TIMEZONE_OFFSET_HOURS: int = 8       # 响应 timestamp 用 +08:00（固定偏移，跨平台无需 tz 库）

    # ── 认证（当前为 mock，仅用于签发演示令牌）──
    JWT_SECRET: str = "school-lifecycle-dev-secret-change-me-please-32"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_IN: int = 7200           # 秒
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # 演示登录（/auth/mock-login）开关。生产环境默认强制关闭，关闭后端点返回 403，
    # 不再免密签发任意角色令牌。留空/未设时按 is_prod 推断（prod 关、非 prod 开）。
    MOCK_LOGIN_ENABLED: str = ""
    # 正式演示租户只读锁：写操作一律 403（参观者改不动演示数据）。置 false 可临时放开。
    DEMO_TENANT_READONLY: str = ""
    # 体验沙箱自动重置开关；默认关闭，运营平台可随时手动恢复。
    SANDBOX_AUTO_RESET: str = "false"
    # 实习请假逾期扫描：生产环境默认开启；多实例通过数据库幂等规则保证重复扫描安全。
    INTERNSHIP_OVERDUE_AUTO_SCAN: bool = True
    # 学工请假逾期扫描（affairs_leave_service.scan_overdue，幂等）：同款启动定时；默认开启。
    AFFAIRS_LEAVE_OVERDUE_AUTO_SCAN: bool = True

    # ── 反向代理 ──
    # 可信代理（逗号分隔，支持单 IP 或 CIDR 网段，如 172.16.0.0/12）。请求直连方 IP 命中时，
    # 才信任 X-Forwarded-For/X-Real-IP 解析真实客户端 IP（登录限流、审计日志按真实 IP 计）；
    # 否则一律用直连 IP，防头部伪造。默认仅本机回环（Nginx 与后端同机直装拓扑）；
    # docker compose 拓扑请设为容器网段（见 deploy/docker/docker-compose.mysql.yml）。
    TRUSTED_PROXY_IPS: str = "127.0.0.1,::1"

    # ── 多租户（对齐 DB 冻结册：单库/单 schema + tenant_id 行级隔离）──
    TENANCY_MODE: str = "single"         # single(私有化单校) / multi(SaaS 多校)
    DEFAULT_TENANT_CODE: str = "demo"

    # ── 微信小程序一键登录（jscode2session）──
    WX_APPID: str = ""                   # 小程序 AppID；未配置则微信登录端点返回"未配置"错误，不影响账号密码登录
    WX_SECRET: str = ""                  # 小程序 AppSecret；仅经 .env/环境变量注入，禁止写进仓库

    # ── 数据库 ──
    DB_ENABLED: bool = False             # 关闭时走 mock；开启后按 effective_database_url 连库
    DATABASE_URL: str = ""               # 显式连接串（最高优先级）：sqlite/mysql/postgresql 均可；留空则按 DB_DRIVER 组装
    REDIS_URL: str = ""                  # 多实例共享鉴权、限流与短时业务缓存；空值时安全降级
    REDIS_KEY_PREFIX: str = "school-lifecycle"
    REDIS_CONNECT_TIMEOUT: float = 0.3
    REDIS_SOCKET_TIMEOUT: float = 0.5
    AUTH_SUBJECT_CACHE_TTL: int = 30      # 账号/租户/角色复核缓存；关键变更会主动失效
    HOME_CACHE_TTL: int = 20              # 学生首页短缓存，写操作后主动失效
    TENANT_API_RATE_LIMIT_PER_SECOND: int = 500  # 单校 API 总量保护；Redis 下多实例共享
    USER_API_RATE_LIMIT_PER_SECOND: int = 120    # 单用户突发保护；正常首页并发不会误伤
    FILE_STORAGE_ENDPOINT: str = ""      # 预留（MinIO/对象存储）

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
    # web=兼容单进程开发；external=生产多 worker，由独立 scheduler 容器执行定时任务。
    SCHEDULER_MODE: str = "web"

    # ── CORS（逗号分隔白名单；留空开发放开）──
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5188"

    # ── 任务 BACKEND-OVERNIGHT 追加（与旧键并存，旧键继续生效）──
    # MySQL-only 收口：测试库标准 = MySQL student_lifecycle_test（utf8mb4）。
    # 密码经 .env / 环境变量注入，禁止写死；无本机 MySQL 时可临时置 sqlite（legacy 演示，不得当 MySQL 验收）。
    TEST_DATABASE_URL: str = "mysql+pymysql://saas_user:@127.0.0.1:3306/student_lifecycle_test?charset=utf8mb4"
    JWT_SECRET_KEY: str = ""            # 优先级高于 JWT_SECRET；生产必须改
    JWT_ALGORITHM: str = ""             # 优先级高于 JWT_ALG
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # legacy 配置名；正式令牌统一读取 JWT_EXPIRES_IN
    UPLOAD_DIR: str = "./uploads"       # 文件落点：local 后端的存储根 / cos 后端的临时·缓存根
    AUDIT_ENABLED: bool = True          # 审计开关（DB_ENABLED=False 时写内存列表）

    # ── 文件存储后端（附件/论文/材料字节存哪）──
    # local（默认）：字节存服务器本地 UPLOAD_DIR，单机部署够用。
    # cos          ：字节存腾讯云对象存储 COS，多机/上云部署用；需下方 COS_* 配置 + cos-python-sdk-v5。
    # 切换只改本项，t_file_object 表零迁移（file_key 语义两后端相同）。
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

    @property
    def is_prod(self) -> bool:
        for val in (self.APP_ENV, self.ENV, self.ENVIRONMENT):
            if (val or "").strip().lower() in ("prod", "production"):
                return True
        return False

    @property
    def mock_login_enabled(self) -> bool:
        """演示登录是否启用。显式配置优先；未配置时生产关、其余环境开。"""
        v = (self.MOCK_LOGIN_ENABLED or "").strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
        return not self.is_prod

    @property
    def demo_tenant_readonly(self) -> bool:
        """正式演示租户是否只读（默认开）。"""
        return (self.DEMO_TENANT_READONLY or "").strip().lower() not in ("false", "0", "no", "off")

    @property
    def sandbox_auto_reset(self) -> bool:
        """沙箱是否启用每晚自动重置（默认关闭；需 DB_ENABLED）。"""
        return (self.SANDBOX_AUTO_RESET or "").strip().lower() not in ("false", "0", "no", "off")

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
