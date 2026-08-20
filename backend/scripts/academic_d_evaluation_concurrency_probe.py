"""Academic D-W3 one-shot MySQL evaluation submission concurrency probe.

Evidence tooling only. It exercises the current public evaluation service without changing
its task-row FOR UPDATE, anonymous HMAC token, roster authority, or submitted_count
semantics. Setup uses the formal production chain: term -> teaching task -> LOCKED roster ->
evaluation create -> generate tasks -> publish -> open. Timings include submission only.
"""
from __future__ import annotations

import argparse
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import func, select, text

TID = 1000000000000000001


def _admin_user() -> dict:
    return {
        "userId": "dw3-benchmark-admin",
        "loginName": "dw3_benchmark_admin",
        "realName": "D-W3评教并发压测管理员",
        "userType": "ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TID),
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(ordered[position], 2)


def _mysql_lock_status(db) -> dict[str, int]:
    names = (
        "Innodb_row_lock_waits",
        "Innodb_row_lock_time",
        "Innodb_row_lock_time_max",
        "Innodb_deadlocks",
    )
    quoted = ",".join(f"'{name}'" for name in names)
    rows = db.execute(text(f"SHOW GLOBAL STATUS WHERE Variable_name IN ({quoted})")).all()
    result = {name: 0 for name in names}
    for key, value in rows:
        try:
            result[str(key)] = int(value or 0)
        except (TypeError, ValueError):
            result[str(key)] = 0
    return result


def _status_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: max(0, int(after.get(key, 0)) - int(before.get(key, 0))) for key in before}


def _seed_formal_teaching_context(student_count: int, task_count: int) -> dict:
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        Major,
        SchoolClass,
        StudentProfile,
    )
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_service as tc_service

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-d-eval-bench"})
    set_current_user(_admin_user())
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2035-2036",
            term_no=1,
            term_name="D-W3评教并发证据学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        db.add(term)
        db.flush()
        college = College(
            tenant_id=TID,
            college_name="D-W3评教并发学院",
            code="DW3-EVAL-CONCURRENCY-COLLEGE",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name="D-W3评教并发专业",
            status="ACTIVE",
        )
        db.add(major)
        db.flush()
        klass = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name="D-W3评教并发教学行政班",
            grade="2035",
            status="ACTIVE",
        )
        db.add(klass)
        db.flush()

        students = []
        for index in range(student_count):
            student = StudentProfile(
                tenant_id=TID,
                student_no=f"DW3E{index + 1:04d}",
                real_name=f"D-W3评教并发学生{index + 1:04d}",
                college_id=college.id,
                major_id=major.id,
                class_id=klass.id,
                grade="2035",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            students.append(student)
        db.flush()

        teaching_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="D-W3评教并发教学任务批次",
            college_id=college.id,
            status="APPROVED",
        )
        db.add(teaching_batch)
        db.flush()

        teaching_tasks = []
        for index in range(task_count):
            course = AaCourse(
                tenant_id=TID,
                course_code=f"DW3-EVAL-{index + 1:02d}",
                course_name=f"D-W3评教并发课程{index + 1}",
                credit=2,
                status="ENABLED",
            )
            db.add(course)
            db.flush()
            task = AaTeachingTask(
                tenant_id=TID,
                batch_id=teaching_batch.id,
                course_id=course.id,
                course_code=course.course_code,
                course_name=course.course_name,
                class_id=klass.id,
                teaching_class_name=f"{klass.class_name}-{index + 1}",
                teacher_key=f"dw3_eval_teacher_{index + 1}",
                teacher_name=f"D-W3评教教师{index + 1}",
                status="READY",
                weekly_hours=2,
                total_hours=36,
                start_week=1,
                end_week=18,
                expected_students=student_count,
            )
            db.add(task)
            db.flush()
            teaching_class = tc_service.ensure_teaching_class_for_task(
                db, int(task.id), initialize_admin_roster=True
            )
            db.flush()
            if teaching_class.roster_status != "LOCKED" or not teaching_class.current_roster_version_id:
                raise RuntimeError(f"教学任务 {task.id} 未形成正式 LOCKED roster")
            teaching_tasks.append(task)
        db.commit()
        return {
            "termId": int(term.id),
            "studentIds": [int(student.id) for student in students],
            "teachingTaskIds": [int(task.id) for task in teaching_tasks],
        }
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def _new_open_eval_tasks(term_id: int, teaching_task_ids: list[int], label: str) -> tuple[int, list[int]]:
    """Create/open evaluation tasks only through the canonical public evaluation service."""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationTask
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    admin = _admin_user()
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-d-eval-bench"})
    set_current_user(admin)
    try:
        created = service.create_batch(
            admin,
            SimpleNamespace(
                batchName=f"D-W3并发-{label}",
                termId=str(term_id),
                anonymous=True,
                scope=None,
                template={"benchmark": "D-W3", "label": label},
            ),
        )
        batch_id = int(created["batchId"])
        generated = service.generate_tasks(
            admin,
            batch_id,
            [str(value) for value in teaching_task_ids],
            "STUDENT",
        )
        if int(generated.get("taskCount") or 0) != len(teaching_task_ids):
            raise RuntimeError(f"评教任务生成数量异常: {generated}")
        service.publish_batch(admin, batch_id)
        opened = service.open_batch(admin, batch_id)
        if opened.get("status") != "OPEN":
            raise RuntimeError(f"评教批次未进入 OPEN: {opened}")

        db = get_sessionmaker()()
        try:
            rows = db.query(AaEvaluationTask).filter(
                AaEvaluationTask.tenant_id == TID,
                AaEvaluationTask.batch_id == batch_id,
                AaEvaluationTask.evaluator_type == "STUDENT",
                AaEvaluationTask.teaching_task_id.in_(teaching_task_ids),
                AaEvaluationTask.is_deleted.is_(False),
            ).order_by(AaEvaluationTask.teaching_task_id).all()
            by_teaching = {int(row.teaching_task_id): int(row.id) for row in rows}
            return batch_id, [by_teaching[int(value)] for value in teaching_task_ids]
        finally:
            db.close()
    finally:
        set_current_user(None)
        set_tenant(None)


