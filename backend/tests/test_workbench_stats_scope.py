"""P3 工作台统计数据范围收敛回归。

锁住：
  1. /stats/workbench 按 build_affairs_context 收敛——辅导员只看本班学生数，看不到别班；
  2. 院级 COLLEGE_ADMIN 按学院展开班级后只看本院学生数；
  3. 未配数据范围的教职工 fail-closed：学生类指标为 0，不回退全校；
  4. 校级 TENANT_ALL 仍可看本租户全量；
  5. 数据中心全校 BI（/stats/overview 等）对一线角色 403002，禁止偷看全校数。
"""
from __future__ import annotations

MAIN = 1000000000000000001
CA_UID, CB_UID, NONE_UID, COL_UID = 52001, 52002, 52099, 52011


def _token(user_id, login_name, role="COUNSELOR", user_type="TEACHER", tenant_id=MAIN):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "loginName": login_name, "realName": f"姓名{user_id}",
        "userType": user_type, "tid": "demo", "tenantId": str(tenant_id),
        "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"})}


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    try:
        ca = SchoolClass(tenant_id=MAIN, major_id=1, class_name="统计软件班", status="ACTIVE")
        cb = SchoolClass(tenant_id=MAIN, major_id=1, class_name="统计机电班", status="ACTIVE")
        db.add_all([ca, cb])
        db.flush()
        sa = StudentProfile(tenant_id=MAIN, student_no="STWB001", real_name="甲一", grade="2023",
                            class_id=ca.id, current_stage="ON_CAMPUS", student_status="NORMAL",
                            status="ACTIVE")
        sb = StudentProfile(tenant_id=MAIN, student_no="STWB002", real_name="乙二", grade="2023",
                            class_id=cb.id, current_stage="ON_CAMPUS", student_status="NORMAL",
                            status="ACTIVE")
        sc = StudentProfile(tenant_id=MAIN, student_no="STWB003", real_name="丙三", grade="2023",
                            class_id=ca.id, current_stage="ON_CAMPUS", student_status="NORMAL",
                            status="ACTIVE")
        db.add_all([sa, sb, sc])
        db.add_all([
            TeacherStudentScope(tenant_id=MAIN, teacher_key="wbStatsA", teacher_name="辅导员A",
                                role_code="COUNSELOR", scope_type="CLASS", ref_value="统计软件班",
                                status="ACTIVE"),
            TeacherStudentScope(tenant_id=MAIN, teacher_key="wbStatsB", teacher_name="辅导员B",
                                role_code="COUNSELOR", scope_type="CLASS", ref_value="统计机电班",
                                status="ACTIVE"),
        ])
        db.commit()
        return {"class_a": ca.id, "class_b": cb.id}
    finally:
        db.close()


