"""Read-only inventory for Academic E2E rows inside ``sandbox-school``.

The 20K reference tenant has an exact topology signature.  Browser fixtures must
not silently change its active college/major/class/student counts, so this script
reports the dedicated ``E2E`` identities and every table that directly stores one
of their stable ids.  It never prints credentials and never mutates the database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import _mysql_env  # noqa: E402,F401
from app.db.session import get_sessionmaker  # noqa: E402
from app.services.sandbox_service import SANDBOX_CODE, SANDBOX_TID  # noqa: E402


E2E_PREFIX = "E2E教务测试"


def _rows(db, sql: str, **params) -> list[dict]:
    return [dict(row) for row in db.execute(text(sql), params).mappings().all()]


def _reference_counts(db, schema: str, column: str, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    candidates = _rows(
        db,
        """
        SELECT c.TABLE_NAME AS tableName
          FROM information_schema.COLUMNS c
          JOIN information_schema.COLUMNS t
            ON t.TABLE_SCHEMA=c.TABLE_SCHEMA
           AND t.TABLE_NAME=c.TABLE_NAME
           AND t.COLUMN_NAME='tenant_id'
         WHERE c.TABLE_SCHEMA=:schema
           AND c.COLUMN_NAME=:column
         ORDER BY c.TABLE_NAME
        """,
        schema=schema,
        column=column,
    )
    placeholders = ",".join(f":id_{index}" for index in range(len(ids)))
    params = {"tenant_id": SANDBOX_TID, **{f"id_{index}": value for index, value in enumerate(ids)}}
    found = []
    for candidate in candidates:
        table = candidate["tableName"]
        count = int(
            db.execute(
                text(
                    f"SELECT COUNT(*) FROM `{table}` "
                    f"WHERE tenant_id=:tenant_id AND `{column}` IN ({placeholders})"
                ),
                params,
            ).scalar()
            or 0
        )
        if count:
            found.append({"table": table, "column": column, "count": count})
    return found


def main() -> int:
    with get_sessionmaker()() as db:
        tenant = _rows(
            db,
            "SELECT id,tenant_code AS tenantCode FROM t_tenant WHERE id=:tenant_id",
            tenant_id=SANDBOX_TID,
        )
        if not tenant or tenant[0]["tenantCode"] != SANDBOX_CODE:
            raise SystemExit("sandbox tenant identity mismatch")
        schema = str(db.execute(text("SELECT DATABASE()")).scalar() or "")

        colleges = _rows(
            db,
            """SELECT id,college_name AS name,code,status,is_deleted AS isDeleted
                 FROM t_college
                WHERE tenant_id=:tenant_id AND college_name LIKE :prefix
                ORDER BY id""",
            tenant_id=SANDBOX_TID,
            prefix=f"{E2E_PREFIX}%",
        )
        majors = _rows(
            db,
            """SELECT id,college_id AS collegeId,major_name AS name,code,status,is_deleted AS isDeleted
                 FROM t_major
                WHERE tenant_id=:tenant_id AND major_name LIKE :prefix
                ORDER BY id""",
            tenant_id=SANDBOX_TID,
            prefix=f"{E2E_PREFIX}%",
        )
        classes = _rows(
            db,
            """SELECT id,major_id AS majorId,class_name AS name,class_code AS code,
                      status,is_deleted AS isDeleted
                 FROM t_class
                WHERE tenant_id=:tenant_id AND class_name LIKE :prefix
                ORDER BY id""",
            tenant_id=SANDBOX_TID,
            prefix=f"{E2E_PREFIX}%",
        )
        students = _rows(
            db,
            """SELECT id,student_no AS studentNo,real_name AS realName,
                      college_id AS collegeId,major_id AS majorId,class_id AS classId,
                      status,student_status AS studentStatus,is_deleted AS isDeleted
                 FROM t_student_profile
                WHERE tenant_id=:tenant_id AND student_no LIKE 'E2EAA2026%'
                ORDER BY id""",
            tenant_id=SANDBOX_TID,
        )
        users = _rows(
            db,
            """SELECT id,login_name AS loginName,real_name AS realName,user_type AS userType,
                      status,is_deleted AS isDeleted
                 FROM t_user
                WHERE tenant_id=:tenant_id
                  AND (login_name LIKE 'e2e_aa_%' OR login_name LIKE 'E2EAA2026%')
                ORDER BY id""",
            tenant_id=SANDBOX_TID,
        )
        links = _rows(
            db,
            """SELECT l.id,l.student_id AS studentId,l.user_id AS userId,
                      l.link_status AS linkStatus,l.source,l.is_deleted AS isDeleted
                 FROM t_student_account_link l
                 JOIN t_user u ON u.id=l.user_id AND u.tenant_id=l.tenant_id
                WHERE l.tenant_id=:tenant_id
                  AND (u.login_name LIKE 'e2e_aa_%' OR u.login_name LIKE 'E2EAA2026%')
                ORDER BY l.id""",
            tenant_id=SANDBOX_TID,
        )

        ids = {
            "college_id": [int(row["id"]) for row in colleges],
            "major_id": [int(row["id"]) for row in majors],
            "class_id": [int(row["id"]) for row in classes],
            "student_id": [int(row["id"]) for row in students],
            "user_id": [int(row["id"]) for row in users],
        }
        references = []
        for column, values in ids.items():
            references.extend(_reference_counts(db, schema, column, values))

        payload = {
            "tenantId": str(SANDBOX_TID),
            "tenantCode": SANDBOX_CODE,
            "database": schema,
            "counts": {
                "colleges": len(colleges),
                "majors": len(majors),
                "classes": len(classes),
                "students": len(students),
                "users": len(users),
                "accountLinks": len(links),
            },
            "colleges": colleges,
            "majors": majors,
            "classes": classes,
            "students": students,
            "users": users,
            "accountLinks": links,
            "directReferenceCounts": references,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
