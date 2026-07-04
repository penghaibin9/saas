"""初始化本地 dev.db：按 app.models metadata 建 20 张核心表（幂等）。"""
from __future__ import annotations

import _dev_env  # noqa: F401  （设置 DATABASE_URL / DB_ENABLED）

from app.db.base import metadata
from app.db.session import get_engine, reset_state

reset_state()
engine = get_engine()
metadata.create_all(bind=engine)
print(f"[init] created {len(metadata.tables)} tables -> {engine.url}")
for name in sorted(metadata.tables):
    print("  -", name)
