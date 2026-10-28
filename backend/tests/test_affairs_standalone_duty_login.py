from datetime import datetime, timedelta


def test_all_eight_standalone_duties_login_and_project_only_their_entries(client, db_mode):
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, User, UserRole
    from app.services.saas_role_service import ensure_builtin_roles
    from test_affairs_security import TID, _base
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr

    ids = _base(db_mode)
    cases = [
        ("STUDENT_AFFAIRS_ADMIN", "SCHOOL", 0, "/risk/records", set()),
        ("STUDENT_AFFAIRS_COLLEGE", "COLLEGE", ids["col1"], "/risk/records", set()),
        ("COUNSELOR", "CLASS", ids["cA"], "/risk/records", set()),
        ("FUNDING_TEACHER", "COLLEGE", ids["col1"], "/funding/projects", {"WORK_STUDY", "LOAN", "REDUCTION"}),
        ("PSYCHOLOGY_TEACHER", "STUDENT", ids["A"], "/mental/list", {"MENTAL"}),
        ("DORM_MANAGER", None, None, "/dorm/buildings", set()),
        ("YOUTH_LEAGUE", "COLLEGE", ids["col1"], "/clubs", {"ACTIVITY"}),
        ("ORG_PERSONNEL", "COLLEGE", ids["col1"], "/counselor-eval/indicators", set()),
    ]
    with get_sessionmaker()() as db:
        ensure_builtin_roles(db, TID)
        password_hash = hash_password(TEST_LOGIN_PASSWORD)
        for code, scope_type, scope_id, _, _ in cases:
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code))
            account = User(tenant_id=TID, login_name=f"standalone_{code.lower()}", real_name="独立任职测试",
                user_type="TEACHER", password_hash=password_hash, status="ACTIVE", must_change_password=False)
            db.add(account); db.flush()
            member = UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE")
            db.add(member); db.flush()
            if scope_type:
                db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=member.id,
                    role_code=code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                    effective_at=datetime.utcnow() - timedelta(days=1)))
        db.commit()

    for code, _, _, path, expected in cases:
        headers = _real_hdr(client, f"standalone_{code.lower()}")
        response = client.get("/api/v1/student-affairs" + path, headers=headers)
        assert response.status_code == 200, (code, response.text)
        workbench = client.get("/api/v1/mobile/teacher/affairs", headers=headers)
        assert workbench.status_code == 200, (code, workbench.text)
        assert set(workbench.json()["data"]["entryActions"]) == expected, code
        other = "/funding/projects" if code != "FUNDING_TEACHER" and code != "COUNSELOR" else "/mental/list"
        assert client.get("/api/v1/student-affairs" + other, headers=headers).status_code == 403, code
