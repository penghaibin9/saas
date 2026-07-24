"""跨域引用完整性扫描（只读）。先扫后修，不盲目加外键。

用法：
  python -m scripts.check_referential_integrity
"""
from __future__ import annotations

import json
import sys

from sqlalchemy import text

from app.db.session import db_enabled, get_sessionmaker


CHECKS = [
    ("student_contact_orphan", """
        SELECT COUNT(*) FROM t_student_contact c
        LEFT JOIN t_student_profile s ON s.id=c.student_id AND s.tenant_id=c.tenant_id
        WHERE s.id IS NULL
    """),
    ("student_class_cross_tenant", """
        SELECT COUNT(*) FROM t_student_profile s
        JOIN t_school_class c ON c.id=s.class_id
        WHERE s.class_id IS NOT NULL AND c.tenant_id <> s.tenant_id
    """),
    ("msg_job_orphan_campaign", """
        SELECT COUNT(*) FROM t_message_delivery_job j
        LEFT JOIN t_message_campaign c ON c.id=j.campaign_id AND c.tenant_id=j.tenant_id
        WHERE c.id IS NULL AND j.is_deleted=0
    """),
    ("soft_deleted_student_no_active_dup", """
        SELECT COUNT(*) FROM t_student_profile a
        JOIN t_student_profile b
          ON a.tenant_id=b.tenant_id AND a.student_no=b.student_no AND a.id<b.id
        WHERE a.is_deleted=0 AND b.is_deleted=0
    """),
]


def run() -> dict:
    if not db_enabled():
        return {"ok": False, "error": "DB_ENABLED=false"}
    db = get_sessionmaker()()
    report = {"ok": True, "checks": []}
    try:
        for name, sql in CHECKS:
            try:
                n = int(db.execute(text(sql)).scalar() or 0)
            except Exception as e:  # noqa: BLE001
                report["checks"].append({"name": name, "error": str(e), "count": None})
                report["ok"] = False
                continue
            item = {"name": name, "count": n}
            if n > 0:
                report["ok"] = False
            report["checks"].append(item)
    finally:
        db.close()
    return report


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if out.get("ok") else 2)
