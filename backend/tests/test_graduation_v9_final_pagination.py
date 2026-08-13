"""V9.2 U3/M10: 成果列表必须在 MySQL 侧分页，未提交必须 SQL NOT EXISTS。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import get_sessionmaker
from app.models import GraduationBatch, GraduationFinal, GraduationStudent
from app.modules.graduation.services import graduation_final_read_service as final_read
from app.modules.graduation.services import graduation_service as service

MAIN_TENANT_ID = 1000000000000000001


def _seed_600_finals():
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=MAIN_TENANT_ID,
            batch_name="M10 真分页 600 人验收",
            batch_no=f"M10-PAGE-{datetime.now(timezone.utc).timestamp():.6f}",
            academic_year="2026-2027",
            grade_year="2027届",
            planned_count=600,
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
        students = [
            GraduationStudent(
                tenant_id=MAIN_TENANT_ID,
                batch_id=batch.id,
                student_no=f"M10{idx:04d}",
                name=f"M10学生{idx:04d}",
                class_name=f"软件{(idx - 1) // 50 + 1:02d}班",
                topic_title=f"M10课题{idx:04d}",
                stage="FINAL_CHECK",
                record_status="ACTIVE",
            )
            for idx in range(1, 601)
        ]
        db.add_all(students)
        db.flush()
        now = datetime.now(timezone.utc)
        finals = []
        for idx, student in enumerate(students[:220], start=1):
            if idx <= 70:
                status = "PENDING_REVIEW"
                active_key = f"pending:{student.id}"
            elif idx <= 170:
                status = "APPROVED"
                active_key = None
            else:
                status = "REJECTED"
                active_key = None
            finals.append(GraduationFinal(
                tenant_id=MAIN_TENANT_ID,
                gd_student_id=student.id,
                final_type="初稿",
                version="v1",
                submit_at=now,
                plagiarism_rate="35%" if idx <= 5 else "20%",
                plagiarism_status="已检测",
                status=status,
                active_key=active_key,
            ))
        db.add_all(finals)
        db.commit()
        return int(batch.id), [int(student.id) for student in students]
    finally:
        db.close()


def test_m10_public_service_entrypoints_are_bound_to_sql_read_model():
    assert service.list_finals.__module__ == "app.modules.graduation.services"
    assert service.list_finals.__name__ == "list_finals"
    assert service.final_stats.__module__ == "app.modules.graduation.services"
    assert service.export_finals_xlsx.__module__ == "app.modules.graduation.services"


def test_m10_mysql_pagination_not_submitted_and_stats(db_mode, graduation_client, auth_headers):
    batch_id, student_ids = _seed_600_finals()

    pending = graduation_client.get(
        "/api/v1/graduation/finals",
        headers=auth_headers,
        params={"batchId": batch_id, "status": "PENDING_REVIEW", "page": 1, "pageSize": 20},
    ).json()["data"]
    assert pending["total"] == 70
    assert len(pending["items"]) == 20

    seen: list[str] = []
    for page in range(1, 20):
        payload = graduation_client.get(
            "/api/v1/graduation/finals",
            headers=auth_headers,
            params={"batchId": batch_id, "status": "NOT_SUBMITTED", "page": page, "pageSize": 20},
        ).json()["data"]
        assert payload["total"] == 380
        seen.extend(row["gdStudentId"] for row in payload["items"])
    assert len(seen) == 380
    assert len(set(seen)) == 380
    assert set(seen) == {str(student_id) for student_id in student_ids[220:]}

    all_page_12 = graduation_client.get(
        "/api/v1/graduation/finals",
        headers=auth_headers,
        params={"batchId": batch_id, "page": 12, "pageSize": 20},
    ).json()["data"]
    assert all_page_12["total"] == 600
    assert all_page_12["items"][0]["studentName"] == "M10学生0221"
    assert all(row["status"] == "NOT_SUBMITTED" for row in all_page_12["items"])

    stats = graduation_client.get(
        "/api/v1/graduation/finals/stats",
        headers=auth_headers,
        params={"batchId": batch_id},
    ).json()["data"]
    assert stats["total"] == 220
    assert stats["plagiarismOver"] == 5
    by_status = {row["status"]: row["count"] for row in stats["byStatus"]}
    assert by_status == {"PENDING_REVIEW": 70, "APPROVED": 100, "REJECTED": 50}


def test_m10_keyword_reaches_late_not_submitted_row(db_mode, graduation_client, auth_headers):
    batch_id, _student_ids = _seed_600_finals()
    payload = graduation_client.get(
        "/api/v1/graduation/finals",
        headers=auth_headers,
        params={
            "batchId": batch_id,
            "status": "NOT_SUBMITTED",
            "keyword": "M100521",
            "page": 1,
            "pageSize": 20,
        },
    ).json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["studentName"] == "M10学生0521"


def test_m10_direct_read_model_page_contract(db_mode):
    batch_id, _student_ids = _seed_600_finals()
    db = get_sessionmaker()()
    try:
        rows, total = final_read.list_finals(
            db, MAIN_TENANT_ID, 1, 37, status="NOT_SUBMITTED", batch_id=batch_id
        )
        assert total == 380
        assert len(rows) == 37
    finally:
        db.close()
