"""W7.1-W7.3 production contracts and real-MySQL evidence."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from sqlalchemy import event, text

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_engine
from app.models import GraduationBatch, GraduationProposal, GraduationReview, GraduationStudent
from app.models.file import FileObject, FileVersion
from app.models.graduation_material import GraduationStudentMaterial
from app.models.graduation_review_evidence import GraduationReviewFeedbackTable
from app.modules.graduation.services import graduation_review_center_contract_service as center
from app.modules.graduation.services import graduation_review_closure_service as closure
from app.services.db_service import session

ROOT = Path(__file__).resolve().parents[1]
TID = 1000000000000000001
MYSQL_ONLY = pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or "").startswith("mysql"),
    reason="MySQL-only W7 production evidence",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _admin(*, role: str = "PLATFORM_SUPER_ADMIN") -> dict:
    return {
        "userId": "1",
        "realName": "W7管理员",
        "loginName": "w7-admin",
        "currentRoleCode": role,
        "roleName": role,
        "userType": "TEACHER",
        "dataScope": "ALL",
    }


def test_w71_w72_contract_is_exact_version_append_only_and_same_transaction():
    migration = _read("alembic/versions/20260822_gd_review_closure.py")
    closure_source = _read("app/modules/graduation/services/graduation_review_closure_service.py")
    evidence = _read("app/modules/graduation/services/graduation_review_feedback_service.py")
    records = _read("app/modules/graduation/materials/record_service.py")
    schema = _read("app/modules/graduation/schemas/graduation_review.py")
    overlay = _read("app/modules/graduation/routers/graduation_review_w7_router.py")
    assert 'down_revision = "20260820_teacher_emp_reco"' in migration
    for column in ("material_id", "file_version_id", "source_sha256", "started_at"):
        assert f'"{column}"' in migration
    assert '"t_gd_review_feedback"' in migration
    assert 'UniqueConstraint("tenant_id", "idempotency_key"' in migration
    for field in ("expectedVersion", "fileVersionId", "categories", "issues", "idempotencyKey"):
        assert field in schema
    for code in (
        "REVIEW_TARGET_VERSION_MISSING",
        "REVIEW_TARGET_VERSION_CHANGED",
        "APPROVAL_VERSION_CONFLICT",
        "FILE_HASH_MISSING",
    ):
        assert code in closure_source
    assert "sod_conflict_with_advisor" in closure_source
    assert "_prior_matches_request" in closure_source
    assert "append_feedback_in_session" in closure_source
    assert records.count("_append_feedback(") >= 3
    assert "review_material_in_session" in records and "db.commit()" in records
    assert "body.expectedVersion" in overlay and "body.fileVersionId" in overlay
    assert "UPDATE t_gd_review_feedback" not in evidence
    assert "DELETE FROM t_gd_review_feedback" not in evidence
    assert "if False" not in closure_source


def test_w73_sql_queue_contract_has_exact_dto_and_db_pagination():
    query = _read("app/modules/graduation/services/graduation_review_center_query_service.py")
    priority = _read("app/modules/graduation/services/graduation_review_center_priority_service.py")
    facade = _read("app/modules/graduation/services/graduation_review_center_contract_service.py")
    for field in (
        "materialCode",
        "materialName",
        "fileName",
        "mimeType",
        "fileVersionId",
        "sourceSha256",
        "canonicalMaterial",
    ):
        assert f'"{field}"' in query
    assert "graduation_review_center_priority_service as priority" in facade
    assert "SELECT COUNT(*) FROM projected" in priority
    assert "LIMIT :limit OFFSET :offset" in priority
    assert "status_group='RETURNED' THEN 0" in priority
    assert "overdue_final" in priority
    assert "case_type IN ('FINAL','FINAL_DRAFT') THEN 2" in priority
    assert "case_type='FORMAL_REVIEW' THEN 3" in priority
    assert "case_type='PROPOSAL' THEN 4" in priority
    assert "_project_bundle" not in priority
    assert "feedback_for_sources" in priority


@MYSQL_ONLY
def test_w71_mysql_permission_tenant_version_and_sod_fail_closed(db_mode):
    batch_id, student_id, review_id = 99071001, 99071002, 99071003
    material_id, version_id = 99071004, 99071005
    set_tenant({"tenantId": TID})
    set_current_user(_admin())
    try:
        with session() as db:
            db.add(GraduationBatch(
                id=batch_id,
                tenant_id=TID,
                batch_name="W7正式评阅安全批次",
                batch_no="W7-SEC-001",
                planned_count=1,
                status="RUNNING",
                archive_status="NOT_ARCHIVED",
            ))
            db.add(GraduationStudent(
                id=student_id,
                tenant_id=TID,
                batch_id=batch_id,
                student_no="W7-SEC-001",
                name="正式评阅安全学生",
                stage="FINAL_CHECK",
                record_status="ACTIVE",
            ))
            db.add(GraduationReview(
                id=review_id,
                tenant_id=TID,
                gd_student_id=student_id,
                gd_final_id=99071999,
                reviewer_name="独立评阅人",
                reviewer_mentor_id=99071888,
                status="ASSIGNED",
                version=7,
            ))
            db.flush()
            db.execute(text(
                "UPDATE t_gd_review SET material_id=:material_id,file_version_id=:file_version_id,"
                "source_sha256=:sha WHERE tenant_id=:tenant_id AND id=:review_id"
            ), {
                "material_id": material_id,
                "file_version_id": version_id,
                "sha": "b" * 64,
                "tenant_id": TID,
                "review_id": review_id,
            })
            db.commit()

        with pytest.raises(AppException) as stale:
            closure.submit_review(
                review_id,
                88,
                "版本冲突测试意见",
                expected_version=6,
                file_version_id=version_id,
            )
        assert stale.value.code == "APPROVAL_VERSION_CONFLICT"

        with pytest.raises(AppException) as wrong_version:
            closure.submit_review(
                review_id,
                88,
                "错误文件版本测试意见",
                expected_version=7,
                file_version_id=version_id + 1,
            )
        assert wrong_version.value.code == "REVIEW_TARGET_VERSION_CHANGED"

        set_current_user(_admin(role="ACADEMIC_TEACHER"))
        with pytest.raises(AppException) as denied:
            closure.submit_review(
                review_id,
                88,
                "越权提交测试意见",
                expected_version=7,
                file_version_id=version_id,
            )
        assert denied.value.code == "NO_PERMISSION"

        set_current_user(_admin())
        set_tenant({"tenantId": TID + 77})
        with pytest.raises(AppException) as cross_tenant:
            closure.submit_review(
                review_id,
                88,
                "跨租户提交测试意见",
                expected_version=7,
                file_version_id=version_id,
            )
        assert cross_tenant.value.code == "DATA_NOT_FOUND"

        set_tenant({"tenantId": TID})
        with session() as db:
            student = db.get(GraduationStudent, student_id)
            student.mentor_id = 99071888
            db.commit()
        with pytest.raises(AppException) as sod:
            closure.submit_review(
                review_id,
                88,
                "SoD 冲突测试意见",
                expected_version=7,
                file_version_id=version_id,
            )
        assert sod.value.code == "VALIDATION_ERROR"
        assert "SoD" in sod.value.message
    finally:
        set_current_user(None)
        set_tenant(None)


@MYSQL_ONLY
def test_w73_mysql_1000_students_5000_feedback_is_bounded_paginated_and_scoped(db_mode):
    batch_id, file_id, version_id, asset_id = 99191001, 99191002, 99191003, 99191004
    set_tenant({"tenantId": TID})
    set_current_user(_admin())
    try:
        with session() as db:
            db.execute(GraduationBatch.__table__.insert(), [{
                "id": batch_id,
                "tenant_id": TID,
                "batch_name": "W7规模批次",
                "batch_no": "W7-SCALE-001",
                "planned_count": 1000,
                "status": "RUNNING",
                "archive_status": "NOT_ARCHIVED",
            }])
            db.execute(FileObject.__table__.insert(), [{
                "id": file_id,
                "tenant_id": TID,
                "file_key": "w7/scale.pdf",
                "file_name": "scale.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 128,
                "sha256": "a" * 64,
                "visibility": "BIZ_SCOPED",
                "security_level": "SENSITIVE",
                "status": "AVAILABLE",
                "scan_required": False,
                "scan_status": "NOT_REQUIRED",
            }])
            db.execute(FileVersion.__table__.insert(), [{
                "id": version_id,
                "tenant_id": TID,
                "asset_id": asset_id,
                "file_object_id": file_id,
                "version_no": 1,
                "source_channel": "STUDENT_SUBMISSION",
                "status": "SUBMITTED",
                "is_current": True,
            }])
            students = []
            proposals = []
            materials = []
            for i in range(1000):
                sid, pid, mid = 99200000 + i, 99300000 + i, 99400000 + i
                students.append({
                    "id": sid,
                    "tenant_id": TID,
                    "batch_id": batch_id,
                    "student_no": f"W7{i:04d}",
                    "name": f"规模学生{i:04d}",
                    "stage": "GUIDING",
                    "record_status": "ACTIVE",
                })
                proposals.append({
                    "id": pid,
                    "tenant_id": TID,
                    "gd_student_id": sid,
                    "version": "v1",
                    "status": "REJECTED" if i < 10 else "PENDING_REVIEW",
                    "active_key": f"w7pending:{sid}",
                })
                materials.append({
                    "id": mid,
                    "tenant_id": TID,
                    "batch_id": batch_id,
                    "gd_student_id": sid,
                    "material_code": "PROPOSAL_REPORT",
                    "material_name": "开题报告",
                    "biz_stage": "PROPOSAL",
                    "asset_id": asset_id,
                    "current_version_id": version_id,
                    "business_status": "SUBMITTED",
                    "review_status": "PENDING",
                })
            db.execute(GraduationStudent.__table__.insert(), students)
            db.execute(GraduationProposal.__table__.insert(), proposals)
            db.execute(GraduationStudentMaterial.__table__.insert(), materials)
            feedback_rows = []
            for i in range(5000):
                feedback_rows.append({
                    "id": 99500000 + i,
                    "tenant_id": TID,
                    "batch_id": batch_id,
                    "gd_student_id": 99200000 + (i % 1000),
                    "stage": "PROPOSAL",
                    "source_record_id": 99300000 + (i % 1000),
                    "material_id": 99400000 + (i % 1000),
                    "file_version_id": version_id,
                    "source_sha256": "a" * 64,
                    "round_no": i // 1000 + 1,
                    "categories": [],
                    "issues": [],
                    "summary": "规模反馈",
                    "result": "REJECTED",
                    "visible_to_student": True,
                    "idempotency_key": f"w7-scale-{i}",
                    "is_superseded": False,
                })
            db.execute(GraduationReviewFeedbackTable.insert(), feedback_rows)

            # Same batch id but another tenant: tenant predicates must keep this row invisible.
            db.execute(GraduationStudent.__table__.insert(), [{
                "id": 99690001,
                "tenant_id": TID + 77,
                "batch_id": batch_id,
                "student_no": "W7-XTENANT",
                "name": "跨租户不可见学生",
                "stage": "GUIDING",
                "record_status": "ACTIVE",
            }])
            db.execute(GraduationProposal.__table__.insert(), [{
                "id": 99690002,
                "tenant_id": TID + 77,
                "gd_student_id": 99690001,
                "version": "v1",
                "status": "PENDING_REVIEW",
                "active_key": "w7-x-tenant",
            }])
            db.commit()

        engine = get_engine()
        statements: list[str] = []

        def before_cursor(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", before_cursor)
        started = time.monotonic()
        try:
            items, total = center.list_tasks(
                batch_id=batch_id,
                page=1,
                page_size=20,
                sort="PRIORITY",
            )
        finally:
            elapsed = time.monotonic() - started
            event.remove(engine, "before_cursor_execute", before_cursor)

        assert total == 1000
        assert len(items) == 20
        assert items[0]["statusGroup"] == "RETURNED"
        assert all(item["materialCode"] == "PROPOSAL_REPORT" for item in items)
        assert all(item["materialName"] == "开题报告" for item in items)
        assert all(item["fileName"] == "scale.pdf" for item in items)
        assert all(item["mimeType"] == "application/pdf" for item in items)
        assert all(item["fileVersionId"] == str(version_id) for item in items)
        assert all(item["studentNo"] != "W7-XTENANT" for item in items)
        assert elapsed < 15.0, f"W7 1000/5000 queue query too slow: {elapsed:.2f}s"
        assert len(statements) <= 12, [s[:120] for s in statements]
        sql = "\n".join(statements).upper()
        assert "COUNT(*) FROM PROJECTED" in sql
        assert "LIMIT" in sql and "OFFSET" in sql

        # Data-scope fail closed: a college-scoped role without college claims gets no rows.
        set_current_user(_admin(role="GD_COLLEGE_ADMIN"))
        scoped_items, scoped_total = center.list_tasks(
            batch_id=batch_id,
            page=1,
            page_size=20,
            sort="PRIORITY",
        )
        assert scoped_total == 0
        assert scoped_items == []
    finally:
        set_current_user(None)
        set_tenant(None)
