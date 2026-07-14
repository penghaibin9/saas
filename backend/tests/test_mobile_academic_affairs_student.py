"""波5 教务中心·学生自视图新增接口冒烟测试：学分/预警/补考/选课浏览，均需登录+返回200不500。"""
from __future__ import annotations

BASE = "/api/v1/mobile/academic"
MAIN = 1000000000000000001


def _stu_token(real_name="学分测生", student_no="CR0001", tenant_id=MAIN, tid="demo"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{real_name}", "realName": real_name, "userType": "STUDENT",
        "studentNo": student_no, "tid": tid, "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_student(student_no, real_name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,
                              grade="2026", current_stage="ON_CAMPUS",
                              student_status="NORMAL", status="ACTIVE"))
        db.commit()
    finally:
        db.close()


def test_credits_my_no_data_not_500(client, db_mode):
    _seed_student("CR0001", "学分测生")
    r = client.get(f"{BASE}/credits/my", headers=_stu_token()).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["requiredCredits"] == 120.0
    assert d["passedCourses"] == []


def test_warning_my_no_data_not_500(client, db_mode):
    _seed_student("CR0002", "预警测生")
    r = client.get(f"{BASE}/warning/my", headers=_stu_token("预警测生", "CR0002")).json()
    assert r["code"] == 0
    assert r["data"]["items"] == [] and r["data"]["total"] == 0


def test_makeup_my_no_data_not_500(client, db_mode):
    _seed_student("CR0003", "补考测生")
    r = client.get(f"{BASE}/makeup/my", headers=_stu_token("补考测生", "CR0003")).json()
    assert r["code"] == 0
    assert r["data"]["retakes"] == [] and r["data"]["exemptions"] == []


def test_makeup_retake_apply_validation(client, db_mode):
    _seed_student("CR0004", "重修测生")
    hdr = _stu_token("重修测生", "CR0004")
    bad = client.post(f"{BASE}/makeup/retake-apply", headers=hdr, json={}).json()
    assert bad["code"] != 0  # courseName 必填校验，未新建服务端崩溃


def test_selection_courses_and_my_selections_no_data_not_500(client, db_mode):
    _seed_student("CR0005", "选课测生")
    hdr = _stu_token("选课测生", "CR0005")
    courses = client.get(f"{BASE}/selection/courses", headers=hdr).json()
    assert courses["code"] == 0 and courses["data"] == []
    mine = client.get(f"{BASE}/selection/my", headers=hdr).json()
    assert mine["code"] == 0 and mine["data"] == []


def test_selection_enroll_requires_selection_course_id(client, db_mode):
    _seed_student("CR0006", "选课测生2")
    hdr = _stu_token("选课测生2", "CR0006")
    bad = client.post(f"{BASE}/selection/enroll", headers=hdr, json={}).json()
    assert bad["code"] != 0


def test_new_academic_endpoints_require_login(client):
    for path in ("/credits/my", "/warning/my", "/makeup/my", "/selection/courses", "/selection/my"):
        assert client.get(BASE + path).json()["code"] == 401001
