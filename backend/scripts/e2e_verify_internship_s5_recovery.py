"""S5 final-RC backup/upgrade/restore verifier for the internship module.

This runner helper never creates final user acceptance facts. It prepares a historical
pre-release snapshot in an isolated E2E MySQL database, records the canonical business
and file facts, verifies the upgraded RC, injects candidate-only damage, then proves the
governed restore returns the database and uploads to the exact historical boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import text

from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipBatch, InternshipPosition, InternshipRecord
from app.models.file import FileBinding, FileObject

EXPECTED_UNIQUE_INDEXES = (
    "uk_intern_batch_no",
    "uk_intern_stu_batch",
    "uk_internship_checkin_day",
    "uk_ix_makeup_active_pending",
    "uk_risk_source",
    "uk_internship_final_score_record",
    "uk_internship_archive_record",
)
CANDIDATE_TABLE = "e2e_s5_candidate_only"


def _state_path() -> Path:
    return Path(
        os.getenv("E2E_S5_STATE_FILE") or "../e2e/runtime/internship-s5-state.json"
    ).resolve()


def _fixture_path() -> Path:
    return Path(
        os.getenv("E2E_INTERNSHIP_FIXTURE_FILE")
        or "../e2e/runtime/internship-fixture.json"
    ).resolve()


def _upload_dir() -> Path:
    return Path(
        os.getenv("UPLOAD_DIR") or "../e2e/runtime/internship-s5-uploads"
    ).resolve()


def _load_fixture() -> dict:
    path = _fixture_path()
    if not path.is_file():
        raise SystemExit(f"missing internship fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_state() -> dict:
    path = _state_path()
    if not path.is_file():
        raise SystemExit(f"missing S5 state: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(payload: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _table_counts(db) -> dict[str, int]:
    names = [
        row[0]
        for row in db.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND (
                    table_name LIKE 't_internship_%'
                    OR table_name IN ('t_emp_company', 't_file_object', 't_file_binding')
                  )
                ORDER BY table_name
                """
            )
        )
    ]
    return {
        name: int(db.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one())
        for name in names
    }


