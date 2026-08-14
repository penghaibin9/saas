"""U7 archive dirty-data read-only, exact fail-closed and MySQL scale contracts."""
from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import GraduationArchiveRecord, GraduationBatch, GraduationStudent
from app.modules.graduation.services.graduation_archive_data_quality import (
    assert_archive_identity_writable,
    identity_anomaly_reasons,
    readonly_missing_markers,
)

ROOT = Path(__file__).resolve().parents[2]
MAIN_TENANT_ID = 1000000000000000001
ARCHIVE = "/api/v1/graduation/gd-archives"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _is_validation_or_conflict(response) -> bool:
    body = response.json() if "application/json" in (response.headers.get("content-type") or "") else {}
    return (
        response.status_code in (400, 409, 422)
        or body.get("bizCode") in {"DATA_CONFLICT", "VALIDATION_ERROR"}
        or body.get("code") in {409001, 422001, 400, 409, 422}
    )


def _new_batch(db, *, planned_count: int, label: str) -> GraduationBatch:
    suffix = uuid.uuid4().hex[:10]
    batch = GraduationBatch(
        tenant_id=MAIN_TENANT_ID,
        batch_name=f"U7 {label}-{suffix}",
        batch_no=f"U7-{label.upper()}-{suffix}",
        academic_year="2026-2027",
        grade_year="2027届",
        planned_count=planned_count,
        status="RUNNING",
    )
    db.add(batch)
    db.flush()
    return batch


def _seed_600_archive_rows():
    db = get_sessionmaker()()
    try:
        batch = _new_batch(db, planned_count=600, label="archive-scale")
        students = []
        for idx in range(1, 601):
            students.append(GraduationStudent(
                tenant_id=MAIN_TENANT_ID,
                batch_id=batch.id,
                student_no="" if idx == 377 else f"U7A{idx:04d}",
                name="" if idx == 121 else f"U7归档学生{idx:04d}",
                class_name=f"软件{(idx - 1) // 50 + 1:02d}班",
                topic_title=f"U7归档课题{idx:04d}",
                stage="FINAL_CHECK",
                record_status="ACTIVE",
            ))
        db.add_all(students)
        db.flush()
        rows = []
        for idx, student in enumerate(students, start=1):
            status = "SUBMITTED" if idx % 3 == 0 else "PENDING_SUBMIT"
            rows.append(GraduationArchiveRecord(
                tenant_id=MAIN_TENANT_ID,
                gd_student_id=student.id,
                status=status,
                checklist_json=[],
                missing_items=[],
            ))
        db.add_all(rows)
        db.commit()
        return int(batch.id), {
            "missing_name": int(students[120].id),
            "missing_name_no": str(students[120].student_no),
            "missing_no": int(students[376].id),
            "missing_no_name": str(students[376].name),
        }
    finally:
        db.close()


def _seed_batch_preview_rows():
    db = get_sessionmaker()()
    try:
        batch = _new_batch(db, planned_count=3, label="dirty-preview")
        rows = [
            GraduationStudent(
                tenant_id=MAIN_TENANT_ID, batch_id=batch.id,
                student_no="U7P0001", name="U7正常学生", stage="FINAL_CHECK", record_status="ACTIVE",
            ),
            GraduationStudent(
                tenant_id=MAIN_TENANT_ID, batch_id=batch.id,
                student_no="U7P0002", name="", stage="FINAL_CHECK", record_status="ACTIVE",
            ),
            GraduationStudent(
                tenant_id=MAIN_TENANT_ID, batch_id=batch.id,
                student_no="", name="U7缺学号学生", stage="FINAL_CHECK", record_status="ACTIVE",
            ),
        ]
        db.add_all(rows)
        db.commit()
        return int(batch.id), [int(row.id) for row in rows]
    finally:
        db.close()


def test_archive_identity_anomaly_rule_is_shared_and_precise():
    clean = SimpleNamespace(name="张三", student_no="20260001")
    missing_name = SimpleNamespace(name=" ", student_no="20260002")
    missing_both = SimpleNamespace(name=None, student_no="")

    assert identity_anomaly_reasons(clean) == []
    assert identity_anomaly_reasons(missing_name) == ["学生姓名缺失"]
    assert identity_anomaly_reasons(missing_both) == ["学生姓名缺失", "学号缺失"]
    assert readonly_missing_markers(missing_both) == [
        "历史主档异常：学生姓名缺失",
        "历史主档异常：学号缺失",
    ]


def test_archive_identity_anomaly_is_server_side_read_only():
    dirty = SimpleNamespace(name="", student_no="20260003")
    with pytest.raises(AppException) as exc:
        assert_archive_identity_writable(dirty)
    assert exc.value.code == "DATA_CONFLICT"
    assert "仅允许只读查看" in exc.value.message


def test_single_archive_writes_use_batch_bound_dirty_data_guard():
    router = text("backend/app/modules/graduation/routers/graduation_archive_sensitive_router.py")
    assert "assert_archive_identity_writable" in router
    assert "student = load_student_in_batch(db, student_id, batch_id)" in router
    assert router.count("writable=True") == 4
    assert "with_for_update()" not in router


def test_batch_archive_snapshot_keeps_dirty_rows_visible_but_non_executable():
    consistency = text("backend/app/modules/graduation/services/graduation_archive_consistency.py")
    assert '"dataAnomaly": bool(anomaly_reasons)' in consistency
    assert '"anomalyReasons": anomaly_reasons' in consistency
    assert "readonly_missing_markers(student)" in consistency
    assert 'if snap.get("dataAnomaly")' in consistency
    assert '"dirtySkipped": dirty_skipped' in consistency
    assert 'reasons.append("dirty_data")' in consistency


