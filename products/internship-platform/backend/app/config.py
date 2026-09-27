from __future__ import annotations
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME:str="跃科岗位实习管理平台"
    APP_ENV:str="development"
    API_PREFIX:str="/api/v1"
    SOURCE_BASELINE_SHA:str="adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c"
    DATABASE_URL:str=""
    REDIS_URL:str=""
    REDIS_KEY_PREFIX:str="internship-standalone"
    REDIS_CONNECT_TIMEOUT:float=0.5
    REDIS_SOCKET_TIMEOUT:float=0.5
    FILE_STORAGE_DIR:str="./data/files"
    FILE_ALLOW_ZIP:bool=False
    FILE_ZIP_MAX_ENTRIES:int=200
    FILE_ZIP_MAX_UNCOMPRESSED_MB:int=100
    FILE_ZIP_MAX_RATIO:int=100
    GUARDIAN_PORTAL_BASE_URL:str=""
    SMS_ENABLED:bool=False
    SMS_PROVIDER:str=""
    SMS_TEMPLATE_GUARDIAN_CONSENT:str=""
    JWT_SECRET:str=""
    JWT_ALG:str="HS256"
    JWT_EXPIRES_IN:int=7200
    REFRESH_TOKEN_EXPIRE_DAYS:int=7
    FIELD_ENCRYPTION_KEY:str=""
    FIELD_ENCRYPTION_KEY_ID:str="1"
    FIELD_ENCRYPTION_PREVIOUS_KEYS:str=""
    SENSITIVE_SEARCH_HMAC_KEY:str=""
    TIMEZONE_OFFSET_HOURS:int=8
    TENANT_TIMEZONE:str="Asia/Shanghai"
    CHECKIN_WATERMARK_FONT_PATH:str=""
    model_config=SettingsConfigDict(env_file=".env",env_file_encoding="utf-8",extra="ignore")
    @property
    def is_prod(self): return self.APP_ENV.strip().lower()=="production"

    @property
    def field_encryption_key(self): return self.FIELD_ENCRYPTION_KEY

    @property
    def field_encryption_key_id(self): return (self.FIELD_ENCRYPTION_KEY_ID or "1").strip()

    @property
    def field_encryption_previous_keys(self):
        out={}
        for item in (self.FIELD_ENCRYPTION_PREVIOUS_KEYS or "").split(","):
            item=item.strip()
            if not item or ":" not in item: continue
            kid,_,key=item.partition(":")
            if kid.strip() and key.strip(): out[kid.strip()]=key.strip()
        return out

    @property
    def sensitive_search_hmac_key(self):
        return (self.SENSITIVE_SEARCH_HMAC_KEY or "").strip() or self.FIELD_ENCRYPTION_KEY

settings=Settings()
