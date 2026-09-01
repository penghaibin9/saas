"""O1 Orientation batch, stable organization and source authority."""
from __future__ import annotations

from sqlalchemy import select, text

TID = 1000000000000000001


def _authority(db):
    from app.models import College, Major, OrientationBatch, SchoolClass
    from app.services.orientation_flow_service import ensure_published_flow_version

    college = College(tenant_id=TID, college_name="O1信息学院", code="O1-COL", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="O1软件专业",
                  code="O1-MAJ", status="ACTIVE")
    db.add(major); db.flush()
    school_class = SchoolClass(tenant_id=TID, major_id=major.id, class_name="O1软件2601班",
                               class_code="O1-CLS", grade="2026", status="ACTIVE")
    flow_version = ensure_published_flow_version(db, TID)
    batch = OrientationBatch(tenant_id=TID, batch_name="O1 2026迎新", batch_no="O1-ORI-2026",
                             year="2026", status="ACTIVE", planned_count=3)
    batch.flow_version_id = flow_version.id
    db.add_all([school_class, batch]); db.commit()
    return {"college": college.id, "major": major.id, "class": school_class.id, "batch": batch.id}


def _row(**overrides):
    row = {
        "batchNo": "O1-ORI-2026", "admissionNo": "O1-ADM-001", "candidateNo": "O1-CAND-001",
        "name": "O1新生", "gender": "女", "collegeCode": "O1-COL",
        "majorCode": "O1-MAJ", "classCode": "O1-CLS", "grade": "2026",
        "origin": "湖南长沙", "admissionType": "统招",
    }
    row.update(overrides)
    return row


def test_o1_batch_aware_import_and_export(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent

    db = get_sessionmaker()()
    ids = _authority(db)
    db.close()

    dry = client.post(
        "/api/v1/import/domain/orientation/validate",
        headers=auth_headers,
        json={"rows": [_row()]},
    ).json()
    assert dry["code"] == 0, dry
    assert dry["data"]["status"] == "DRY_RUN_PASSED"
    confirm = client.post(
        "/api/v1/import/domain/confirm",
        headers={**auth_headers, "Idempotency-Key": "o1-import-confirm-001"},
        json={"domain": "orientation", "batchNo": dry["data"]["batchNo"]},
    ).json()
    assert confirm["code"] == 0 and confirm["data"]["insertedRows"] == 1, confirm

    db = get_sessionmaker()()
    student = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == TID,
        OrientationStudent.admission_no == "O1-ADM-001",
    )).one()
    assert (student.batch_id, student.college_id, student.major_id, student.class_id) == (
        ids["batch"], ids["college"], ids["major"], ids["class"],
    )
    assert student.source_type == "DOMAIN_IMPORT" and student.source_record_id == "O1-CAND-001"
    assert student.identity_status == "UNLINKED" and student.admission_type == "统招"
    db.close()

    missing_batch = client.post(
        "/api/v1/export/domain/orientation",
        headers={**auth_headers, "Idempotency-Key": "o1-export-missing-batch"},
        json={"purpose": "O1批次导出验收"},
    ).json()
    assert missing_batch["code"] == 422001, missing_batch

    exported = client.post(
        "/api/v1/export/domain/orientation",
        headers={**auth_headers, "Idempotency-Key": "o1-export-batch-001"},
        json={"purpose": "O1批次导出验收", "batchId": ids["batch"]},
    ).json()
    assert exported["code"] == 0 and exported["data"]["rowCount"] == 1, exported


def test_o1_import_fails_closed_on_unknown_or_ambiguous_authority(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    _authority(db)
    db.close()

    unknown = client.post(
        "/api/v1/import/domain/orientation/validate",
        headers=auth_headers,
        json={"rows": [_row(collegeCode="OTHER-TENANT-CODE")]},
    ).json()
    assert unknown["code"] == 0
    assert unknown["data"]["status"] == "DRY_RUN_FAILED"
    assert unknown["data"]["errors"][0]["field"] == "collegeCode"

    duplicate_source = client.post(
        "/api/v1/import/domain/orientation/validate",
        headers=auth_headers,
        json={"rows": [
            _row(admissionNo="O1-ADM-002", candidateNo="O1-CAND-DUP"),
            _row(admissionNo="O1-ADM-003", candidateNo="O1-CAND-DUP"),
        ]},
    ).json()
    assert duplicate_source["data"]["status"] == "DRY_RUN_FAILED"
    assert any(error["field"] == "candidateNo" for error in duplicate_source["data"]["errors"])


def test_o1_database_authority_has_no_batch_source_or_org_drift(db_mode):
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    _authority(db)
    checks = {
        "missing_batch_source": """
            SELECT COUNT(*) FROM t_orientation_student
            WHERE batch_id IS NULL OR source_type IS NULL OR source_record_id IS NULL
               OR identity_status NOT IN ('UNLINKED','LINKED')
               OR (student_id IS NULL AND identity_status<>'UNLINKED')
               OR (student_id IS NOT NULL AND identity_status<>'LINKED')
        """,
        "batch_cross_tenant": """
            SELECT COUNT(*) FROM t_orientation_student o
            LEFT JOIN t_orientation_batch b ON b.id=o.batch_id AND b.tenant_id=o.tenant_id
            WHERE b.id IS NULL
        """,
        "org_cross_tenant": """
            SELECT COUNT(*) FROM t_orientation_student o
            LEFT JOIN t_class c ON c.id=o.class_id AND c.tenant_id=o.tenant_id
            LEFT JOIN t_major m ON m.id=o.major_id AND m.tenant_id=o.tenant_id
            LEFT JOIN t_college g ON g.id=o.college_id AND g.tenant_id=o.tenant_id
            WHERE o.class_id IS NOT NULL
              AND (c.id IS NULL OR m.id IS NULL OR g.id IS NULL
                   OR c.major_id<>o.major_id OR m.college_id<>o.college_id)
        """,
        "duplicate_source": """
            SELECT COUNT(*) FROM (
              SELECT tenant_id,batch_id,source_type,source_record_id
              FROM t_orientation_student
              GROUP BY tenant_id,batch_id,source_type,source_record_id HAVING COUNT(*)>1
            ) d
        """,
    }
    assert {name: int(db.execute(text(sql)).scalar() or 0) for name, sql in checks.items()} == {
        name: 0 for name in checks
    }
    db.close()


def test_o1_migration_is_single_parent_and_preserves_legacy_reference():
    from pathlib import Path

    migration = (Path(__file__).parents[1] / "alembic" / "versions" /
                 "20260901_orientation_batch_o1.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260831_iam_alias_backfill"' in migration
    assert 'new_column_name="class_ref_legacy"' in migration
    assert "CLASS_CODE_AMBIGUOUS" in migration and "CLASS_REF_UNRESOLVED" in migration
    org_backfill = migration.split("def _backfill_organization", 1)[1].split(
        "def _backfill_identity_status", 1
    )[0]
    assert "class_name" not in org_backfill and "college_name" not in org_backfill
