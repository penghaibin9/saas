"""学工中心 · 移动端家校联系（新聚合 affairs_family_contact_students + 登记/回执包装）。
全部经 HTTP client 走真库(db_mode)。范围口径为 t_teacher_student_scope(CLASS)，与 PC 端
create_contact 内部 _scope_or_403 完全同一收敛路径——用真实 TeacherStudentScope 授权行验证
"选得到的学生 == 提交时不会 403 的学生"。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"
TID = 1000000000000000001


def _counselor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}


def _seed():
    """1个班级(软件2601)挂2个学生 + 1条 TeacherStudentScope(王老师→软件2601,CLASS)。
    另建1个班级(软件2602)挂1个学生，无任何授权行，验证越权学生不出现在名单里。
    返回 (in_scope_student_id, out_of_scope_student_id)。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    try:
        c1 = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2601", grade="2026", status="ACTIVE")
        c2 = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2602", grade="2026", status="ACTIVE")
        db.add(c1); db.add(c2)
        db.flush()
        s1 = StudentProfile(tenant_id=TID, student_no="FC001", real_name="家校测试甲",
                            class_id=c1.id, current_stage="ON_CAMPUS", status="ACTIVE")
        s2 = StudentProfile(tenant_id=TID, student_no="FC002", real_name="家校测试乙",
                            class_id=c2.id, current_stage="ON_CAMPUS", status="ACTIVE")
        db.add(s1); db.add(s2)
        db.flush()
        db.add(TeacherStudentScope(tenant_id=TID, teacher_key="u-王老师", teacher_name="王老师",
                                   role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2601",
                                   status="ACTIVE"))
        db.commit()
        return str(s1.id), str(s2.id)
    finally:
        db.close()


def test_student_picker_matches_scope_and_create_succeeds(db_mode, client):
    in_id, out_id = _seed()
    h = _counselor("王老师")

    r = client.get(f"{MOB}/teacher/affairs/family-contacts/students", headers=h)
    assert r.status_code == 200
    ids = {x["studentId"] for x in r.json()["data"]["list"]}
    assert in_id in ids
    assert out_id not in ids  # 越权班级学生不出现在可登记名单里

    create = client.post(f"{MOB}/teacher/affairs/family-contacts/{in_id}", headers=h,
                         json={"contactType": "PHONE", "reason": "学业沟通", "result": "已知晓"})
    assert create.status_code == 200 and create.json()["code"] == 0

    lst = client.get(f"{MOB}/teacher/affairs/family-contacts", headers=h).json()["data"]["list"]
    assert any(x["studentNo"] == "FC001" for x in lst)


def test_out_of_scope_student_create_forbidden(db_mode, client):
    in_id, out_id = _seed()
    h = _counselor("王老师")

    r = client.post(f"{MOB}/teacher/affairs/family-contacts/{out_id}", headers=h,
                    json={"contactType": "PHONE", "reason": "测试越权", "result": "已完成沟通"})
    assert r.status_code == 403


def test_receipt_flow(db_mode, client):
    in_id, _ = _seed()
    h = _counselor("王老师")

    create = client.post(f"{MOB}/teacher/affairs/family-contacts/{in_id}", headers=h,
                         json={"contactType": "WECHAT", "reason": "作业完成情况", "result": "家长已知晓"})
    cid = create.json()["data"]["contactId"]

    pending = client.get(f"{MOB}/teacher/affairs/family-contacts", headers=h,
                         params={"receiptStatus": "PENDING"}).json()["data"]["list"]
    assert any(x["contactId"] == cid for x in pending)

    receipt = client.post(f"{MOB}/teacher/affairs/family-contacts/{cid}/receipt", headers=h,
                          json={"note": "家长已回复知晓"})
    assert receipt.status_code == 200 and receipt.json()["code"] == 0

    received = client.get(f"{MOB}/teacher/affairs/family-contacts", headers=h,
                          params={"receiptStatus": "RECEIVED"}).json()["data"]["list"]
    row = next(x for x in received if x["contactId"] == cid)
    assert row["receiptNote"] == "家长已回复知晓"

    dup = client.post(f"{MOB}/teacher/affairs/family-contacts/{cid}/receipt", headers=h, json={})
    assert dup.status_code != 200 or dup.json()["code"] != 0
