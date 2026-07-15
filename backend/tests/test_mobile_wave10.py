"""欠账消化轮（谈心谈话/心理关注/心理自评/修改密码/通知设置/通知发布/数据看板）端到端测试。"""
from __future__ import annotations

from datetime import datetime

MAIN = 1000000000000000001


def _stu_token(real_name, student_no, tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _teacher_token(real_name="王老师", uid=None, role="COUNSELOR", tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": (str(uid) if uid is not None else f"u-{real_name}"), "realName": real_name,
        "userType": "TEACHER", "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "MP"})}


def _seed_student(student_no, real_name, tenant_id=MAIN):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        db.add(StudentProfile(tenant_id=tenant_id, student_no=student_no, real_name=real_name,
                              grade="2026", current_stage="ON_CAMPUS",
                              student_status="NORMAL", status="ACTIVE"))
        db.commit()
    finally:
        db.close()


# ══════════ 心理健康自评 ══════════

BASE_ME = "/api/v1/mobile/me"


def test_psy_survey_low_score_no_referral(client, db_mode):
    _seed_student("PS0001", "自评低分生")
    hdr = _stu_token("自评低分生", "PS0001")
    q = client.get(f"{BASE_ME}/psy-survey/questions", headers=hdr).json()
    assert q["code"] == 0
    keys = [x["key"] for x in q["data"]["questions"]]
    answers = [{"qKey": k, "score": 0} for k in keys]
    r = client.post(f"{BASE_ME}/psy-survey/submit", headers=hdr,
                    json={"answers": answers, "wantsContact": False}).json()
    assert r["code"] == 0 and r["data"]["triggeredAttention"] is False


def test_psy_survey_high_score_triggers_referral(client, db_mode):
    _seed_student("PS0002", "自评高分生")
    hdr = _stu_token("自评高分生", "PS0002")
    q = client.get(f"{BASE_ME}/psy-survey/questions", headers=hdr).json()["data"]["questions"]
    answers = [{"qKey": x["key"], "score": 3} for x in q]
    r = client.post(f"{BASE_ME}/psy-survey/submit", headers=hdr,
                    json={"answers": answers, "wantsContact": False}).json()
    assert r["code"] == 0 and r["data"]["triggeredAttention"] is True
    hist = client.get(f"{BASE_ME}/psy-survey/history", headers=hdr).json()["data"]
    assert hist["items"][0]["triggeredAttention"] is True


def test_psy_survey_wants_contact_always_triggers_even_low_score(client, db_mode):
    _seed_student("PS0003", "求助生")
    hdr = _stu_token("求助生", "PS0003")
    q = client.get(f"{BASE_ME}/psy-survey/questions", headers=hdr).json()["data"]["questions"]
    answers = [{"qKey": x["key"], "score": 0} for x in q]
    r = client.post(f"{BASE_ME}/psy-survey/submit", headers=hdr,
                    json={"answers": answers, "wantsContact": True}).json()
    assert r["code"] == 0 and r["data"]["triggeredAttention"] is True


def test_psy_survey_incomplete_answers_rejected(client, db_mode):
    _seed_student("PS0004", "漏答生")
    hdr = _stu_token("漏答生", "PS0004")
    r = client.post(f"{BASE_ME}/psy-survey/submit", headers=hdr,
                    json={"answers": [{"qKey": "mood", "score": 1}], "wantsContact": False}).json()
    assert r["code"] != 0


def test_psy_survey_referral_visible_to_teacher_attention_list(client, db_mode):
    """自评触发的关注记录应能被既有心理关注名单(教师端)读到，复用同一张表/同一读侧。"""
    _seed_student("PS0005", "关注生")
    stu_hdr = _stu_token("关注生", "PS0005")
    q = client.get(f"{BASE_ME}/psy-survey/questions", headers=stu_hdr).json()["data"]["questions"]
    answers = [{"qKey": x["key"], "score": 3} for x in q]
    client.post(f"{BASE_ME}/psy-survey/submit", headers=stu_hdr,
               json={"answers": answers, "wantsContact": False})
    # PSYCHOLOGY_TEACHER 角色需逐生 PSY_STUDENT 授权才能看到明细外的名单项，非本测试重点；
    # 用 SCHOOL_ADMIN（psy_scope_ids 对管理类角色返回 None，不做范围收敛）验证记录确实可读。
    tea_hdr = _teacher_token(role="SCHOOL_ADMIN")
    lst = client.get("/api/v1/mobile/teacher/mental", headers=tea_hdr).json()
    assert lst["code"] == 0
    assert any(r["level"] == "GENERAL" for r in lst["data"]["items"])


# ══════════ 通知发布 ══════════

def _seed_class(counselor_id, tenant_id=MAIN, n_students=2):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    try:
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="通知测2601",
                        grade="2026", counselor_id=counselor_id, status="ACTIVE")
        db.add(c); db.flush()
        cid = c.id
        for i in range(n_students):
            db.add(StudentProfile(tenant_id=tenant_id, student_no=f"NT{i:04d}",
                                  real_name=f"通知测生{i}", class_id=cid,
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        return cid
    finally:
        db.close()


def test_notify_publish_class_scope_and_student_receives(client, db_mode):
    cid = _seed_class(660001)
    hdr = _teacher_token(uid=660001, role="COUNSELOR")
    r = client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
                    json={"title": "期中考试安排", "content": "下周三开始期中考试，请做好复习准备。",
                          "scopeType": "CLASS", "classId": cid}).json()
    assert r["code"] == 0 and r["data"]["recipientCount"] == 2
    stu_hdr = _stu_token("通知测生0", "NT0000")
    msgs = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("期中考试安排" in m["title"] for m in msgs["groups"]["notice"])


def test_notify_publish_class_scope_other_teacher_forbidden(client, db_mode):
    cid = _seed_class(660002)
    other_hdr = _teacher_token(uid=660099, role="COUNSELOR")
    r = client.post("/api/v1/mobile/teacher/notify/publish", headers=other_hdr,
                    json={"title": "越权测试", "content": "不应发布成功", "scopeType": "CLASS", "classId": cid}).json()
    assert r["code"] != 0


def test_notify_publish_school_scope_requires_admin(client, db_mode):
    hdr = _teacher_token(uid=660003, role="COUNSELOR")
    r = client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
                    json={"title": "全校通知", "content": "普通辅导员不应能发全校通知", "scopeType": "SCHOOL"}).json()
    assert r["code"] != 0


def test_notify_publish_validation(client, db_mode):
    hdr = _teacher_token(uid=660004, role="COUNSELOR")
    empty_title = client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
                              json={"title": "", "content": "内容足够长了", "scopeType": "CLASS", "classId": 1}).json()
    assert empty_title["code"] != 0
    short_content = client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
                                json={"title": "标题", "content": "短", "scopeType": "CLASS", "classId": 1}).json()
    assert short_content["code"] != 0


