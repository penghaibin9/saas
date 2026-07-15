"""学籍管理 Tier1 R2（学籍档案/学籍状态/学籍异动记录/学籍导入导出）—— 独立 SQLite 自测脚本
（不连 MySQL，不跑 pytest 默认 conftest，因其 TEST_DATABASE_URL 被多个并行任务共用）。

用法：VENV_PYTHON diag_aa_roster.py
仅用于本轮子智能体自测证据留存，非正式 pytest 用例；正式回归由总控在 MySQL 环境统一执行。
"""
from __future__ import annotations

import os
import sys

os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "true"
_DB_PATH = "D:/tmp_diag/diag_aa_roster.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["TEST_DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["MOCK_LOGIN_ENABLED"] = "true"

os.makedirs("D:/tmp_diag", exist_ok=True)
if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

from app.db.base import metadata  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

engine = get_engine()
metadata.create_all(bind=engine)
print("[1] metadata.create_all OK（零新表，全部复用既有 t_student_profile/t_aa_status_change/College/Major/SchoolClass）")

TID = 1000000000000000001

from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope  # noqa: E402

db = get_sessionmaker()()

college_sw = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
college_wl = College(tenant_id=TID, college_name="网络学院", status="ACTIVE")
db.add(college_sw); db.add(college_wl); db.flush()
major_sw = Major(tenant_id=TID, college_id=college_sw.id, major_name="软件技术", status="ACTIVE")
major_wl = Major(tenant_id=TID, college_id=college_wl.id, major_name="网络技术", status="ACTIVE")
db.add(major_sw); db.add(major_wl); db.flush()
class_sw = SchoolClass(tenant_id=TID, major_id=major_sw.id, class_name="软件2601", grade="2026", status="ACTIVE")
class_wl = SchoolClass(tenant_id=TID, major_id=major_wl.id, class_name="网络2601", grade="2026", status="ACTIVE")
db.add(class_sw); db.add(class_wl); db.flush()

s1 = StudentProfile(tenant_id=TID, student_no="R0001", real_name="档案甲", class_id=class_sw.id,
                    college_id=college_sw.id, major_id=major_sw.id, grade="2026", current_stage="ON_CAMPUS",
                    student_status="NORMAL", status="ACTIVE", id_card_encrypted="110101200001011234")
s2 = StudentProfile(tenant_id=TID, student_no="R0002", real_name="档案乙", class_id=class_sw.id,
                    college_id=college_sw.id, major_id=major_sw.id, current_stage="ON_CAMPUS",
                    student_status="SUSPENDED", status="ACTIVE")
s_out = StudentProfile(tenant_id=TID, student_no="R0003", real_name="档案丙(越院)", class_id=class_wl.id,
                       college_id=college_wl.id, major_id=major_wl.id, current_stage="ON_CAMPUS",
                       student_status="NORMAL", status="ACTIVE")
db.add(s1); db.add(s2); db.add(s_out); db.flush()

db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="张晓明",
                           role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))

from app.models import AaStatusChange  # noqa: E402
db.add(AaStatusChange(tenant_id=TID, student_id=s2.id, change_type="SUSPEND", from_status="NORMAL",
                      to_status="SUSPENDED", reason="自测休学", status="EFFECTIVE",
                      from_college_id=college_sw.id, to_college_id=college_sw.id,
                      from_class_id=class_sw.id, to_class_id=class_sw.id))

db.commit()
ids = {"s1": s1.id, "s2": s2.id, "sOut": s_out.id, "classSw": class_sw.id, "classWl": class_wl.id,
      "collegeSw": college_sw.id}
db.close()
print(f"[2] 种子数据 OK（2 学院/2 专业/2 班级/3 学生[1休学]/1 异动流水/1 学院教务 scope）ids={ids}")

login = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"})
assert login.status_code == 200, f"mock-login 失败: {login.status_code} {login.text}"
H = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
college_login = client.post("/api/v1/auth/mock-login", json={"loginName": "college_admin01", "password": "any"})
assert college_login.status_code == 200
HC = {"Authorization": f"Bearer {college_login.json()['data']['accessToken']}"}
print("[3] mock-login(school_admin01 / college_admin01) OK")

BASE = "/api/v1/academic-affairs"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'OK ' if ok else 'FAIL'} {name}{'  ' + detail if (not ok and detail) else ''}")


# ═══════════ 学籍档案 ═══════════
r = client.get(f"{BASE}/roster/{ids['s1']}", headers=H)
check("学籍档案详情-200", r.status_code == 200, r.text[:200])
d = r.json()["data"]
check("学籍档案详情-字段完整", d.get("studentNo") == "R0001" and d.get("collegeName") == "软件学院"
     and d.get("majorName") == "软件技术" and d.get("className") == "软件2601" and d.get("grade") == "2026",
     str(d))
check("学籍档案详情-idCardMasked已脱敏", "*" in (d.get("idCardMasked") or "") or d.get("idCardMasked") != "110101200001011234")

r = client.get(f"{BASE}/roster/{ids['s2']}", headers=H)
d2 = r.json()["data"]
check("学籍档案详情-异动历史非空", len(d2.get("statusHistory") or []) == 1
     and d2["statusHistory"][0]["changeType"] == "SUSPEND", str(d2.get("statusHistory")))

r = client.get(f"{BASE}/roster/{ids['sOut']}", headers=HC)
check("学籍档案详情-越院403", r.status_code == 403, f"{r.status_code} {r.text[:150]}")

r = client.get(f"{BASE}/roster/{ids['s1']}", headers=HC)
check("学籍档案详情-本院200", r.status_code == 200, r.text[:150])

r = client.get(f"{BASE}/roster/999999", headers=H)
check("学籍档案详情-不存在404", r.status_code == 404, str(r.status_code))

# ── 敏感证件号查看 ──
r = client.post(f"{BASE}/roster/{ids['s1']}/reveal", headers=H, json={"reason": "短"})
check("证件号查看-理由过短400", r.status_code == 400, str(r.status_code))
r = client.post(f"{BASE}/roster/{ids['s1']}/reveal", headers=H, json={"reason": "核对身份证材料真实性"})
check("证件号查看-成功200且返回明文", r.status_code == 200 and r.json()["data"]["idCard"] == "110101200001011234",
     r.text[:200])

# ═══════════ 学籍状态总览 ═══════════
r = client.get(f"{BASE}/roster/status-summary", headers=H)
check("学籍状态总览-200", r.status_code == 200, r.text[:200])
sm = r.json()["data"]
by_status = {row["status"]: row["count"] for row in sm["byStatus"]}
check("学籍状态总览-分布正确", by_status.get("NORMAL") == 2 and by_status.get("SUSPENDED") == 1
     and sm["enrolledCount"] == 2 and sm["notEnrolledCount"] == 1, str(sm))

r = client.get(f"{BASE}/roster/status-summary", headers=HC)
smc = r.json()["data"]
check("学籍状态总览-学院范围收敛(不含越院学生)", smc["total"] == 2, str(smc))

# ═══════════ 学籍异动记录（只读复用 status-changes） ═══════════
r = client.get(f"{BASE}/status-changes", headers=H, params={"studentId": str(ids["s2"])})
check("学籍异动记录(复用)-200且含1条", r.status_code == 200 and r.json()["data"]["total"] == 1, r.text[:200])
r = client.get(f"{BASE}/status-changes/stats", headers=H)
check("学籍异动统计(复用)-200", r.status_code == 200, r.text[:150])

# ═══════════ 学籍导出 ═══════════
r = client.post(f"{BASE}/roster/export", headers=H, json={"purpose": "短"})
check("学籍导出-用途过短400", r.status_code == 400, str(r.status_code))
r = client.post(f"{BASE}/roster/export", headers=H, json={"purpose": "月度学籍台账核对导出"})
check("学籍导出-成功200且为xlsx", r.status_code == 200 and len(r.content) > 500
     and r.headers.get("content-type", "").startswith("application/vnd.openxmlformats"), str(r.status_code))

