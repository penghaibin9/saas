"""MySQL 脚本公共入口：强制 DB_ENABLED=true，并把 MySQL 连接参数落到进程环境。

用法：任何 MySQL 脚本第一行 `import _mysql_env`。
参数来源优先级（从高到低）：
  1) 进程已有的环境变量 / backend/.env（DB_DRIVER=mysql + DB_HOST/PORT/NAME/USER/PASSWORD 或 DATABASE_URL）
  2) 本文件的默认值（saas_user@127.0.0.1:3306/saas_lifecycle）
密码只从环境/.env 读取，绝不写死在仓库里。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 读取 backend/.env（若存在），让脚本与 uvicorn 用同一套配置
try:  # pragma: no cover
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    # 无 python-dotenv 也不阻塞：pydantic-settings 起服务时仍会读 .env；
    # 这里手动兜底解析一次 .env 的 DB_* 键，保证脚本单独运行也能拿到参数。
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# 强制走 MySQL（除非调用方/环境已显式给了 DATABASE_URL）
os.environ["DB_ENABLED"] = "true"
if not os.environ.get("DATABASE_URL"):
    os.environ.setdefault("DB_DRIVER", "mysql")
    os.environ.setdefault("DB_HOST", "127.0.0.1")
    os.environ.setdefault("DB_PORT", "3306")
    os.environ.setdefault("DB_NAME", "saas_lifecycle")
    os.environ.setdefault("DB_USER", "saas_user")
    # 注意：DB_PASSWORD 不设默认值——缺失时脚本会明确提示用户去 .env 填。

# 让 app.core.config 重新读取（清缓存）
try:
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
except Exception:
    pass


def describe() -> str:
    drv = os.environ.get("DB_DRIVER", "mysql")
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "saas_lifecycle")
    user = os.environ.get("DB_USER", "saas_user")
    has_pwd = "是" if (os.environ.get("DB_PASSWORD") or os.environ.get("DATABASE_URL")) else "否(未设置)"
    return f"driver={drv} host={host} port={port} db={name} user={user} 密码已提供={has_pwd}"


def password_missing() -> bool:
    return not (os.environ.get("DB_PASSWORD") or os.environ.get("DATABASE_URL"))
