from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_draft_impact_compares_published_permissions_not_another_draft(monkeypatch):
    published = SimpleNamespace(id=1, template_code="COLLEGE_ADMIN", template_version=1,
                                publish_status=svc.PUBLISHED, previous_template_id=None)
    earlier_draft = SimpleNamespace(id=2, template_code="COLLEGE_ADMIN", template_version=2,
                                    publish_status=svc.DRAFT, previous_template_id=1)
    candidate = SimpleNamespace(id=3, template_code="COLLEGE_ADMIN", template_version=3,
                                publish_status=svc.DRAFT, previous_template_id=2,
                                permission_ceiling_json={"basePublishedTemplateId": 1})
    permissions = {1: [f"p{n}" for n in range(459)],
                   2: [f"p{n}" for n in range(9, 459)],
                   3: [f"p{n}" for n in range(28, 459)]}
    db = MagicMock()
    db.scalar.return_value = published
    db.scalars.return_value.all.return_value = []
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(svc, "_load", lambda _db, template_id, **_kw: {1: published, 2: earlier_draft, 3: candidate}[template_id])
    monkeypatch.setattr(svc, "_items", lambda _db, item: permissions[item.id])

    result = svc.impact(3)
    assert result["baselineTemplateId"] == "1"
    assert len(result["removedPermissions"]) == 28


def test_publish_rejects_candidate_after_published_baseline_changes(monkeypatch):
    current = SimpleNamespace(id=4, template_code="COLLEGE_ADMIN", template_version=4,
                              publish_status=svc.PUBLISHED)
    candidate = SimpleNamespace(id=3, template_code="COLLEGE_ADMIN", template_version=3,
                                publish_status=svc.DRAFT, previous_template_id=1,
                                permission_ceiling_json={"basePublishedTemplateId": 1}, version=1,
                                template_plane="TENANT", change_reason="初始变更原因")
    db = MagicMock()
    db.scalar.return_value = current
    monkeypatch.setattr(svc, "get_sessionmaker", lambda: lambda: db)
    monkeypatch.setattr(svc, "_load", lambda _db, _id, **_kw: candidate)
    monkeypatch.setattr(svc, "_items", lambda _db, _item: [CATALOG_VIEW])
    monkeypatch.setattr(svc, "_row", lambda _db, _item: {})
    monkeypatch.setattr(svc, "impact", lambda _id: {})
    monkeypatch.setattr(audit_log, "record_critical_in_session", lambda *_args, **_kw: None)

    with pytest.raises(AppException) as exc:
        svc.publish_draft(3, expected_version=1, actor_user_id=9001)
    assert exc.value.code == "DATA_CONFLICT"
    db.commit.assert_not_called()


def test_two_drafts_publish_serially_and_rollback_keeps_source(db_mode, monkeypatch):
    first = svc.create_draft(template_code="COLLEGE_ADMIN", template_name="学院管理员",
                             permission_codes=[CATALOG_VIEW, CATALOG_MANAGE, CATALOG_INVITE],
                             change_reason="建立当前发布基线", actor_user_id=9001)
    first = svc.publish_draft(int(first["id"]), expected_version=first["version"], actor_user_id=9001)
    second = svc.create_draft(template_code="COLLEGE_ADMIN", template_name="学院管理员",
                              permission_codes=[CATALOG_VIEW, CATALOG_MANAGE],
                              change_reason="候选一收窄权限", actor_user_id=9001)
    third = svc.create_draft(template_code="COLLEGE_ADMIN", template_name="学院管理员",
                             permission_codes=[CATALOG_VIEW],
                             change_reason="候选二收窄权限", actor_user_id=9001)
    assert third["previousTemplateId"] == second["id"]
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate
    db = get_sessionmaker()()
    try:
        assert db.get(RoleTemplate, int(third["id"])).permission_ceiling_json["basePublishedTemplateId"] == int(first["id"])
    finally:
        db.close()
    assert set(svc.impact(int(third["id"]))["removedPermissions"]) == {CATALOG_MANAGE, CATALOG_INVITE}

    original_load = svc._load
    ready = Barrier(2)

    def load_together(db, template_id, *, lock=False):
        item = original_load(db, template_id, lock=lock)
        if lock and template_id in {int(second["id"]), int(third["id"])}:
            ready.wait(timeout=15)
        return item

    monkeypatch.setattr(svc, "_load", load_together)

    def publish(row):
        try:
            return svc.publish_draft(int(row["id"]), expected_version=row["version"], actor_user_id=9001)
        except AppException as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, (second, third)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("DATA_CONFLICT") == 1

    winner = next(result for result in results if isinstance(result, dict))
    rollback = svc.create_rollback_draft(int(first["id"]), change_reason="恢复原发布权限",
                                         actor_user_id=9001)
    assert rollback["previousTemplateId"] == first["id"]
    assert set(svc.impact(int(rollback["id"]))["addedPermissions"]) == (
        set(first["permissions"]) - set(winner["permissions"])
    )
    restored = svc.publish_draft(int(rollback["id"]), expected_version=rollback["version"], actor_user_id=9001)
    assert restored["publishStatus"] == "PUBLISHED"
