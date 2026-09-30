"""13A-P5 谈心谈话 + 家校联系 · 端到端（真实 DB 模式）。

T1 建计划+记录→COMPLETED进360；T2 内容<20字校验；T3 转风险联动；T4 转家校联动；
T5 心理类明细按角色隐藏；T6 完整号码查看必填原因+审计；越权跨班403。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _student_hdr(student_no, real_name):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"student-{student_no}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": "leave-ui-test", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP",
    })}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add(a); db.add(b); db.flush()
    sa = StudentProfile(tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sb = StudentProfile(tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sa); db.add(sb); db.flush()
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
                               status="ACTIVE"))
    db.commit()
    ids = {"A": a.id, "B": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids


def _create_talk(client, hdr, sid, ttype="DAILY"):
    return client.post(f"{BASE}/talks", headers=hdr, json={
        "studentIds": [str(sid)], "talkType": ttype, "topic": "近期学习情况"}).json()["data"]["talkIds"][0]


def _content():
    return "与学生进行了深入交流，了解到其近期学习状态良好，情绪稳定"


def test_t1_create_record_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    tid = _create_talk(client, hdr, ids["sa"])
    r = post_versioned(client, f"{BASE}/talks/{tid}/record", headers=hdr,
                    json={"content": _content(), "result": "GOOD", "needFollowUp": False}).json()
    assert r["data"]["status"] == "COMPLETED"
    from app.db.session import get_sessionmaker
    from app.models import StudentStageEvent
    db = get_sessionmaker()()
    assert db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="TALK_COMPLETED").count() == 1
    db.close()


def test_t2_content_min_length(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    tid = _create_talk(client, hdr, ids["sa"])
    assert post_versioned(client, f"{BASE}/talks/{tid}/record", headers=hdr,
                       json={"content": "太短", "result": "GOOD", "needFollowUp": False}).status_code == 400


def test_t3_follow_to_risk(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    tid = _create_talk(client, hdr, ids["sa"])
    post_versioned(client, f"{BASE}/talks/{tid}/record", headers=hdr,
                json={"content": _content(), "result": "NEED_HELP", "needFollowUp": True})
    r = post_versioned(client, f"{BASE}/talks/{tid}/follow-up", headers=hdr,
                    json={"action": "TO_RISK", "content": "发现学业风险，转风险跟进"}).json()
    assert r["data"]["relatedRiskId"]
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    assert db.query(AffairsRiskRecord).filter_by(student_id=ids["sa"], source_ref_id=int(tid)).count() == 1
    db.close()


def test_t4_follow_to_home_school(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    tid = _create_talk(client, hdr, ids["sa"])
    post_versioned(client, f"{BASE}/talks/{tid}/record", headers=hdr,
                json={"content": _content(), "result": "GOOD", "needFollowUp": True})
    r = post_versioned(client, f"{BASE}/talks/{tid}/follow-up", headers=hdr,
                    json={"action": "TO_HOME_SCHOOL", "content": "已联系家长沟通"}).json()
    assert r["data"]["relatedContactId"]


def test_t5_psychology_masked_by_role(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tid = _create_talk(client, admin, ids["sa"], ttype="PSYCHOLOGY")
    post_versioned(client, f"{BASE}/talks/{tid}/record", headers=admin,
                json={"content": "心理咨询详细谈话内容，涉及个人隐私与敏感信息，需严格保密处理不外泄",
                      "result": "GOOD", "needFollowUp": False})
    # 学工处见全文
    d_admin = client.get(f"{BASE}/talks/{tid}", headers=admin).json()["data"]
    assert d_admin["psyMasked"] is False and "心理咨询详细" in d_admin["content"]
    # 辅导员明细受限
    d_c = client.get(f"{BASE}/talks/{tid}", headers=_hdr(client, "counselor01")).json()["data"]
    assert d_c["psyMasked"] is True and "心理咨询详细" not in d_c["content"]


def test_t6_family_full_phone_requires_reason(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 查看完整号码但无原因 → 400
    assert client.post(f"{BASE}/students/{ids['sa']}/family-contacts", headers=hdr, json={
        "contactType": "PHONE", "reason": "了解情况", "fullPhoneView": True, "viewReason": ""
    }).status_code == 400
    # 带原因 → 成功 + SENSITIVE_VIEW 审计
    r = client.post(f"{BASE}/students/{ids['sa']}/family-contacts", headers=hdr, json={
        "contactType": "PHONE", "reason": "学业异常沟通", "result": "家长知悉",
        "fullPhoneView": True, "viewReason": "需电话联系家长核实情况"}).json()
    assert r["data"]["fullPhoneViewed"] is True
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    db = get_sessionmaker()()
    assert db.query(SecurityAuditLog).filter_by(action="SENSITIVE_VIEW").count() == 1
    db.close()


def test_t7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    tid = _create_talk(client, admin, ids["sb"])
    r = client.get(f"{BASE}/talks/{tid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_t8_mobile_talk_to_family_uses_version_and_is_visible_to_student(client, db_mode):
    """同一谈心单经教师移动端转家校，学生移动端回读摘要；旧版本不可重复操作。"""
    ids = _seed(db_mode)
    teacher = _hdr(client, "school_admin01")
    talk_id = _create_talk(client, teacher, ids["sa"])
    initial = client.get(f"/api/v1/mobile/teacher/talk/{talk_id}", headers=teacher).json()["data"]

    recorded = client.post(
        f"/api/v1/mobile/teacher/talk/{talk_id}/record",
        headers=teacher,
        json={
            "content": _content(), "result": "需要家校协同", "needFollow": True,
            "version": initial["version"],
        },
    )
    assert recorded.status_code == 200
    recorded_row = recorded.json()["data"]

    transferred = client.post(
        f"/api/v1/mobile/teacher/talk/{talk_id}/follow-up",
        headers=teacher,
        json={
            "action": "TO_HOME_SCHOOL", "content": "已约定本周共同跟进学习作息",
            "version": recorded_row["version"],
        },
    )
    assert transferred.status_code == 200
    contact_id = transferred.json()["data"]["relatedContactId"]
    assert contact_id

    stale = client.post(
        f"/api/v1/mobile/teacher/talk/{talk_id}/follow-up",
        headers=teacher,
        json={"action": "FOLLOW", "content": "重复处理应被拒绝", "version": recorded_row["version"]},
    )
    assert stale.status_code == 409

    contacts = client.get("/api/v1/mobile/teacher/affairs/family-contacts", headers=teacher)
    assert any(str(row["contactId"]) == str(contact_id) for row in contacts.json()["data"]["list"])

    student = client.get("/api/v1/mobile/affairs/talk/my", headers=_student_hdr("A001", "甲一"))
    student_row = next(row for row in student.json()["data"]["items"] if str(row["talkId"]) == str(talk_id))
    assert student_row["status"] == "FOLLOW_UP"
    assert "content" not in student_row and "relatedContactId" not in student_row
