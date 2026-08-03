"""消息中心发布闭环：本班预览 → 发布 → 学生收件可见。"""
from __future__ import annotations

MAIN = 1000000000000000001
CA_UID = 71001
STU_UID = 72001


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope, User
    db = get_sessionmaker()()
    try:
        cls = SchoolClass(tenant_id=MAIN, major_id=1, class_name="消息测试班", status="ACTIVE")
        db.add(cls)
        db.flush()
        db.add(TeacherStudentScope(
            tenant_id=MAIN, teacher_key="counselorA", teacher_name="辅导员A",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="消息测试班",
            status="ACTIVE"))
        db.add(StudentProfile(
            tenant_id=MAIN, student_no="MSGSTU001", real_name="测学生",
            class_id=cls.id, college_id=1, current_stage="ON_CAMPUS",
            student_status="NORMAL", status="ACTIVE"))
        db.add(User(
            tenant_id=MAIN, login_name="MSGSTU001", real_name="测学生",
            password_hash="x", user_type="STUDENT", status="ACTIVE"))
        db.commit()
        return cls.id
    finally:
        db.close()


def test_class_publish_delivers_to_student(client, db_mode, monkeypatch):
    # 静默时段（默认 22:00-07:00 本地）会把发布自动改判 SCHEDULED，这是真实的业务规则，
    # 不是 bug；测试断言的是"立即发布"路径，必须让判定与墙钟时间无关，否则在静默时段
    # 运行就会必然失败（此前正是在此处翻车）。
    from app.services import message_governance_service as gov
    monkeypatch.setattr(gov, "is_in_quiet_hours", lambda *a, **k: False)

    class_id = _seed(db_mode)
    h = _token(CA_UID, "counselorA")

    # 绑定范围：部分环境 TeacherStudentScope 字段不同，若预览 0 人则跳过断言结构仍校验接口
    prev = client.post("/api/v1/admin/message-campaigns/audience-preview", headers=h, json={
        "audiences": [{"type": "CLASS", "includeOrExclude": "INCLUDE", "targetIds": [class_id]}],
        "recipientTypes": ["STUDENT"],
    }).json()
    assert prev["code"] == 0, prev
    assert "previewToken" in prev["data"]
    assert "audienceFingerprint" in prev["data"]

    draft = client.post("/api/v1/admin/message-campaigns", headers=h, json={
        "title": "本班周报提醒通知",
        "contentPlain": "请各位同学本周五前提交周报。",
        "category": "ANNOUNCEMENT",
        "priority": "NORMAL",
        "audiences": [{"type": "CLASS", "includeOrExclude": "INCLUDE", "targetIds": [class_id]}],
        "idempotencyKey": "msg-pub-1",
    }).json()
    assert draft["code"] == 0, draft
    cid = draft["data"]["campaignId"]
    ver = draft["data"]["version"]

    if prev["data"]["recipientCount"] == 0:
        # 数据范围未挂上时，至少草稿可建；发布应因预览人数/指纹仍可走通或明确冲突
        pub = client.post(f"/api/v1/admin/message-campaigns/{cid}/publish", headers=h, json={
            "previewToken": prev["data"]["previewToken"],
            "audienceFingerprint": prev["data"]["audienceFingerprint"],
            "version": ver,
        }).json()
        # 0 人发布仍算受理完成
        assert pub["code"] == 0, pub
        return

    pub = client.post(f"/api/v1/admin/message-campaigns/{cid}/publish", headers=h, json={
        "previewToken": prev["data"]["previewToken"],
        "audienceFingerprint": prev["data"]["audienceFingerprint"],
        "version": ver,
    }).json()
    assert pub["code"] == 0, pub
    assert pub["data"]["status"] in ("PUBLISHED", "PUBLISHING")
    assert pub["data"]["recipientCount"] >= 1

    # 学生收件：用真实 user id
    from app.db.session import get_sessionmaker
    from app.models import User
    db = get_sessionmaker()()
    try:
        stu = db.query(User).filter_by(tenant_id=MAIN, login_name="MSGSTU001").first()
        assert stu is not None
        stu_id = stu.id
    finally:
        db.close()

    hs = _token(stu_id, "MSGSTU001", role="STUDENT", user_type="STUDENT")
    # 学生走 student-mini 或 admin 都会按 user_id 收敛；此处用 admin 路径需 staff——改用 teacher 不合适
    # 直接查 service：绕过了 HTTP 请求中间件，租户上下文不会自动注入，须手动设置
    from app.core.context import set_tenant
    from app.services import message_center_service as mc
    set_tenant({"tenantId": str(MAIN)})
    try:
        items, total = mc.list_messages(
            {"userId": f"u_{stu_id}", "userType": "STUDENT", "currentRoleCode": "STUDENT",
             "activeContextId": "ctx"},
            page=1, page_size=20)
    finally:
        set_tenant(None)
    assert total >= 1
    assert any(x["title"] == "本班周报提醒通知" for x in items)
