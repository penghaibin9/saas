"""GPA 绩点换算策略版本化 + 历史冻结回归（P1 GPA）。

核心不变量（GPA-POLICY-01）：一条正式成绩第一次计入 GPA 时按当时生效策略冻结绩点，此后
即使租户发布新策略版本，这条历史记录的绩点也不再改变——学校 2028 年调整绩点口径，不会
改写 2026 届学生已经算过的历史 GPA。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _svc_user():
    return {
        "tenantId": str(TID), "userId": "81003", "realName": "GPA策略测试",
        "userType": "TEACHER", "currentRoleCode": "ACADEMIC_ADMIN",
        "permissions": ["*"], "dataScope": "ALL",
    }


def _seed_student_with_grade(db, score=85, credit=3):
    from app.models import AcademicGrade, AcademicStudent
    student = AcademicStudent(tenant_id=TID, name="GPA测试生", gpa=0)
    db.add(student); db.flush()
    grade = AcademicGrade(
        tenant_id=TID, acad_student_id=student.id, course_name="GPA测试课", credit_value=credit,
        score=score, pass_status="PASSED", record_status="ACTIVE", source="LEGACY",
    )
    db.add(grade); db.flush()
    db.commit()
    return student.id, grade.id


def test_default_policy_matches_legacy_formula(client, db_mode):
    """未配置任何策略时，默认 LINEAR 策略必须与旧硬编码公式 (score-50)/10 逐分值一致。"""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_grade_core_service import _refresh_aggregates

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    db = get_sessionmaker()()
    try:
        student_id, grade_id = _seed_student_with_grade(db, score=85, credit=3)
        student = db.get(AcademicStudent, student_id)
        _refresh_aggregates(db, student)
        db.commit()
        grade = db.get(AcademicGrade, grade_id)
        assert grade.gpa_point is not None
        assert float(grade.gpa_point) == 3.5, "85分旧公式 (85-50)/10=3.5"
        assert grade.gpa_policy_code == "DEFAULT" and grade.gpa_policy_version == 1
        assert float(student.gpa) == 3.5
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_grade_service_public_refresh_also_freezes(client, db_mode):
    """academic_affairs_grade_service.py（"成绩域唯一公开 Service"）有自己独立的
    _refresh_aggregates 实现，被发布/复查/认定/补考等主链路调用——必须同样走
    _course_point_frozen，不能各用各的绩点公式导致两条链路算出不同 GPA。"""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services.academic_affairs_grade_service import (
        _refresh_aggregates as public_refresh_aggregates,
    )

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    db = get_sessionmaker()()
    try:
        student_id, grade_id = _seed_student_with_grade(db, score=85, credit=3)
        student = db.get(AcademicStudent, student_id)
        public_refresh_aggregates(db, student)
        db.commit()
        grade = db.get(AcademicGrade, grade_id)
        assert float(grade.gpa_point) == 3.5
        assert grade.gpa_policy_code == "DEFAULT" and grade.gpa_policy_version == 1
        assert float(student.gpa) == 3.5
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_frozen_point_survives_new_policy_activation(client, db_mode):
    """已冻结绩点的历史记录，在租户激活新策略版本后重新走一次台账刷新，绩点必须原封不动。"""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services import academic_affairs_gpa_policy_service as gpa_svc
    from app.modules.academic_affairs.services.academic_affairs_grade_core_service import _refresh_aggregates

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    db = get_sessionmaker()()
    try:
        student_id, grade_id = _seed_student_with_grade(db, score=90, credit=2)
        student = db.get(AcademicStudent, student_id)
        _refresh_aggregates(db, student)
        db.commit()
        frozen_point = float(db.get(AcademicGrade, grade_id).gpa_point)
        assert frozen_point == 4.0, "90分旧公式 (90-50)/10=4.0"
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)

    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/gpa-policies/activate", headers=hdr, json={
        "policyCode": "STRICT_BANDS", "scaleType": "BANDS",
        "bands": [
            {"minScore": 90, "maxScore": 100, "point": 4.5},
            {"minScore": 60, "maxScore": 89, "point": 2.0},
            {"minScore": 0, "maxScore": 59, "point": 0},
        ],
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "ACTIVE"

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    db = get_sessionmaker()()
    try:
        student = db.get(AcademicStudent, student_id)
        _refresh_aggregates(db, student)  # 新策略下 90 分应该是 4.5，但这条记录已冻结
        db.commit()
        grade = db.get(AcademicGrade, grade_id)
        assert float(grade.gpa_point) == frozen_point == 4.0, "已冻结的历史记录不得随新策略重算"
        assert grade.gpa_policy_code == "DEFAULT" and grade.gpa_policy_version == 1
        assert float(student.gpa) == 4.0
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_new_grade_after_activation_uses_new_policy(client, db_mode):
    """新策略生效之后第一次计入 GPA 的成绩，必须按新策略冻结，不是继续沿用旧策略。"""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent

    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/gpa-policies/activate", headers=hdr, json={
        "policyCode": "STRICT_BANDS2", "scaleType": "BANDS",
        "bands": [
            {"minScore": 90, "maxScore": 100, "point": 4.5},
            {"minScore": 60, "maxScore": 89, "point": 2.0},
            {"minScore": 0, "maxScore": 59, "point": 0},
        ],
    })
    assert r.status_code == 200, r.text

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    db = get_sessionmaker()()
    try:
        from app.modules.academic_affairs.services.academic_affairs_grade_core_service import _refresh_aggregates
        student_id, grade_id = _seed_student_with_grade(db, score=95, credit=1)
        student = db.get(AcademicStudent, student_id)
        _refresh_aggregates(db, student)
        db.commit()
        grade = db.get(AcademicGrade, grade_id)
        assert float(grade.gpa_point) == 4.5, "新策略下95分应落在90-100档=4.5，不是旧公式的4.5(巧合)也不是2.0"
        assert grade.gpa_policy_code == "STRICT_BANDS2"
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_activate_rejects_overlapping_bands(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/gpa-policies/activate", headers=hdr, json={
        "scaleType": "BANDS",
        "bands": [
            {"minScore": 60, "maxScore": 90, "point": 3.0},
            {"minScore": 80, "maxScore": 100, "point": 4.0},  # 与上一档重叠
        ],
    })
    assert r.status_code != 200


def test_policy_version_chain_increments(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r1 = client.post(f"{BASE}/gpa-policies/activate", headers=hdr,
                     json={"policyCode": "CHAIN_TEST", "scaleType": "LINEAR"}).json()["data"]
    r2 = client.post(f"{BASE}/gpa-policies/activate", headers=hdr,
                     json={"policyCode": "CHAIN_TEST", "scaleType": "LINEAR", "linearDivisor": 8}).json()["data"]
    assert r2["policyVersion"] == r1["policyVersion"] + 1
    listing = client.get(f"{BASE}/gpa-policies", headers=hdr).json()["data"]
    statuses = {item["policyCode"]: item["status"] for item in listing if item["policyCode"] == "CHAIN_TEST"
               and item["policyVersion"] == r1["policyVersion"]}
    assert statuses.get("CHAIN_TEST") == "SUPERSEDED"
