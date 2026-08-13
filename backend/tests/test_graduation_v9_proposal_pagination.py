"""V9.2 U2/M9: 开题列表必须在 MySQL 侧分页，未提交必须 SQL NOT EXISTS。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.context import set_current_user
from app.db.session import get_sessionmaker
from app.models import GraduationBatch, GraduationMentor, GraduationProposal, GraduationStudent
from app.modules.graduation.services import graduation_proposal_read_service as proposal_read

MAIN_TENANT_ID = 1000000000000000001


def _seed_600():
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=MAIN_TENANT_ID,
            batch_name="M9 真分页 600 人验收",
            batch_no=f"M9-PAGE-{datetime.now(timezone.utc).timestamp():.6f}",
            academic_year="2026-2027",
            grade_year="2027届",
            planned_count=600,
            status="RUNNING",
        )
        db.add(batch)
        db.flush()
        students = []
        for idx in range(1, 601):
            students.append(GraduationStudent(
                tenant_id=MAIN_TENANT_ID,
                batch_id=batch.id,
                student_no=f"M9{idx:04d}",
                name=f"M9学生{idx:04d}",
                class_name=f"软件{(idx - 1) // 50 + 1:02d}班",
                topic_title=f"M9课题{idx:04d}",
                stage="TASKBOOK_CONFIRM",
                record_status="ACTIVE",
            ))
        db.add_all(students)
        db.flush()
        proposals = []
        now = datetime.now(timezone.utc)
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
            proposals.append(GraduationProposal(
                tenant_id=MAIN_TENANT_ID,
                gd_student_id=student.id,
                version="v1",
                is_resubmit=False,
                submit_at=now,
                background="真实分页验收",
                plan="MySQL COUNT/OFFSET/LIMIT",
                outcome="锁住 M9",
                status=status,
                active_key=active_key,
            ))
        db.add_all(proposals)
        db.commit()
        return int(batch.id), [int(s.id) for s in students]
    finally:
        db.close()


def test_m9_mysql_pagination_not_submitted_and_keyword(db_mode, graduation_client, auth_headers):
    batch_id, student_ids = _seed_600()

    pending = graduation_client.get(
        "/api/v1/graduation/proposals",
        headers=auth_headers,
        params={"batchId": batch_id, "status": "PENDING_REVIEW", "page": 1, "pageSize": 20},
    ).json()["data"]
    assert pending["total"] == 70
    assert len(pending["list"]) == 20

    seen: list[str] = []
    for page in range(1, 20):
        payload = graduation_client.get(
            "/api/v1/graduation/proposals",
            headers=auth_headers,
            params={"batchId": batch_id, "status": "NOT_SUBMITTED", "page": page, "pageSize": 20},
        ).json()["data"]
        assert payload["total"] == 380
        seen.extend(row["gdStudentId"] for row in payload["list"])
    assert len(seen) == 380
    assert len(set(seen)) == 380
    assert set(seen) == {str(sid) for sid in student_ids[220:]}

    late = graduation_client.get(
        "/api/v1/graduation/proposals",
        headers=auth_headers,
        params={"batchId": batch_id, "status": "NOT_SUBMITTED", "keyword": "M90521",
                "page": 1, "pageSize": 20},
    ).json()["data"]
    assert late["total"] == 1
    assert late["list"][0]["studentName"] == "M9学生0521"

    all_page_12 = graduation_client.get(
        "/api/v1/graduation/proposals",
        headers=auth_headers,
        params={"batchId": batch_id, "page": 12, "pageSize": 20},
    ).json()["data"]
    assert all_page_12["total"] == 600
    assert all_page_12["list"][0]["studentName"] == "M9学生0221"
    assert all(row["status"] == "NOT_SUBMITTED" for row in all_page_12["list"])


def test_proposal_sql_scope_keeps_stable_mentor_relation(db_mode):
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=MAIN_TENANT_ID, batch_name="M9 导师范围", batch_no="M9-MENTOR-SCOPE",
            planned_count=2, status="RUNNING",
        )
        mentor_a = GraduationMentor(
            tenant_id=MAIN_TENANT_ID, teacher_no="T-M9-A", teacher_name="M9导师甲",
            qualification_status="QUALIFIED",
        )
        mentor_b = GraduationMentor(
            tenant_id=MAIN_TENANT_ID, teacher_no="T-M9-B", teacher_name="M9导师乙",
            qualification_status="QUALIFIED",
        )
        db.add_all([batch, mentor_a, mentor_b])
        db.flush()
        own = GraduationStudent(
            tenant_id=MAIN_TENANT_ID, batch_id=batch.id, student_no="M9OWN", name="导师甲学生",
            mentor_id=mentor_a.id, advisor_name="M9导师甲", stage="TASKBOOK_CONFIRM", record_status="ACTIVE",
        )
        other = GraduationStudent(
            tenant_id=MAIN_TENANT_ID, batch_id=batch.id, student_no="M9OTHER", name="导师乙学生",
            mentor_id=mentor_b.id, advisor_name="M9导师乙", stage="TASKBOOK_CONFIRM", record_status="ACTIVE",
        )
        db.add_all([own, other])
        db.flush()
        db.add_all([
            GraduationProposal(tenant_id=MAIN_TENANT_ID, gd_student_id=own.id, version="v1",
                               status="PENDING_REVIEW", active_key=f"pending:{own.id}"),
            GraduationProposal(tenant_id=MAIN_TENANT_ID, gd_student_id=other.id, version="v1",
                               status="PENDING_REVIEW", active_key=f"pending:{other.id}"),
        ])
        db.commit()

        set_current_user({
            "tenantId": str(MAIN_TENANT_ID), "currentRoleCode": "GD_MENTOR", "userType": "TEACHER",
            "realName": "M9导师甲", "loginName": "T-M9-A",
        })
        ids = db.scalars(proposal_read.student_scope_select(db, MAIN_TENANT_ID, batch_id=batch.id)).all()
        assert ids == [own.id]
        rows, total = proposal_read.list_proposals(
            db, MAIN_TENANT_ID, 1, 20, status="PENDING_REVIEW", batch_id=batch.id
        )
        assert total == 1
        assert rows[0]["studentName"] == "导师甲学生"
    finally:
        set_current_user(None)
        db.close()
