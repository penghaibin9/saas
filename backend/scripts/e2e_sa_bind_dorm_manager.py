"""Bind E2E dorm manager to E2E building via manager_teacher_key (official dorm scope key)."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import get_sessionmaker  # noqa: E402

TENANT = "sandbox-school"
DORM_CODE = "E2E-DORM-1"
LOGIN = "e2e_dorm_manager"


def main() -> int:
    db = get_sessionmaker()()
    try:
        tid = db.execute(text(
            "SELECT id FROM t_tenant WHERE tenant_code=:c AND is_deleted=0 LIMIT 1"
        ), {"c": TENANT}).scalar()
        u = db.execute(text(
            "SELECT id, login_name, real_name FROM t_user "
            "WHERE tenant_id=:tid AND login_name=:ln AND is_deleted=0 LIMIT 1"
        ), {"tid": tid, "ln": LOGIN}).first()
        if not u:
            print("missing user", LOGIN)
            return 1
        # dorm scope matches userId / loginName(from ctx_) / realName
        key = str(u[1])  # bind by loginName (工号) — dorm scope now also matches loginName
        rows = db.execute(text(
            "UPDATE t_affairs_dorm_building SET manager_teacher_key=:k, version=COALESCE(version,0)+1 "
            "WHERE tenant_id=:tid AND building_code=:code AND is_deleted=0"
        ), {"k": key, "tid": tid, "code": DORM_CODE}).rowcount
        db.commit()
        print("bound", LOGIN, "manager_teacher_key", key, "userId", u[0], "buildings_updated", rows)
        return 0 if rows else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
