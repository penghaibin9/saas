"""dev 脚本公共入口：默认指向 backend/dev.db 的 SQLite，并强制 DB_ENABLED=true。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DEV_DB_PATH = DATA_DIR / "dev.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{DEV_DB_PATH.as_posix()}")
os.environ["DB_ENABLED"] = "true"
