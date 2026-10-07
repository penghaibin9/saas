"""Critical Mutation Matrix: SYSTEM runtime must consume published B8 authority."""
from __future__ import annotations

from sqlalchemy import select

from app.core import permissions as permission_runtime
from app.db.session import get_sessionmaker
from app.models import Role
from app.models.permission_governance import RoleTemplate, RoleTemplatePermission


TEST_TENANT_ID = 1000000000000000001
SYSTEM_ROLE_CODE = "SYS_ADMIN"
PROBE_PERMISSION = "systemAdmin.role.view"


def _session():
    return get_sessionmaker()()


def test_system_role_runtime_uses_published_template_and_fails_closed_on_drift(db_mode):
    """A DB SYSTEM context must never regain permission from legacy ROLE_PERMISSIONS."""
    created_role = False
    deleted_grant_id: int | None = None

    with _session() as db:
        role = db.scalars(select(Role).where(
            Role.tenant_id == TEST_TENANT_ID,
            Role.role_code == SYSTEM_ROLE_CODE,
            Role.is_deleted.is_(False),
        ).limit(1)).first()
        if role is None:
            role = Role(
                tenant_id=TEST_TENANT_ID,
                role_code=SYSTEM_ROLE_CODE,
                role_name="Critical Matrix SYS_ADMIN",
                role_type="SYSTEM",
                status="ACTIVE",
            )
            db.add(role)
            db.commit()
            db.refresh(role)
            created_role = True
        else:
            role.role_type = "SYSTEM"
            role.status = "ACTIVE"
            db.commit()
            db.refresh(role)
        role_id = int(role.id)

        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == SYSTEM_ROLE_CODE,
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.status == "ACTIVE",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).one()
        grant = db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.tenant_id == 0,
            RoleTemplatePermission.role_template_id == int(template.id),
            RoleTemplatePermission.permission_code == PROBE_PERMISSION,
            RoleTemplatePermission.is_deleted.is_(False),
        ).limit(1)).one()
        deleted_grant_id = int(grant.id)
        grant.is_deleted = True
        db.commit()

    actor = {
        "tenantId": str(TEST_TENANT_ID),
        "userId": "920401",
        "userType": SYSTEM_ROLE_CODE,
        "currentRoleCode": SYSTEM_ROLE_CODE,
        "activeContextId": f"role:{role_id}",
    }

    # Prove the old static baseline would ALLOW this permission. The runtime
    # decision must nevertheless DENY while published normalized Authority drifts.
    assert permission_runtime._match(
        PROBE_PERMISSION,
        permission_runtime.ROLE_PERMISSIONS[SYSTEM_ROLE_CODE],
    ) is True
    assert permission_runtime.has_permission(actor, PROBE_PERMISSION) is False

    try:
        with _session() as db:
            grant = db.get(RoleTemplatePermission, int(deleted_grant_id))
            assert grant is not None
            grant.is_deleted = False
            db.commit()

        # Restoring published Authority restores the runtime permission without
        # changing the legacy static baseline, proving the source actually used.
        assert permission_runtime.has_permission(actor, PROBE_PERMISSION) is True
    finally:
        with _session() as db:
            grant = db.get(RoleTemplatePermission, int(deleted_grant_id))
            if grant is not None and grant.is_deleted:
                grant.is_deleted = False
            if created_role:
                role = db.get(Role, role_id)
                if role is not None:
                    role.is_deleted = True
            db.commit()



