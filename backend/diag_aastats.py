"""教务统计 Tier1 10 项三级模块 —— 独立 SQLite 自测脚本（不连 MySQL，不跑 pytest 默认配置）。

用法：VENV_PYTHON diag_aastats.py
仅用于本轮子智能体自测证据留存，非正式 pytest 用例（正式回归用例见 backend/tests/test_academic_affairs_stats.py，
由总控后续统一在 MySQL 环境执行）。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "true"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./diag_aastats.db"
os.environ["TEST_DATABASE_URL"] = "sqlite+pysqlite:///./diag_aastats.db"
os.environ["MOCK_LOGIN_ENABLED"] = "true"

# 清理旧库，保证幂等
if os.path.exists("./diag_aastats.db"):
    os.remove("./diag_aastats.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

from app.db.base import metadata  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

engine = get_engine()
metadata.create_all(bind=engine)
print("[1] metadata.create_all OK（含新增 10 项聚合复用的既有表，无新建表）")

TID = 1000000000000000001

# ═══════════ 种子数据 ═══════════
from app.models import (  # noqa: E402
    AaCourse, AaGraduationAuditBatch, AaGraduationAuditResult, AaRegistration,
    AaRegistrationBatch, AaScheduleBatch, AaScheduleItem, AaStatusChange, AaTeachingTask, AaTerm,
    AcademicGrade, AcademicStudent, AcademicWarning, College, Major, StudentProfile,
)

db = get_sessionmaker()()

college = College(tenant_id=TID, college_name="软件学院", code="RJ", status="ACTIVE")
db.add(college)
db.flush()

major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", code="RJ01")
db.add(major)
db.flush()

term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1, term_name="2025秋",
             is_current=True, status="PUBLISHED")
db.add(term)
db.flush()

students = []
for i in range(4):
    s = StudentProfile(tenant_id=TID, student_no=f"DIAG{i:04d}", real_name=f"诊断学生{i}",
                       current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
                       college_id=college.id, major_id=major.id)
    db.add(s)
    students.append(s)
db.flush()

# 注册批次 + 注册记录（3 已注册 / 1 未注册）
reg_batch = AaRegistrationBatch(tenant_id=TID, batch_name="2025秋学年注册", register_type="ANNUAL",
                                term_id=term.id, status="OPEN")
db.add(reg_batch)
db.flush()
for i, s in enumerate(students):
    db.add(AaRegistration(tenant_id=TID, batch_id=reg_batch.id, student_id=s.id,
                          status="REGISTERED" if i < 3 else "PENDING_REGISTER"))

# 学籍异动（2 条 TRANSFER_MAJOR EFFECTIVE）
for i in range(2):
    db.add(AaStatusChange(tenant_id=TID, student_id=students[i].id, change_type="TRANSFER_MAJOR",
                          from_status="NORMAL", to_status="NORMAL", term_code="2025-2026",
                          status="EFFECTIVE"))

# 课程（2 ENABLED）
c1 = AaCourse(tenant_id=TID, course_code="C001", course_name="高等数学", category="PUBLIC_BASIC",
             credit=4, hours_total=64, owner_college_id=college.id, status="ENABLED")
c2 = AaCourse(tenant_id=TID, course_code="C002", course_name="Java开发", category="MAJOR_CORE",
             credit=5, hours_total=80, owner_college_id=college.id, status="ENABLED")
db.add(c1)
db.add(c2)
db.flush()

# 教学任务（1 已确认 + 1 未确认）
db.add(AaTeachingTask(tenant_id=TID, batch_id=1, course_id=c1.id, course_name=c1.course_name,
                      teaching_class_name="高数01班", teacher_key="T001", teacher_name="王老师",
                      weekly_hours=4, total_hours=64, confirm_at=datetime.utcnow(),
                      status="TEACHER_CONFIRMED"))
db.add(AaTeachingTask(tenant_id=TID, batch_id=1, course_id=c2.id, course_name=c2.course_name,
                      teaching_class_name="Java01班", teacher_key="T002", teacher_name="李老师",
                      weekly_hours=6, total_hours=96, confirm_at=None, status="ASSIGNED"))
db.flush()

# 课表批次 + 排课项（含 1 组冲突：同班同星期同节次同单双周 2 条）
sb = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="2025秋课表批次",
                     college_id=college.id, status="PUBLISHED")
db.add(sb)
db.flush()
db.add(AaScheduleItem(tenant_id=TID, batch_id=sb.id, course_name="高等数学", class_id=1,
                      class_name="高数01班", teacher_key="T001", teacher_name="王老师",
                      weekday=1, slot_no=1, week_parity="ALL", status="EFFECTIVE"))
db.add(AaScheduleItem(tenant_id=TID, batch_id=sb.id, course_name="Java开发", class_id=1,
                      class_name="高数01班", teacher_key="T002", teacher_name="李老师",
                      weekday=1, slot_no=1, week_parity="ALL", status="EFFECTIVE"))

# 学业过程域：AcademicStudent + 成绩 + 预警
acad_students = []
for i, s in enumerate(students):
    a = AcademicStudent(tenant_id=TID, student_id=s.id, student_no=s.student_no, name=s.real_name,
                        class_name="诊断班", college_name="软件学院", major_name="软件技术")
    db.add(a)
    acad_students.append(a)
db.flush()

db.add(AcademicGrade(tenant_id=TID, acad_student_id=acad_students[0].id, course_name="高等数学",
                     term="2025-2026", score=45, pass_status="FAILED", record_status="ACTIVE"))
db.add(AcademicGrade(tenant_id=TID, acad_student_id=acad_students[1].id, course_name="Java开发",
                     term="2025-2026", score=85, pass_status="PASSED", record_status="ACTIVE"))
db.add(AcademicWarning(tenant_id=TID, acad_student_id=acad_students[0].id, warn_type="MULTI_FAIL",
                       level="HIGH", source_code="EXAM_FAIL", status="PENDING_HANDLE",
                       record_status="ACTIVE"))

# 毕业资格：1 SYSTEM_PASSED + 1 SYSTEM_ABNORMAL（含 item_results_json）
import json  # noqa: E402
gb = AaGraduationAuditBatch(tenant_id=TID, batch_name="2026届预审", grade_year="2026", status="PRECHECKED")
db.add(gb)
db.flush()
db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=gb.id, student_id=students[0].id,
                               overall="SYSTEM_PASSED", conclusion="GRADUATED", status="SYSTEM_PASSED",
                               item_results_json=json.dumps([{"item": "CREDIT", "result": "PASS"}])))
db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=gb.id, student_id=students[1].id,
                               overall="SYSTEM_ABNORMAL", conclusion=None, status="SYSTEM_ABNORMAL",
                               item_results_json=json.dumps([{"item": "CREDIT", "result": "FAIL"},
                                                             {"item": "DISCIPLINE", "result": "PASS"}])))

db.commit()
db.close()
print("[2] 种子数据写入 OK（4 学生/2 课程/2 教学任务/1 冲突组/2 成绩/1 预警/2 毕业预审结果）")

# ═══════════ 登录（school_admin01 → SCHOOL_ADMIN，TENANT_ALL） ═══════════
login = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"})
assert login.status_code == 200, f"mock-login 失败: {login.status_code} {login.text}"
token = login.json()["data"]["accessToken"]
H = {"Authorization": f"Bearer {token}"}
print("[3] mock-login(school_admin01) OK")

results = []


def check(name, method, path, expect_keys=None, params=None, body=None, expect_status=200, headers=H):
    fn = client.get if method == "GET" else client.post
    kwargs = {"headers": headers} if headers else {}
    if params is not None:
        kwargs["params"] = params
    if body is not None:
        kwargs["json"] = body
    r = fn(path, **kwargs)
    ok = r.status_code == expect_status
    detail = ""
    if ok and expect_keys:
        try:
            d = r.json()["data"]
            missing = [k for k in expect_keys if k not in d]
            if missing:
                ok = False
                detail = f"missing keys {missing} in {d}"
        except Exception as e:  # noqa: BLE001
            ok = False
            detail = f"parse error: {e}"
    if not ok and not detail:
        detail = r.text[:300]
    results.append((name, ok, r.status_code, detail))
    print(f"  {'OK ' if ok else 'FAIL'} {name} [{r.status_code}] {detail}")
    return r


print("[4] 10 项 Tier1 端点联调：")
check("学籍统计-聚合", "GET", "/api/v1/academic-affairs/stats/status-change/summary", ["total", "byType"])
check("学籍统计-明细(既有)", "GET", "/api/v1/academic-affairs/stats/status-change", None, {"page": 1, "pageSize": 20})
check("注册统计-聚合", "GET", "/api/v1/academic-affairs/stats/registration/summary", ["registered", "expected", "rate"])
check("注册统计-明细(既有)", "GET", "/api/v1/academic-affairs/stats/registration", None, {"page": 1, "pageSize": 20})
check("课程统计-聚合", "GET", "/api/v1/academic-affairs/stats/course", ["total", "byCategory", "byCollege"])
check("课程统计-明细", "GET", "/api/v1/academic-affairs/stats/course/detail", None, {"page": 1, "pageSize": 20})
check("教学任务统计-聚合", "GET", "/api/v1/academic-affairs/stats/teaching-task", ["confirmed", "expected", "rate"])
check("教学任务统计-明细", "GET", "/api/v1/academic-affairs/stats/teaching-task/pending", None, {"page": 1, "pageSize": 20})
check("课表统计-聚合", "GET", "/api/v1/academic-affairs/stats/schedule", ["publishedRate", "unresolvedConflicts"])
check("课表统计-明细", "GET", "/api/v1/academic-affairs/stats/schedule/conflicts", None, {"page": 1, "pageSize": 20})
check("成绩统计-聚合", "GET", "/api/v1/academic-affairs/stats/grade", ["failRate", "entryPublishRate", "makeupCount", "retakeCount"])
check("成绩统计-明细", "GET", "/api/v1/academic-affairs/stats/grade/detail", None, {"page": 1, "pageSize": 20})
check("学业预警统计-聚合", "GET", "/api/v1/academic-affairs/stats/warning/summary", ["total", "byLevel", "bySource"])
check("学业预警统计-明细(既有)", "GET", "/api/v1/academic-affairs/stats/warning", None, {"page": 1, "pageSize": 20})
check("毕业资格统计-聚合", "GET", "/api/v1/academic-affairs/stats/graduation", ["passRate", "passed", "expected", "byAbnormalItem"])
check("毕业资格统计-明细", "GET", "/api/v1/academic-affairs/stats/graduation/abnormal", None, {"page": 1, "pageSize": 20})
check("教师工作量统计-聚合", "GET", "/api/v1/academic-affairs/stats/workload", ["ranking", "disclaimer"])
wl = check("教师工作量统计-明细", "GET", "/api/v1/academic-affairs/stats/workload/detail", None,
          {"teacherKey": "T001", "page": 1, "pageSize": 20})

print("[5] 导出报表（15 号卡）domain 选择：")
check("导出-overview", "POST", "/api/v1/academic-affairs/stats/export", None, None,
     {"domain": "overview", "purpose": "自测导出验证"}, 200)
check("导出-course", "POST", "/api/v1/academic-affairs/stats/export", None, None,
     {"domain": "course", "purpose": "自测导出验证"}, 200)
check("导出-用途过短应400", "POST", "/api/v1/academic-affairs/stats/export", None, None,
     {"domain": "overview", "purpose": "短"}, 400)

print("[6] 越权/无权限：")
check("无 token 访问-应401", "GET", "/api/v1/academic-affairs/stats/course", None, None, None, 401, headers=None)

# 明细数值正确性核对（挂科率应为 1/2=50%，注册完成率 3/4=75%）
r = client.get("/api/v1/academic-affairs/stats/grade", headers=H).json()["data"]
assert r["failRate"] == 50.0, f"挂科率期望 50.0，实得 {r['failRate']}"
r2 = client.get("/api/v1/academic-affairs/stats/registration/summary", headers=H).json()["data"]
assert r2["rate"] == 75.0, f"注册完成率期望 75.0，实得 {r2['rate']}"
r3 = client.get("/api/v1/academic-affairs/stats/schedule", headers=H).json()["data"]
assert r3["unresolvedConflicts"] == 1, f"未解决冲突期望 1，实得 {r3['unresolvedConflicts']}"
r4 = client.get("/api/v1/academic-affairs/stats/graduation", headers=H).json()["data"]
assert r4["passed"] == 1 and r4["expected"] == 2, f"毕业资格通过数期望 1/2，实得 {r4}"
print("[7] 数值正确性核对 OK（挂科率50%/注册完成率75%/课表冲突1组/毕业资格1/2通过）")

fail_count = sum(1 for _, ok, _, _ in results if not ok)
print(f"\n=== 汇总：{len(results)} 项检查，{len(results) - fail_count} 通过，{fail_count} 失败 ===")
if fail_count:
    sys.exit(1)
print("ALL PASS")
