"""C-W2 browser fixture for Teacher Today -> attendance real-click acceptance.

This script mutates only the isolated local Playwright MySQL database. It creates one current
formal schedule occurrence for the existing sandbox teacher ``e2e_advisor_a`` with a LOCKED
teaching-class roster and an APPLIED ADJUST marker. No production route or test-only API is added.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.db.session import get_sessionmaker
from app.models import (
    AaCourse,
    AaScheduleBatch,
    AaScheduleChange,
    AaScheduleItem,
    AaTeachingClass,
    AaTeachingClassMember,
    AaTeachingClassRosterVersion,
    AaTeachingClassTeacher,
    AaTeachingTask,
    AaTeachingTaskBatch,
    AaTerm,
    College,
    Major,
    SchoolClass,
    StudentProfile,
    Tenant,
    User,
)
from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as schedule_truth
from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash

TENANT_CODE = "sandbox-school"
TEACHER_LOGIN = "e2e_advisor_a"
OTHER_TEACHER_LOGIN = "e2e_advisor_b"
STUDENT_NOS = ("E2E20260001", "E2E20260002")
STATE_PATH = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_c_teacher_today_state.local.json"
TZ = ZoneInfo("Asia/Shanghai")


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing C-W2 browser fixture in production")
    if os.getenv("E2E_ALLOW_DESTRUCTIVE_TESTS") != "true":
        raise SystemExit("E2E_ALLOW_DESTRUCTIVE_TESTS=true is required")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    parsed = urlparse(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("C-W2 browser fixture only accepts a local database")


def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _restore_current_terms(db, state: dict) -> None:
    tenant_id = int(state.get("tenantId") or 0)
    if not tenant_id:
        return
    fixture_term_id = int(state.get("termId") or 0)
    if fixture_term_id:
        row = db.get(AaTerm, fixture_term_id)
        if row and row.tenant_id == tenant_id:
            row.is_current = False
    for raw_id in state.get("previousCurrentTermIds") or []:
        term = db.get(AaTerm, int(raw_id))
        if term and term.tenant_id == tenant_id and not term.is_deleted:
            term.is_current = True


def cleanup() -> int:
    assert_safe_target()
    state = _read_state()
    if not state:
        return 0
    db = get_sessionmaker()()
    try:
        _restore_current_terms(db, state)
        db.commit()
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _one(db, model, *criteria):
    return db.scalars(select(model).where(*criteria)).first()


def seed() -> int:
    assert_safe_target()
    previous_state = _read_state()
    db = get_sessionmaker()()
    try:
        if previous_state:
            _restore_current_terms(db, previous_state)
            db.flush()

        tenant = _one(db, Tenant, Tenant.tenant_code == TENANT_CODE, Tenant.is_deleted.is_(False))
        if not tenant:
            raise SystemExit("sandbox-school missing; run Playwright tenant bootstrap first")
        tenant_id = int(tenant.id)
        teacher = _one(
            db,
            User,
            User.tenant_id == tenant_id,
            User.login_name == TEACHER_LOGIN,
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        )
        other_teacher = _one(
            db,
            User,
            User.tenant_id == tenant_id,
            User.login_name == OTHER_TEACHER_LOGIN,
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
        )
        if not teacher or not other_teacher:
            raise SystemExit("graduation E2E teacher accounts missing; bootstrap accounts first")

        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.student_no.in_(STUDENT_NOS),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.student_no)).all()
        if len(students) != len(STUDENT_NOS):
            raise SystemExit("C-W2 fixture students missing; graduation identity bootstrap must run first")
        class_ids = {int(student.class_id or 0) for student in students}
        if len(class_ids) != 1 or 0 in class_ids:
            raise SystemExit("C-W2 fixture students must share one real administrative class")
        school_class = db.get(SchoolClass, next(iter(class_ids)))
        if not school_class or school_class.tenant_id != tenant_id:
            raise SystemExit("C-W2 administrative class missing")
        major = db.get(Major, int(school_class.major_id)) if school_class.major_id else None
        college = db.get(College, int(major.college_id)) if major and major.college_id else None

        current_terms = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == tenant_id,
            AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False),
        )).all()
        previous_current_ids = [int(row.id) for row in current_terms]
        for row in current_terms:
            row.is_current = False

        now = datetime.now(TZ).replace(tzinfo=None)
        target_date = now.date()
        term_start_date = target_date - timedelta(days=target_date.weekday() + 14)
        term_end_date = term_start_date + timedelta(weeks=18, days=-1)
        run_key = str(time.time_ns())[-10:]

        term = AaTerm(
            tenant_id=tenant_id,
            year_code=f"CW2-{target_date.year}-{run_key[-6:]}",
            term_no=1,
            term_name=f"E2E C-W2 Teacher Today {run_key}",
            start_date=datetime.combine(term_start_date, datetime.min.time()),
            end_date=datetime.combine(term_end_date, datetime.min.time()),
            teaching_weeks=18,
            is_current=True,
            status="PUBLISHED",
        )
        db.add(term)
        db.flush()

        course = AaCourse(
            tenant_id=tenant_id,
            course_code=f"E2ECW2-{run_key}",
            course_name=f"C-W2浏览器验收课程-{run_key[-4:]}",
            credit=2,
            status="ENABLED",
        )
        db.add(course)
        db.flush()
        task_batch = AaTeachingTaskBatch(
            tenant_id=tenant_id,
            term_id=term.id,
            college_id=(int(college.id) if college else None),
            batch_name=f"C-W2浏览器教学任务-{run_key}",
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()
        task = AaTeachingTask(
            tenant_id=tenant_id,
            batch_id=task_batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_key=TEACHER_LOGIN,
            teacher_name=teacher.real_name,
            class_id=school_class.id,
            teaching_class_name=school_class.class_name,
            expected_students=len(students),
            status="READY",
            weekly_hours=2,
            total_hours=36,
            start_week=1,
            end_week=18,
        )
        db.add(task)
        db.flush()

        batch = AaScheduleBatch(
            tenant_id=tenant_id,
            term_id=term.id,
            college_id=None,
            batch_name=f"C-W2当前正式课表-{run_key}",
            status="PUBLISHED",
            publish_at=now,
        )
        db.add(batch)
        db.flush()
        origin = AaScheduleItem(
            tenant_id=tenant_id,
            batch_id=batch.id,
            task_id=task.id,
            course_id=course.id,
            course_name=course.course_name,
            teacher_key=TEACHER_LOGIN,
            teacher_name=teacher.real_name,
            class_id=school_class.id,
            class_name=school_class.class_name,
            classroom_text="E2E旧教室-A101",
            weekday=target_date.isoweekday(),
            slot_no=1,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            status="CHANGED",
            source="MANUAL",
        )
        adjusted = AaScheduleItem(
            tenant_id=tenant_id,
            batch_id=batch.id,
            task_id=task.id,
            course_id=course.id,
            course_name=course.course_name,
            teacher_key=TEACHER_LOGIN,
            teacher_name=teacher.real_name,
            class_id=school_class.id,
            class_name=school_class.class_name,
            classroom_text="E2E调课教室-B202",
            weekday=target_date.isoweekday(),
            slot_no=2,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            status="EFFECTIVE",
            source="MANUAL",
        )
        db.add_all([origin, adjusted])
        db.flush()
        change = AaScheduleChange(
            tenant_id=tenant_id,
            term_id=term.id,
            batch_id=batch.id,
            origin_item_id=origin.id,
            task_id=task.id,
            change_type="ADJUST",
            course_name=course.course_name,
            class_id=school_class.id,
            class_name=school_class.class_name,
            origin_weekday=origin.weekday,
            origin_slot_no=origin.slot_no,
            origin_start_week=origin.start_week,
            origin_end_week=origin.end_week,
            origin_week_parity=origin.week_parity,
            origin_classroom=origin.classroom_text,
            target_weekday=adjusted.weekday,
            target_slot_no=adjusted.slot_no,
            target_start_week=adjusted.start_week,
            target_end_week=adjusted.end_week,
            target_week_parity=adjusted.week_parity,
            target_classroom=adjusted.classroom_text,
            reason="C-W2 Playwright 已生效调课证据",
            new_item_id=adjusted.id,
            applied_at=now,
            applicant_id=teacher.id,
            status="APPLIED",
        )
        db.add(change)
        db.flush()
        adjusted.change_id = change.id

        set_tenant({"tenantId": str(tenant_id)})
        set_current_user({
            "userId": f"db-{teacher.id}",
            "tenantId": str(tenant_id),
            "loginName": TEACHER_LOGIN,
            "realName": teacher.real_name,
            "userType": "TEACHER",
            "currentRoleCode": "GD_MENTOR",
        })
        head = schedule_truth.lock_scope_head(db, term.id, "SCHOOL", 0)
        head.active_batch_id = batch.id
        head.version = max(int(head.version or 0), 1)
        head.published_at = now

        teaching_class = AaTeachingClass(
            tenant_id=tenant_id,
            teaching_task_id=task.id,
            term_id=term.id,
            course_id=course.id,
            class_code=f"E2E-CW2-TC-{run_key}",
            class_name=f"{course.course_name} · {school_class.class_name}",
            class_type="ADMIN",
            source_type="TEACHING_TASK",
            source_id=task.id,
            capacity=len(students),
            current_roster_version_no=0,
            roster_status="DRAFT",
            status="ACTIVE",
            source_snapshot_json="{}",
        )
        db.add(teaching_class)
        db.flush()
        student_ids = [int(student.id) for student in students]
        version = AaTeachingClassRosterVersion(
            tenant_id=tenant_id,
            teaching_class_id=teaching_class.id,
            version_no=1,
            source_type="ADMIN_CLASS",
            source_id=int(school_class.id),
            member_count=len(student_ids),
            roster_hash=roster_hash(student_ids),
            status="LOCKED",
            reason="C-W2 Playwright 正式名单",
            locked_at=now,
            locked_by=TEACHER_LOGIN,
        )
        db.add(version)
        db.flush()
        for student in students:
            db.add(AaTeachingClassMember(
                tenant_id=tenant_id,
                teaching_class_id=teaching_class.id,
                roster_version_id=version.id,
                student_id=student.id,
                source_type="ADMIN_CLASS",
                source_id=int(school_class.id),
                status="ACTIVE",
            ))
        db.add(AaTeachingClassTeacher(
            tenant_id=tenant_id,
            teaching_class_id=teaching_class.id,
            teacher_id=teacher.id,
            teacher_key=TEACHER_LOGIN,
            teacher_name=teacher.real_name,
            role_type="PRIMARY",
            start_week=1,
            end_week=18,
            status="ACTIVE",
        ))
        teaching_class.current_roster_version_id = version.id
        teaching_class.current_roster_version_no = 1
        teaching_class.roster_status = "LOCKED"
        db.commit()

        state = {
            "tenantId": tenant_id,
            "tenantCode": TENANT_CODE,
            "termId": int(term.id),
            "previousCurrentTermIds": previous_current_ids,
            "teacherLogin": TEACHER_LOGIN,
            "otherTeacherLogin": OTHER_TEACHER_LOGIN,
            "courseName": course.course_name,
            "className": school_class.class_name,
            "studentName": students[0].real_name,
            "studentNo": students[0].student_no,
            "targetDate": target_date.isoformat(),
            "teachingTaskId": int(task.id),
            "scheduleItemId": int(adjusted.id),
            "changeId": int(change.id),
            "slotNo": int(adjusted.slot_no),
        }
        STATE_PATH.parent.mkdir(exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(state, ensure_ascii=False))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    command = (sys.argv[1] if len(sys.argv) > 1 else "seed").lower()
    if command == "seed":
        return seed()
    if command == "cleanup":
        return cleanup()
    raise SystemExit("usage: e2e_seed_academic_c_teacher_today.py [seed|cleanup]")


if __name__ == "__main__":
    raise SystemExit(main())