def test_published_reduction_updates_existing_signed_session_without_logout(client, db_mode):
    """Real MySQL/HTTP regression, not evidence for the lost original 3311 JWTs."""
    import hashlib
    import secrets
    import time

    from app.core.config import settings
    from app.core.security import create_access_token, decode_token, hash_password
    from app.db.session import get_engine
    from app.models import Tenant, User, UserRole
    from app.modules.system_admin.services import role_template_service as templates
    from app.services.auth_service_db import _claims, _role_contexts
    from app.services.system_role_shadow_service import (
        expected_system_role_permissions, published_system_role_permissions,
    )

    assert get_engine().dialect.name == "mysql"
    removed = {"academicAffairs." + suffix for suffix in """
        term.manage calendar.manage calendarPublish.manage timeslot.manage
        classTimeBand.manage program.publish program.changeStatus schedule.rule.manage
        schedule.archive scheduleChange.academicReview selection.manage
        selection.rule.manage selection.lock selection.adjust exam.publish
        grade.publish grade.return grade.archive grade.policy.manage graduation.manage
        graduation.final graduationCert.manage archive.manage archive.export
        evaluation.batch.manage registration.archive.manage
        registration.unregistered.scan statusChange.officeReview
    """.split()}
    retained = {
        "academicAffairs.teachingTask.assign", "academicAffairs.teachingTask.confirm",
        "academicAffairs.schedule.edit", "academicAffairs.schedule.view",
        "academicAffairs.selection.rosterView", "academicAffairs.grade.collegeReview",
        "academicAffairs.graduation.collegeReview",
    }
    baseline = set(expected_system_role_permissions("COLLEGE_ADMIN"))
    other_baseline = set(expected_system_role_permissions("ACADEMIC_ADMIN"))
    assert len(removed) == 28 and removed <= baseline
    assert retained <= baseline - removed

    def draft(role_code, codes):
        return templates.create_draft(
            template_code=role_code, template_name=role_code,
            permission_codes=sorted(codes), change_reason="Existing session authority regression",
            actor_user_id=None,
        )

    def publish(candidate):
        return templates.publish_draft(
            int(candidate["id"]), expected_version=int(candidate["version"]), actor_user_id=None,
        )

    first = publish(draft("COLLEGE_ADMIN", baseline))
    publish(draft("ACADEMIC_ADMIN", other_baseline))
    # Use real subjects/links and the existing claims producer, without dependency
    # overrides, mock login or fabricated identity claims. Sign only before publish.
    with _session() as db:
        if db.get(Tenant, TEST_TENANT_ID) is None:
            db.add(Tenant(id=TEST_TENANT_ID, tenant_code="demo",
                          school_name="Existing session regression", status="ACTIVE"))
            db.flush()
        user_ids = {}
        for code in ("COLLEGE_ADMIN", "ACADEMIC_ADMIN"):
            role = db.scalars(select(Role).where(
                Role.tenant_id == TEST_TENANT_ID, Role.role_code == code,
                Role.is_deleted.is_(False),
            )).first()
            if role is None:
                role = Role(tenant_id=TEST_TENANT_ID, role_code=code, role_name=code,
                            role_type="SYSTEM", status="ACTIVE")
                db.add(role)
                db.flush()
            else:
                role.role_type = "SYSTEM"
                role.status = "ACTIVE"
            user = User(tenant_id=TEST_TENANT_ID,
                        login_name="existing_session_" + code.lower(), real_name=code,
                        password_hash=hash_password(secrets.token_urlsafe(32)),
                        user_type="SCHOOL_ADMIN", status="ACTIVE", must_change_password=False)
            db.add(user)
            db.flush()
            db.add(UserRole(tenant_id=TEST_TENANT_ID, user_id=user.id,
                            role_id=role.id, status="ACTIVE"))
            user_ids[code] = int(user.id)
        db.commit()
        headers, identities = {}, {}
        for code, user_id in user_ids.items():
            user = db.get(User, user_id)
            contexts = _role_contexts(db, user)
            context = next(item for item in contexts if item["roleCode"] == code)
            token = create_access_token(_claims(db, user, context, contexts, "PC"))
            headers[code] = {"Authorization": "Bearer " + token}
            identities[code] = decode_token(token)

    # Pace genuine requests within existing limits; never disable/reset enforcement.
    interval = 1.05 / max(1, min(settings.USER_API_RATE_LIMIT_PER_SECOND,
                               settings.TENANT_API_RATE_LIMIT_PER_SECOND))
    last_request = 0.0

    def check(role_code, permission, allowed):
        nonlocal last_request
        time.sleep(max(0.0, interval - (time.monotonic() - last_request)))
        response = client.post("/api/v1/authz/check", headers=headers[role_code],
                               json={"permissionCode": permission})
        last_request = time.monotonic()
        assert response.status_code == 200
        assert response.json()["data"]["allowed"] is allowed

    token_digests = {code: hashlib.sha256(value["Authorization"].encode()).hexdigest()
                     for code, value in headers.items()}
    for permission in sorted(removed | retained):
        check("COLLEGE_ADMIN", permission, True)
    other_probe = "academicAffairs.grade.publish"
    assert other_probe in other_baseline
    check("ACADEMIC_ADMIN", other_probe, True)
    with _session() as db:
        other_before = set(published_system_role_permissions(db, "ACADEMIC_ADMIN"))

    candidate = draft("COLLEGE_ADMIN", baseline - removed)
    impact = templates.impact(int(candidate["id"]))
    assert impact["baselineTemplateId"] == first["id"]
    assert set(impact["removedPermissions"]) == removed
    assert impact["addedPermissions"] == []
    published = publish(candidate)
    assert set(first["permissions"]) - set(published["permissions"]) == removed
    assert set(published["permissions"]) - set(first["permissions"]) == set()
    assert set(published["permissions"]) == baseline - removed
    for permission in sorted(removed):
        check("COLLEGE_ADMIN", permission, False)
    for permission in sorted(retained):
        check("COLLEGE_ADMIN", permission, True)
    check("ACADEMIC_ADMIN", other_probe, True)
    for code in headers:
        time.sleep(interval)
        response = client.get("/api/v1/auth/me", headers=headers[code])
        assert response.status_code == 200
        assert response.json()["data"]["userId"] == identities[code]["userId"]
    with _session() as db:
        assert set(published_system_role_permissions(db, "COLLEGE_ADMIN")) == baseline - removed
        assert set(published_system_role_permissions(db, "ACADEMIC_ADMIN")) == other_before
    assert {code: hashlib.sha256(value["Authorization"].encode()).hexdigest()
            for code, value in headers.items()} == token_digests
