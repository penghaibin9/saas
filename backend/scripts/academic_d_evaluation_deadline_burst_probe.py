"""Academic D-W3 one-shot school-wide evaluation deadline-burst evidence.

This wrapper reuses the canonical MySQL contention helpers and adds the V2.1-required
school-wide deadline burst without creating another runtime implementation. Setup follows
the same formal chain: term -> teaching task -> LOCKED TeachingRoster -> evaluation
create/generate/publish/open. Only submission latency is measured.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sqlalchemy import func, select, text

from scripts import academic_d_evaluation_concurrency_probe as probe


def _verify_task_from_answer_facts(eval_task_id: int) -> dict:
    """OPEN-window submittedCount is the active answer-fact count, not the deferred task projection."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationRecord, AaEvaluationTask

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(probe.TID), "tenantCode": "academic-d-eval-bench"})
    try:
        task = db.get(AaEvaluationTask, int(eval_task_id))
        record_count = int(db.scalar(select(func.count()).select_from(AaEvaluationRecord).where(
            AaEvaluationRecord.tenant_id == probe.TID,
            AaEvaluationRecord.task_id == int(eval_task_id),
            AaEvaluationRecord.evaluator_type == "STUDENT",
            AaEvaluationRecord.is_deleted.is_(False),
        )) or 0)
        return {
            "recordCount": record_count,
            "submittedCount": record_count,
            "storedProjectionCount": int(task.submitted_count or 0) if task else None,
        }
    finally:
        db.close()
        set_tenant(None)


def _reset_statement_digests() -> None:
    """Reset MySQL digest counters after fixture setup so profiling focuses on D-W3 scenarios."""
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        db.execute(text("TRUNCATE TABLE performance_schema.events_statements_summary_by_digest"))
        db.commit()
    finally:
        db.close()


def _statement_digest_evidence(limit: int = 20) -> list[dict]:
    """Return normalized, parameter-free MySQL statement digests ranked by total DB time."""
    from app.db.session import get_sessionmaker

    limit = max(1, min(int(limit), 50))
    db = get_sessionmaker()()
    try:
        rows = db.execute(text(
            "SELECT DIGEST_TEXT, COUNT_STAR, SUM_TIMER_WAIT, AVG_TIMER_WAIT, MAX_TIMER_WAIT "
            "FROM performance_schema.events_statements_summary_by_digest "
            "WHERE SCHEMA_NAME = DATABASE() AND DIGEST_TEXT IS NOT NULL "
            f"ORDER BY SUM_TIMER_WAIT DESC LIMIT {limit}"
        )).all()
        output = []
        for digest_text, count_star, sum_wait, avg_wait, max_wait in rows:
            output.append({
                "digest": " ".join(str(digest_text or "").split())[:1200],
                "count": int(count_star or 0),
                # Performance Schema statement timers are picoseconds; 1 ms = 1e9 ps.
                "totalMs": round(float(sum_wait or 0) / 1_000_000_000.0, 2),
                "avgMs": round(float(avg_wait or 0) / 1_000_000_000.0, 3),
                "maxMs": round(float(max_wait or 0) / 1_000_000_000.0, 2),
            })
        return output
    finally:
        db.close()


def _run_deadline_burst(term_id: int, teaching_task_ids: list[int], student_ids: list[int]) -> dict:
    """Exercise 200 simultaneous submissions spread across 20 formal evaluation tasks."""
    selected_tasks = teaching_task_ids[:20]
    if len(selected_tasks) != 20 or len(student_ids) < 200:
        raise RuntimeError("school-wide deadline burst requires 20 teaching tasks and 200 students")

    _batch_id, eval_task_ids = probe._new_open_eval_tasks(
        term_id,
        selected_tasks,
        "school-wide-deadline-20x10",
    )
    submissions: list[tuple[int, int]] = []
    per_task = 10
    for index, eval_task_id in enumerate(eval_task_ids):
        start = index * per_task
        for student_id in student_ids[start:start + per_task]:
            submissions.append((int(eval_task_id), int(student_id)))

    before = probe._lock_snapshot()
    barrier = threading.Barrier(len(submissions))
    started = time.perf_counter()
    with ThreadPoolExecutor(
        max_workers=len(submissions),
        thread_name_prefix="dw3-deadline-burst",
    ) as pool:
        futures = [
            pool.submit(probe._submit, task_id, student_id, barrier)
            for task_id, student_id in submissions
        ]
        results = [future.result() for future in as_completed(futures)]
    total_ms = round((time.perf_counter() - started) * 1000, 2)
    after = probe._lock_snapshot()

    verifies = [probe._verify_task(task_id) for task_id in eval_task_ids]
    successes = [row for row in results if row["ok"]]
    failures = [row for row in results if not row["ok"]]
    latencies = [row["elapsedMs"] for row in successes]
    record_count = sum(int(row["recordCount"] or 0) for row in verifies)
    submitted_count = sum(int(row["submittedCount"] or 0) for row in verifies)
    duplicate_rows = max(0, record_count - len(submissions))

    return {
        "scenario": "school-wide-deadline-20x10",
        "concurrency": len(submissions),
        "taskCount": len(eval_task_ids),
        "studentsPerTask": per_task,
        "totalElapsedMs": total_ms,
        "throughputPerSecond": round(len(successes) / max(total_ms / 1000.0, 0.001), 2),
        "successCount": len(successes),
        "failureCount": len(failures),
        "p50Ms": probe._percentile(latencies, 0.50),
        "p95Ms": probe._percentile(latencies, 0.95),
        "p99Ms": probe._percentile(latencies, 0.99),
        "mysqlLockDelta": probe._status_delta(before, after),
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


def main() -> int:
    import argparse
    from app.db.session import get_sessionmaker

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="test-results/academic-d-evaluation-concurrency.json")
    args = parser.parse_args()

    setup = get_sessionmaker()()
    try:
        setup.execute(text("SET GLOBAL max_connections = 400"))
        setup.commit()
    finally:
        setup.close()

    # Reuse the original timing scenarios but verify OPEN-window counts from answer facts.
    probe._verify_task = _verify_task_from_answer_facts

    seeded = probe._seed_formal_teaching_context(student_count=200, task_count=20)
    term_id = seeded["termId"]
    students = seeded["studentIds"]
    tasks = seeded["teachingTaskIds"]
    _reset_statement_digests()
    scenarios = [
        probe._run_same_task("same-task-50", 50, term_id, tasks[0], students),
        probe._run_same_task("same-task-100", 100, term_id, tasks[0], students),
        probe._run_same_task("same-task-200", 200, term_id, tasks[0], students),
        probe._run_mixed(term_id, tasks, students),
        _run_deadline_burst(term_id, tasks, students),
        probe._run_duplicate_race(term_id, tasks[0], students[0]),
    ]
    report = {
        "schema": "academic-d-evaluation-concurrency/v4",
        "tenantId": str(probe.TID),
        "database": "mysql8",
        "setupAuthority": "public evaluation create/generate/publish/open + formal LOCKED TeachingRoster",
        "studentLockProtocol": (
            "READ COMMITTED transaction + evaluation batch SHARE + current TeachingClass SHARE + "
            "current student member UPDATE; answer facts are live submitted-count authority"
        ),
        "closedBatchProjection": "AaEvaluationTask.submitted_count reconciled under close/score batch UPDATE lock",
        "roleTaskLockProtocol": "EvaluationTask UPDATE for SELF/PEER/SUPERVISOR",
        "anonymousTokenStorage": "answers_json HMAC token LIKE lookup",
        "statementDigests": _statement_digest_evidence(),
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
