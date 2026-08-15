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
