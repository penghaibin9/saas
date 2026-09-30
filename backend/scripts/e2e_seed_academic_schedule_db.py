"""Seed one guarded Academic E2E timetable item for four-end browser journeys.

The command is dry-run by default.  It only inserts or repairs an item owned by
the ``e2e_aa_teacher_a`` fixture inside the immutable sandbox tenant.  The item
uses an existing class whose college already has a unique canonical review
assignee; it never mutates class/IAM truth, non-E2E timetable rows, or scope heads.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import (
    AaScheduleBatch,
    AaScheduleChange,
    AaScheduleItem,
    AaScheduleScopeHead,
    AaTerm,
    College,
    Major,
    SchoolClass,
    StudentProfile,
    User,
)


SANDBOX_TENANT_ID = 1000000000000000007
TEACHER_LOGIN = "e2e_aa_teacher_a"
STUDENT_NO = "E2EAA20260001"
COURSE_NAME = "E2E 教务四端联调课"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="insert the guarded E2E timetable item; omission is dry-run",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    set_tenant(SANDBOX_TENANT_ID)
    db = get_sessionmaker()()
    try:
        term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == SANDBOX_TENANT_ID,
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        ).order_by(AaTerm.id.desc()).limit(1)).first()
        if not term:
            raise RuntimeError("sandbox current academic term is missing")

        head = db.scalars(select(AaScheduleScopeHead).where(
            AaScheduleScopeHead.tenant_id == SANDBOX_TENANT_ID,
            AaScheduleScopeHead.term_id == term.id,
            AaScheduleScopeHead.scope_type == "SCHOOL",
            AaScheduleScopeHead.scope_id == 0,
            AaScheduleScopeHead.is_deleted.is_(False),
        )).first()
        batch = db.get(AaScheduleBatch, int(head.active_batch_id)) if head and head.active_batch_id else None
        if not batch or batch.tenant_id != SANDBOX_TENANT_ID or batch.status != "PUBLISHED":
            raise RuntimeError("sandbox current published schedule authority is missing")

        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == SANDBOX_TENANT_ID,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        fixture_class = db.get(SchoolClass, int(student.class_id)) if student and student.class_id else None
        if not fixture_class or not str(fixture_class.class_name or "").upper().startswith("E2E"):
            raise RuntimeError("guarded E2E class is missing")

        # Do not invent or mutate IAM.  Reuse the first existing class whose
        # college secretary already holds the canonical schedule-change review
        # permission, so the real workflow can resolve exactly one assignee.
        from app.modules.academic_affairs.services.academic_affairs_grade_task_assignee_guard import (
            SCHEDULE_CHANGE_COLLEGE_PERM,
            _runtime_permission_holder_ids,
        )
        holders = _runtime_permission_holder_ids(db, SCHEDULE_CHANGE_COLLEGE_PERM)
        school_class = db.scalars(select(SchoolClass)
            .join(Major, Major.id == SchoolClass.major_id)
            .join(College, College.id == Major.college_id)
            .where(
                SchoolClass.tenant_id == SANDBOX_TENANT_ID,
                SchoolClass.is_deleted.is_(False),
                Major.tenant_id == SANDBOX_TENANT_ID,
                Major.is_deleted.is_(False),
                College.tenant_id == SANDBOX_TENANT_ID,
                College.is_deleted.is_(False),
                College.secretary_id.in_(holders or [-1]),
            )
            .order_by(College.id, SchoolClass.id)
            .limit(1)).first()
        if not school_class:
            raise RuntimeError("no existing class has a canonical schedule-change college reviewer")

        teacher = db.scalars(select(User).where(
            User.tenant_id == SANDBOX_TENANT_ID,
            User.login_name == TEACHER_LOGIN,
            User.is_deleted.is_(False),
        )).first()
        if not teacher:
            raise RuntimeError("guarded E2E teacher account is missing")

        existing = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == SANDBOX_TENANT_ID,
            AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.teacher_key == TEACHER_LOGIN,
            AaScheduleItem.course_name == COURSE_NAME,
            AaScheduleItem.is_deleted.is_(False),
        ).order_by(AaScheduleItem.id.desc()).limit(1)).first()
        if existing:
            references = db.scalar(select(AaScheduleChange.id).where(
                AaScheduleChange.tenant_id == SANDBOX_TENANT_ID,
                AaScheduleChange.origin_item_id == existing.id,
                AaScheduleChange.is_deleted.is_(False),
            ).limit(1))
            needs_repair = int(existing.class_id or 0) != int(school_class.id)
            if needs_repair:
                if existing.status != "EFFECTIVE" or existing.change_id or references:
                    raise RuntimeError("existing E2E timetable item is already in use; refusing repair")
                if args.confirm:
                    existing.class_id = school_class.id
                    existing.class_name = school_class.class_name
                    db.commit()
            print({
                "mode": "repaired" if needs_repair and args.confirm else ("repair-dry-run" if needs_repair else "existing"),
                "itemId": str(existing.id),
                "batchId": str(batch.id),
                "status": existing.status,
                "classId": str(school_class.id),
            })
            return 0

        summary = {
            "mode": "confirm" if args.confirm else "dry-run",
            "batchId": str(batch.id),
            "termId": str(term.id),
            "teacherLogin": TEACHER_LOGIN,
            "classId": str(school_class.id),
            "courseName": COURSE_NAME,
            "origin": {"weekday": 7, "slotNo": 10, "startWeek": 1, "endWeek": 18},
        }
        if not args.confirm:
            print(summary)
            return 0

        row = AaScheduleItem(
            tenant_id=SANDBOX_TENANT_ID,
            batch_id=batch.id,
            task_id=None,
            course_id=None,
            course_name=COURSE_NAME,
            class_id=school_class.id,
            class_name=school_class.class_name,
            teacher_key=TEACHER_LOGIN,
            teacher_name=teacher.real_name or TEACHER_LOGIN,
            weekday=7,
            slot_no=10,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            classroom_id=None,
            classroom_text="E2E 云教室",
            status="EFFECTIVE",
            source="MANUAL",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        summary.update({"itemId": str(row.id), "status": row.status})
        print(summary)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
