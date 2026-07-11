"""P1-Stage1 · 打卡台账 + 异常处理 owner 校验 + 补卡工作流（申请/审批/驳回/撤回）。

覆盖：台账数据范围 / 学生管理端403 / 越范围处理异常403 / 学生只能提交本人补卡 /
教师只能审批本人指导学生补卡(owner) / 异常处理+补卡审批写审计 / xlsx 导出权限。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"
MB = "/api/v1/mobile/internship"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _mentor(name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER", "tid": "x",
        "tenantId": str(TID), "activeContextId": "ctx", "currentRoleCode": "INTERN_MENTOR"})}


def _student(sno):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": f"学生{sno}", "studentNo": sno, "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID), "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (AttendanceException, InternshipCheckin, InternshipRecord, StudentProfile)
    db = get_sessionmaker()()
    ids = {}
    try:
        for no, name, adv, key in [("STU-A", "甲", "刘强", "a"), ("STU-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", status="ONBOARD", risk_level="NONE")
            db.add(r); db.flush()
            db.add(InternshipCheckin(tenant_id=TID, internship_id=r.id, checkin_date="2026-03-05",
                                     checkin_at=datetime.utcnow(), result="RECORDED"))
            ids[key] = r.id
            ids[f"{key}_no"] = no
        exc = AttendanceException(tenant_id=TID, internship_id=ids["a"], exception_type="MISSING",
                                  exception_date=datetime.utcnow(), status="PENDING_HANDLE")
        db.add(exc); db.flush()
        ids["exc_a"] = exc.id
        db.commit()
        return ids
    finally:
        db.close()


def _audit_count(target_type, target_id):
    from app.db.session import get_sessionmaker
    from app.models import InternshipAuditTrail
    db = get_sessionmaker()()
    try:
        from sqlalchemy import func, select
        return db.scalar(select(func.count()).select_from(InternshipAuditTrail).where(
            InternshipAuditTrail.target_type == target_type,
            InternshipAuditTrail.target_id == int(target_id))) or 0
    finally:
        db.close()


# ── 打卡台账 ──

def test_checkin_ledger_scope(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/checkins", headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/checkins", headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_checkin_student_403(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/checkins", headers=_student("STU-A")).status_code == 403


def test_checkin_export_perm_and_audit(client, db_mode):
    _seed(db_mode)
    assert client.post(f"{INT}/checkins/export", headers=_student("STU-A")).status_code == 403
    body = client.post(f"{INT}/checkins/export", headers=_admin(client)).json()
    assert body["code"] == 0 and body["data"]["filename"].endswith(".xlsx")


# ── 异常处理 owner ──

def test_exception_handle_owner(client, db_mode):
    ids = _seed(db_mode)
    payload = {"action": "REASONABLE", "comment": "已电话核实，属实合理"}
    # 王芳 处理 甲(刘强指导) 的异常 → 403
    r = client.post(f"{INT}/exceptions/{ids['exc_a']}/handle", headers=_mentor("王芳"), json=payload)
    assert r.status_code == 403
    # 刘强 处理自己学生异常 → 200 + 审计
    ok = client.post(f"{INT}/exceptions/{ids['exc_a']}/handle", headers=_mentor("刘强"), json=payload)
    assert ok.status_code == 200 and ok.json()["code"] == 0
    assert _audit_count("EXCEPTION", ids["exc_a"]) >= 1


def test_exception_batch_handle_and_export_selected(client, db_mode):
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AttendanceException
    db = get_sessionmaker()()
    try:
        exc2 = AttendanceException(tenant_id=TID, internship_id=ids["a"], exception_type="OUT_OF_RANGE",
                                   exception_date=datetime.utcnow(), status="PENDING_HANDLE")
        db.add(exc2); db.flush()
        ids["exc_b"] = exc2.id
        db.commit()
    finally:
        db.close()
    payload = {"ids": [str(ids["exc_a"]), str(ids["exc_b"])], "action": "REASONABLE",
               "comment": "经批量核实，打卡情况合理"}
    ok = client.post(f"{INT}/exceptions/batch-handle", json=payload, headers=_mentor("刘强"))
    assert ok.status_code == 200 and ok.json()["code"] == 0
    body = ok.json()["data"]
    assert body["processedCount"] == 2
    exp = client.post(f"{INT}/exceptions/export", json={"ids": [str(ids["exc_a"])]},
                      headers=_admin(client))
    assert exp.status_code == 200 and exp.json()["code"] == 0
    assert exp.json()["data"]["rowCount"] == 1


# ── 补卡工作流 ──

def test_makeup_apply_and_owner_review(client, db_mode):
    ids = _seed(db_mode)
    # 学生 STU-A 本人申请补卡
    ap = client.post(f"{MB}/makeup", headers=_student("STU-A"),
                     json={"checkinDate": "2026-03-06", "reason": "当日网络故障未能打卡"}).json()
    assert ap["code"] == 0 and ap["data"]["status"] == "PENDING"
    mid = ap["data"]["id"]
    # 管理端台账：管理员见 1，王芳(非本人指导)见 0，刘强见 1
    assert client.get(f"{INT}/makeups", headers=_admin(client)).json()["data"]["total"] == 1
    assert client.get(f"{INT}/makeups", headers=_mentor("王芳")).json()["data"]["total"] == 0
    assert client.get(f"{INT}/makeups", headers=_mentor("刘强")).json()["data"]["total"] == 1
    # 王芳 审批 → 403（owner）；刘强 审批通过 → 200 + 审计 + 补写打卡
    assert client.post(f"{INT}/makeups/{mid}/approve", headers=_mentor("王芳"), json={}).status_code == 403
    ok = client.post(f"{INT}/makeups/{mid}/approve", headers=_mentor("刘强"), json={}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"
    assert _audit_count("MAKEUP", mid) >= 1
    # 补写了 2026-03-06 的打卡（台账 total 由 1 变 2）
    assert client.get(f"{INT}/checkins", headers=_mentor("刘强")).json()["data"]["total"] == 2


def test_makeup_reject_requires_reason(client, db_mode):
    _seed(db_mode)
    mid = client.post(f"{MB}/makeup", headers=_student("STU-A"),
                      json={"checkinDate": "2026-03-07", "reason": "漏打卡"}).json()["data"]["id"]
    # 驳回不填原因 → 422/校验错
    bad = client.post(f"{INT}/makeups/{mid}/reject", headers=_mentor("刘强"), json={"comment": "x"})
    assert bad.status_code in (400, 422)
    ok = client.post(f"{INT}/makeups/{mid}/reject", headers=_mentor("刘强"),
                     json={"comment": "无有效证明，驳回"}).json()
    assert ok["data"]["status"] == "REJECTED"


def test_makeup_student_only_own(client, db_mode):
    _seed(db_mode)
    mid = client.post(f"{MB}/makeup", headers=_student("STU-A"),
                      json={"checkinDate": "2026-03-08", "reason": "漏打卡"}).json()["data"]["id"]
    # STU-B 撤回 STU-A 的补卡 → 403
    assert client.post(f"{MB}/makeup/{mid}/withdraw", headers=_student("STU-B")).status_code == 403
    # STU-A 撤回本人 → 200
    assert client.post(f"{MB}/makeup/{mid}/withdraw", headers=_student("STU-A")).json()["data"]["status"] == "WITHDRAWN"


def test_makeup_student_list_403_and_export(client, db_mode):
    _seed(db_mode)
    assert client.get(f"{INT}/makeups", headers=_student("STU-A")).status_code == 403
    assert client.post(f"{INT}/makeups/export", headers=_admin(client)).json()["data"]["filename"].endswith(".xlsx")
