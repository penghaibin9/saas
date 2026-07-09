"""一次性补齐 t_internship_record 缺失列（模型已加、create_all 不会改旧表）。"""
from __future__ import annotations

import _mysql_env  # noqa: F401
import pymysql
import re

from app.core.config import settings

m = re.search(r"//([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)", settings.effective_database_url)
user, pw, host, port, db = m.groups()
conn = pymysql.connect(host=host, port=int(port), user=user, password=pw, database=db, charset="utf8mb4")
cur = conn.cursor()
cur.execute("DESCRIBE t_internship_record")
existing = {r[0] for r in cur.fetchall()}
stmts = []
if "eligibility_status" not in existing:
    stmts.append(
        "ALTER TABLE t_internship_record ADD COLUMN eligibility_status VARCHAR(50) "
        "NOT NULL DEFAULT 'PENDING' COMMENT '实习资格' AFTER enterprise_mentor_name"
    )
if "destination_type" not in existing:
    stmts.append(
        "ALTER TABLE t_internship_record ADD COLUMN destination_type VARCHAR(50) "
        "NOT NULL DEFAULT 'NONE' COMMENT '实习去向' AFTER eligibility_status"
    )
if "enterprise_id" not in existing:
    stmts.append(
        "ALTER TABLE t_internship_record ADD COLUMN enterprise_id BIGINT NULL "
        "COMMENT 'emp company' AFTER destination_type"
    )
if "position_id" not in existing:
    stmts.append(
        "ALTER TABLE t_internship_record ADD COLUMN position_id BIGINT NULL "
        "COMMENT 'position' AFTER enterprise_id"
    )
if "mentor_contact_id" not in existing:
    stmts.append(
        "ALTER TABLE t_internship_record ADD COLUMN mentor_contact_id BIGINT NULL "
        "COMMENT 'mentor contact' AFTER position_id"
    )
for s in stmts:
    print("[alter]", s[:90], "...")
    cur.execute(s)
conn.commit()
print(f"[alter] applied {len(stmts)} statement(s)")
conn.close()
