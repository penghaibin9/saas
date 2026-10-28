from app.core.permissions import ROLE_PERMISSIONS, _match
from app.services.saas_role_templates import AFFAIRS_DELIVERY_ROLE_CODES, ROLE_TEMPLATE_BY_CODE, role_catalog


def test_confirmed_roles_have_explicit_defaults_without_sensitive_or_export_grants():
    from app.core.permission_catalog import permission_meta
    from app.core.student_affairs_permission_registry import STUDENT_AFFAIRS_PERMISSION_CODES
    assert all(permission_meta(code) is not None for code in STUDENT_AFFAIRS_PERMISSION_CODES)
    assert len(AFFAIRS_DELIVERY_ROLE_CODES) == 8
    assert "STUDENT_AFFAIRS_COLLEGE" in AFFAIRS_DELIVERY_ROLE_CODES
    forbidden = (
        "studentAffairs.aid.sensitiveView", "studentAffairs.funding.sensitiveView",
        "studentAffairs.risk.psyDetail.view", "studentAffairs.archive.psySensitive",
        "studentAffairs.leave.export", "studentAffairs.dorm.export", "studentAffairs.orientation.export",
        "studentAffairs.export", "studentAffairs.funding.disburse.manage", "campusService.leave.export",
    )
    for role in AFFAIRS_DELIVERY_ROLE_CODES:
        assert role in ROLE_TEMPLATE_BY_CODE
        patterns = ROLE_PERMISSIONS[role]
        assert _match("workbench.home.view", patterns)
        assert _match("approval.todo.view", patterns)
        assert not any(_match(code, patterns) for code in forbidden), role
        assert not any(code.startswith("studentAffairs.") and "*" in code for code in patterns), role
    from app.services.system_role_shadow_service import expected_system_role_permissions
    for role in ("COLLEGE_ADMIN", "STUDENT_AFFAIRS"):
        assert "studentAffairs.aid.sensitiveView" not in expected_system_role_permissions(role)
        assert "studentAffairs.funding.sensitiveView" not in expected_system_role_permissions(role)


def test_basic_positions_do_not_implicitly_receive_specialist_management():
    specialist = ("studentAffairs.mental.manage", "studentAffairs.funding.project.manage",
                  "studentAffairs.club.manage", "studentAffairs.org.manage", "studentAffairs.league.manage",
                  "studentAffairs.dorm.resource.manage", "studentAffairs.counselorEval.manage")
    for role in ("STUDENT_AFFAIRS_ADMIN", "STUDENT_AFFAIRS_COLLEGE", "COUNSELOR"):
        assert not any(_match(code, ROLE_PERMISSIONS[role]) for code in specialist), role
    assert not _match("studentAffairs.config.manage", ROLE_PERMISSIONS["STUDENT_AFFAIRS_COLLEGE"])
    assert _match("studentAffairs.aid.approve", ROLE_PERMISSIONS["STUDENT_AFFAIRS_COLLEGE"])
    assert _match("studentAffairs.aid.counselorReview", ROLE_PERMISSIONS["COUNSELOR"])
    assert not _match("studentAffairs.aid.approve", ROLE_PERMISSIONS["COUNSELOR"])
    assert _match("studentAffairs.mental.manage", ROLE_PERMISSIONS["PSYCHOLOGY_TEACHER"])


def test_role_catalog_keeps_legacy_identity_but_new_choices_use_the_confirmed_roles():
    all_codes = {row["roleCode"] for row in role_catalog()["items"]}
    choices = {row["roleCode"] for row in role_catalog(teacher_only=True)["items"]}
    assert "STUDENT_AFFAIRS" in all_codes and "STUDENT_AFFAIRS" not in choices
    assert AFFAIRS_DELIVERY_ROLE_CODES <= choices
    for role in ("FUNDING_TEACHER", "YOUTH_LEAGUE", "ORG_PERSONNEL"):
        assert ROLE_TEMPLATE_BY_CODE[role]["defaultScope"] == "SCHOOL_OR_COLLEGE"


def test_scoped_publication_restricts_affairs_without_rewriting_history_or_other_centers(db_mode):
    from datetime import datetime
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
    from app.services import system_role_shadow_service as shadow

    def publish_fixture(db, code, permissions):
        previous = shadow._latest_published_template(db, code)
        row = RoleTemplate(tenant_id=0, template_code=code, template_name="隔离测试发布版",
            template_version=previous.template_version + 1, publish_status="PUBLISHED", status="ACTIVE",
            permission_digest=shadow._digest(permissions), previous_template_id=previous.id,
            permission_ceiling_json={"items": sorted(permissions)}, published_at=datetime.utcnow())
        db.add(row); db.flush()
        for permission in permissions:
            db.add(RoleTemplatePermission(tenant_id=0, role_template_id=row.id,
                                          permission_code=permission, effect="ALLOW"))
        return row.id

    with get_sessionmaker()() as db:
        old_codes = set(shadow.published_system_role_permissions(db, "STUDENT_AFFAIRS_ADMIN"))
        old_codes |= {"studentAffairs.risk.psyDetail.view", "studentAffairs.leave.export"}
        old_id = publish_fixture(db, "STUDENT_AFFAIRS_ADMIN", old_codes)
        academic_codes = set(shadow.published_system_role_permissions(db, "ACADEMIC_TEACHER"))
        academic_codes.discard("academicAffairs.schedule.view")
        academic_id = publish_fixture(db, "ACADEMIC_TEACHER", academic_codes)
        db.commit()
        assert "studentAffairs.risk.psyDetail.view" in shadow.published_system_role_permissions(db, "STUDENT_AFFAIRS_ADMIN")
    result = shadow.converge_affairs_role_templates(actor_user_id=9801, source_commit_sha="isolated-affairs-template-test")
    assert set(result["targetRoleCodes"]) == AFFAIRS_DELIVERY_ROLE_CODES
    assert {row["roleCode"] for row in result["created"]} == {"STUDENT_AFFAIRS_ADMIN"}
    with get_sessionmaker()() as db:
        assert "studentAffairs.risk.psyDetail.view" not in shadow.published_system_role_permissions(db, "STUDENT_AFFAIRS_ADMIN")
        assert "studentAffairs.leave.approve" in shadow.published_system_role_permissions(db, "STUDENT_AFFAIRS_COLLEGE")
        assert shadow._latest_published_template(db, "ACADEMIC_TEACHER").id == academic_id
        assert set(shadow.published_system_role_permissions(db, "ACADEMIC_TEACHER")) == academic_codes
        assert set(db.scalars(select(RoleTemplatePermission.permission_code).where(
            RoleTemplatePermission.role_template_id == old_id)).all()) == old_codes
    again = shadow.converge_affairs_role_templates(actor_user_id=9801, source_commit_sha="isolated-affairs-template-test")
    assert again["createdCount"] == 0


