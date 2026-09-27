from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "跃科岗位实习管理平台"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api/v1"
    SOURCE_BASELINE_SHA: str = "adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c"

    DATABASE_URL: str = "mysql+pymysql://internship:internship@127.0.0.1:3306/yueke_internship?charset=utf8mb4"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    JWT_SECRET: str = "standalone-dev-secret-change-before-production"
    MOCK_LOGIN_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def production_guard(self):
        if self.APP_ENV.lower() == "production":
            if self.MOCK_LOGIN_ENABLED:
                raise ValueError("production 禁止启用 mock login")
            if "change-before-production" in self.JWT_SECRET or len(self.JWT_SECRET) < 32:
                raise ValueError("production 必须配置独立强 JWT_SECRET")
            if not self.DATABASE_URL.startswith("mysql+"):
                raise ValueError("production Standalone 仅允许 MySQL")
        return self


settings = Settings()
