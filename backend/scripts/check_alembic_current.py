"""发布验收：仓库 Alembic 必须单头，数据库 current 必须等于该动态 head。

禁止把具体 revision 写死在部署脚本里；仓库新增迁移后本检查无需人工改版本号。
"""
from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

# The systemd units supply PYTHONPATH, but this verifier is also executed
# directly by the release installer from ``backend/``.  Keep both paths
# equivalent so an already-applied migration is checked rather than failing
# before the application package can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import db_enabled, get_engine


def main() -> int:
    if not db_enabled():
        print("alembic_check_failed: DB_ENABLED must be true", file=sys.stderr)
        return 1

    config = Config("alembic.ini")
    expected = set(ScriptDirectory.from_config(config).get_heads())
    if len(expected) != 1:
        print(f"alembic_check_failed: repository has {len(expected)} heads", file=sys.stderr)
        return 1

    try:
        with get_engine().connect() as conn:
            current = set(MigrationContext.configure(conn).get_current_heads())
    except Exception as exc:  # noqa: BLE001 - CLI 统一转成非零退出码
        print(f"alembic_check_failed: database_unreachable:{type(exc).__name__}", file=sys.stderr)
        return 1

    if current != expected:
        print(
            "alembic_check_failed: database current does not match repository head",
            file=sys.stderr,
        )
        return 1

    print(f"alembic_schema_current: head={next(iter(expected))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
