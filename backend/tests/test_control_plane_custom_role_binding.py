from sqlalchemy import select


def test_b1_clone_creates_one_runtime_custom_role_and_one_bound_source(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import Role, RolePermission
    from app.models.permission_governance import CustomRoleSource
    from app.services import permission_bundle_service as svc

    tenant_id = 8811
    svc.bootstrap_from_code(tenant_id=tenant_id)
    created = svc.clone_template(
        "SYS_ADMIN",
        new_role_code="BOUND_CUSTOM_ROLE",
        permission_codes=["systemAdmin.role.view"],
        tenant_id=tenant_id,
    )

    db = get_sessionmaker()()
    try:
        role = db.scalar(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code == "BOUND_CUSTOM_ROLE",
            Role.is_deleted.is_(False),
        ))
        source = db.scalar(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tenant_id,
            CustomRoleSource.role_code == "BOUND_CUSTOM_ROLE",
            CustomRoleSource.is_deleted.is_(False),
        ))
        assert role is not None and source is not None
        assert role.role_type == "CUSTOM"
        assert int(source.role_id) == int(role.id) == int(created["roleId"])
        # DRAFT governance is not runtime permission truth until SecurityChange activation.
        assert list(db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
        )).all()) == []
    finally:
        db.close()


def test_b1_materialization_fails_closed_if_role_id_binding_drifts(db_mode):
    import pytest

    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import Role
    from app.models.permission_governance import CustomRoleSource
    from app.modules.system_admin.services.role_permission_service import materialize_custom_role_source
    from app.services import permission_bundle_service as svc

    tenant_id = 8812
    svc.bootstrap_from_code(tenant_id=tenant_id)
    created = svc.clone_template(
        "SYS_ADMIN",
        new_role_code="DRIFT_CUSTOM_ROLE",
        permission_codes=[],
        tenant_id=tenant_id,
    )

    db = get_sessionmaker()()
    try:
        source = db.scalar(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tenant_id,
            CustomRoleSource.role_code == "DRIFT_CUSTOM_ROLE",
        ))
        other = Role(
            tenant_id=tenant_id,
            role_code="OTHER_CUSTOM_ROLE",
            role_name="other",
            role_type="CUSTOM",
            status="ACTIVE",
        )
        db.add(other)
        db.flush()
        source.role_id = int(other.id)
        db.commit()

        with pytest.raises(AppException) as exc:
            materialize_custom_role_source(db, tenant_id, "DRIFT_CUSTOM_ROLE")
        assert exc.value.code == "CUSTOM_ROLE_BINDING_DRIFT"
        assert exc.value.details["roleId"] == str(other.id)
    finally:
        db.rollback()
        db.close()


def test_p05_materialization_returns_controlled_409_for_unbound_n_minus_one_source(db_mode):
    import pytest

    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import CustomRoleSource
    from app.modules.system_admin.services.role_permission_service import materialize_custom_role_source
    from app.services import permission_bundle_service as svc

    tenant_id = 8813
    svc.bootstrap_from_code(tenant_id=tenant_id)
    svc.clone_template("SYS_ADMIN", new_role_code="N1_PENDING_ROLE", permission_codes=[], tenant_id=tenant_id)

    db = get_sessionmaker()()
    try:
        source = db.scalar(select(CustomRoleSource).where(
            CustomRoleSource.tenant_id == tenant_id,
            CustomRoleSource.role_code == "N1_PENDING_ROLE",
        ))
        source.role_id = None
        db.commit()

        with pytest.raises(AppException) as exc:
            materialize_custom_role_source(db, tenant_id, "N1_PENDING_ROLE")
        assert exc.value.code == "CUSTOM_ROLE_BINDING_PENDING"
        assert exc.value.http_status == 409
        assert exc.value.details == {"roleCode": "N1_PENDING_ROLE"}
    finally:
        db.rollback()
        db.close()


def test_p05_reconcile_creates_identity_only_role_and_is_replay_safe(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import Role, RolePermission
    from app.models.permission_governance import CustomRoleSource
    from app.modules.system_admin.services.custom_role_binding_reconciliation_service import (
        reconcile_custom_role_bindings,
    )

    tenant_id = 8814
    db = get_sessionmaker()()
    audits = []
    try:
        source = CustomRoleSource(
            tenant_id=tenant_id,
            role_id=None,
            role_code="N1_RECONCILE_ROLE",
            source_template_code="SYS_ADMIN",
            source_template_version=1,
            permission_codes_json={"items": ["systemAdmin.role.view"]},
            drift_json={"policy": "DERIVED_PINNED", "automaticUpgrade": False},
            status="DRAFT",
        )
        db.add(source)
        db.commit()

        monkeypatch.setattr(
            "app.modules.system_admin.services.custom_role_binding_reconciliation_service.audit_log.record_critical_in_session",
            lambda *args, **kwargs: audits.append((args, kwargs)),
        )
        dry = reconcile_custom_role_bindings(db, dry_run=True)
        assert dry["updated"] == 0
        assert dry["unresolved"] == 0
        assert dry["items"][0]["action"] == "CREATE_IDENTITY_ONLY"

        applied = reconcile_custom_role_bindings(
            db,
            dry_run=False,
            writer_fence_confirmed=True,
            n_minus_one_writer_count=0,
            release_sha="test-release-sha",
        )
        db.commit()
        assert applied["updated"] == 1
        assert applied["unresolved"] == 0

        db.refresh(source)
        role = db.scalar(select(Role).where(Role.id == source.role_id))
        assert role is not None
        assert role.role_type == "CUSTOM"
        assert role.role_code == source.role_code
        assert role.status == "ACTIVE"
        assert list(db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
        )).all()) == []
        assert len(audits) == 1
        assert audits[0][1]["detail"]["permissionMaterialized"] is False

        replay = reconcile_custom_role_bindings(
            db,
            dry_run=False,
            writer_fence_confirmed=True,
            n_minus_one_writer_count=0,
            release_sha="test-release-sha",
        )
        db.commit()
        assert replay["total"] == 0
        assert replay["updated"] == 0
        assert len(audits) == 1
    finally:
        db.rollback()
        db.close()


def test_p05_reconcile_refuses_apply_without_external_writer_drain_evidence(db_mode):
    import pytest

    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.modules.system_admin.services.custom_role_binding_reconciliation_service import (
        reconcile_custom_role_bindings,
    )

    db = get_sessionmaker()()
    try:
        with pytest.raises(AppException) as exc:
            reconcile_custom_role_bindings(
                db,
                dry_run=False,
                writer_fence_confirmed=False,
                n_minus_one_writer_count=1,
                release_sha="test-release-sha",
            )
        assert exc.value.code == "CUSTOM_ROLE_WRITER_FENCE_REQUIRED"
    finally:
        db.rollback()
        db.close()
