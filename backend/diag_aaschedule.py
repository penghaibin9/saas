"""课表管理 Tier1 R2（班级课表/教师课表/教室课表/课表发布/课表导出）—— 独立 SQLite 自测脚本。

用法：VENV_PYTHON diag_aaschedule.py
仅用于本轮子智能体自测证据留存，非正式 pytest 用例；正式回归由总控后续在 MySQL 环境统一执行。
不连共享 MySQL 测试库（DATABASE_URL 指向本地 sqlite 文件）。
"""
from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "true"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./diag_aaschedule.db"
os.environ["TEST_DATABASE_URL"] = "sqlite+pysqlite:///./diag_aaschedule.db"
os.environ["MOCK_LOGIN_ENABLED"] = "true"

if os.path.exists("./diag_aaschedule.db"):
    os.remove("./diag_aaschedule.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

from app.db.base import metadata  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

engine = get_engine()
metadata.create_all(bind=engine)
print("[1] metadata.create_all OK（含新表 t_aa_schedule_publish）")

TID = 1000000000000000001

from app.models import (  # noqa: E402
    AaClassroom, AaScheduleBatch, AaScheduleItem, AaTerm, College, Major, SchoolClass,
)
from app.models.teacher_scope import TeacherStudentScope  # noqa: E402

db = get_sessionmaker()()

college = College(tenant_id=TID, college_name="软件学院", code="RJ", status="ACTIVE")
db.add(college)
db.flush()

major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", code="RJ01")
db.add(major)
db.flush()

class_a = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401班", class_code="RJ2401",
                      class_status="NORMAL", status="ACTIVE")
class_b = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2402班", class_code="RJ2402",
                      class_status="NORMAL", status="ACTIVE")
db.add_all([class_a, class_b])
db.flush()

term = AaTerm(tenant_id=TID, year_code="2025-2026", term_no=1, term_name="2025秋",
             is_current=True, status="PUBLISHED")
db.add(term)
db.flush()

room = AaClassroom(tenant_id=TID, building_code="A", building_name="A教学楼", room_code="101",
                   capacity=60, room_type="LECTURE", status="AVAILABLE")
db.add(room)
db.flush()

# 辅导员 counselor01 授权范围 = 软件2401班（class_a），2402班（class_b）不授权
scope = TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                            role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2401班", status="ACTIVE")
db.add(scope)
db.flush()

batch = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="2025秋课表批次", status="DRAFT")
db.add(batch)
db.flush()

item = AaScheduleItem(tenant_id=TID, batch_id=batch.id, course_name="高等数学",
                      class_id=class_a.id, class_name=class_a.class_name,
                      teacher_key="academic01", teacher_name="赵敏",
                      weekday=1, slot_no=1, start_week=1, end_week=16, week_parity="ALL",
                      classroom_text="A教学楼101", status="EFFECTIVE")
db.add(item)
db.commit()
class_a_id, class_b_id, batch_id, room_id = class_a.id, class_b.id, batch.id, room.id
db.close()
print("[2] 种子数据写入 OK（2 班级/1 教室/1 批次课表项/辅导员本班授权）")


def login(login_name):
    r = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"})
    assert r.status_code == 200, f"mock-login({login_name}) 失败: {r.status_code} {r.text}"
    token = r.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


H_ADMIN = login("school_admin01")
H_COUNSELOR = login("counselor01")
H_TEACHER = login("academic01")
print("[3] mock-login(school_admin01/counselor01/academic01) OK")

results = []


def check(name, method, path, expect_status, headers, params=None, body=None, expect_code=None):
    fn = client.get if method == "GET" else client.post
    kwargs = {"headers": headers}
    if params is not None:
        kwargs["params"] = params
    if body is not None:
        kwargs["json"] = body
    r = fn(path, **kwargs)
    ok = r.status_code == expect_status
    detail = ""
    if ok and expect_code is not None:
        try:
            d = r.json()
            if d.get("code") != expect_code:
                ok = False
                detail = f"expect code={expect_code} got={d.get('code')}"
        except Exception as e:  # noqa: BLE001
            ok = False
            detail = f"parse error: {e}"
    if not ok and not detail:
        detail = r.text[:300]
    results.append((name, ok, r.status_code, detail))
    print(f"  {'OK ' if ok else 'FAIL'} {name} [{r.status_code}] {detail}")
    return r


print("[4] 发布前：DRAFT 批次无已发布课表，班级课表应走空态：")
r0 = check("发布前-班级课表空态", "GET", f"/api/v1/academic-affairs/schedule/class/{class_a_id}", 200, H_ADMIN)
assert r0.json()["data"]["items"] == [], "发布前不应有课表项"
assert r0.json()["data"]["note"], "发布前应有空态提示"

print("[5] 预发布 + 发布：")
check("预发布", "POST", f"/api/v1/academic-affairs/schedule-batches/{batch_id}/pre-publish", 200, H_ADMIN)
check("发布", "POST", f"/api/v1/academic-affairs/schedule-batches/{batch_id}/publish", 200, H_ADMIN)