def _seed_college(_db_mode):
    """两个学院：信息学院 2 班共 3 人，机电学院 1 班 1 人；院管只授权信息学院。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    try:
        col_a = College(tenant_id=MAIN, college_name="信息学院", status="ACTIVE")
        col_b = College(tenant_id=MAIN, college_name="机电学院", status="ACTIVE")
        db.add_all([col_a, col_b])
        db.flush()
        maj_a = Major(tenant_id=MAIN, college_id=col_a.id, major_name="软件技术", status="ACTIVE")
        maj_b = Major(tenant_id=MAIN, college_id=col_b.id, major_name="机电一体化", status="ACTIVE")
        db.add_all([maj_a, maj_b])
        db.flush()
        c1 = SchoolClass(tenant_id=MAIN, major_id=maj_a.id, class_name="信息软2301", status="ACTIVE")
        c2 = SchoolClass(tenant_id=MAIN, major_id=maj_a.id, class_name="信息软2302", status="ACTIVE")
        c3 = SchoolClass(tenant_id=MAIN, major_id=maj_b.id, class_name="机电2301", status="ACTIVE")
        db.add_all([c1, c2, c3])
        db.flush()
        db.add_all([
            StudentProfile(tenant_id=MAIN, student_no="COL001", real_name="院甲", grade="2023",
                           college_id=col_a.id, class_id=c1.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE"),
            StudentProfile(tenant_id=MAIN, student_no="COL002", real_name="院乙", grade="2023",
                           college_id=col_a.id, class_id=c1.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE"),
            StudentProfile(tenant_id=MAIN, student_no="COL003", real_name="院丙", grade="2023",
                           college_id=col_a.id, class_id=c2.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE"),
            StudentProfile(tenant_id=MAIN, student_no="COL004", real_name="院丁", grade="2023",
                           college_id=col_b.id, class_id=c3.id, current_stage="ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE"),
            TeacherStudentScope(tenant_id=MAIN, teacher_key="wbCollegeA", teacher_name="院管A",
                                role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="信息学院",
                                status="ACTIVE"),
        ])
        db.commit()
    finally:
        db.close()


def test_workbench_stats_counselor_converges_by_class(client, db_mode):
    """辅导员 A 只带软件班（2 人），B 只带机电班（1 人）；studentTotal 必须不同且不等于全校 3。"""
    _seed(db_mode)
    a = client.get("/api/v1/stats/workbench", headers=_token(CA_UID, "wbStatsA")).json()
    b = client.get("/api/v1/stats/workbench", headers=_token(CB_UID, "wbStatsB")).json()
    assert a["code"] == 0 and b["code"] == 0, (a, b)
    assert a["data"]["scopeType"] == "CLASS"
    assert b["data"]["scopeType"] == "CLASS"
    assert a["data"]["studentTotal"] == 2, a["data"]
    assert b["data"]["studentTotal"] == 1, b["data"]
    assert a["data"]["studentTotal"] != b["data"]["studentTotal"]


def test_workbench_stats_college_admin_converges_by_college(client, db_mode):
    """COLLEGE_ADMIN 授权信息学院 → studentTotal=3（本院），看不到机电学院的 1 人。"""
    _seed_college(db_mode)
    r = client.get("/api/v1/stats/workbench",
                   headers=_token(COL_UID, "wbCollegeA", role="COLLEGE_ADMIN")).json()
    assert r["code"] == 0, r
    assert r["data"]["scopeType"] == "COLLEGE", r["data"]
    assert r["data"]["studentTotal"] == 3, r["data"]
    assert r["data"]["studentTotal"] < 4  # 全校 4 人，本院只能 3


def test_workbench_stats_no_scope_fail_closed(client, db_mode):
    """未配 TeacherStudentScope 的辅导员：学生类指标为 0，不得回退全校 3。"""
    _seed(db_mode)
    r = client.get("/api/v1/stats/workbench",
                   headers=_token(NONE_UID, "wbStatsNone")).json()
    assert r["code"] == 0, r
    assert r["data"]["studentTotal"] == 0, r["data"]
    assert r["data"]["academicWarning"] == 0
    assert r["data"]["unemployed"] == 0
    assert r["data"]["orientationPending"] == 0
    assert r["data"]["scopeType"] in ("CLASS", "NONE")


def test_workbench_stats_school_admin_sees_tenant(client, auth_headers, db_mode):
    """校级 SCHOOL_ADMIN（TENANT_ALL）看到本租户全量学生数。"""
    _seed(db_mode)
    r = client.get("/api/v1/stats/workbench", headers=auth_headers).json()
    assert r["code"] == 0, r
    assert r["data"]["scopeType"] == "TENANT_ALL"
    assert r["data"]["studentTotal"] >= 3, r["data"]


def test_school_bi_forbidden_for_counselor(client, db_mode):
    """一线辅导员调全校 BI → 403002，不能偷看全校 overview。"""
    _seed(db_mode)
    h = _token(CA_UID, "wbStatsA")
    for path in ("overview", "lifecycle", "risk", "rankings"):
        r = client.get(f"/api/v1/stats/{path}", headers=h).json()
        assert r["code"] != 0, f"/stats/{path} 应拒绝辅导员: {r}"
        assert r.get("bizCode") == "NO_DATA_SCOPE", r
