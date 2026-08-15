from sqlalchemy import select

from app.core.permissions import ROLE_PERMISSIONS, get_base_permission_patterns, has_permission
from app.core.school_admin_permission_resolver import catalog_school_admin_permissions
from app.services import system_role_shadow_service as shadow


def _school_admin_user(user_id: str = "db-9821") -> dict:
    return {
        "userId": user_id,
        "tenantId": "1",
        "currentRoleCode": "SCHOOL_ADMIN",
        "userType": "STAFF",
    }


def test_school_admin_runtime_is_explicit_while_legacy_shadow_stays_frozen(db_mode):
    shadow.converge_published_system_templates(
        actor_user_id=9821,
        source_commit_sha="school-admin-runtime-cutover",
    )
    expected = set(catalog_school_admin_permissions())
    runtime = set(get_base_permission_patterns(_school_admin_user()))

    # The old wildcard remains solely as B8 comparison evidence. Runtime must
    # never consume it after the cutover.
    assert ROLE_PERMISSIONS["SCHOOL_ADMIN"] == {"*"}
    assert runtime == expected
    assert len(runtime) > 400
    assert "*" not in runtime
    assert not any(code.startswith("platform.") for code in runtime)
    assert not any(code.startswith("enterprise.") for code in runtime)
    # Legacy callers may still ask the semantic full-school question, but the
    # answer is derived from complete permanent TENANT coverage, not a token.
    assert has_permission(_school_admin_user(), "*") is True


def test_temporary_wildcard_never_becomes_full_school_authority(db_mode, monkeypatch):
    from app.services import system_governance_service as gov

    monkeypatch.setattr(gov, "active_delegation_permission_patterns", lambda user: ["*"])
    teacher = {
        "userId": "db-9823",
        "tenantId": "1",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "userType": "TEACHER",
    }
    assert has_permission(teacher, "academicAffairs.grade.view") is True
    assert has_permission(teacher, "*") is False


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

    user = _school_admin_user("db-9822")
    runtime = get_base_permission_patterns(user)
    assert runtime == []
    assert has_permission(user, "*") is False