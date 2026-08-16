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
