"""D3-U 学籍异动材料：原子绑定与便利性合同。"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select


def test_d3u_convenience_dto_extends_without_mutating_legacy_contract():
    from app.modules.academic_affairs.routers import status_change_convenience_router as convenience
    from app.modules.academic_affairs.routers import status_change_router

    canonical_fields = set(status_change_router.StatusChangeSubmit.model_fields)
    convenience_fields = set(convenience.StatusChangeConvenienceSubmit.model_fields)
    assert "materialFileIds" not in canonical_fields
    assert "effectiveDate" not in canonical_fields
    assert canonical_fields < convenience_fields
    assert {"materialFileIds", "effectiveDate"}.issubset(convenience_fields)


def test_d3u_convenience_submit_delegates_to_canonical_service(monkeypatch):
    from app.modules.academic_affairs.services import status_change_material_service as material_svc

    marker = object()
    calls = []

    def fake_submit(body, user):
        calls.append((body, user))
        return {"changeId": "123", "status": "SUBMITTED"}

    monkeypatch.setattr(material_svc.change_service, "submit", fake_submit)
    result = material_svc.submit_with_materials(marker, {"userId": "7"}, [])
    assert calls == [(marker, {"userId": "7"})]
    assert result["changeId"] == "123"
    assert result["materialCount"] == 0


def test_d3u_idempotent_replay_requires_exact_material_set(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import status_change_material_service as material_svc

    marker = object()
    monkeypatch.setattr(
        material_svc.change_service,
        "submit",
        lambda body, user: {"changeId": "123", "status": "SUBMITTED"},
    )
    monkeypatch.setattr(
        material_svc,
        "list_materials",
        lambda change_id, user: [{"fileId": "1"}, {"fileId": "2"}],
    )

    with pytest.raises(AppException) as caught:
        material_svc.submit_with_materials(marker, {"userId": "7"}, ["1"])
    assert caught.value.code == "IDEMPOTENCY_MATERIAL_MISMATCH"

    result = material_svc.submit_with_materials(marker, {"userId": "7"}, ["2", "1"])
    assert result["materialCount"] == 2


def test_d3u_material_file_ids_are_bounded_and_deduplicated():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import status_change_material_service as material_svc

    assert material_svc._validate_file_ids(["1", 1, "2"]) == ("1", "2")
    with pytest.raises(AppException):
        material_svc._validate_file_ids([str(i) for i in range(1, 12)])
    with pytest.raises(AppException):
        material_svc._validate_file_ids(["not-a-file"])


def test_d3u_router_shapes_are_public_and_do_not_replace_legacy_routes():
    from app.modules.academic_affairs.routers import academic_affairs_bundle

    routes = [r for r in academic_affairs_bundle.build_router().routes if isinstance(r, APIRoute)]
    shapes = {(r.path, method) for r in routes for method in (r.methods or set())}
    assert ("/academic-affairs/status-changes/convenience-submit", "POST") in shapes
    assert ("/academic-affairs/status-changes/{changeId}/materials", "GET") in shapes
    assert ("/academic-affairs/status-changes", "POST") in shapes
    assert ("/academic-affairs/status-changes/scheduled", "POST") in shapes


def _temp_file(tenant_id: int, *, owner_id: int, ready: bool = True):
    from app.models.file import FileObject

    suffix = uuid4().hex[:10]
    return FileObject(
        tenant_id=tenant_id,
        file_key=f"d3u/{suffix}.pdf",
        file_name=f"d3u-{suffix}.pdf",
        ext="pdf",
        mime_type="application/pdf",
        size_bytes=128,
        sha256=(suffix * 7)[:64].ljust(64, "a"),
        biz_type="TEMP_PRIVATE",
        biz_id=None,
        visibility="PRIVATE",
        security_level="NORMAL",
        status="AVAILABLE" if ready else "QUARANTINED",
        storage_backend="local",
        storage_zone="QUARANTINE",
        upload_source="USER",
        owner_user_id=owner_id,
        scan_required=True,
        scan_status="CLEAN" if ready else "PENDING",
    )


def test_d3u_flush_hook_binds_ready_temp_file_inside_same_session(db_mode):
    del db_mode
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange
    from app.models.file import FileBinding
    from app.modules.academic_affairs.services import status_change_material_service as material_svc

    tenant_id = 1000000000000000001
    owner_id = 1
    set_tenant({"tenantId": tenant_id, "tenantCode": "default"})
    db = get_sessionmaker()()
    token = None
    try:
        file_obj = _temp_file(tenant_id, owner_id=owner_id)
        db.add(file_obj)
        db.flush()
        token = material_svc._PENDING.set(((str(file_obj.id),), {"userId": str(owner_id), "userType": "STAFF"}))
        change = AaStatusChange(
            tenant_id=tenant_id,
            student_id=987654321,
            change_type="SUSPEND",
            from_status="REGISTERED",
            to_status="SUSPENDED",
            status="SUBMITTED",
        )
        db.add(change)
        db.flush()
        db.flush()
        binding = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == file_obj.id,
            FileBinding.biz_type == "AA_STATUS_CHANGE",
            FileBinding.biz_id == str(change.id),
            FileBinding.is_deleted.is_(False),
        )).first()
        assert binding is not None
        assert binding.subject_type == "STUDENT"
        assert binding.subject_id == str(change.student_id)
        assert file_obj.biz_type == "AA_STATUS_CHANGE"
        assert file_obj.biz_id == str(change.id)
        assert file_obj.visibility == "BIZ_SCOPED"
    finally:
        if token is not None:
            material_svc._PENDING.reset(token)
        db.rollback()
        db.close()


def test_d3u_flush_hook_rejects_unscanned_file_before_commit(db_mode):
    del db_mode
    from app.core.context import set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services import status_change_material_service as material_svc

    tenant_id = 1000000000000000001
    owner_id = 1
    set_tenant({"tenantId": tenant_id, "tenantCode": "default"})
    db = get_sessionmaker()()
    token = None
    try:
        file_obj = _temp_file(tenant_id, owner_id=owner_id, ready=False)
        db.add(file_obj)
        db.flush()
        token = material_svc._PENDING.set(((str(file_obj.id),), {"userId": str(owner_id), "userType": "STAFF"}))
        db.add(AaStatusChange(
            tenant_id=tenant_id,
            student_id=987654322,
            change_type="SUSPEND",
            from_status="REGISTERED",
            to_status="SUSPENDED",
            status="SUBMITTED",
        ))
        with pytest.raises(AppException) as caught:
            db.flush()
        assert caught.value.code == "FILE_NOT_READY"
    finally:
        if token is not None:
            material_svc._PENDING.reset(token)
        db.rollback()
        db.close()
