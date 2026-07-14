"""排课管理增强（/academic-affairs/scheduling/*）端点测试（SM-07 增强层）。

覆盖：排课规则保存/列表/删除、教师可用时间提交+学院采纳、批次全量冲突报告(HARD物理冲突/SOFT撞教师不可排课时段)、
学生越权403。复用既有课表批次/条目。MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_batch_with_conflict(db_mode):
    """建课表批次 + 2 个同教师同时段条目（HARD 冲突）。返回 batch_id。"""
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem, AaTerm
    db = get_sessionmaker()()
    term = AaTerm(tenant_id=TID, year_code="2024-2025", term_no=1, status="PUBLISHED", is_current=True)
    db.add(term); db.flush()
    b = AaScheduleBatch(tenant_id=TID, term_id=term.id, batch_name="排课冲突测试批次", status="DRAFT")
    db.add(b); db.flush()
    # 两条：同教师 counselor01、同周一第1节、周次重叠 → HARD TEACHER 冲突
    db.add_all([
        AaScheduleItem(tenant_id=TID, batch_id=b.id, course_name="高数", class_id=1, class_name="软件2401",
                       teacher_key="counselor01", teacher_name="王老师", weekday=1, slot_no=1,
                       start_week=1, end_week=18, week_parity="ALL", classroom_text="A101", status="EFFECTIVE"),
        AaScheduleItem(tenant_id=TID, batch_id=b.id, course_name="英语", class_id=2, class_name="软件2402",
                       teacher_key="counselor01", teacher_name="王老师", weekday=1, slot_no=1,
                       start_week=1, end_week=18, week_parity="ALL", classroom_text="A102", status="EFFECTIVE"),
    ])
    db.commit()
    ids = {"term": term.id, "batch": b.id}
    db.close()
    return ids


def test_sc1_rule_crud(client, db_mode):
    ids = _seed_batch_with_conflict(db_mode)
    admin = _hdr(client, "school_admin01")
    r = client.put(f"{BASE}/scheduling/rules", headers=admin,
                   json={"ruleKey": "maxDailySlots", "termId": str(ids["term"]), "ruleValue": {"max": 8}}).json()
    assert r["code"] == 0 and r["data"]["ruleKey"] == "maxDailySlots"
    rid = r["data"]["ruleId"]
    lst = client.get(f"{BASE}/scheduling/rules", headers=admin, params={"termId": str(ids["term"])}).json()
    assert any(x["ruleKey"] == "maxDailySlots" for x in lst["data"]["items"])
    assert client.delete(f"{BASE}/scheduling/rules/{rid}", headers=admin).json()["data"]["deleted"] is True


def test_sc2_teacher_availability_flow(client, db_mode):
    ids = _seed_batch_with_conflict(db_mode)
    teacher = _hdr(client, "counselor01")  # 以教职工身份提交本人不可排课时段
    admin = _hdr(client, "school_admin01")
    a = client.post(f"{BASE}/scheduling/teacher-availability", headers=teacher,
                    json={"termId": str(ids["term"]), "weekday": 1, "slotNo": 1, "reason": "固定教研会"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "PENDING"
    aid = a["data"]["availabilityId"]
    # 我提交的
    mine = client.get(f"{BASE}/scheduling/teacher-availability/my", headers=teacher, params={"termId": str(ids["term"])}).json()
    assert any(x["availabilityId"] == aid for x in mine["data"]["items"])
    # 学院采纳
    assert client.post(f"{BASE}/scheduling/teacher-availability/{aid}/review", headers=admin,
                       json={"action": "ADOPT"}).json()["data"]["status"] == "ADOPTED"


def test_sc3_conflict_report_hard(client, db_mode):
    ids = _seed_batch_with_conflict(db_mode)
    admin = _hdr(client, "school_admin01")
    rep = client.get(f"{BASE}/scheduling/batches/{ids['batch']}/conflict-report", headers=admin).json()
    assert rep["code"] == 0
    assert rep["data"]["hardCount"] == 1  # 同教师同时段
    assert rep["data"]["hardConflicts"][0]["dimension"] == "TEACHER"
    assert rep["data"]["canPrePublish"] is False


def test_sc4_conflict_report_soft(client, db_mode):
    ids = _seed_batch_with_conflict(db_mode)
    teacher = _hdr(client, "counselor01")
    admin = _hdr(client, "school_admin01")
    # 教师登记周一第1节不可排 + 学院采纳 → 该批次条目撞上 = SOFT
    a = client.post(f"{BASE}/scheduling/teacher-availability", headers=teacher,
                    json={"termId": str(ids["term"]), "weekday": 1, "slotNo": 1, "reason": "教研会"}).json()["data"]["availabilityId"]
    client.post(f"{BASE}/scheduling/teacher-availability/{a}/review", headers=admin, json={"action": "ADOPT"})
    rep = client.get(f"{BASE}/scheduling/batches/{ids['batch']}/conflict-report", headers=admin).json()["data"]
    assert rep["softCount"] >= 1 and rep["softConflicts"][0]["dimension"] == "TEACHER_UNAVAILABLE"


def test_sc5_student_forbidden(client, db_mode):
    _seed_batch_with_conflict(db_mode)
    stu = _stu_token("学生", "SC001")
    assert client.put(f"{BASE}/scheduling/rules", headers=stu, json={"ruleKey": "x"}).status_code == 403