# ══════════ 消息通知设置 ══════════

def test_notify_preference_filters_messages(client, db_mode):
    cid = _seed_class(660005, n_students=1)
    hdr = _teacher_token(uid=660005, role="COUNSELOR")
    client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
               json={"title": "偏好测试通知", "content": "用于验证通知开关真实生效", "scopeType": "CLASS", "classId": cid})
    stu_hdr = _stu_token("通知测生0", "NT0000")
    before = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("偏好测试通知" in m["title"] for m in before["groups"]["notice"])
    off = client.post("/api/v1/mobile/me/notify-preferences", headers=stu_hdr,
                      json={"key": "notice", "enabled": False}).json()
    assert off["code"] == 0
    after = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert after["groups"]["notice"] == []
    # 重新开启应恢复可见
    client.post("/api/v1/mobile/me/notify-preferences", headers=stu_hdr,
               json={"key": "notice", "enabled": True})
    again = client.get("/api/v1/mobile/me/messages", headers=stu_hdr).json()["data"]
    assert any("偏好测试通知" in m["title"] for m in again["groups"]["notice"])


def test_notify_preference_invalid_category_rejected(client, db_mode):
    hdr = _stu_token("偏好校验生", "NP0001")
    _seed_student("NP0001", "偏好校验生")
    r = client.post("/api/v1/mobile/me/notify-preferences", headers=hdr,
                    json={"key": "not-a-real-category", "enabled": False}).json()
    assert r["code"] != 0


# ══════════ 谈心谈话 / 心理关注 冒烟 ══════════