def _submit(eval_task_id: int, student_id: int, barrier: threading.Barrier | None = None) -> dict:
    from app.core.context import set_current_user, set_tenant
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as service

    if barrier is not None:
        barrier.wait()
    user = {
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
        "studentId": str(student_id),
        "tenantId": str(TID),
        "userId": f"dw3-bench-student-{student_id}",
        "loginName": f"dw3_bench_student_{student_id}",
    }
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-d-eval-bench"})
    set_current_user(user)
    started = time.perf_counter()
    try:
        payload = service.submit_evaluation(
            user,
            int(eval_task_id),
            {"教学质量": 5},
            90,
            "D-W3 concurrency evidence",
        )
        return {
            "ok": True,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            "payload": payload,
        }
    except Exception as exc:
        return {
            "ok": False,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            "errorType": exc.__class__.__name__,
            "error": str(exc),
        }
    finally:
        set_current_user(None)
        set_tenant(None)


def _verify_task(eval_task_id: int) -> dict:
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationRecord, AaEvaluationTask

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-d-eval-bench"})
    try:
        task = db.get(AaEvaluationTask, int(eval_task_id))
        record_count = int(db.scalar(select(func.count()).select_from(AaEvaluationRecord).where(
            AaEvaluationRecord.tenant_id == TID,
            AaEvaluationRecord.task_id == int(eval_task_id),
            AaEvaluationRecord.evaluator_type == "STUDENT",
            AaEvaluationRecord.is_deleted.is_(False),
        )) or 0)
        return {
            "recordCount": record_count,
            "submittedCount": int(task.submitted_count or 0) if task else None,
        }
    finally:
        db.close()
        set_tenant(None)


def _lock_snapshot() -> dict[str, int]:
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        return _mysql_lock_status(db)
    finally:
        db.close()


def _run_same_task(label: str, concurrency: int, term_id: int, teaching_task_id: int,
                   student_ids: list[int]) -> dict:
    _batch_id, eval_tasks = _new_open_eval_tasks(term_id, [teaching_task_id], label)
    eval_task_id = eval_tasks[0]
    selected = student_ids[:concurrency]
    before = _lock_snapshot()
    barrier = threading.Barrier(len(selected))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix=f"dw3-{label}") as pool:
        futures = [pool.submit(_submit, eval_task_id, student_id, barrier) for student_id in selected]
        results = [future.result() for future in as_completed(futures)]
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    after = _lock_snapshot()
    verified = _verify_task(eval_task_id)
    successes = [row for row in results if row["ok"]]
    failures = [row for row in results if not row["ok"]]
    latencies = [row["elapsedMs"] for row in successes]
    duplicate_rows = max(0, verified["recordCount"] - len(selected))
    return {
        "scenario": label,
        "concurrency": concurrency,
        "totalElapsedMs": total_ms,
        "throughputPerSecond": round(len(successes) / max(total_ms / 1000.0, 0.001), 2),
        "successCount": len(successes),
        "failureCount": len(failures),
        "p50Ms": _percentile(latencies, 0.50),
        "p95Ms": _percentile(latencies, 0.95),
        "p99Ms": _percentile(latencies, 0.99),
        "mysqlLockDelta": _status_delta(before, after),
        "recordCount": verified["recordCount"],
        "submittedCount": verified["submittedCount"],
        "duplicateRows": duplicate_rows,
        "failures": failures[:20],
        "correct": (
            not failures
            and verified["recordCount"] == len(selected)
            and verified["submittedCount"] == len(selected)
            and duplicate_rows == 0
        ),
    }


