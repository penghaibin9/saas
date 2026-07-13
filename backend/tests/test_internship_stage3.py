"""P1-Stage3 + 欠账修复 · 风险处置闭环 / 实习请假 / 指导转风险 / 附件 file_id 校验。

- 风险处置：handle→follow→escalate→close 状态机；跨导师 owner 403；数据范围收敛；审计。
- 指导转风险：guidance toRisk=True 自动生成 t_risk_record 风险单（source=guidance）。
- 附件：无效 fileId 被拒 400；有效 fileId（预置 t_file_object）可挂载并在详情还原。
- 请假：学生申请/撤回（mobile）+ 教师审批（owner 403 + 数据范围）。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"


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


def _student(sno, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{sno}", "realName": "学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(tid), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """记录 A(刘强,SNO=S3-A) / B(王芳,SNO=S3-B)。返回 {rec_a, rec_b}。"""
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        for no, name, adv, key in [("S3-A", "甲", "刘强", "a"), ("S3-B", "乙", "王芳", "b")]:
            s = StudentProfile(tenant_id=TID, student_no=no, real_name=name,
                               current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(s); db.flush()
            r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name=adv,
                                 enterprise_name="测试企业", position_name="实习生",
                                 status="ONBOARD", risk_level="NONE")
            db.add(r); db.flush()
            ids[f"rec_{key}"] = r.id
            ids[f"stu_{key}"] = s.id
        db.commit()
        return ids
    finally:
        db.close()


def _seed_risk(rec_id, level="MEDIUM"):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, RiskRecord
    db = get_sessionmaker()()
    try:
        rec = db.get(InternshipRecord, rec_id)
        r = RiskRecord(tenant_id=TID, internship_id=rec.id, risk_code="INT-R07",
                       risk_title="打卡异常", risk_level=level, source_module="system",
                       status="PENDING_HANDLE")
        db.add(r); db.flush(); rid = r.id; db.commit()
        return rid
    finally:
        db.close()


# ══════════════ 风险处置闭环 ══════════════

def test_risk_lifecycle_handle_follow_escalate_close(client, db_mode):
    ids = _seed(db_mode)
    rid = _seed_risk(ids["rec_a"])
    h = _mentor("刘强")
    # 受理 PENDING→PROCESSING
    r1 = client.post(f"{INT}/risks/{rid}/handle", json={"comment": "已联系企业核实", "ownerName": "刘强"}, headers=h)
    assert r1.status_code == 200 and r1.json()["data"]["status"] == "PROCESSING"
    # 跟进
    r2 = client.post(f"{INT}/risks/{rid}/follow", json={"note": "企业反馈已到岗"}, headers=h)
    assert r2.status_code == 200
    # 升级 MEDIUM→HIGH
    r3 = client.post(f"{INT}/risks/{rid}/escalate", json={"level": "HIGH", "note": "连续缺勤"}, headers=h)
    assert r3.status_code == 200 and r3.json()["data"]["riskLevel"] == "HIGH"
    # 降级/平级拒绝（note≥2 先过校验，再命中状态冲突 409）
    bad = client.post(f"{INT}/risks/{rid}/escalate", json={"level": "MEDIUM", "note": "尝试降级"}, headers=h)
    assert bad.status_code == 409
    # 关闭
    r4 = client.post(f"{INT}/risks/{rid}/close", json={"result": "RESOLVED", "comment": "学生已恢复正常打卡"}, headers=h)
    assert r4.status_code == 200 and r4.json()["data"]["status"] == "CLOSED"
    # 详情含全链审计
    detail = client.get(f"{INT}/risks/{rid}", headers=h).json()["data"]
    actions = [t["action"] for t in detail["auditTrail"]]
    assert {"HANDLE", "FOLLOW", "ESCALATE", "CLOSE"} <= set(actions)


def test_risk_owner_and_scope(client, db_mode):
    ids = _seed(db_mode)
    rid_b = _seed_risk(ids["rec_b"])  # 王芳的学生
    # 刘强 受理 王芳 学生风险 → 403（comment≥5 先过校验，再命中 owner）
    assert client.post(f"{INT}/risks/{rid_b}/handle", json={"comment": "越权受理测试例"}, headers=_mentor("刘强")).status_code == 403
    # 刘强 详情越权 → 403
    assert client.get(f"{INT}/risks/{rid_b}", headers=_mentor("刘强")).status_code == 403
    # 数据范围：管理员看 1，刘强看 0
    assert client.get(f"{INT}/risks", headers=_admin(client)).json()["data"]["total"] == 1
    assert client.get(f"{INT}/risks", headers=_mentor("刘强")).json()["data"]["total"] == 0


def test_risk_handle_comment_required(client, db_mode):
    ids = _seed(db_mode)
    rid = _seed_risk(ids["rec_a"])
    assert client.post(f"{INT}/risks/{rid}/handle", json={"comment": "短"}, headers=_mentor("刘强")).status_code == 400


def test_risk_student_forbidden(client, db_mode):
    ids = _seed(db_mode)
    rid = _seed_risk(ids["rec_a"])
    assert client.get(f"{INT}/risks", headers=_student("S3-A")).status_code == 403
    assert client.post(f"{INT}/risks/{rid}/handle", json={"comment": "aaaaa"}, headers=_student("S3-A")).status_code == 403


# ══════════════ 指导转风险联动 ══════════════

def test_guidance_spawns_risk(client, db_mode):
    ids = _seed(db_mode)
    h = _mentor("刘强")
    # 无转风险：不产生风险单
    client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "常规指导"}, headers=h)
    assert client.get(f"{INT}/risks", headers=h).json()["data"]["total"] == 0
    # 转风险：自动生成 1 条 source=guidance 风险单
    res = client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "发现安全隐患",
                                                "topic": "安全", "toRisk": True, "notifyCounselor": True}, headers=h)
    assert res.status_code == 200 and res.json()["data"]["riskId"]
    rid = res.json()["data"]["riskId"]
    assert client.get(f"{INT}/risks", headers=h).json()["data"]["total"] == 1
    # 详情验证来源为 guidance（列表沿用旧 svc 形状，来源字段在详情）
    detail = client.get(f"{INT}/risks/{rid}", headers=h).json()["data"]
    assert detail["sourceModule"] == "guidance" and detail["riskCode"] == "INT-GUIDE"


# ══════════════ 附件 file_id 校验 ══════════════

def test_attachment_invalid_fileid_rejected(client, db_mode):
    ids = _seed(db_mode)
    r = client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "带附件",
                                              "fileId": "999999"}, headers=_mentor("刘强"))
    assert r.status_code == 400  # 无效附件 → VALIDATION_ERROR


def test_attachment_valid_fileid_resolved(client, db_mode):
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    try:
        f = FileObject(tenant_id=TID, file_key="20260709/abc.pdf", file_name="实习证明.pdf",
                       ext="pdf", size_bytes=1234, biz_type="ATTACHMENT", status="STORED")
        db.add(f); db.flush(); fid = str(f.id); db.commit()
    finally:
        db.close()
    h = _mentor("刘强")
    res = client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "带附件",
                                                "fileId": fid}, headers=h)
    assert res.status_code == 200
    detail = client.get(f"{INT}/guidances/{res.json()['data']['id']}", headers=h).json()["data"]
    assert detail["attachment"] and detail["attachment"]["fileName"] == "实习证明.pdf"


# ══════════════ 实习请假 ══════════════

def test_leave_apply_withdraw_and_review(client, db_mode):
    ids = _seed(db_mode)
    # 学生 S3-A 申请
    ap = client.post("/api/v1/mobile/internship/leave",
                     json={"leaveType": "SICK", "startDate": "2026-07-10", "endDate": "2026-07-12",
                           "reason": "感冒发烧需就医"}, headers=_student("S3-A"))
    assert ap.status_code == 200 and ap.json()["data"]["days"] == 3
    lid = ap.json()["data"]["id"]
    # 教师数据范围：刘强看 1，王芳看 0
    assert client.get(f"{INT}/leaves", headers=_mentor("刘强")).json()["data"]["total"] == 1
    assert client.get(f"{INT}/leaves", headers=_mentor("王芳")).json()["data"]["total"] == 0
    # 越权审批：王芳审批刘强学生请假 → 403
    assert client.post(f"{INT}/leaves/{lid}/review", json={"action": "APPROVE"}, headers=_mentor("王芳")).status_code == 403
    # 刘强审批通过
    ok = client.post(f"{INT}/leaves/{lid}/review", json={"action": "APPROVE"}, headers=_mentor("刘强"))
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "APPROVED"


def test_leave_reject_reason_required_and_end_before_start(client, db_mode):
    ids = _seed(db_mode)
    # 结束早于开始 → 400
    bad = client.post("/api/v1/mobile/internship/leave",
                      json={"startDate": "2026-07-12", "endDate": "2026-07-10", "reason": "事假"},
                      headers=_student("S3-A"))
    assert bad.status_code == 400
    ap = client.post("/api/v1/mobile/internship/leave",
                     json={"startDate": "2026-07-10", "endDate": "2026-07-10", "reason": "家中有事"},
                     headers=_student("S3-A")).json()["data"]
    # 驳回需原因≥5字
    assert client.post(f"{INT}/leaves/{ap['id']}/review", json={"action": "REJECT", "comment": "no"},
                       headers=_mentor("刘强")).status_code == 400


def test_leave_approve_writes_leave_checkins(client, db_mode):
    ids = _seed(db_mode)
    ap = client.post("/api/v1/mobile/internship/leave",
                     json={"startDate": "2026-07-10", "endDate": "2026-07-12", "reason": "感冒发烧就医"},
                     headers=_student("S3-A")).json()["data"]
    ok = client.post(f"{INT}/leaves/{ap['id']}/review", json={"action": "APPROVE"}, headers=_mentor("刘强"))
    assert ok.status_code == 200 and ok.json()["data"]["leaveDays"] == 3
    # 打卡台账显示这 3 天为「请假」
    checkins = client.get(f"{INT}/checkins", headers=_mentor("刘强")).json()["data"]["items"]
    leave_days = [c for c in checkins if c["result"] == "LEAVE"]
    assert len(leave_days) == 3 and all(c["resultLabel"] == "请假" for c in leave_days)


def test_guidance_notify_counselor_sends_message(client, db_mode):
    ids = _seed(db_mode)
    # 给学生甲(rec_a/stu_a)配一个带辅导员的班级
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, UnifiedMessage
    db = get_sessionmaker()()
    try:
        cls = SchoolClass(tenant_id=TID, major_id=1, class_name="测试2401班", counselor_id=88888)
        db.add(cls); db.flush()
        db.get(StudentProfile, ids["stu_a"]).class_id = cls.id
        db.commit()
    finally:
        db.close()
    # 指导转风险 + 通知辅导员
    res = client.post(f"{INT}/guidances", json={"internshipId": str(ids["rec_a"]), "content": "发现安全隐患",
                                                "topic": "安全", "toRisk": True, "notifyCounselor": True},
                      headers=_mentor("刘强"))
    assert res.status_code == 200
    db = get_sessionmaker()()
    try:
        from sqlalchemy import select
        msgs = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TID, UnifiedMessage.receiver_id == 88888,
            UnifiedMessage.source_module == "internship")).all()
        assert len(msgs) == 1 and "实习风险提醒" in msgs[0].title
    finally:
        db.close()


def test_leave_student_withdraw(client, db_mode):
    ids = _seed(db_mode)
    ap = client.post("/api/v1/mobile/internship/leave",
                     json={"startDate": "2026-07-10", "endDate": "2026-07-11", "reason": "个人事务处理"},
                     headers=_student("S3-A")).json()["data"]
    w = client.post(f"/api/v1/mobile/internship/leave/{ap['id']}/withdraw", headers=_student("S3-A"))
    assert w.status_code == 200 and w.json()["data"]["status"] == "WITHDRAWN"


def test_leave_overdue_creates_one_risk_and_student_can_return(client, db_mode):
    _seed(db_mode)
    student = _student("S3-A")
    apply = client.post("/api/v1/mobile/internship/leave", json={
        "startDate": "2026-07-01", "endDate": "2026-07-02", "reason": "病后恢复观察",
    }, headers=student)
    assert apply.status_code == 200
    leave_id = apply.json()["data"]["id"]
    assert client.post(f"{INT}/leaves/{leave_id}/review", json={"action": "APPROVE"},
                       headers=_mentor("刘强")).status_code == 200
    refreshed = client.post(f"{INT}/leaves/overdue/refresh", headers=_admin(client)).json()["data"]
    assert refreshed["markedOverdue"] == 1 and refreshed["risksCreated"] == 1
    # Idempotent recurring invocation must not create another risk card.
    repeat = client.post(f"{INT}/leaves/overdue/refresh", headers=_admin(client)).json()["data"]
    assert repeat["markedOverdue"] == 0 and repeat["risksCreated"] == 0
    returned = client.post(f"/api/v1/mobile/internship/leave/{leave_id}/return",
                           json={"returnNote": "已于今日返岗"}, headers=student)
    assert returned.status_code == 200 and returned.json()["data"] == {
        "id": leave_id, "status": "RETURNED", "statusLabel": "已销假", "wasOverdue": True,
    }
    detail = client.get(f"{INT}/leaves/{leave_id}", headers=_mentor("刘强")).json()["data"]
    assert detail["overdue"] is False and detail["returnNote"] == "已于今日返岗"
    assert {x["action"] for x in detail["auditTrail"]} >= {"APPLY", "REVIEW_APPROVE", "MARK_OVERDUE", "RETURN"}
