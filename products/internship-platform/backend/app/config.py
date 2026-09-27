from __future__ import annotations
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME:str="跃科岗位实习管理平台"
    APP_ENV:str="development"
    API_PREFIX:str="/api/v1"
    SOURCE_BASELINE_SHA:str="adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c"
    DATABASE_URL:str=""
    REDIS_URL:str=""
    TIMEZONE_OFFSET_HOURS:int=8
    TENANT_TIMEZONE:str="Asia/Shanghai"
    model_config=SettingsConfigDict(env_file=".env",env_file_encoding="utf-8",extra="ignore")
    @property
    def is_prod(self): return self.APP_ENV.strip().lower()=="production"

settings=Settings()