def _run_mixed(term_id: int, teaching_task_ids: list[int], student_ids: list[int]) -> dict:
    _batch_id, eval_task_ids = _new_open_eval_tasks(term_id, teaching_task_ids[:4], "mixed-4x50")
    submissions = []
    per_task = 50
    for index, eval_task_id in enumerate(eval_task_ids):
        start = index * per_task
        for student_id in student_ids[start:start + per_task]:
            submissions.append((eval_task_id, student_id))
    before = _lock_snapshot()
    barrier = threading.Barrier(len(submissions))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(submissions), thread_name_prefix="dw3-mixed") as pool:
        futures = [pool.submit(_submit, task_id, student_id, barrier) for task_id, student_id in submissions]
        results = [future.result() for future in as_completed(futures)]
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    after = _lock_snapshot()
    verifies = [_verify_task(task_id) for task_id in eval_task_ids]
    successes = [row for row in results if row["ok"]]
    failures = [row for row in results if not row["ok"]]
    latencies = [row["elapsedMs"] for row in successes]
    record_count = sum(row["recordCount"] for row in verifies)
    submitted_count = sum(int(row["submittedCount"] or 0) for row in verifies)
    duplicate_rows = max(0, record_count - len(submissions))
    return {
        "scenario": "mixed-4x50",
        "concurrency": len(submissions),
        "taskCount": len(eval_task_ids),
        "totalElapsedMs": total_ms,
        "throughputPerSecond": round(len(successes) / max(total_ms / 1000.0, 0.001), 2),
        "successCount": len(successes),
        "failureCount": len(failures),
        "p50Ms": _percentile(latencies, 0.50),
        "p95Ms": _percentile(latencies, 0.95),
        "p99Ms": _percentile(latencies, 0.99),
        "mysqlLockDelta": _status_delta(before, after),
        "recordCount": record_count,
        "submittedCount": submitted_count,
        "duplicateRows": duplicate_rows,
        "perTask": verifies,
        "failures": failures[:20],
        "correct": (
            not failures
            and record_count == len(submissions)
            and submitted_count == len(submissions)
            and duplicate_rows == 0
        ),
    }


def _run_duplicate_race(term_id: int, teaching_task_id: int, student_id: int) -> dict:
    _batch_id, eval_tasks = _new_open_eval_tasks(term_id, [teaching_task_id], "duplicate-race")
    eval_task_id = eval_tasks[0]
    attempts = 20
    before = _lock_snapshot()
    barrier = threading.Barrier(attempts)
    with ThreadPoolExecutor(max_workers=attempts, thread_name_prefix="dw3-duplicate") as pool:
        futures = [pool.submit(_submit, eval_task_id, student_id, barrier) for _ in range(attempts)]
        results = [future.result() for future in as_completed(futures)]
    after = _lock_snapshot()
    verified = _verify_task(eval_task_id)
    successes = [row for row in results if row["ok"]]
    failures = [row for row in results if not row["ok"]]
    return {
        "scenario": "duplicate-race",
        "attempts": attempts,
        "successCount": len(successes),
        "rejectedCount": len(failures),
        "recordCount": verified["recordCount"],
        "submittedCount": verified["submittedCount"],
        "mysqlLockDelta": _status_delta(before, after),
        "failureTypes": sorted({row.get("errorType") for row in failures}),
        "correct": (
            len(successes) == 1
            and verified["recordCount"] == 1
            and verified["submittedCount"] == 1
            and len(failures) == attempts - 1
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="test-results/academic-d-evaluation-concurrency.json")
    args = parser.parse_args()

    from app.db.session import get_sessionmaker

    setup = get_sessionmaker()()
    try:
        setup.execute(text("SET GLOBAL max_connections = 400"))
        setup.commit()
    finally:
        setup.close()

    seeded = _seed_formal_teaching_context(student_count=200, task_count=4)
    term_id = seeded["termId"]
    students = seeded["studentIds"]
    tasks = seeded["teachingTaskIds"]
    scenarios = [
        _run_same_task("same-task-50", 50, term_id, tasks[0], students),
        _run_same_task("same-task-100", 100, term_id, tasks[0], students),
        _run_same_task("same-task-200", 200, term_id, tasks[0], students),
        _run_mixed(term_id, tasks, students),
        _run_duplicate_race(term_id, tasks[0], students[0]),
    ]
    report = {
        "schema": "academic-d-evaluation-concurrency/v1",
        "tenantId": str(TID),
        "database": "mysql8",
        "setupAuthority": "public evaluation create/generate/publish/open + formal LOCKED TeachingRoster",
        "taskLockProtocol": "AaEvaluationTask FOR UPDATE",
        "anonymousTokenStorage": "answers_json HMAC token LIKE lookup",
        "scenarios": scenarios,
        "correctnessPassed": all(row["correct"] for row in scenarios),
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["correctnessPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
