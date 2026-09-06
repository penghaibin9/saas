from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle import derived_access as access
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


class _ScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _ResolverDb:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = 0

    def scalars(self, _statement):
        self.calls += 1
        return _ScalarResult(self.rows.pop(0))


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


def test_derivative_resolver_rejects_forged_file_to_artifact_binding(monkeypatch) -> None:
    set_tenant(101)
    try:
        auth_calls = []
        monkeypatch.setattr(
            access, "authorize_extracted_artifact_read",
            lambda **kwargs: auth_calls.append(kwargs),
        )
        binding = SimpleNamespace(
            file_id=900, is_deleted=False, status="ACTIVE", biz_type="DOCUMENT_DERIVATIVE",
            scope_json={
                "derivativeKind": "EXTRACTED_TEXT", "artifactId": "77",
                "sourceFileVersionId": "30", "sourceSha256": "a" * 64,
            },
        )
        file_obj = SimpleNamespace(
            id=900, tenant_id=101, is_deleted=False, biz_type="DOCUMENT_DERIVATIVE",
        )
        allowed = access.document_derivative_resolver(
            _ResolverDb([[], []]), file_obj,
            [binding], {"userId": "7"}, "preview",
        )
        assert allowed is False
        assert auth_calls == []

        artifact = SimpleNamespace(source_file_version_id=30, source_sha256="a" * 64)
        allowed = access.document_derivative_resolver(
            _ResolverDb([[artifact], []]), file_obj, [binding], {"userId": "7"}, "preview",
        )
        assert allowed is True
        assert auth_calls[0]["source_file_version_id"] == 30

        allowed = access.document_derivative_resolver(
            _ResolverDb([[artifact], [SimpleNamespace()]]),
            file_obj, [], {"userId": "7"}, "preview",
        )
        assert allowed is False
    finally:
        set_tenant(None)


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


def test_employment_projection_never_blocks_legacy_row_without_student_identity() -> None:
    class _Scalars:
        @staticmethod
        def first():
            return None

    class _Db:
        @staticmethod
        def scalars(_statement):
            return _Scalars()

    result = employment_verified(
        _Db(),
        student=SimpleNamespace(
            id=8, student_id=None, student_no="LEGACY-1", tenant_id=101, version=2,
        ),
        actor_id=7,
    )
    assert result is None


def test_canonical_hooks_are_registered_in_c7_without_after_commit() -> None:
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
        assert call in source
        assert "after_commit" not in source


def test_internship_completion_fact_is_written_only_by_archive_mutation() -> None:
    source = Path("app/modules/internship/services/internship_archive_service.py").read_text(
        encoding="utf-8",
    )
    mutation = source[source.index("def archive_student_in_session"):source.index("def archive_student(")]
    preflight = source[source.index("def preflight_archive"):]
    assert "internship_completed(" in mutation
    assert "internship_completed(" not in preflight