def test_real_combined_account_switches_scope_and_cannot_borrow_another_duty(client, db_mode):
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Permission, Role, RoleAssignmentScope, RolePermission, User, UserRole
    from app.services.saas_role_service import ensure_builtin_roles
    from app.services.system_role_shadow_service import published_system_role_permissions
    from test_affairs_security import TID, _base
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_mental import _refer

    ids = _base(db_mode)
    with get_sessionmaker()() as db:
        ensure_builtin_roles(db, TID)
        account = User(tenant_id=TID, login_name="confirmed_combined", real_name="兼岗验证老师",
            user_type="TEACHER", password_hash=hash_password(TEST_LOGIN_PASSWORD), status="ACTIVE", must_change_password=False)
        db.add(account); db.flush()
        contexts = {}
        for code, scope_type, scope_id in (("STUDENT_AFFAIRS_COLLEGE", "COLLEGE", ids["col1"]),
                ("FUNDING_TEACHER", "COLLEGE", ids["col2"]), ("PSYCHOLOGY_TEACHER", "STUDENT", ids["A"])):
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code))
            link = UserRole(tenant_id=TID, user_id=account.id, role_id=role.id, status="ACTIVE")
            db.add(link); db.flush()
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=account.id, user_role_id=link.id, role_code=code,
                scope_type=scope_type, scope_id=scope_id, status="ACTIVE", effective_at=datetime.utcnow() - timedelta(days=1)))
            contexts[code] = role.id
        db.commit()
    headers = _real_hdr(client, "confirmed_combined")

    def switch(code):
        nonlocal headers
        response = client.post("/api/v1/auth/switch-role", headers=headers,
            json={"contextId": f"role:{contexts[code]}", "clientType": "PC"})
        assert response.status_code == 200, response.text
        headers = {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}

    def students():
        response = client.get("/api/v1/students", headers=headers, params={"pageSize": 50})
        assert response.status_code == 200, response.text
        return {row["studentNo"] for row in response.json()["data"]["items"]}

    switch("STUDENT_AFFAIRS_COLLEGE")
    assert students() == {"A001", "B001"}
    assert client.get("/api/v1/student-affairs/funding/projects", headers=headers).status_code == 403
    switch("FUNDING_TEACHER")
    assert students() == {"C001", "D001"}
    assert client.get("/api/v1/student-affairs/leave/pending", headers=headers).status_code == 403
    denied_project = client.post("/api/v1/student-affairs/funding/projects", headers=headers,
        json={"projectName": "学院不得建校级项目", "projectType": "GRANT", "amount": 1000, "quota": 10})
    assert denied_project.status_code == 403, denied_project.text
    switch("PSYCHOLOGY_TEACHER")
    assert students() == {"A001"}
    assert client.get(f"/api/v1/student-affairs/students/{ids['B']}/profile", headers=headers).status_code == 403
    created = _refer(client, headers, ids["A"])
    assert created.status_code == 200, created.text
    record = created.json()["data"]
    assert record["noteMasked"] and not record["canReveal"]
    denied = _refer(client, headers, ids["B"])
    assert denied.status_code == 403, denied.text
    url = f"/api/v1/student-affairs/mental/referrals/{record['referralId']}"
    masked = client.get(url, headers=headers, params={"reason": "查看当前授权个案记录"})
    assert masked.status_code == 200 and masked.json()["data"]["noteMasked"]

    # 单独安排当前心理职责的原文授权；不改变该人的其他职责或学生范围。
    with get_sessionmaker()() as db:
        role = db.get(Role, contexts["PSYCHOLOGY_TEACHER"])
        codes = set(published_system_role_permissions(db, role.role_code)) | {"studentAffairs.risk.psyDetail.view"}
        role.role_type = "CUSTOM"; role.version += 1
        for permission in db.scalars(select(Permission).where(Permission.permission_code.in_(codes))).all():
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
        db.commit()
    headers = _real_hdr(client, "confirmed_combined")
    switch("PSYCHOLOGY_TEACHER")
    revealed = client.get(url, headers=headers, params={"reason": "核实当前授权个案原始记录"})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["data"]["note"] == "涉密明细内容XYZ"
    assert students() == {"A001"}
