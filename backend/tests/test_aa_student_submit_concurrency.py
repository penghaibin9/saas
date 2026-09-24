"""学生教务首次提交的 MySQL 并发回归。

暂缓注册和成绩复查在第一次提交前都没有待办业务行可加锁。这里用同一正式学生、
同一正式对象的两个并发请求验证：只有一个命令能落单，另一个必须得到可恢复的 409，
而不是形成两条待处理记录。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from sqlalchemy import select

from app.core.exceptions import AppException


TID = 1000000000000000001


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _student_context(student_id: int, *, student_no: str, real_name: str) -> dict:
    from app.core.context import set_current_user, set_tenant

    user = {
        "userId": f"concurrent-student-{student_id}",
        "tenantId": str(TID),
        "studentId": str(student_id),
        "studentNo": student_no,
        "realName": real_name,
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "clientType": "STUDENT_MINI",
        "activeContextId": "concurrent-submit",
    }
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    return user


def _race(fn):
    """Run exactly two formal commands from independent MySQL sessions."""
    barrier = Barrier(2)
    succeeded, failed = [], []
    lock = Lock()

    def invoke():
        try:
            barrier.wait(timeout=30)
            result = fn()
            with lock:
                succeeded.append(result)
        except AppException as exc:
            with lock:
                failed.append((exc.http_status, exc.code, exc.message))
        except Exception as exc:  # noqa: BLE001 - an unexpected database error is a test failure
            with lock:
                failed.append((None, type(exc).__name__, repr(exc)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(invoke) for _ in range(2)]
        for future in futures:
            future.result(timeout=90)
    return succeeded, failed


def _seed_deferral_target():
    from app.models import AaRegistrationBatch, StudentProfile

    with _session() as db:
        student = StudentProfile(
            tenant_id=TID,
            student_no="CONCURRENT_REG_01",
            real_name="注册并发学生",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        batch = AaRegistrationBatch(
            tenant_id=TID,
            batch_name="注册暂缓并发回归批次",
            register_type="ANNUAL",
            status="OPEN",
        )
        db.add_all([student, batch])
        db.flush()
        result = int(student.id), str(student.student_no), int(batch.id)
        db.commit()
        return result


def test_concurrent_student_registration_deferrals_create_one_pending_record(db_mode):
    """学生小程序双击/重试与门户同源命令不能生成两条暂缓申请。"""
    del db_mode
    from app.models import AaRegistrationDeferral, AffairsAuditTrail
    from app.modules.academic_affairs.services import mobile_academic_gaps_service as gaps

    student_id, student_no, batch_id = _seed_deferral_target()

    def submit_once():
        user = _student_context(student_id, student_no=student_no, real_name="注册并发学生")
        return gaps.registration_defer_apply_my(
            user,
            batch_id,
            "网络重试下仍必须只保留一条暂缓注册申请",
        )

    succeeded, failed = _race(submit_once)
    assert len(succeeded) == 1, (succeeded, failed)
    assert len(failed) == 1 and failed[0][0:2] == (409, "DATA_CONFLICT"), failed

    with _session() as db:
        pending = db.scalars(select(AaRegistrationDeferral).where(
            AaRegistrationDeferral.tenant_id == TID,
            AaRegistrationDeferral.batch_id == batch_id,
            AaRegistrationDeferral.student_id == student_id,
            AaRegistrationDeferral.status == "PENDING",
            AaRegistrationDeferral.is_deleted.is_(False),
        )).all()
        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_REG_DEFERRAL",
            AffairsAuditTrail.action == "SELF_APPLY",
        )).all()
    assert len(pending) == 1
    assert len(audits) == 1


def _seed_recheck_target():
    from app.models import AcademicGrade, AcademicStudent, StudentProfile

    with _session() as db:
        student = StudentProfile(
            tenant_id=TID,
            student_no="CONCURRENT_RC_01",
            real_name="复查并发学生",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        academic = AcademicStudent(
            tenant_id=TID,
            student_id=student.id,
            student_no=student.student_no,
            name=student.real_name,
        )
        db.add(academic)
        db.flush()
        grade = AcademicGrade(
            tenant_id=TID,
            acad_student_id=academic.id,
            course_id=991001,
            course_code="CONCURRENT_RC",
            course_name="并发复查课程",
            term="2026-2027-1",
            credit_value=2,
            score=59,
            pass_status="FAILED",
            source="PUBLISH",
            record_status="ACTIVE",
        )
        db.add(grade)
        db.flush()
        result = int(student.id), str(student.student_no), int(grade.id)
        db.commit()
        return result


def test_concurrent_student_grade_rechecks_create_one_pending_record(db_mode):
    """两次同一成绩复查提交必须收敛到一条正式在途记录和一条审计。"""
    del db_mode
    from app.models import AaGradeRecheck, AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_grade_recheck_service as recheck

    student_id, student_no, grade_id = _seed_recheck_target()

    def submit_once():
        _student_context(student_id, student_no=student_no, real_name="复查并发学生")
        return recheck.submit({}, {
            "acadGradeId": str(grade_id),
            "reason": "并发网络重试不能重复创建成绩复查申请",
        })

    succeeded, failed = _race(submit_once)
    assert len(succeeded) == 1, (succeeded, failed)
    assert len(failed) == 1 and failed[0][0:2] == (409, "DATA_CONFLICT"), failed

    with _session() as db:
        pending = db.scalars(select(AaGradeRecheck).where(
            AaGradeRecheck.tenant_id == TID,
            AaGradeRecheck.acad_grade_id == grade_id,
            AaGradeRecheck.status == "SUBMITTED",
            AaGradeRecheck.is_deleted.is_(False),
        )).all()
        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_type == "AA_GRADE_RECHECK",
            AffairsAuditTrail.action == "RECHECK_SUBMIT",
        )).all()
    assert len(pending) == 1
    assert len(audits) == 1
