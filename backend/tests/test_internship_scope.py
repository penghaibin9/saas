"""P0-D · 岗位实习管理端数据范围（教师只看本人指导学生 / 管理员看全校 / 学生403 / 跨租户不可见）。

机制：resolve_teacher_scope —— INTERN_MENTOR 新数据按 advisor_user_id 收敛；历史记录尚未
回填账号 ID 时才按唯一姓名兼容；管理角色 ADMIN_TENANT 看全校；学生由 require_staff 门禁 403。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
OTHER_TID = 1000000000000000002
BASE = "/api/v1/internship/intern-students"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student():
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-STU", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """两名学生 + 两条实习记录：advisor=刘强 / advisor=王芳；外租户一条（跨租户不可见）。"""
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        for tid, no, name, adv, key in [
            (TID, "SCOPE-A", "甲同学", "刘强", "a"),
            (TID, "SCOPE-B", "乙同学", "王芳", "b"),
            (OTHER_TID, "SCOPE-X", "外校生", "刘强", "x"),
        ]:
            s = StudentProfile(tenant_id=tid, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=tid, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE",
                                 intern_start_date=datetime(2026, 3, 2))
            db.add(r); db.flush()
            ids[key] = r.id
        db.commit()
        return ids
    finally:
        db.close()


def test_admin_sees_all(client, db_mode):
    _seed(db_mode)
    body = client.get(BASE, headers=_admin(client)).json()
    assert body["code"] == 0
    # 管理员看本租户全校（2 条，不含外租户）
    assert body["data"]["total"] == 2


def test_mentor_sees_only_own(client, db_mode):
    _seed(db_mode)
    liu = client.get(BASE, headers=_mentor("刘强")).json()
    assert liu["data"]["total"] == 1
    assert liu["data"]["items"][0]["advisorName"] == "刘强"
    wang = client.get(BASE, headers=_mentor("王芳")).json()
    assert wang["data"]["total"] == 1
    assert wang["data"]["items"][0]["advisorName"] == "王芳"


def test_mentor_cannot_see_other_mentor_detail(client, db_mode):
    ids = _seed(db_mode)
    # 刘强 访问 王芳 的学生详情 → 403
    r = client.get(f"{BASE}/{ids['b']}", headers=_mentor("刘强"))
    assert r.status_code == 403
    # 刘强 访问自己学生详情 → 200
    ok = client.get(f"{BASE}/{ids['a']}", headers=_mentor("刘强"))
    assert ok.status_code == 200 and ok.json()["code"] == 0


def test_student_forbidden(client, db_mode):
    _seed(db_mode)
    assert client.get(BASE, headers=_student()).status_code == 403


def test_unauthenticated_401(client):
    assert client.get(BASE).status_code == 401


def test_cross_tenant_invisible(client, db_mode):
    _seed(db_mode)
    # 本租户管理员看不到外租户那条（外校生 SCOPE-X）
    body = client.get(BASE + "?keyword=外校生", headers=_admin(client)).json()
    assert body["data"]["total"] == 0


# ═══════════ 余项：internship_service（看板/周报/打卡异常/风险）+ 匹配 意向 ═══════════

INT = "/api/v1/internship"


def _seed_full(db_mode):
    """记录 A(刘强)/B(王芳) 各挂 1 条 周报待批 / 打卡异常待核实 / 风险待处理 / 意向。"""
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (AttendanceException, InternshipIntention, InternshipRecord,
                            RiskRecord, StudentProfile, WeeklyReport)
    db = get_sessionmaker()()
    try:
        for no, name, adv in [("FULL-A", "甲", "刘强"), ("FULL-B", "乙", "王芳")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 status="ONBOARD", risk_level="HIGH")
            db.add(r); db.flush()
            db.add(AttendanceException(tenant_id=TID, internship_id=r.id, exception_type="OUT_OF_RANGE",
                                       exception_date=datetime.utcnow(), status="PENDING_HANDLE"))
            db.add(WeeklyReport(tenant_id=TID, internship_id=r.id, week_number=3, word_count=800,
                                report_version=1, submitted_at=datetime.utcnow(), status="PENDING_REVIEW"))
            db.add(RiskRecord(tenant_id=TID, internship_id=r.id, risk_code="INT-R07",
                              risk_title="打卡异常", risk_level="HIGH", source_module="system",
                              status="PENDING_HANDLE"))
            db.add(InternshipIntention(tenant_id=TID, record_id=r.id, student_id=s.id, status="SUBMITTED"))
        db.commit()
    finally:
        db.close()


def test_dashboard_scope(client, db_mode):
    _seed_full(db_mode)
    adm = client.get(f"{INT}/dashboard", headers=_admin(client)).json()["data"]
    liu = client.get(f"{INT}/dashboard", headers=_mentor("刘强")).json()["data"]
    amap = {s["label"]: s["value"] for s in adm["stats"]}
    lmap = {s["label"]: s["value"] for s in liu["stats"]}
    # 管理员：待批阅周报/待处理异常/风险各 2；刘强：各 1（仅本人指导）
    assert amap["待批阅周报"] == "2" and lmap["待批阅周报"] == "1"
    assert amap["待处理打卡异常"] == "2" and lmap["待处理打卡异常"] == "1"
    assert amap["风险学生"] == "2" and lmap["风险学生"] == "1"


def test_weekly_list_scope(client, db_mode):
    _seed_full(db_mode)
    assert client.get(f"{INT}/reports", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/reports", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_exception_list_scope(client, db_mode):
    _seed_full(db_mode)
    assert client.get(f"{INT}/exceptions", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/exceptions", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_risk_list_scope(client, db_mode):
    _seed_full(db_mode)
    assert client.get(f"{INT}/risks", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/risks", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_match_intentions_scope(client, db_mode):
    _seed_full(db_mode)
    assert client.get(f"{INT}/match/intentions", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/match/intentions", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_legacy_students_list_scope(client, db_mode):
    _seed_full(db_mode)
    assert client.get(f"{INT}/students", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/students", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_service_endpoints_student_403(client, db_mode):
    for ep in ("/dashboard", "/students", "/reports", "/exceptions", "/risks", "/match/intentions"):
        assert client.get(f"{INT}{ep}", headers=_student()).status_code == 403