def test_archive_read_model_is_sql_paged_and_exposes_explicit_read_only_state():
    read_model = text("backend/app/modules/graduation/services/graduation_archive_read_service.py")
    assert "select(func.count(" in read_model
    assert ".offset(" in read_model and ".limit(" in read_model
    assert "accessible_student_ids" not in read_model
    assert 'item["status"] = "DATA_ANOMALY"' in read_model
    assert 'item["statusLabel"] = "历史数据异常 · 只读"' in read_model
    assert 'item["statusTone"] = "danger"' in read_model
    assert 'item["allowedActions"] = []' in read_model


def test_u7_mysql_archive_list_600_rows_is_paged_and_dirty_rows_stay_visible(
    db_mode, graduation_client, auth_headers
):
    assert db_mode == "mysql"
    batch_id, dirty = _seed_600_archive_rows()

    first = graduation_client.get(
        ARCHIVE,
        headers=auth_headers,
        params={"batchId": batch_id, "page": 1, "pageSize": 20},
    ).json()["data"]
    assert first["total"] == 600
    assert first["page"] == 1 and first["pageSize"] == 20
    assert len(first["items"]) == 20

    late = graduation_client.get(
        ARCHIVE,
        headers=auth_headers,
        params={"batchId": batch_id, "page": 30, "pageSize": 20},
    ).json()["data"]
    assert late["total"] == 600 and len(late["items"]) == 20

    missing_name = graduation_client.get(
        ARCHIVE,
        headers=auth_headers,
        params={"batchId": batch_id, "keyword": dirty["missing_name_no"], "page": 1, "pageSize": 20},
    ).json()["data"]
    assert missing_name["total"] == 1
    assert missing_name["items"][0]["gdStudentId"] == str(dirty["missing_name"])
    assert missing_name["items"][0]["status"] == "DATA_ANOMALY"
    assert missing_name["items"][0]["allowedActions"] == []
    assert "学生姓名缺失" in missing_name["items"][0]["anomalyReasons"]

    missing_no = graduation_client.get(
        ARCHIVE,
        headers=auth_headers,
        params={"batchId": batch_id, "keyword": dirty["missing_no_name"], "page": 1, "pageSize": 20},
    ).json()["data"]
    assert missing_no["total"] == 1
    assert missing_no["items"][0]["gdStudentId"] == str(dirty["missing_no"])
    assert "学号缺失" in missing_no["items"][0]["anomalyReasons"]


def test_u7_mysql_archive_missing_wrong_batch_and_dirty_single_write_fail_closed(
    db_mode, graduation_client, auth_headers
):
    assert db_mode == "mysql"
    batch_id, dirty = _seed_600_archive_rows()
    db = get_sessionmaker()()
    try:
        other_batch = _new_batch(db, planned_count=0, label="wrong-batch")
        db.commit()
        other_batch_id = int(other_batch.id)
    finally:
        db.close()

    missing = graduation_client.get(ARCHIVE, headers=auth_headers)
    missing_body = missing.json()
    assert missing.status_code == 400, missing.text
    assert missing_body["bizCode"] == "VALIDATION_ERROR", missing_body
    assert any(item.get("field") == "batchId" for item in missing_body.get("details") or []), missing_body

    wrong = graduation_client.get(
        f"{ARCHIVE}/{dirty['missing_name']}",
        headers=auth_headers,
        params={"batchId": other_batch_id},
    )
    assert _is_validation_or_conflict(wrong), wrong.text

    blocked = graduation_client.post(
        f"{ARCHIVE}/{dirty['missing_name']}/generate",
        headers=auth_headers,
        params={"batchId": batch_id},
    )
    assert _is_validation_or_conflict(blocked), blocked.text
    body = blocked.json()
    assert body.get("bizCode") == "DATA_CONFLICT" or "只读" in str(body), body


def test_u7_mysql_batch_preview_and_execute_never_write_dirty_students(
    db_mode, graduation_client, auth_headers
):
    assert db_mode == "mysql"
    batch_id, student_ids = _seed_batch_preview_rows()

    preview_response = graduation_client.post(
        f"{ARCHIVE}/batch-generate/preview",
        headers=auth_headers,
        params={"batchId": batch_id},
    )
    preview_body = preview_response.json()
    assert preview_body["code"] == 0, preview_body
    preview = preview_body["data"]
    assert preview["candidateCount"] == 3
    dirty_reason = next(row for row in preview["skipReasons"] if row["reason"] == "dirty_data")
    assert dirty_reason["count"] == 2
    assert preview["previewToken"]

    executed_response = graduation_client.post(
        f"{ARCHIVE}/batch-generate",
        headers=auth_headers,
        params={"batchId": batch_id},
        json={"previewToken": preview["previewToken"]},
    )
    executed_body = executed_response.json()
    assert executed_body["code"] == 0, executed_body
    executed = executed_body["data"]
    assert executed["submitted"] == 0
    assert executed["skipped"] == 3
    assert executed["dirtySkipped"] == 2

    db = get_sessionmaker()()
    try:
        dirty_count = int(db.scalar(select(func.count()).select_from(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == MAIN_TENANT_ID,
            GraduationArchiveRecord.gd_student_id.in_(student_ids[1:]),
            GraduationArchiveRecord.is_deleted.is_(False),
        )) or 0)
        clean_rows = list(db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == MAIN_TENANT_ID,
            GraduationArchiveRecord.gd_student_id == student_ids[0],
            GraduationArchiveRecord.is_deleted.is_(False),
        )).all())
        assert dirty_count == 0, "dirty-data students must remain true read-only even in batch execution"
        assert len(clean_rows) == 1 and clean_rows[0].status == "PENDING_SUBMIT"
    finally:
        db.close()
