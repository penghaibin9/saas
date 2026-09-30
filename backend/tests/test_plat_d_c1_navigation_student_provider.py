from __future__ import annotations

import inspect

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import SchoolClass, StudentProfile
from app.modules.platform.business_collaboration.navigation import NavigationTargetResolver
from app.modules.platform.business_collaboration.schemas import SearchContext
from app.modules.platform.business_collaboration.student_provider import StudentSearchProvider


TENANT = 1001
OTHER_TENANT = 1002


def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SchoolClass.__table__.create(engine)
    StudentProfile.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        allowed = SchoolClass(tenant_id=TENANT, major_id=1, class_name="软件2301", status="ACTIVE")
        denied = SchoolClass(tenant_id=TENANT, major_id=1, class_name="机电2301", status="ACTIVE")
        other = SchoolClass(tenant_id=OTHER_TENANT, major_id=1, class_name="外租户", status="ACTIVE")
        db.add_all([allowed, denied, other])
        db.flush()
        db.add_all([
            StudentProfile(
                tenant_id=TENANT, student_no="S20260001", real_name="张三", class_id=allowed.id,
                grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
            ),
            StudentProfile(
                tenant_id=TENANT, student_no="S20260002", real_name="张四", class_id=denied.id,
                grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
            ),
            StudentProfile(
                tenant_id=OTHER_TENANT, student_no="S20260003", real_name="张五", class_id=other.id,
                grade="2026", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
            ),
        ])
        db.commit()
    return factory, int(allowed.id)


def _actor(**extra):
    return {
        "userId": "u_91",
        "userType": "TEACHER",
        "currentRoleCode": "COUNSELOR",
        "tenantId": str(TENANT),
        "permissionPatterns": ["student.profile.view"],
        **extra,
    }


def test_navigation_target_is_allowlisted_and_client_specific():
    resolver = NavigationTargetResolver()
    pc = resolver.student(88, client="pc", actor=_actor())
    assert pc and pc.route_name == "student-detail"
    assert pc.route_params == {"studentId": "88"}
    assert pc.path == "/admin/student/88" and pc.exact is True

    teacher = resolver.student(88, client="teacherMini", actor=_actor())
    assert teacher and teacher.path == "/pages/teacher/student-detail/index"
    assert teacher.query == {"id": "88"}

    assert resolver.student(88, client="studentPc", actor=_actor(studentId="99")) is None
    own = resolver.student(88, client="studentPc", actor=_actor(userType="STUDENT", studentId="88"))
    assert own and own.path == "/profile"


def test_student_provider_applies_tenant_and_scope_in_sql_before_hydration():
    factory, allowed_class_id = _factory()
    provider = StudentSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: StudentProfile.class_id == allowed_class_id,
    )
    hits = provider.search(SearchContext(
        tenant_id=TENANT, actor=_actor(), keyword="张三", client="pc", limit=10,
    ))
    assert [hit.title for hit in hits] == ["张三"]
    assert hits[0].secondary == "S20260001 · 软件2301 · 2026级"
    assert hits[0].allowed_actions == ["OPEN"]
    assert hits[0].target and hits[0].target.route_params == {"studentId": hits[0].object_id}

    # Student numbers are identifiers: exact matching is allowed, prefix
    # discovery is not.
    assert [hit.title for hit in provider.search(SearchContext(
        tenant_id=TENANT, actor=_actor(), keyword="S20260001", client="pc",
    ))] == ["张三"]
    assert provider.search(SearchContext(
        tenant_id=TENANT, actor=_actor(), keyword="S2026", client="pc",
    )) == []


def test_student_provider_min_keyword_permission_and_no_target_fail_closed():
    factory, allowed_class_id = _factory()
    provider = StudentSearchProvider(
        factory,
        scope_resolver=lambda _db, _ctx: StudentProfile.class_id == allowed_class_id,
    )
    assert provider.search(SearchContext(tenant_id=TENANT, actor=_actor(), keyword="张")) == []
    assert provider.search(SearchContext(
        tenant_id=TENANT,
        actor={
            "userType": "TEACHER", "currentRoleCode": "UNSCOPED",
            "tenantId": str(TENANT), "permissionPatterns": [],
        },
        keyword="张三",
    )) == []

    student = provider.search(SearchContext(
        tenant_id=TENANT,
        actor={"userType": "STUDENT", "studentId": "999", "tenantId": str(TENANT)},
        keyword="张三",
        client="studentPc",
    ))
    assert len(student) == 1
    assert student[0].target is None
    assert student[0].allowed_actions == []

    assert provider.search(SearchContext(
        tenant_id=TENANT,
        actor=_actor(tenantId=str(OTHER_TENANT)),
        keyword="张三",
    )) == []


def test_provider_does_not_construct_raw_client_urls():
    source = inspect.getsource(StudentSearchProvider)
    assert "/admin/" not in source
    assert "/pages/" not in source
    assert "NavigationTargetResolver" in source