print("[6] 班级课表（正向 + 越权 + 教务处广域）：")
r1 = check("辅导员查本班-应200", "GET", f"/api/v1/academic-affairs/schedule/class/{class_a_id}", 200, H_COUNSELOR)
assert len(r1.json()["data"]["items"]) == 1, "本班应有 1 条课表项"
check("辅导员查非本班-应403002", "GET", f"/api/v1/academic-affairs/schedule/class/{class_b_id}", 403, H_COUNSELOR,
     expect_code=403002)
check("教务处广域查任意班-应200", "GET", f"/api/v1/academic-affairs/schedule/class/{class_b_id}", 200, H_ADMIN)
check("班级不存在-应404", "GET", "/api/v1/academic-affairs/schedule/class/999999", 404, H_ADMIN)

print("[7] 教师课表（本人 + 越权 + 教务处广域 + 周次过滤）：")
r2 = check("教师查本人-应200", "GET", "/api/v1/academic-affairs/schedule/teacher/academic01", 200, H_TEACHER)
assert len(r2.json()["data"]["items"]) == 1
assert r2.json()["data"]["weeklyHours"] == 1
check("教师查他人-应403002", "GET", "/api/v1/academic-affairs/schedule/teacher/other_teacher", 403, H_TEACHER,
     expect_code=403002)
check("教务处查任意教师-应200", "GET", "/api/v1/academic-affairs/schedule/teacher/academic01", 200, H_ADMIN)
r3 = check("周次过滤-命中范围内(第5周)-应200且有数据", "GET", "/api/v1/academic-affairs/schedule/teacher/academic01",
          200, H_ADMIN, params={"week": 5})
assert len(r3.json()["data"]["items"]) == 1, "第5周在1-16周范围内应命中"
r4 = check("周次过滤-命中范围外(第20周)-应200且无数据", "GET", "/api/v1/academic-affairs/schedule/teacher/academic01",
          200, H_ADMIN, params={"week": 20})
assert len(r4.json()["data"]["items"]) == 0, "第20周超出1-16周范围应为空"

print("[8] 教室课表（教务处只读 + 辅导员无权限）：")
r5 = check("教务处查教室-应200", "GET", f"/api/v1/academic-affairs/schedule/room/{room_id}", 200, H_ADMIN)
assert len(r5.json()["data"]["items"]) == 1
check("辅导员查教室-无classroom.view权限-应403001", "GET", f"/api/v1/academic-affairs/schedule/room/{room_id}",
     403, H_COUNSELOR, expect_code=403001)
check("教室不存在-应404", "GET", "/api/v1/academic-affairs/schedule/room/999999", 404, H_ADMIN)

print("[9] 课表发布记录（发布+作废两条流水）：")
r6 = check("发布记录-应含PUBLISH", "GET", "/api/v1/academic-affairs/schedule/publish-records", 200, H_ADMIN)
recs = r6.json()["data"]["items"]
assert any(x["action"] == "PUBLISH" and x["batchId"] == str(batch_id) for x in recs), "应含本次发布记录"
check("作废重发", "POST", f"/api/v1/academic-affairs/schedule-batches/{batch_id}/void-reissue", 200, H_ADMIN,
     body={"reason": "教学计划调整需重排"})
r7 = check("发布记录-应含VOID_REISSUE", "GET", "/api/v1/academic-affairs/schedule/publish-records", 200, H_ADMIN)
recs2 = r7.json()["data"]["items"]
assert any(x["action"] == "VOID_REISSUE" for x in recs2), "应含作废记录"
print(f"  发布记录条数={len(recs2)}（预期>=2）")
assert len(recs2) >= 2

print("[10] 课表导出（xlsx 二进制 + 校验错误）：")
r8 = check("导出班级课表-应200", "POST", "/api/v1/academic-affairs/schedule/export", 200, H_ADMIN,
          body={"scope": "CLASS", "identifier": str(class_a_id), "purpose": "自测导出验证留痕"})
assert r8.headers["content-type"].startswith("application/vnd.openxmlformats"), "应返回 xlsx MIME"
assert len(r8.content) > 500, "xlsx 内容不应为空"
check("导出-用途过短-应400", "POST", "/api/v1/academic-affairs/schedule/export", 400, H_ADMIN,
     body={"scope": "CLASS", "identifier": str(class_a_id), "purpose": "短"})
check("导出-scope非法-应400", "POST", "/api/v1/academic-affairs/schedule/export", 400, H_ADMIN,
     body={"scope": "BAD", "identifier": "1", "purpose": "自测导出验证留痕"})
check("导出-辅导员导教师课表-无export权限-应403001", "POST", "/api/v1/academic-affairs/schedule/export", 403, H_COUNSELOR,
     body={"scope": "TEACHER", "identifier": "academic01", "purpose": "自测导出验证留痕"}, expect_code=403001)

print("[11] 无 token 访问：")
check("无token-应401", "GET", f"/api/v1/academic-affairs/schedule/class/{class_a_id}", 401, None)

failed = [x for x in results if not x[1]]
print("=" * 60)
print(f"总计 {len(results)} 项，失败 {len(failed)} 项")
if failed:
    for name, _ok, status, detail in failed:
        print(f"  FAIL: {name} [{status}] {detail}")
    raise SystemExit(1)
print("全部通过（含 assert 数值/内容核对）")
