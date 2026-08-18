from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.exceptions import AppException
from app.modules.system_admin.policies.role_template_plane import assert_school_role_template_code
from app.modules.system_admin.services import role_template_service as svc
from app.services import audit_log


CATALOG_VIEW = "internship.recruitment.view"
CATALOG_MANAGE = "internship.recruitment.manage"
CATALOG_INVITE = "internship.recruitment.invite"


def test_published_template_status_and_audit_contract():
    assert svc.PUBLISHED == "PUBLISHED"
    assert "ROLE_TEMPLATE_PUBLISH" in audit_log.CRITICAL_ACTIONS


def test_enterprise_and_platform_roles_cannot_enter_school_role_templates():
    for role in ("COMPANY_ADMIN", "HR", "MENTOR", "PLATFORM_OWNER", "PLATFORM_OPERATIONS"):
        try:
            assert_school_role_template_code(role)
        except Exception:
            pass
        else:
            raise AssertionError(f"{role} must not be a school RoleTemplate")


def test_role_template_digest_is_order_independent():
    assert svc._digest([CATALOG_VIEW, CATALOG_MANAGE]) == svc._digest([
        CATALOG_MANAGE, CATALOG_VIEW
    ])


def test_b5_migration_is_existing_table_upgrade_not_v2_and_has_normalized_relation():
    path = Path("alembic/versions/20260815_control_plane_role_governance.py")
    source = path.read_text(encoding="utf-8")
    assert 'revision = "20260815_ctrl_role_gov"' in source
    assert 'down_revision = "20260814_merge_ix_v93_main"' in source
    assert '"t_role_template_permission"' in source
    assert '"role_id"' in source
    assert "t_role_template_v2" not in source
    assert "_preaudit_custom_role_sources" in source
    assert "Repair explicitly before retry" in source


def test_b5_draft_publish_materializes_normalized_rows_and_freezes_version(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission

    draft = svc.create_draft(
        template_code="SYS_ADMIN",
        template_name="系统管理员",
        permission_codes=[CATALOG_VIEW, CATALOG_MANAGE],
        change_reason="建立规范化发布测试",
        source_commit_sha="abc123",
        actor_user_id=9001,
    )
    assert draft["publishStatus"] == "DRAFT"
    assert draft["storedStatus"] == "ACTIVE"
    assert draft["templatePlane"] == "TENANT"
    assert draft["permissions"] == sorted([CATALOG_VIEW, CATALOG_MANAGE])

    db = get_sessionmaker()()
    try:
        template = db.get(RoleTemplate, int(draft["id"]))
        rows = list(db.scalars(select(RoleTemplatePermission).where(
            RoleTemplatePermission.role_template_id == int(draft["id"]),
            RoleTemplatePermission.is_deleted.is_(False),
        )).all())
        assert template is not None
        assert template.publish_status == "DRAFT"
        assert template.status == "ACTIVE"
        assert template.permission_digest == svc._digest(draft["permissions"])
        assert {row.permission_code for row in rows} == set(draft["permissions"])
    finally:
        db.close()

    published = svc.publish_draft(
        int(draft["id"]),
        expected_version=int(draft["version"]),
        actor_user_id=9002,
    )
    assert published["publishStatus"] == "PUBLISHED"
    assert published["storedStatus"] == "ACTIVE"
    assert published["publishedBy"] == 9002
    assert published["publishedAt"]

    with pytest.raises(AppException) as exc:
        svc.update_draft(
            int(draft["id"]),
            expected_version=int(published["version"]),
            permission_codes=[CATALOG_VIEW],
            change_reason="不允许原地修改",
            actor_user_id=9003,
        )
    assert exc.value.code == "IMMUTABLE_TEMPLATE"


def test_b5_new_version_uses_previous_template_id_not_json_pointer(db_mode):
    first = svc.create_draft(
        template_code="ACADEMIC_ADMIN",
        template_name="教务管理员",
        permission_codes=[CATALOG_VIEW],
        change_reason="建立第一版模板",
        actor_user_id=9010,
    )
    first = svc.publish_draft(
        int(first["id"]), expected_version=int(first["version"]), actor_user_id=9010
    )
    second = svc.create_draft(
        template_code="ACADEMIC_ADMIN",
        template_name="教务管理员",
        permission_codes=[CATALOG_VIEW, CATALOG_INVITE],
        change_reason="建立第二版模板",
        actor_user_id=9011,
    )
    assert second["previousTemplateId"] == first["id"]
    assert second["previousTemplateVersion"] == int(first["templateVersion"])
