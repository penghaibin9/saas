from sqlalchemy import select

from app.core.permissions import ROLE_PERMISSIONS, get_base_permission_patterns
from app.core.school_admin_permission_resolver import catalog_school_admin_permissions
from app.services import system_role_shadow_service as shadow


def test_school_admin_runtime_is_explicit_while_legacy_shadow_stays_frozen(db_mode):
    shadow.converge_published_system_templates(
        actor_user_id=9821,
        source_commit_sha="school-admin-runtime-cutover",
    )
    expected = set(catalog_school_admin_permissions())
    runtime = set(get_base_permission_patterns({
        "userId": "db-9821",
        "tenantId": "1",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "STAFF",
    }))

    # The old wildcard remains solely as B8 comparison evidence. Runtime must
    # never consume it after the cutover.
    assert ROLE_PERMISSIONS["SCHOOL_ADMIN"] == {"*"}
    assert runtime == expected
    assert len(runtime) > 400
    assert "*" not in runtime
    assert not any(code.startswith("platform.") for code in runtime)
    assert not any(code.startswith("enterprise.") for code in runtime)


def test_school_admin_runtime_fails_closed_when_published_snapshot_drifts(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission

    shadow.converge_published_system_templates(
        actor_user_id=9822,
        source_commit_sha="school-admin-runtime-cutover-drift",
    )
    db = get_sessionmaker()()
    try:
        template = db.scalars(select(RoleTemplate).where(
            RoleTemplate.tenant_id == 0,
            RoleTemplate.template_code == "SCHOOL_ADMIN",
            RoleTemplate.publish_status == "PUBLISHED",
            RoleTemplate.is_deleted.is_(False),
        ).order_by(RoleTemplate.template_version.desc(), RoleTemplate.id.desc()).limit(1)).first()
        assert template is not None
        row = db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == int(template.id),
            RoleTemplatePermission.is_deleted.is_(False),
        ).limit(1)).first()
        assert row is not None
        row.is_deleted = True
        db.commit()
    finally:
        db.close()

    runtime = get_base_permission_patterns({
        "userId": "db-9822",
        "tenantId": "1",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "STAFF",
    })
    assert runtime == []
