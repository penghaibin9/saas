"""阶段 5固定门禁。

文件名匹配普通 CI 的 tests/test_portal_*.py 受信任集合，确保学工公共版本、退回重交、
真实 Manifest 与强敏感不可枚举验收不会被变更感知选择器漏掉。
"""
from __future__ import annotations

import os
import runpy
from pathlib import Path


def test_phase5_public_material_center_real_mysql(db_mode, monkeypatch):
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    assert database_url, "real MySQL test database is required"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DB_ENABLED", "true")
    script = Path(__file__).with_name("affairs_material_center_mysql_acceptance.py")
    runpy.run_path(str(script), run_name="__main__")