# ═══════════ 学籍导入 ═══════════
r = client.get(f"{BASE}/roster/import/template", headers=H)
check("导入模板-200且为xlsx", r.status_code == 200 and len(r.content) > 500, str(r.status_code))

good_row = {"studentNo": "IMP001", "realName": "导入甲", "gender": "男", "idCard": "",
           "className": "软件2601", "initialStatus": "PENDING_REGISTER"}
dup_in_file_row = dict(good_row)
unknown_class_row = {**good_row, "studentNo": "IMP002", "className": "不存在的班级"}
bad_status_row = {**good_row, "studentNo": "IMP003", "initialStatus": "SUSPENDED"}
existing_no_row = {**good_row, "studentNo": "R0001"}

r = client.post(f"{BASE}/roster/import/dry-run", headers=H,
                json={"rows": [good_row, dup_in_file_row, unknown_class_row, bad_status_row, existing_no_row]})
check("导入预校验-200", r.status_code == 200, r.text[:300])
pre = r.json()["data"]
check("导入预校验-5行1通过4失败", pre["total"] == 5 and pre["validRows"] == 1 and pre["invalidRows"] == 4, str(pre))
err_fields = {e["rowNo"] for e in pre["errors"]}
check("导入预校验-错误行号覆盖第2/3/4/5行", err_fields == {2, 3, 4, 5}, str(err_fields))

r = client.post(f"{BASE}/roster/import/dry-run", headers=H, json={"rows": [good_row]})
pre_ok = r.json()["data"]
check("导入预校验-单条合法行通过", pre_ok["passed"] and pre_ok["validRows"] == 1, str(pre_ok))

r = client.post(f"{BASE}/roster/import/confirm", headers=H, json={"rows": pre_ok["rows"]})
check("导入确认-200且created=1", r.status_code == 200 and r.json()["data"]["created"] == 1, r.text[:200])

db2 = get_sessionmaker()()
created = db2.query(StudentProfile).filter_by(tenant_id=TID, student_no="IMP001").first()
check("导入确认-学生已入库且组织关系正确",
     created is not None and created.college_id == college_sw.id and created.major_id == major_sw.id
     and created.class_id == class_sw.id and created.grade == "2026"
     and created.student_status == "PENDING_REGISTER",
     str(created and (created.college_id, created.major_id, created.class_id, created.grade, created.student_status)))
from app.models import StudentStageEvent  # noqa: E402
ev = db2.query(StudentStageEvent).filter_by(tenant_id=TID, student_id=created.id,
                                            source_module="academic-affairs").count() if created else 0
check("导入确认-写入360阶段事件", ev == 1, str(ev))
db2.close()

# 重复导入同学号应在预校验阶段被库内查重拦截
r = client.post(f"{BASE}/roster/import/dry-run", headers=H, json={"rows": [good_row]})
pre_dup = r.json()["data"]
check("导入预校验-库内查重拦截已入库学号", not pre_dup["passed"] and pre_dup["invalidRows"] == 1, str(pre_dup))

# 越权：学生令牌禁访问
stu_login = client.post("/api/v1/auth/mock-login", json={"loginName": "student01", "password": "any"})
if stu_login.status_code == 200:
    HS = {"Authorization": f"Bearer {stu_login.json()['data']['accessToken']}"}
    r = client.get(f"{BASE}/roster/{ids['s1']}", headers=HS)
    check("学生令牌访问学籍档案-403", r.status_code == 403, str(r.status_code))

fail_count = sum(1 for _, ok, _ in results if not ok)
print(f"\n=== 汇总：{len(results)} 项检查，{len(results) - fail_count} 通过，{fail_count} 失败 ===")
if fail_count:
    sys.exit(1)
print("ALL PASS")
