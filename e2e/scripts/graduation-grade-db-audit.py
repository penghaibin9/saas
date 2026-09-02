import json
from datetime import date, datetime
from decimal import Decimal
from itertools import chain
from pathlib import Path

import pymysql

PRODUCT_EXACT_HEAD = "63195a6dc9d25fa3805563910fb699ec163b552a"


def cv(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="e2e_root",
    database="student_lifecycle_e2e", charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
with conn.cursor() as cur:
    cur.execute("SELECT * FROM t_gd_grade ORDER BY id")
    grades = list(cur.fetchall())
    cur.execute("SELECT * FROM t_gd_grade_appeal ORDER BY id")
    appeals = list(cur.fetchall())
    cur.execute("SELECT id,tenant_id,batch_id,student_no,name,stage FROM t_gd_student ORDER BY id")
    students = list(cur.fetchall())
    cur.execute(
        "SELECT id,tenant_id,biz_type,biz_id,action,operator,role_name,detail,before_val,after_val,"
        "occurred_at,request_id,request_path,role_code,permission_code "
        "FROM t_gd_audit_trail WHERE biz_type IN ('GRADE','GRADE_APPEAL') ORDER BY id"
    )
    audits = list(cur.fetchall())
conn.close()

for row in chain(grades, appeals, students, audits):
    for key, value in list(row.items()):
        row[key] = cv(value)

evidence = {
    "productExactHead": PRODUCT_EXACT_HEAD,
    "grades": grades,
    "appeals": appeals,
    "students": students,
    "audits": audits,
}
out = Path("test-results/graduation-grade-db-audit.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))

grade = next((row for row in reversed(grades) if int(row.get("advisor_score") or -1) == 95), None)
assert grade, grades
assert grade["status"] == "PUBLISHED", grade
assert int(grade["advisor_score"]) == 95, grade
assert int(grade["reviewer_score"]) == 92, grade
assert int(grade["defense_score"]) == 93, grade
assert int(grade["total_score"]) == 94, grade
assert grade["grade_level"] == "优秀", grade
assert grade.get("published_at") and grade.get("published_by"), grade
assert grade.get("source_snapshot_hash"), grade

student = next((row for row in students if str(row["id"]) == str(grade["gd_student_id"])), None)
assert student and student["stage"] == "COMPLETED", (grade, students)

mine_appeals = [row for row in appeals if str(row.get("gd_student_id")) == str(grade["gd_student_id"])]
assert mine_appeals, appeals
appeal = mine_appeals[-1]
assert appeal["status"] == "APPROVED", appeal
assert "E2E-AUDIT-20260823" in str(appeal.get("reason") or ""), appeal
assert appeal.get("reviewed_at") and appeal.get("reviewed_by"), appeal

grade_actions = [row["action"] for row in audits if row["biz_type"] == "GRADE"]
assert grade_actions.count("核算成绩") >= 4, grade_actions
assert grade_actions.count("复核退回") >= 1, grade_actions
assert grade_actions.count("复核通过") >= 3, grade_actions
assert grade_actions.count("发布成绩") >= 3, grade_actions
assert grade_actions.count("撤回成绩") >= 1, grade_actions

appeal_actions = [row["action"] for row in audits if row["biz_type"] == "GRADE_APPEAL"]
assert any("申诉" in str(action) for action in appeal_actions), appeal_actions
assert any("受理" in str(action) for action in appeal_actions), appeal_actions

for row in audits:
    assert row["tenant_id"] and row["operator"] and row["role_name"] and row["occurred_at"], row
    assert row["request_id"] and row["request_path"] and row["role_code"], row