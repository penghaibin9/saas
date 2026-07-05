"""迁移覆盖检查（P13-E，只读，不改任何迁移）。
比对：ORM 模型注册的表 vs alembic versions 中 create_table 的表。
输出：已覆盖 / 未覆盖（疑似靠 create_all 建）/ 迁移中多余 三类。
用法：cd backend && ../.venv/Scripts/python.exe ../scripts/check/check-migration-coverage.py
      或在 backend 目录：python ../scripts/check/check-migration-coverage.py
"""
from __future__ import annotations

import os
import re
import sys

# 允许从 backend 目录运行
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def model_tables() -> set[str]:
    import app.models  # noqa: F401  触发全部模型注册
    from app.models.base import Base
    return set(Base.metadata.tables.keys())


def migration_tables() -> set[str]:
    vdir = os.path.join(BACKEND, "alembic", "versions")
    tables: set[str] = set()
    if not os.path.isdir(vdir):
        return tables
    pat = re.compile(r"create_table\(\s*['\"]([^'\"]+)['\"]")
    for fn in os.listdir(vdir):
        if fn.endswith(".py"):
            with open(os.path.join(vdir, fn), encoding="utf-8") as f:
                for m in pat.finditer(f.read()):
                    tables.add(m.group(1))
    return tables


def main() -> int:
    models = model_tables()
    migs = migration_tables()
    covered = sorted(models & migs)
    missing = sorted(models - migs)   # 模型有、迁移无 → 疑似靠 create_all
    extra = sorted(migs - models)     # 迁移有、模型无 → 历史/重命名遗留
    print(f"模型表总数: {len(models)}")
    print(f"迁移覆盖表: {len(covered)}")
    print(f"未纳入迁移(疑似 create_all): {len(missing)}")
    for t in missing:
        print(f"  - {t}")
    if extra:
        print(f"迁移中多余(模型已无): {len(extra)}")
        for t in extra:
            print(f"  ? {t}")
    print("\n结论:", "全部已覆盖" if not missing else f"{len(missing)} 张表需纳入下一版迁移")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
