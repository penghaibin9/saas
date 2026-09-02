import json
import os
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pymysql

EXPECTED_HEAD = os.environ.get("E2E_EXPECTED_SHA", "").strip()
PRODUCT_EXACT_HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert EXPECTED_HEAD, "E2E_EXPECTED_SHA must be set for exact-head review audit"
assert PRODUCT_EXACT_HEAD == EXPECTED_HEAD, (PRODUCT_EXACT_HEAD, EXPECTED_HEAD)


def cv(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="e2e_root",
    database="student_lifecycle_e2e",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
with conn.cursor() as cur:
    cur.execute("SELECT * FROM t_gd_review ORDER BY id")
    reviews = list(cur.fetchall())
    cur.execute(
        "SELECT id,tenant_id,biz_type,biz_id,action,operator,role_name,detail,"
        "before_val,after_val,occurred_at,request_id,request_path,role_code,permission_code "
        "FROM t_gd_audit_trail WHERE biz_type='REVIEW' ORDER BY id"
    )
    audits = list(cur.fetchall())
    cur.execute(
        "SELECT id,tenant_id,gd_student_id,final_type,version,status,plagiarism_rate,plagiarism_status "
        "FROM t_gd_final WHERE final_type='定稿' ORDER BY id"
    )
    finals = list(cur.fetchall())
    cur.execute(
        "SELECT id,tenant_id,gd_student_id,gd_final_id,status,rate,threshold,over_threshold,recheck_of_id "
        "FROM t_gd_plagiarism WHERE status='DONE' ORDER BY id"
    )
    plagiarism = list(cur.fetchall())
conn.close()

for row in reviews + audits + finals + plagiarism:
    for key, value in list(row.items()):
        row[key] = cv(value)

evidence = {
    "productExactHead": PRODUCT_EXACT_HEAD,
    "reviews": reviews,
    "audits": audits,
    "finals": finals,
    "plagiarism": plagiarism,
}
out = Path("test-results/graduation-review-db-audit.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))

rows = [row for row in reviews if str(row.get("reviewer_name") or "") == "E2E评阅教师"]
assert len(rows) == 1, reviews
review = rows[0]
assert review["tenant_id"] and review["gd_student_id"] and review["gd_final_id"] and review["reviewer_mentor_id"], review
assert review["status"] == "COMPLETED", review
assert int(review["score"]) == 92, review
assert "E2E-AUDIT-20260823 重评完成" in str(review.get("opinion") or ""), review
assert int(review.get("version") or 0) >= 3, review

formal_final = next((row for row in finals if int(row["id"]) == int(review["gd_final_id"])), None)
assert formal_final and formal_final["status"] == "APPROVED" and formal_final["final_type"] == "定稿", (review, finals)
checks = [row for row in plagiarism if int(row["gd_final_id"]) == int(review["gd_final_id"])]
assert checks, plagiarism
assert any(
    not row["over_threshold"]
    and float(str(row["rate"]).replace("%", "")) <= float(row["threshold"])
    for row in checks
), checks

actions = [row["action"] for row in audits if str(row["biz_id"]) == str(review["id"])]
assert "分配评阅任务" in actions, actions
assert actions.count("提交评阅") >= 2, actions
assert "退回重评" in actions, actions
returned = [
    row for row in audits
    if str(row["biz_id"]) == str(review["id"]) and row["action"] == "退回重评"
]
assert returned and "E2E-AUDIT-20260823" in str(returned[-1].get("detail") or ""), returned
for audit in [row for row in audits if str(row["biz_id"]) == str(review["id"])]:
    assert audit["tenant_id"] and audit["operator"] and audit["role_name"] and audit["occurred_at"], audit
    assert audit["request_id"] and audit["request_path"] and audit["role_code"], audit
