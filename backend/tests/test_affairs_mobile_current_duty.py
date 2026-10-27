from datetime import datetime, timedelta


def test_real_mobile_role_switch_keeps_keyset_detail_and_cursor_in_current_duty(client, db_mode):
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, SchoolClass, StudentProfile, User, UserRole
    from app.services.saas_role_service import ensure_builtin_roles
    from test_affairs_security import TID, _base
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr

    ids = _base(db_mode)
    with get_sessionmaker()() as db:
        ensure_builtin_roles(db, TID)
        account = User(tenant_id=TID, login_name="mobile_combined_duties", real_name="手机兼岗验收",
            user_type="TEACHER", password_hash=hash_password(TEST_LOGIN_PASSWORD), status="ACTIVE", must_change_password=False)
        db.add(account); db.flush()
        db.get(SchoolClass, ids["cA"]).counselor_id = account.id
        db.get(SchoolClass, ids["cB"]).head_teacher_id = account.id
        # 同名班也不能把资助/心理/辅导员范围互相扩大。
        db.get(SchoolClass, ids["cC"]).class_name = db.get(SchoolClass, ids["cA"]).class_name
        peer = StudentProfile(tenant_id=TID, student_no="C002", real_name="同班未授权学生",
            class_id=ids["cC"], college_id=ids["col2"], current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE",
            created_at=datetime.utcnow() - timedelta(minutes=1))
        db.add(peer); db.flush()
        contexts = {}
        funding_scope_id = None
        for code, scope_type, scope_id in (("COUNSELOR", "CLASS", ids["cA"]),
                ("FUNDING_TEACHER", "COLLEGE", ids["col2"]),
                ("PSYCHOLOGY_TEACHER", "STUDENT", ids["C"]), ("DORM_MANAGER", None, None)):
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code))
            member = UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE")
            db.add(member); db.flush(); contexts[code] = role.id
            if scope_type:
                row = RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=member.id,
                    role_code=code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                    effective_at=datetime.utcnow() - timedelta(days=1))
                db.add(row); db.flush()
                if code == "FUNDING_TEACHER":
                    funding_scope_id = row.id
        db.commit()

    headers = _real_hdr(client, "mobile_combined_duties", client_type="TEACHER_MINI")

    def switch(code):
        nonlocal headers
        result = client.post("/api/v1/auth/switch-role", headers=headers,
            json={"contextId": f"role:{contexts[code]}", "clientType": "TEACHER_MINI"})
        assert result.status_code == 200, result.text
        headers = {"Authorization": "Bearer " + result.json()["data"]["accessToken"]}

    def listing(**params):
        return client.get("/api/v1/teacher-mobile/students", headers=headers, params=params)

    def projection(sid):
        return client.get(f"/api/v1/teacher-mobile/students/{sid}/projection", headers=headers)

    switch("FUNDING_TEACHER")
    first = listing(pageSize=1)
    assert first.status_code == 200, first.text
    first = first.json()["data"]
    assert first["items"][0]["studentNo"] == "C001" and first["total"] == 3
    cursor = first["nextCursor"]
    assert cursor
    second = listing(pageSize=1, cursor=cursor)
    assert second.status_code == 200 and second.json()["data"]["items"][0]["studentNo"] == "C002"
    assert projection(ids["A"]).status_code == 404
    assert projection(ids["C"]).status_code == 200
    assert client.get(f"/api/v1/mobile/teacher/student/{ids['A']}", headers=headers).status_code == 403

    switch("COUNSELOR")
    mine = listing().json()["data"]
    assert [x["studentNo"] for x in mine["items"]] == ["A001"]
    assert listing(cursor=cursor).status_code == 400
    assert projection(ids["B"]).status_code == 404
    assert projection(ids["C"]).status_code == 404
    from app.core.context import get_tenant, set_tenant
    from app.services import mobile_teacher_service as teacher
    from app.services import _mobile_teacher_service_impl as legacy_teacher
    previous = get_tenant(); set_tenant(TID)
    try:
        current = {"userId": str(account.id), "loginName": account.login_name, "userType": "TEACHER",
            "currentRoleCode": "COUNSELOR", "tenantId": str(TID),
            "activeContextId": f"role:{contexts['COUNSELOR']}"}
        own = legacy_teacher._filter_approvals_by_scope(teacher.resolve_teacher_scope(current),
            [{"taskId": "own", "applicantName": "甲一"}, {"taskId": "other", "applicantName": "乙一"}], user=current)
        assert [row["taskId"] for row in own] == ["own"]
    finally:
        set_tenant(previous)

    switch("PSYCHOLOGY_TEACHER")
    mine = listing().json()["data"]
    assert [x["studentNo"] for x in mine["items"]] == ["C001"]
    assert projection(ids["C"]).status_code == 200
    assert projection(peer.id).status_code == 404
    assert projection(ids["A"]).status_code == 404
    assert listing(cursor=cursor).status_code == 400

    switch("DORM_MANAGER")
    assert listing().status_code == 403
    assert projection(ids["A"]).status_code == 403

    switch("FUNDING_TEACHER")
    with get_sessionmaker()() as db:
        db.get(RoleAssignmentScope, funding_scope_id).status = "REVOKED"
        db.commit()
    assert listing(cursor=cursor).status_code == 400
    response = listing()
    assert response.status_code == 200 and response.json()["data"]["items"] == []
    # 明确撤销本职责全部学工能力也不能退回账号其他任职的带班范围。
    with get_sessionmaker()() as db:
        role = db.get(Role, contexts["FUNDING_TEACHER"])
        role.role_type = "CUSTOM"; role.version += 1
        db.commit()
    headers = _real_hdr(client, "mobile_combined_duties", client_type="TEACHER_MINI")
    switch("FUNDING_TEACHER")
    assert listing().status_code == 403
    assert projection(ids["A"]).status_code == 403