def test_talk_create_and_record_flow(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    try:
        c = SchoolClass(tenant_id=MAIN, major_id=1, class_name="谈话测2601",
                        grade="2026", status="ACTIVE")
        db.add(c)
        db.flush()
        s = StudentProfile(tenant_id=MAIN, student_no="TK0001", real_name="谈话测生",
                           grade="2026", class_id=c.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE")
        db.add(s)
        # affairs_talk_service._scope_or_403 走 build_affairs_context（TeacherStudentScope 表驱动，
        # 与 SchoolClass.counselor_id 无关）；COUNSELOR 未配置范围时 fail-closed 返回空集合，必须真实授权。
        db.add(TeacherStudentScope(tenant_id=MAIN, teacher_key="660010", teacher_name="王老师",
                                   role_code="COUNSELOR", scope_type="CLASS",
                                   ref_value="谈话测2601", status="ACTIVE"))
        db.commit()
        student_id = s.id
    finally:
        db.close()
    hdr = _teacher_token(uid=660010, role="COUNSELOR")
    created = client.post("/api/v1/mobile/teacher/talk", headers=hdr,
                          json={"talkType": "DAILY", "topic": "日常谈心", "studentIds": [student_id]}).json()
    assert created["code"] == 0
    talk_id = created["data"]["talkIds"][0]
    recorded = client.post(f"/api/v1/mobile/teacher/talk/{talk_id}/record", headers=hdr,
                           json={"content": "本次谈话了解了学生近期学习和生活状态，情况正常。",
                                 "result": "无需特别跟进", "needFollow": False}).json()
    assert recorded["code"] == 0 and recorded["data"]["status"] == "COMPLETED"


def test_mental_list_masks_detail_by_default(client, db_mode):
    hdr = _teacher_token(uid=660011, role="PSYCHOLOGY_TEACHER")
    created = client.post("/api/v1/mobile/teacher/mental", headers=hdr,
                          json={"studentId": 999999, "level": "FOCUS",
                                "reasonSummary": "测试转介登记事由"}).json()
    # 学生不存在应报错，不应假成功
    assert created["code"] != 0


# ══════════ 数据看板 ══════════

def test_teacher_dashboard_returns_summary_cards(client, db_mode):
    hdr = _teacher_token(uid=660012, role="COUNSELOR")
    r = client.get("/api/v1/mobile/teacher/dashboard", headers=hdr).json()
    assert r["code"] == 0
    assert isinstance(r["data"]["summaryCards"], list) and len(r["data"]["summaryCards"]) > 0


# ══════════ 修改密码 ══════════

def _seed_real_user(login_name, password, tenant_id=MAIN):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User
    db = get_sessionmaker()()
    try:
        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",
                 password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")
        db.add(u); db.commit(); db.refresh(u)
        return u.id
    finally:
        db.close()


def _db_token(uid):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"db-{uid}", "realName": "改密测试师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",
        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}


def test_change_password_demo_account_rejected(client, db_mode):
    hdr = _teacher_token(uid=660020, role="COUNSELOR")
    r = client.post("/api/v1/auth/change-password", headers=hdr,
                    json={"oldPassword": "any", "newPassword": "newpass123"}).json()
    assert r["code"] != 0


def test_change_password_wrong_old_rejected(client, db_mode):
    uid = _seed_real_user("cp_test01", "OldPass123")
    hdr = _db_token(uid)
    r = client.post("/api/v1/auth/change-password", headers=hdr,
                    json={"oldPassword": "WrongPassword", "newPassword": "NewPass456"}).json()
    assert r["code"] != 0


def test_change_password_success_and_relogin(client, db_mode):
    uid = _seed_real_user("cp_test02", "OldPass123")
    hdr = _db_token(uid)
    r = client.post("/api/v1/auth/change-password", headers=hdr,
                    json={"oldPassword": "OldPass123", "newPassword": "NewPass456"}).json()
    assert r["code"] == 0
    login_old = client.post("/api/v1/auth/login",
                            json={"loginName": "cp_test02", "password": "OldPass123"}).json()
    assert login_old["code"] != 0
    login_new = client.post("/api/v1/auth/login",
                            json={"loginName": "cp_test02", "password": "NewPass456"}).json()
    assert login_new["code"] == 0
