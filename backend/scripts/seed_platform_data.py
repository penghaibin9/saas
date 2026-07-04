"""P6 · 在既有 dev.db 上追加平台总控种子（幂等；不触碰 demo=5 / main=100 学生基线）。
先确保缺失表已建（create_all 只建缺失表，不动既有表）。"""
from __future__ import annotations

import _dev_env  # noqa: F401

from _seed_platform import seed_platform
from app.db.base import metadata
from app.db.session import get_engine, get_sessionmaker, reset_state

reset_state()
metadata.create_all(bind=get_engine())
db = get_sessionmaker()()
try:
    out = seed_platform(db)
finally:
    db.close()
print(f"[seed-platform] {out}")
