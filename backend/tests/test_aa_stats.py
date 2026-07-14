"""教务统计（/academic-affairs/stats/*）端点测试：主流程 + 越权(学生403) + 数据范围(学院跨范围403) + 导出用途校验。

MySQL-only：依赖 db_mode 夹具（TEST_DATABASE_URL）。多 worktree 共用测试库时由总控合并后统一跑。
口径核对施工包 §9 / 融合设计 §4。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """在 db_mode 干净库上补种教务统计所需数据，返回关键 id。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaRegistration, AaRegistrationBatch, AcademicGrade, AcademicStudent,
                            AcademicWarning, College, Major, StudentProfile, TeacherStudentScope)
    db = get_sessionmaker()()
    soft = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    other = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
    db.add_all([soft, other]); db.flush()
    major = Major(tenant_id=TID, college_id=soft.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="2024001", real_name="钱二",
                        college_id=soft.id, major_id=major.id, student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="2024002", real_name="孙三",
                        college_id=soft.id, major_id=major.id, student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2]); db.flush()
    batch = AaRegistrationBatch(tenant_id=TID, batch_name="2024入学注册", register_type="ENROLL",
                               status="OPEN")
    db.add(batch); db.flush()
    db.add_all([
        AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=s1.id, status="REGISTERED"),
        AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=s2.id, status="PENDING_REGISTER"),
    ])
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="2024001", name="钱二",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    db.add_all([
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="高数", credit_value=4,
                      score=45, pass_status="FAILED", record_status="ACTIVE"),
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="英语", credit_value=3,
                      score=80, pass_status="PASSED", record_status="ACTIVE"),
        AcademicWarning(tenant_id=TID, acad_student_id=a1.id, warn_type="MULTI_FAIL", level="HIGH",
                        status="PENDING_HANDLE", record_status="ACTIVE"),
    ])
    # college_admin01 → 软件学院 数据范围
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"soft": soft.id, "other": other.id, "major": major.id, "s2": s2.id}
    db.close()
    return ids


def test_overview_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/overview", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert len(d["indicators"]) == 15
    by_key = {i["key"]: i for i in d["indicators"]}
    # 4 项底层未建 → MODULE_NOT_ENABLED 占位
    for k in ("scheduleChange", "courseSelection", "exam", "resource"):
        assert by_key[k]["status"] == "MODULE_NOT_ENABLED"
    # 注册完成率：1 已注册 / 2 应注册 = 50%
    reg = by_key["registration"]
    assert reg["numerator"] == 1 and reg["denominator"] == 2 and reg["rate"] == 50.0
    # 挂科率：1 FAILED / 2 有成绩 = 50%
    assert by_key["failRate"]["numerator"] == 1 and by_key["failRate"]["denominator"] == 2
    # 预警数 = 1
    assert by_key["warning"]["value"] == 1
    assert d["scope"]["all"] is True


def test_filters_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/filters", headers=hdr).json()
    assert r["code"] == 0
    assert isinstance(r["data"]["colleges"], list) and len(r["data"]["colleges"]) >= 2
    assert isinstance(r["data"]["majors"], list) and len(r["data"]["majors"]) >= 1


def test_registration_drill_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/registration", headers=hdr).json()
    assert r["code"] == 0
    names = [row["studentName"] for row in r["data"]["items"]]
    assert "孙三" in names            # 未注册（PENDING_REGISTER）
    assert "钱二" not in names        # 已注册不在未注册名单
    # 学号脱敏（非明文全串）
    for row in r["data"]["items"]:
        assert row["studentNo"] != "2024002"


def test_warning_drill_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/warning", headers=hdr).json()
    assert r["code"] == 0
    assert r["data"]["total"] == 1
    assert r["data"]["items"][0]["level"] == "HIGH"


def test_student_forbidden(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "student01")
    for path in ("/stats/overview", "/stats/registration", "/stats/warning"):
        assert client.get(f"{BASE}{path}", headers=hdr).status_code == 403


def test_college_admin_cross_scope_denied(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "college_admin01")
    # 本院（软件学院）→ 允许
    ok = client.get(f"{BASE}/stats/overview", headers=hdr, params={"collegeId": ids["soft"]}).json()
    assert ok["code"] == 0
    # 越院（机械学院）→ 越权拒绝
    denied = client.get(f"{BASE}/stats/overview", headers=hdr, params={"collegeId": ids["other"]})
    body = denied.json()
    assert denied.status_code == 403 or body.get("code") == "NO_DATA_SCOPE"


def test_export_purpose_required(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 用途缺失 / 过短 → 400（本项目 pydantic 校验错误统一转 400）
    assert client.post(f"{BASE}/stats/export", headers=hdr, json={"purpose": "x"}).status_code == 400
    # 合法导出 → xlsx 字节（zip 魔数 PK）
    r = client.post(f"{BASE}/stats/export", headers=hdr, json={"purpose": "期末教务运行汇报"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