def _assert_schema_contract(db) -> dict:
    missing: list[str] = []
    for index_name in EXPECTED_UNIQUE_INDEXES:
        count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                      AND index_name = :index_name
                      AND non_unique = 0
                    """
                ),
                {"index_name": index_name},
            ).scalar_one()
        )
        if count < 1:
            missing.append(index_name)
    if missing:
        raise AssertionError(f"missing unique internship indexes: {missing}")

    nullable = db.execute(
        text(
            """
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 't_internship_record'
              AND column_name = 'batch_id'
            """
        )
    ).scalar_one()
    if nullable != "NO":
        raise AssertionError(f"t_internship_record.batch_id must be NOT NULL, got {nullable}")

    revisions = [
        row[0]
        for row in db.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num"))
    ]
    if len(revisions) != 1:
        raise AssertionError(f"expected one Alembic head in DB, got {revisions}")

    return {
        "alembicRevision": revisions[0],
        "uniqueIndexes": list(EXPECTED_UNIQUE_INDEXES),
        "batchIdNullable": nullable,
    }


def _canonical_snapshot(db, fixture: dict, file_id: int, binding_id: int, relative_upload_path: str) -> dict:
    batch = db.get(InternshipBatch, int(fixture["batchId"]))
    record = db.get(InternshipRecord, int(fixture["internshipId"]))
    company = db.get(EmpCompany, int(fixture["companyId"]))
    position = db.get(InternshipPosition, int(fixture["positionId"]))
    file_obj = db.get(FileObject, file_id)
    binding = db.get(FileBinding, binding_id)
    if not all((batch, record, company, position, file_obj, binding)):
        raise AssertionError("S5 historical business/file facts are incomplete")

    if record.enterprise_id != company.id or record.position_id != position.id:
        raise AssertionError("canonical internship enterprise/position relation is broken")
    if binding.file_id != file_obj.id or str(binding.biz_id) != str(record.id):
        raise AssertionError("file binding does not point to the canonical internship record")

    return {
        "batch": {
            "id": batch.id,
            "batchNo": batch.batch_no,
            "batchName": batch.batch_name,
            "status": batch.status,
        },
        "record": {
            "id": record.id,
            "studentId": record.student_id,
            "batchId": record.batch_id,
            "enterpriseId": record.enterprise_id,
            "positionId": record.position_id,
            "status": record.status,
            "destinationType": record.destination_type,
            "version": record.version,
        },
        "company": {
            "id": company.id,
            "name": company.name,
            "creditCode": company.credit_code,
            "status": company.status,
        },
        "position": {
            "id": position.id,
            "title": position.title,
            "companyId": position.company_id,
            "status": position.status,
            "headcount": position.headcount,
            "allocatedCount": position.allocated_count,
        },
        "file": {
            "id": file_obj.id,
            "fileKey": file_obj.file_key,
            "fileName": file_obj.file_name,
            "sha256": file_obj.sha256,
            "bizType": file_obj.biz_type,
            "bizId": file_obj.biz_id,
            "relativeUploadPath": relative_upload_path,
        },
        "binding": {
            "id": binding.id,
            "fileId": binding.file_id,
            "bizType": binding.biz_type,
            "bizId": binding.biz_id,
            "relationType": binding.relation_type,
            "moduleCode": binding.module_code,
            "batchId": binding.batch_id,
            "studentId": binding.student_id,
        },
    }


def snapshot() -> None:
    fixture = _load_fixture()
    upload_dir = _upload_dir()
    relative = f"internship/s5/{fixture['runId']}-historical-evidence.txt"
    physical = upload_dir / relative
    physical.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"INTERNSHIP-S5-HISTORICAL\n"
        f"batch={fixture['batchId']}\n"
        f"record={fixture['internshipId']}\n"
        f"student={fixture['studentId']}\n"
    ).encode("utf-8")
    physical.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()

    db = get_sessionmaker()()
    try:
        record = db.get(InternshipRecord, int(fixture["internshipId"]))
        if record is None:
            raise AssertionError("seeded internship record missing")

        file_obj = FileObject(
            tenant_id=record.tenant_id,
            file_key=relative,
            file_name=physical.name,
            ext="txt",
            mime_type="text/plain",
            size_bytes=len(content),
            sha256=digest,
            biz_type="INTERNSHIP_S5_RECOVERY",
            biz_id=str(record.id),
            visibility="PRIVATE",
            security_level="NORMAL",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            object_key=relative,
            upload_source="SYSTEM",
            scan_required=False,
            scan_status="NOT_REQUIRED",
            remark="S5 governed backup/restore evidence",
        )
        db.add(file_obj)
        db.flush()
        binding = FileBinding(
            tenant_id=record.tenant_id,
            file_id=file_obj.id,
            biz_type="INTERNSHIP_RECORD",
            biz_id=str(record.id),
            relation_type="RECOVERY_EVIDENCE",
            subject_type="BUSINESS_OBJECT",
            subject_id=str(record.id),
            batch_id=str(record.batch_id),
            version_no=1,
            is_current=True,
            status="ACTIVE",
            module_code="internship",
            student_id=record.student_id,
        )
        db.add(binding)
        db.commit()

        schema = _assert_schema_contract(db)
        canonical = _canonical_snapshot(db, fixture, file_obj.id, binding.id, relative)
        state = {
            "phase": "SNAPSHOT_READY",
            "productExactSha": os.getenv("E2E_PRODUCT_EXACT_SHA") or "",
            "runnerExactSha": os.getenv("E2E_EXPECTED_SHA") or "",
            "fixture": fixture,
            "schema": schema,
            "canonical": canonical,
            "tableCounts": _table_counts(db),
            "uploadSha256": digest,
        }
        _save_state(state)
        print(
            "[internship-s5] snapshot ready:",
            json.dumps(
                {
                    "alembicRevision": schema["alembicRevision"],
                    "batchId": fixture["batchId"],
                    "internshipId": fixture["internshipId"],
                    "fileId": file_obj.id,
                    "bindingId": binding.id,
                    "trackedTableCount": len(state["tableCounts"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_upgraded() -> None:
    state = _load_state()
    db = get_sessionmaker()()
    try:
        schema = _assert_schema_contract(db)
        canonical = state["canonical"]
        current = _canonical_snapshot(
            db,
            state["fixture"],
            int(canonical["file"]["id"]),
            int(canonical["binding"]["id"]),
            canonical["file"]["relativeUploadPath"],
        )
        if current != canonical:
            raise AssertionError(f"historical facts drifted after upgrade: {current!r} != {canonical!r}")
        physical = _upload_dir() / canonical["file"]["relativeUploadPath"]
        if hashlib.sha256(physical.read_bytes()).hexdigest() != state["uploadSha256"]:
            raise AssertionError("historical upload bytes drifted after upgrade")
        state["upgradedSchema"] = schema
        state["phase"] = "UPGRADED_VERIFIED"
        _save_state(state)
        print("[internship-s5] upgrade/schema/history verified")
    finally:
        db.close()


def mutate_candidate() -> None:
    state = _load_state()
    fixture = state["fixture"]
    canonical = state["canonical"]
    db = get_sessionmaker()()
    try:
        batch = db.get(InternshipBatch, int(fixture["batchId"]))
        record = db.get(InternshipRecord, int(fixture["internshipId"]))
        binding = db.get(FileBinding, int(canonical["binding"]["id"]))
        if not all((batch, record, binding)):
            raise AssertionError("candidate mutation prerequisites missing")
        batch.batch_name = f"{batch.batch_name} [CANDIDATE-DAMAGE]"
        record.status = "ASSESSING"
        db.delete(binding)
        db.flush()
        db.execute(text(f"DROP TABLE IF EXISTS `{CANDIDATE_TABLE}`"))
        db.execute(text(f"CREATE TABLE `{CANDIDATE_TABLE}` (id BIGINT PRIMARY KEY, note VARCHAR(80) NOT NULL)"))
        db.execute(text(f"INSERT INTO `{CANDIDATE_TABLE}` (id, note) VALUES (1, 'candidate-only')"))
        db.commit()

        physical = _upload_dir() / canonical["file"]["relativeUploadPath"]
        physical.write_text("CANDIDATE-DAMAGE\n", encoding="utf-8")
        extra = _upload_dir() / "internship/s5/candidate-only.txt"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("candidate-only\n", encoding="utf-8")
        state["phase"] = "CANDIDATE_DAMAGE_INJECTED"
        _save_state(state)
        print("[internship-s5] candidate-only DB/file damage injected")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_restored() -> None:
    state = _load_state()
    canonical = state["canonical"]
    db = get_sessionmaker()()
    try:
        schema = _assert_schema_contract(db)
        current = _canonical_snapshot(
            db,
            state["fixture"],
            int(canonical["file"]["id"]),
            int(canonical["binding"]["id"]),
            canonical["file"]["relativeUploadPath"],
        )
        if current != canonical:
            raise AssertionError(f"historical facts did not restore exactly: {current!r} != {canonical!r}")

        current_counts = _table_counts(db)
        if current_counts != state["tableCounts"]:
            changed = {
                key: {"before": state["tableCounts"].get(key), "after": current_counts.get(key)}
                for key in sorted(set(state["tableCounts"]) | set(current_counts))
                if state["tableCounts"].get(key) != current_counts.get(key)
            }
            raise AssertionError(f"key table counts did not restore exactly: {changed}")

        candidate_count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE() AND table_name = :name
                    """
                ),
                {"name": CANDIDATE_TABLE},
            ).scalar_one()
        )
        if candidate_count != 0:
            raise AssertionError("candidate-only table survived governed restore")

        physical = _upload_dir() / canonical["file"]["relativeUploadPath"]
        digest = hashlib.sha256(physical.read_bytes()).hexdigest()
        if digest != state["uploadSha256"]:
            raise AssertionError(f"historical upload bytes not restored: {digest}")
        if (_upload_dir() / "internship/s5/candidate-only.txt").exists():
            raise AssertionError("candidate-only upload survived governed restore")

        if schema["alembicRevision"] != state["schema"]["alembicRevision"]:
            raise AssertionError(
                f"Alembic revision did not restore: {schema['alembicRevision']} != {state['schema']['alembicRevision']}"
            )

        state["restoredSchema"] = schema
        state["restoredTableCounts"] = current_counts
        state["phase"] = "RESTORE_VERIFIED"
        state["verified"] = True
        _save_state(state)
        print(
            "[internship-s5] RESTORE_VERIFIED:",
            json.dumps(
                {
                    "alembicRevision": schema["alembicRevision"],
                    "trackedTableCount": len(current_counts),
                    "uniqueIndexes": len(schema["uniqueIndexes"]),
                    "fileBindingRestored": True,
                    "candidateOnlyObjectsRemoved": True,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
    finally:
        db.close()


def main() -> int:
    phase = (os.getenv("E2E_S5_PHASE") or "").strip().lower()
    if phase == "snapshot":
        snapshot()
    elif phase == "verify-upgraded":
        verify_upgraded()
    elif phase == "mutate":
        mutate_candidate()
    elif phase == "verify-restored":
        verify_restored()
    else:
        raise SystemExit("E2E_S5_PHASE must be snapshot|verify-upgraded|mutate|verify-restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
