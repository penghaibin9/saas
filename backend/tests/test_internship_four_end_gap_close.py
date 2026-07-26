"""岗位实习四端补齐：学生求助、换岗防假通过、成绩等次、代录口径。"""
from __future__ import annotations

TID = 1000000000000000001
MOB = "/api/v1/mobile"
INT = "/api/v1/internship"


def _student(sno="HELP-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-help", "realName": "求助学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed(db_mode, sno="HELP-STU-01"):
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no=sno, real_name="求助学生",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(tenant_id=TID, student_id=s.id, advisor_name="刘强",
                             enterprise_name="测试企业", position_name="测试岗位",
                             status="ONBOARD", risk_level="NONE")
        db.add(r)
        db.flush()
        db.commit()
        return {"rec_id": r.id, "stu_id": s.id}
    finally:
        db.close()


def test_student_help_creates_risk_for_mentor(client, db_mode):
    _seed(db_mode)
    bad = client.post(f"{MOB}/internship/help",
                      json={"content": "短"}, headers=_student())
    assert bad.status_code == 400
    ok = client.post(f"{MOB}/internship/help",
                     json={"content": "岗位与专业不符，请求调整", "riskLevel": "HIGH",
                           "title": "岗位不适求助"},
                     headers=_student())
    assert ok.status_code == 200 and ok.json()["code"] == 0
    rid = ok.json()["data"]["id"]
    risks = client.get(f"{MOB}/teacher/internship/risks", headers=_mentor("刘强"))
    assert risks.status_code == 200
    items = risks.json()["data"]["list"]
    assert any(x["id"] == rid for x in items)
    assert any(x.get("riskCode") == "INT-R-HELP" for x in items)


def test_grade_level_on_score_row():
    from app.modules.internship.services.internship_score_service import _grade_level
    assert _grade_level(95) == "优秀"
    assert _grade_level(85) == "良好"
    assert _grade_level(75) == "中等"
    assert _grade_level(65) == "及格"
    assert _grade_level(50) == "不及格"
    assert _grade_level(None) == ""


def test_school_recorded_source_label():
    from app.modules.internship.services.internship_enterprise_eval_service import SOURCE_LABEL
    # 口径收紧后完整表述来源（避免误读成"企业已评"），语义不变，字面已更新
    assert SOURCE_LABEL["SCHOOL_RECORDED"] == "学校根据企业纸质材料录入"
