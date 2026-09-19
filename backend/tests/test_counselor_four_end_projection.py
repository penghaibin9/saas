"""班级主辅导员交接后，教师范围与学生两端责任人展示使用同一权威关系。"""
from __future__ import annotations

from test_affairs_counselor_assignment import BASE, _assign, _hdr, _seed


def _token(user_id, *, user_type, role, student_id=None):
    from app.core.security import create_access_token

    payload = {
        "userId": str(user_id) if user_type == "STUDENT" else f"db-{user_id}",
        "realName": "四端责任关系验收账号",
        "userType": user_type,
        "tid": "demo",
        "tenantId": "1000000000000000001",
        "currentRoleCode": role,
        "clientType": "STUDENT_MINI" if user_type == "STUDENT" else "TEACHER_MINI",
    }
    if student_id is not None:
        payload["studentId"] = str(student_id)
        payload["studentNo"] = "CA001"
    return {"Authorization": "Bearer " + create_access_token(payload)}


def _data(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def test_primary_handover_updates_teacher_scope_and_student_pc_mini_projection(client, db_mode):
    ids = _seed(db_mode)
    # Real teacher tokens require an active school role; class responsibility
    # assignments alone do not grant a login position.
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import Role, UserRole
    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(Role.tenant_id == 1000000000000000001,
                                           Role.role_code == "COUNSELOR"))
        if role is None:
            role = Role(tenant_id=1000000000000000001, role_code="COUNSELOR",
                        role_name="辅导员", status="ACTIVE")
            db.add(role)
            db.flush()
        for user_id in (ids["u1"], ids["u2"]):
            db.add(UserRole(tenant_id=1000000000000000001, user_id=user_id,
                            role_id=role.id, status="ACTIVE"))
        db.commit()
    admin = _hdr(client, "school_admin01")
    old_teacher = _token(ids["u1"], user_type="TEACHER", role="COUNSELOR")
    new_teacher = _token(ids["u2"], user_type="TEACHER", role="COUNSELOR")

    from app.db.session import get_sessionmaker
    from app.models import AcademicStudent, StudentProfile

    with get_sessionmaker()() as db:
        # This story hands over existing students. Keep their creation before the
        # keyset snapshot (MySQL DATETIME can round a fresh ORM timestamp forward).
        from datetime import datetime, timedelta
        db.query(StudentProfile).filter_by(
            tenant_id=1000000000000000001, class_id=ids["a"]
        ).update({StudentProfile.created_at: datetime.utcnow() - timedelta(days=1)})
        db.commit()
        student_id = db.query(StudentProfile.id).filter_by(
            tenant_id=1000000000000000001, class_id=ids["a"], student_no="CA001"
        ).scalar()
        other_student_id = db.query(StudentProfile.id).filter_by(
            tenant_id=1000000000000000001, class_id=ids["a"], student_no="CA002"
        ).scalar()
        # The stable profile link is authoritative.  The later malformed
        # legacy snapshot has A's number but explicitly belongs to B and must
        # never become A's academic summary merely because it has the larger id.
        db.add_all([
            AcademicStudent(
                tenant_id=1000000000000000001, student_id=student_id,
                student_no="CA001", name="学生甲", gpa=3.3,
            ),
            AcademicStudent(
                tenant_id=1000000000000000001, student_id=other_student_id,
                student_no="CA001", name="错误绑定的学生乙", gpa=0.1,
            ),
        ])
        db.commit()
    student = _token(910001, user_type="STUDENT", role="STUDENT", student_id=student_id)

    original = _data(_assign(client, admin, ids["a"], ids["u1"], reason="新学期带班安排"))

    old_classes = _data(client.get("/api/v1/mobile/teacher/my-classes", headers=old_teacher))
    assert str(ids["a"]) in {row["classId"] for row in old_classes["items"]}
    old_students = _data(client.get(
        "/api/v1/teacher-mobile/students",
        headers=old_teacher,
        params={"classId": ids["a"], "pageSize": 20},
    ))
    assert str(student_id) in {row["studentId"] for row in old_students["items"]}

    before_pc = _data(client.get("/api/v1/portal/profile/enrollment", headers=student))
    before_mini = _data(client.get("/api/v1/mobile/me/profile", headers=student))
    assert before_pc["counselorName"] == "辅导员一"
    assert before_mini["counselorName"] == "辅导员一"

    moved = _data(client.post(
        f"{BASE}/classes/{ids['a']}/counselor-handover",
        headers=admin,
        json={
            "fromUserId": ids["u1"],
            "toUserId": ids["u2"],
            "reason": "岗位调整，完整移交班级责任",
            "version": original["version"],
        },
    ))
    assert moved["counselorName"] == "辅导员二"

    old_after = _data(client.get("/api/v1/mobile/teacher/my-classes", headers=old_teacher))
    assert str(ids["a"]) not in {row["classId"] for row in old_after["items"]}
    old_deep_link = _data(client.get(
        "/api/v1/teacher-mobile/students",
        headers=old_teacher,
        params={"classId": ids["a"], "pageSize": 20},
    ))
    assert old_deep_link["items"] == []

    new_after = _data(client.get("/api/v1/mobile/teacher/my-classes", headers=new_teacher))
    assert str(ids["a"]) in {row["classId"] for row in new_after["items"]}
    new_deep_link = _data(client.get(
        "/api/v1/teacher-mobile/students",
        headers=new_teacher,
        params={"classId": ids["a"], "pageSize": 20},
    ))
    assert str(student_id) in {row["studentId"] for row in new_deep_link["items"]}

    # MyStudents and Student360 must compile exactly the same responsibility
    # predicate.  A direct counselor/head-teacher relation is a real scope, not
    # merely enough to render a list row that then fails with a false 404.
    old_projection = client.get(
        f"/api/v1/teacher-mobile/students/{student_id}/projection",
        headers=old_teacher,
    )
    assert old_projection.status_code == 404, old_projection.text
    new_projection = _data(client.get(
        f"/api/v1/teacher-mobile/students/{student_id}/projection",
        headers=new_teacher,
    ))
    assert new_projection["studentId"] == str(student_id)
    assert new_projection["base"]["studentNo"] == "CA001"
    academic = next(section for section in new_projection["sections"] if section["key"] == "academic")
    assert "平均绩点 3.30" in academic["summary"]

    after_pc = _data(client.get("/api/v1/portal/profile/enrollment", headers=student))
    after_mini = _data(client.get("/api/v1/mobile/me/profile", headers=student))
    assert after_pc["counselorName"] == "辅导员二"
    assert after_mini["counselorName"] == "辅导员二"


def test_co_counselor_cannot_replace_primary_through_handover_endpoint(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    primary = _data(_assign(client, admin, ids["a"], ids["u1"], reason="主责安排"))
    co = _data(_assign(client, admin, ids["a"], ids["u2"], duty="CO", reason="协同支持"))

    denied = client.post(
        f"{BASE}/classes/{ids['a']}/counselor-handover",
        headers=admin,
        json={
            "fromUserId": ids["u2"],
            "toUserId": ids["u3"],
            "reason": "错误地从协同关系发起交接",
            "version": co["version"],
        },
    )
    assert denied.status_code == 409
    assert denied.json()["bizCode"] == "DATA_CONFLICT"

    rows = _data(client.get(
        f"{BASE}/counselor-assignments", headers=admin,
        params={"classId": ids["a"], "status": "ACTIVE"},
    ))["items"]
    current = next(row for row in rows if row["dutyType"] == "PRIMARY")
    assert current["id"] == primary["id"]


def test_teacher_numeric_id_accepts_production_login_prefix():
    from app.services import _mobile_teacher_service_impl as service

    assert service._teacher_numeric_id({"userId": "db-12345"}) == 12345
    assert service._teacher_numeric_id({"userId": "u_12345"}) == 12345
