from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.derived_access import (
    authorize_compare_result_read,
    authorize_extracted_artifact_read,
    require_compare_result_read,
)
from app.modules.platform.document_lifecycle.exact_file_version_read_port import ExactSourceVersion
from app.modules.platform.document_lifecycle.fact_hooks import (
    academic_status_effective,
    affairs_leave_approved,
    employment_verified,
    graduation_archived,
    internship_completed,
)
from app.modules.platform.document_lifecycle.models import StudentLifecycleFact


class _Port:
    def __init__(self, revoked: set[int] | None = None):
        self.revoked = revoked or set()
        self.calls: list[int] = []

    def resolve(self, *, file_version_id, expected_sha256, action, user):
        self.calls.append(file_version_id)
        if file_version_id in self.revoked:
            raise AppException("DATA_NOT_FOUND", "revoked", http_status=404)
        return ExactSourceVersion(
            tenant_id=101, asset_id=file_version_id + 10,
            file_version_id=file_version_id, file_object_id=file_version_id + 20,
            version_no=1, source_sha256=expected_sha256, mime_type="text/plain",
            ext="txt", size_bytes=1, sensitivity_level="PERSONAL",
            source_binding_refs=(),
        )


def test_extracted_artifact_reauthorizes_source_on_every_read() -> None:
    port = _Port()
    authorize_extracted_artifact_read(
        source_file_version_id=1, source_sha256="a" * 64,
        user={"userId": "7"}, port=port,
    )
    authorize_extracted_artifact_read(
        source_file_version_id=1, source_sha256="a" * 64,
        user={"userId": "7"}, port=port,
    )
    assert port.calls == [1, 1]


def test_compare_denies_whole_result_when_either_side_is_revoked() -> None:
    left_revoked = _Port({1})
    with pytest.raises(AppException):
        authorize_compare_result_read(
            left_file_version_id=1, left_source_sha256="a" * 64,
            right_file_version_id=2, right_source_sha256="b" * 64,
            user={"userId": "7"}, port=left_revoked,
        )
    assert left_revoked.calls == [1]

    right_revoked = _Port({2})
    with pytest.raises(AppException) as exc:
        require_compare_result_read(
            left_file_version_id=1, left_source_sha256="a" * 64,
            right_file_version_id=2, right_source_sha256="b" * 64,
            user={"userId": "7"}, port=right_revoked,
        )
    assert exc.value.code == "DATA_NOT_FOUND"
    assert right_revoked.calls == [1, 2]


def test_five_selected_fact_hooks_share_one_rollback_boundary() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    StudentLifecycleFact.__table__.create(engine)
    set_tenant(101)
    try:
        with Session(engine) as db:
            academic_status_effective(
                db, student=SimpleNamespace(id=1, college_id=2), academic_fact_version=3,
                event_time=datetime(2026, 8, 29), change_type="GRADUATED", actor_id=7,
            )
            graduation_archived(
                db,
                student=SimpleNamespace(id=4, student_id=1, college_id=2),
                manifest=SimpleNamespace(id=5, revision=1, frozen_at=datetime(2026, 8, 29)),
                actor_id=7,
            )
            internship_completed(
                db, record=SimpleNamespace(id=6, student_id=1),
                archive=SimpleNamespace(id=7, archived_at=datetime(2026, 8, 29)),
                source_version=1, actor_id=7,
            )
            employment_verified(
                db, student=SimpleNamespace(id=8, student_id=1, student_no="S1", tenant_id=101, version=2),
                actor_id=7,
            )
            affairs_leave_approved(
                db, leave=SimpleNamespace(id=9, student_id=1, version=2), actor_id=7,
            )
            assert len(db.scalars(select(StudentLifecycleFact)).all()) == 5
            db.rollback()
        with Session(engine) as db:
            assert db.scalars(select(StudentLifecycleFact)).all() == []
    finally:
        set_tenant(None)
        engine.dispose()


def test_canonical_hooks_wait_for_c7_schema_and_registration_slot() -> None:
    root = Path("app")
    sites = {
        "modules/academic_affairs/services/academic_affairs_status_service.py": "academic_status_effective(",
        "modules/graduation/materials/manifest_service.py": "graduation_archived(",
        "modules/internship/services/internship_archive_service.py": "internship_completed(",
        "modules/employment/services/employment_runtime_material_service.py": "employment_verified(",
        "services/affairs_leave_service.py": "affairs_leave_approved(",
    }
    for relative, call in sites.items():
        source = (root / relative).read_text(encoding="utf-8")
        assert call not in source
        assert "after_commit" not in source
