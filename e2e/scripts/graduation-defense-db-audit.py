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
    cur.execute("SELECT * FROM t_gd_defense_group ORDER BY id")
    groups = list(cur.fetchall())
    cur.execute("SELECT * FROM t_gd_defense_score ORDER BY id")
    scores = list(cur.fetchall())
    cur.execute("SELECT id,tenant_id,batch_id,student_no,name,defense_group_id,stage FROM t_gd_student ORDER BY id")
    students = list(cur.fetchall())
    cur.execute(
        "SELECT id,tenant_id,biz_type,biz_id,action,operator,role_name,detail,before_val,after_val,"
        "occurred_at,request_id,request_path,role_code,permission_code "
        "FROM t_gd_audit_trail WHERE biz_type='DEFENSE_SCORE' ORDER BY id"
    )
    audits = list(cur.fetchall())
conn.close()

for row in chain(groups, scores, students, audits):
    for key, value in list(row.items()):
        row[key] = cv(value)

evidence = {
    "productExactHead": PRODUCT_EXACT_HEAD,
    "groups": groups,
    "scores": scores,
    "students": students,
    "audits": audits,
}
out = Path("test-results/graduation-defense-db-audit.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))

group = next((row for row in reversed(groups) if str(row.get("group_name") or "").startswith("E2E-AUDIT-20260823 答辩组 ")), None)
assert group, groups
assert bool(group.get("published")), group
assert str(group.get("chair") or "") == "E2E答辩专家A", group
assert str(group.get("secretary") or "") == "E2E答辩秘书", group

student = next((row for row in students if str(row.get("defense_group_id") or "") == str(group["id"])), None)
assert student and str(student.get("student_no") or "").startswith("E2E2026"), (group, students)

mine = [row for row in scores if str(row.get("gd_student_id")) == str(student["id"])]
assert len(mine) == 4, mine
by_round = {1: [], 2: []}
for row in mine:
    by_round[int(row["round_no"])].append(row)
for round_no, expected in ((1, {"E2E答辩专家A": 91, "E2E答辩专家B": 89}),
                           (2, {"E2E答辩专家A": 94, "E2E答辩专家B": 92})):
    rows = by_round[round_no]
    assert len(rows) == 2, (round_no, rows)
    assert {row["judge_name"] for row in rows} == set(expected), rows
    for row in rows:
        assert row["status"] == "CONFIRMED" and row.get("confirmed_at"), row
        assert int(row["score"]) == expected[row["judge_name"]], row
        assert row.get("judge_mentor_id"), row

actions = [row["action"] for row in audits]
assert actions.count("录入答辩评分") >= 4, actions
assert actions.count("确认答辩成绩") >= 2, actions
assert any("二次答辩" in str(action) for action in actions), actions
for row in audits:
    assert row["tenant_id"] and row["operator"] and row["role_name"] and row["occurred_at"], row
    assert row["request_id"] and row["request_path"] and row["role_code"], row