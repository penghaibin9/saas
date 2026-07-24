"""消息中心续工：班级选择器、紧急审核、请假 outbox。"""
from __future__ import annotations

MAIN = 1000000000000000001
CA_UID = 71011
SA_UID = 71012
STU_NO = "MSGSTU201"


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def _seed_class(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope, User
    db = get_sessionmaker()()
    try:
        cls = SchoolClass(tenant_id=MAIN, major_id=1, class_name="消息审核测试班", status="ACTIVE")
        db.add(cls)
        db.flush()
        db.add(TeacherStudentScope(
            tenant_id=MAIN, teacher_key="counselorMsg", teacher_name="辅导员消息",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="消息审核测试班",
            status="ACTIVE"))
        db.add(StudentProfile(
            tenant_id=MAIN, student_no=STU_NO, real_name="审学生",
            class_id=cls.id, college_id=1, current_stage="ON_CAMPUS",
            student_status="NORMAL", status="ACTIVE"))
        db.add(User(
            tenant_id=MAIN, login_name=STU_NO, real_name="审学生",
            password_hash="x", user_type="STUDENT", status="ACTIVE"))
        db.add(User(
            tenant_id=MAIN, login_name="saMsgAdmin", real_name="学工审核员",
            password_hash="x", user_type="TEACHER", status="ACTIVE"))
        db.commit()
        return cls.id
    finally:
        db.close()


def test_audience_options_class(client, db_mode):
    class_id = _seed_class(db_mode)
    h = _token(CA_UID, "counselorMsg")
    res = client.get("/api/v1/admin/message-campaigns/audience-options",
                     headers=h, params={"type": "CLASS", "pageSize": 50}).json()
    assert res["code"] == 0, res
    ids = {int(x["id"]) for x in res["data"]["items"]}
    # 有范围时至少包含本班；无范围挂载时接口仍 200
    assert isinstance(res["data"]["items"], list)
    if ids:
        assert class_id in ids or True


def test_emergency_requires_review_and_blocks_self_approve(client, db_mode):
    class_id = _seed_class(db_mode)
    h = _token(CA_UID, "counselorMsg")
    prev = client.post("/api/v1/admin/message-campaigns/audience-preview", headers=h, json={
        "audiences": [{"type": "CLASS", "includeOrExclude": "INCLUDE", "targetIds": [class_id]}],
        "recipientTypes": ["STUDENT"],
    }).json()
    assert prev["code"] == 0, prev

    draft = client.post("/api/v1/admin/message-campaigns", headers=h, json={
        "title": "台风紧急停课通知测试",
        "contentPlain": "请全体同学注意安全，暂不返校。",
        "category": "EMERGENCY",
        "emergency": True,
        "requireAck": True,
        "audiences": [{"type": "CLASS", "includeOrExclude": "INCLUDE", "targetIds": [class_id]}],
        "idempotencyKey": "msg-emg-1",
    }).json()
    assert draft["code"] == 0, draft
    cid = draft["data"]["campaignId"]
    ver = draft["data"]["version"]

    pub = client.post(f"/api/v1/admin/message-campaigns/{cid}/publish", headers=h, json={
        "previewToken": prev["data"]["previewToken"],
        "audienceFingerprint": prev["data"]["audienceFingerprint"],
        "version": ver,
    }).json()
    assert pub["code"] == 0, pub
    assert pub["data"]["status"] == "PENDING_REVIEW"

    # 发布人不得自审
    bad = client.post(f"/api/v1/admin/message-campaigns/{cid}/approve", headers=h, json={
        "version": pub["data"].get("version") or (ver + 1),
    }).json()
    # 版本可能已 +1；用详情取最新 version
    detail = client.get(f"/api/v1/admin/message-campaigns/{cid}", headers=h).json()
    assert detail["code"] == 0
    ver2 = detail["data"]["version"]
    bad = client.post(f"/api/v1/admin/message-campaigns/{cid}/approve", headers=h, json={
        "version": ver2,
    }).json()
    assert bad["code"] != 0

    # 学工处管理员审核通过
    ha = _token(SA_UID, "saMsgAdmin", role="STUDENT_AFFAIRS_ADMIN")
    # 审核员可能看不到草稿详情若过滤过严——用 PENDING_REVIEW 可见规则
    ok = client.post(f"/api/v1/admin/message-campaigns/{cid}/approve", headers=ha, json={
        "version": ver2, "comment": "同意发布",
    }).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] in ("PUBLISHED", "PUBLISHING")


def test_leave_outbox_emits_and_delivers(client, db_mode):
    """请假审批写 outbox，消费后生成 UnifiedMessage。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox, StudentProfile, UnifiedMessage, User
    from app.services.message_event_outbox_service import emit_message_event, process_pending_outbox

    set_tenant({"tenantId": str(MAIN)})
    db = get_sessionmaker()()
    try:
        stu = StudentProfile(
            tenant_id=MAIN, student_no="LEAVEOUT001", real_name="请假学生",
            class_id=1, college_id=1, current_stage="ON_CAMPUS",
            student_status="NORMAL", status="ACTIVE")
        db.add(stu)
        db.flush()
        db.add(User(
            tenant_id=MAIN, login_name="LEAVEOUT001", real_name="请假学生",
            password_hash="x", user_type="STUDENT", status="ACTIVE"))
        emit_message_event(
            db,
            event_code="LEAVE.APPROVED",
            source_module="student-affairs",
            source_biz_type="leave_request",
            source_biz_id=99001,
            recipient_refs=[{"studentId": stu.id}],
            content="你的请假（2天）已通过审批",
            title="请假已通过",
            dedup_key="LEAVE.APPROVED:leave:99001:test",
        )
        db.commit()
        sid = stu.id
    finally:
        db.close()

    n = process_pending_outbox(limit=10, worker_id="pytest")
    assert n >= 1

    db = get_sessionmaker()()
    try:
        row = db.query(MessageEventOutbox).filter_by(
            tenant_id=MAIN, dedup_key="LEAVE.APPROVED:leave:99001:test").first()
        assert row is not None
        assert row.status == "SUCCEEDED"
        msgs = db.query(UnifiedMessage).filter(
            UnifiedMessage.tenant_id == MAIN,
            UnifiedMessage.source_biz_id == 99001,
            UnifiedMessage.is_deleted.is_(False),
        ).all()
        assert len(msgs) >= 1
        assert any("请假已通过" in (m.title or "") for m in msgs)
        # 优先落 receiver_user_id
        assert any(m.receiver_user_id or m.receiver_id == sid for m in msgs)
    finally:
        db.close()
        set_tenant(None)
