"""Seed isolated W2 exam-incident browser facts in the writable Playwright sandbox tenant."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401
from sqlalchemy import delete, select

from app.db.session import get_sessionmaker
from app.models import AaExamAuditTrail, AaExamBatch, AaExamCourse, AaExamIncident, AaExamRoom, Tenant, User

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
ADMIN_LOGIN = "admin2"
BATCH_NAME = "W2考务异常浏览器验收批次"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "e2e" / "academic-exam-incident-w2-fixture.json"


def assert_safe_target() -> None:
    if str(os.getenv("APP_ENV") or "").lower() in {"prod", "production"}:
        raise SystemExit("refusing W2 E2E seed in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks unsafe")
    if urlparse(db_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("W2 E2E seed only accepts local database")


def main() -> int:
    assert_safe_target()
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if tenant is None or tenant.tenant_code != TENANT_CODE:
            raise SystemExit("run e2e_seed_playwright_tenants.py before W2 seed")
        admin = db.scalar(select(User).where(
            User.tenant_id == TENANT_ID,
            User.login_name == ADMIN_LOGIN,
            User.is_deleted.is_(False),
        ))
        if admin is None:
            raise SystemExit("sandbox-school admin missing")

        previous_batches = db.scalars(select(AaExamBatch.id).where(
            AaExamBatch.tenant_id == TENANT_ID,
            AaExamBatch.batch_name == BATCH_NAME,
        )).all()
        if previous_batches:
            course_ids = db.scalars(select(AaExamCourse.id).where(
                AaExamCourse.tenant_id == TENANT_ID,
                AaExamCourse.batch_id.in_(previous_batches),
            )).all()
            incident_ids = db.scalars(select(AaExamIncident.id).where(
                AaExamIncident.tenant_id == TENANT_ID,
                AaExamIncident.exam_course_id.in_(course_ids),
            )).all() if course_ids else []
            if incident_ids:
                db.execute(delete(AaExamAuditTrail).where(
                    AaExamAuditTrail.tenant_id == TENANT_ID,
                    AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
                    AaExamAuditTrail.biz_id.in_(incident_ids),
                ))
                db.execute(delete(AaExamIncident).where(AaExamIncident.id.in_(incident_ids)))
            if course_ids:
                db.execute(delete(AaExamRoom).where(
                    AaExamRoom.tenant_id == TENANT_ID,
                    AaExamRoom.exam_course_id.in_(course_ids),
                ))
                db.execute(delete(AaExamCourse).where(AaExamCourse.id.in_(course_ids)))
            db.execute(delete(AaExamBatch).where(AaExamBatch.id.in_(previous_batches)))
            db.flush()

        batch = AaExamBatch(
            tenant_id=TENANT_ID,
            batch_name=BATCH_NAME,
            exam_type="FINAL",
            published_at=datetime.utcnow(),
            status="PUBLISHED",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(batch)
        db.flush()
        course = AaExamCourse(
            tenant_id=TENANT_ID,
            batch_id=batch.id,
            course_name="软件工程综合实践",
            class_name="软件2601",
            teacher_key="w2_teacher",
            teacher_name="W2监考教师",
            expected_students=9,
            exam_date="2029-06-21",
            start_time="09:00",
            end_time="11:00",
            duration_minutes=120,
            status="CONFIRMED",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(course)
        db.flush()
        room = AaExamRoom(
            tenant_id=TENANT_ID,
            exam_course_id=course.id,
            room_seq=1,
            classroom_text="实训楼A101",
            capacity=40,
            planned_count=9,
            seat_mode="SEQUENTIAL",
            source="MANUAL",
            status="ACTIVE",
            created_by=admin.id,
            updated_by=admin.id,
        )
        db.add(room)
        db.flush()

        attempts = []
        for retry in range(3):
            suffix = retry + 1
            absent = AaExamIncident(
                tenant_id=TENANT_ID,
                exam_room_id=room.id,
                exam_course_id=course.id,
                student_id=990100 + retry * 10 + 1,
                student_no=f"W2ABS{suffix:02d}",
                student_name=f"W2缺考学生{suffix}",
                incident_type="ABSENT",
                description="缺考风险联动已经送达，等待教务正式关闭",
                recorded_by="W2监考教师",
                recorded_at=datetime(2029, 6, 21, 9, 20 + retry),
                risk_alert_sent=True,
                status="ACTIVE",
                created_by=admin.id,
                updated_by=admin.id,
            )
            discipline = AaExamIncident(
                tenant_id=TENANT_ID,
                exam_room_id=room.id,
                exam_course_id=course.id,
                student_id=990100 + retry * 10 + 2,
                student_no=f"W2DISC{suffix:02d}",
                student_name=f"W2违纪学生{suffix}",
                incident_type="DISCIPLINE_VIOLATION",
                description="考试中使用违规资料，等待移交处分线索",
                recorded_by="W2监考教师",
                recorded_at=datetime(2029, 6, 21, 9, 30 + retry),
                risk_alert_sent=False,
                status="ACTIVE",
                created_by=admin.id,
                updated_by=admin.id,
            )
            other = AaExamIncident(
                tenant_id=TENANT_ID,
                exam_room_id=room.id,
                exam_course_id=course.id,
                student_id=990100 + retry * 10 + 3,
                student_no=f"W2VOID{suffix:02d}",
                student_name=f"W2误登记学生{suffix}",
                incident_type="OTHER",
                description="监考误选学生，等待正式作废",
                recorded_by="W2监考教师",
                recorded_at=datetime(2029, 6, 21, 9, 40 + retry),
                risk_alert_sent=False,
                status="ACTIVE",
                created_by=admin.id,
                updated_by=admin.id,
            )
            db.add_all([absent, discipline, other])
            db.flush()
            attempts.append({
                "absent": {"incidentId": str(absent.id), "studentNo": absent.student_no},
                "discipline": {"incidentId": str(discipline.id), "studentNo": discipline.student_no},
                "void": {"incidentId": str(other.id), "studentNo": other.student_no},
            })

        db.commit()
        fixture = {
            "tenant": TENANT_CODE,
            "username": ADMIN_LOGIN,
            "password": "123456",
            "batchId": str(batch.id),
            "batchName": BATCH_NAME,
            "attempts": attempts,
        }
        FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[w2-e2e-seed] tenant={TENANT_CODE} batch={batch.id} attempts={len(attempts)} fixture={FIXTURE_PATH}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
