#!/usr/bin/env python3
"""Deterministic school-scale capacity fixture for the internship domain.

Safety contract:
- dedicated isolated tenant only;
- MySQL only for real seeding/cleanup;
- refuses production-like environments;
- deterministic IDs/content; rerun requires --replace;
- --dry-run computes the full row plan without touching the database.

This is test/capacity infrastructure, never a production data repair tool.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import delete, func, insert, select

from app.core.config import settings
from app.db.session import get_engine, get_sessionmaker
from app.models import (
    AttendanceException,
    InternshipBatch,
    InternshipBatchPlan,
    InternshipCheckin,
    InternshipGuidance,
    InternshipPlanTaskProgress,
    InternshipProcessReport,
    InternshipRecord,
    RiskRecord,
    StudentProfile,
    Tenant,
    WeeklyReport,
)

DEFAULT_TENANT_ID = 8_130_000_000_000_001
DEFAULT_TENANT_CODE = "capacity-internship-school"
ID_BASE = 8_131_000_000_000_000
FIXTURE_NOW = datetime(2026, 8, 13, 8, 0, 0)
CURRENT_BATCH_START = datetime(2026, 3, 1, 0, 0, 0)
CHUNK_SIZE = 2_000


def _positive(name: str, value: int, *, allow_zero: bool = False) -> int:
    floor = 0 if allow_zero else 1
    if value < floor:
        raise SystemExit(f"{name} must be >= {floor}")
    return value


def _ratio(value: float) -> float:
    if not 0 <= value <= 1:
        raise SystemExit("risk-ratio must be between 0 and 1")
    return value


def _student_no(index: int) -> str:
    return f"CAP-INT-{index:05d}"


def _student_id(index: int) -> int:
    return ID_BASE + 100_000 + index


def _batch_id(index: int) -> int:
    return ID_BASE + 200_000 + index


def _record_id(batch_index: int, student_index: int, students: int) -> int:
    return ID_BASE + 1_000_000 + batch_index * (students + 1) + student_index


def _common(row_id: int, tenant_id: int) -> dict:
    return {
        "id": row_id,
        "tenant_id": tenant_id,
        "created_at": FIXTURE_NOW,
        "updated_at": FIXTURE_NOW,
        "created_by": None,
        "updated_by": None,
        "is_deleted": False,
        "version": 0,
    }


def build_expected(args: argparse.Namespace) -> dict[str, int]:
    months = max(1, math.ceil(args.days / 30))
    risks = int(round(args.active_interns * args.risk_ratio))
    history_records = args.active_interns * args.history_batches
    return {
        "tenants": 1,
        "students": args.students,
        "batches": args.history_batches + 1,
        "internshipRecords": args.active_interns + history_records,
        "checkins": args.active_interns * args.days,
        "weeklyReports": args.active_interns * args.weeks,
        "guidances": args.active_interns * args.guidance_per_student,
        "batchPlans": 1,
        "planTaskProgress": args.active_interns * args.tasks,
        "processReports": args.active_interns * months,
        "risks": risks,
        "attendanceExceptions": risks,
    }


def build_manifest(args: argparse.Namespace, *, seeded: bool, actual: dict[str, int] | None = None,
                   duration_seconds: float | None = None) -> dict:
    expected = build_expected(args)
    current_batch_id = _batch_id(args.history_batches + 1)
    return {
        "fixture": "internship-school-scale-v1",
        "seeded": seeded,
        "tenantId": args.tenant_id,
        "tenantCode": args.tenant_code,
        "studentNoPattern": "CAP-INT-{index:05d}",
        "studentCount": args.students,
        "activeInternCount": args.active_interns,
        "currentBatchId": current_batch_id,
        "currentBatchNo": "CAP-INT-CURRENT",
        "historyBatches": args.history_batches,
        "days": args.days,
        "weeks": args.weeks,
        "tasks": args.tasks,
        "guidancePerStudent": args.guidance_per_student,
        "riskRatio": args.risk_ratio,
        "expected": expected,
        "actual": actual or {},
        "seedDurationSeconds": None if duration_seconds is None else round(duration_seconds, 3),
    }


def _assert_safe_environment() -> None:
    markers = {
        str(os.getenv("APP_ENV") or "").strip().lower(),
        str(os.getenv("DEPLOYMENT_MODE") or "").strip().lower(),
    }
    if settings.is_prod or markers.intersection({"prod", "production"}):
        raise SystemExit("internship capacity fixture refuses production environments")
    engine = get_engine()
    if engine.dialect.name != "mysql":
        raise SystemExit(f"internship capacity fixture requires MySQL, got {engine.dialect.name}")


def _chunks(rows: Iterable[dict], size: int = CHUNK_SIZE) -> Iterator[list[dict]]:
    chunk: list[dict] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _bulk(db, model, rows: Iterable[dict]) -> int:
    count = 0
    for chunk in _chunks(rows):
        db.execute(insert(model), chunk)
        count += len(chunk)
        db.commit()
    return count


def _student_rows(args: argparse.Namespace) -> Iterator[dict]:
    for index in range(1, args.students + 1):
        active = index <= args.active_interns
        yield {
            **_common(_student_id(index), args.tenant_id),
            "student_no": _student_no(index),
            "real_name": f"容量实习学生{index:05d}",
            "grade": "2023" if active else "2024",
            "current_stage": "INTERN" if active else "ENROLLED",
            "student_status": "NORMAL",
            "status": "ACTIVE",
        }


def _batch_rows(args: argparse.Namespace) -> Iterator[dict]:
    for h in range(args.history_batches, 0, -1):
        index = args.history_batches - h + 1
        start = CURRENT_BATCH_START - timedelta(days=365 * h)
        yield {
            **_common(_batch_id(index), args.tenant_id),
            "batch_name": f"容量历史实习批次{index}",
            "batch_no": f"CAP-INT-H{index:02d}",
            "academic_year": f"{start.year}-{start.year + 1}",
            "term": "2",
            "start_date": start,
            "end_date": start + timedelta(days=args.days - 1),
            "planned_count": args.active_interns,
            "status": "ARCHIVED",
            "archive_status": "ARCHIVED",
            "archived_at": start + timedelta(days=args.days),
            "rules_version": 1,
        }
    current_index = args.history_batches + 1
    yield {
        **_common(_batch_id(current_index), args.tenant_id),
        "batch_name": "容量当前实习批次",
        "batch_no": "CAP-INT-CURRENT",
        "academic_year": "2025-2026",
        "term": "2",
        "start_date": CURRENT_BATCH_START,
        "end_date": CURRENT_BATCH_START + timedelta(days=args.days - 1),
        "planned_count": args.active_interns,
        "status": "RUNNING",
        "archive_status": "NOT_ARCHIVED",
        "rules_version": 1,
        "rules_config": {
            "weeklyReport": {"requiredWeeks": args.weeks},
            "guidance": {"requiredCount": args.guidance_per_student},
        },
    }


def _record_rows(args: argparse.Namespace) -> Iterator[dict]:
    batch_count = args.history_batches + 1
    for batch_index in range(1, batch_count + 1):
        current = batch_index == batch_count
        batch_id = _batch_id(batch_index)
        for student_index in range(1, args.active_interns + 1):
            yield {
                **_common(_record_id(batch_index, student_index, args.students), args.tenant_id),
                "student_id": _student_id(student_index),
                "batch_id": batch_id,
                "enterprise_name": f"容量合作企业{((student_index - 1) % 200) + 1:03d}",
                "position_name": f"实习岗位{((student_index - 1) % 80) + 1:02d}",
                "advisor_name": f"容量导师{((student_index - 1) % 100) + 1:03d}",
                "eligibility_status": "QUALIFIED",
                "destination_type": "ASSIGNED",
                "status": "ONBOARD" if current else "ARCHIVED",
                "risk_level": "NONE",
                "intern_start_date": CURRENT_BATCH_START if current else CURRENT_BATCH_START - timedelta(days=365 * (batch_count - batch_index)),
                "intern_end_date": (CURRENT_BATCH_START + timedelta(days=args.days - 1)) if current else None,
                "insurance_info": "VERIFIED",
                "agreement_info": "EFFECTIVE",
            }


def _current_record_id(args: argparse.Namespace, student_index: int) -> int:
    return _record_id(args.history_batches + 1, student_index, args.students)


def _checkin_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 10_000_000
    for student_index in range(1, args.active_interns + 1):
        internship_id = _current_record_id(args, student_index)
        for day in range(args.days):
            row += 1
            date = CURRENT_BATCH_START + timedelta(days=day)
            yield {
                **_common(row, args.tenant_id),
                "internship_id": internship_id,
                "checkin_date": date.strftime("%Y-%m-%d"),
                "checkin_at": date.replace(hour=8, minute=(student_index + day) % 55),
                "lat": 28.2278,
                "lng": 112.9388,
                "address": "容量测试园区",
                "result": "OUT_OF_RANGE" if (student_index + day) % 97 == 0 else "NORMAL",
                "gps_accuracy": 12.0,
                "device_risk_flag": "normal",
            }


def _weekly_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 20_000_000
    for student_index in range(1, args.active_interns + 1):
        internship_id = _current_record_id(args, student_index)
        for week in range(1, args.weeks + 1):
            row += 1
            pending = (student_index + week) % 5 == 0
            submitted = CURRENT_BATCH_START + timedelta(days=week * 7 - 1, hours=18)
            yield {
                **_common(row, args.tenant_id),
                "internship_id": internship_id,
                "week_number": week,
                "work_content": f"第{week}周容量实习工作内容，完成岗位任务与过程记录。",
                "harvest_content": "掌握岗位流程、安全规范与协作方法。",
                "plan_content": "下周继续完成计划任务并复盘问题。",
                "word_count": 120,
                "report_version": 1,
                "submitted_at": submitted,
                "status": "PENDING_REVIEW" if pending else "APPROVED",
                "review_action": None if pending else "APPROVE",
                "reviewed_by_name": None if pending else "容量导师",
                "reviewed_at": None if pending else submitted + timedelta(days=1),
            }


def _guidance_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 30_000_000
    for student_index in range(1, args.active_interns + 1):
        internship_id = _current_record_id(args, student_index)
        for seq in range(1, args.guidance_per_student + 1):
            row += 1
            yield {
                **_common(row, args.tenant_id),
                "internship_id": internship_id,
                "student_id": _student_id(student_index),
                "advisor_name": f"容量导师{((student_index - 1) % 100) + 1:03d}",
                "method": "ONLINE" if seq % 3 else "ONSITE",
                "topic": f"第{seq}次岗位指导",
                "content": "核对实习进度、岗位安全、任务质量和下一步计划。",
                "suggestion": "按计划完成任务并及时记录异常。",
                "next_follow_date": (CURRENT_BATCH_START + timedelta(days=seq * 14)).strftime("%Y-%m-%d"),
                "to_risk": False,
                "notify_counselor": False,
                "status": "NORMAL",
            }


def _plan_rows(args: argparse.Namespace) -> Iterator[dict]:
    plan_id = ID_BASE + 40_000_001
    current_batch = _batch_id(args.history_batches + 1)
    tasks_json = [
        {"sortOrder": i, "name": f"容量岗位任务{i:02d}", "required": True}
        for i in range(1, args.tasks + 1)
    ]
    yield {
        **_common(plan_id, args.tenant_id),
        "batch_id": current_batch,
        "title": "容量实习计划",
        "objectives": "验证学校规模下实习任务读取与聚合。",
        "content": "容量测试专用计划，不属于生产业务数据。",
        "tasks_json": tasks_json,
        "status": "PUBLISHED",
        "published_at": FIXTURE_NOW,
        "published_by_name": "capacity-fixture",
    }


def _task_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 41_000_000
    plan_id = ID_BASE + 40_000_001
    for student_index in range(1, args.active_interns + 1):
        internship_id = _current_record_id(args, student_index)
        for task in range(1, args.tasks + 1):
            row += 1
            status = "SUBMITTED" if (student_index + task) % 4 == 0 else "APPROVED"
            yield {
                **_common(row, args.tenant_id),
                "plan_id": plan_id,
                "internship_id": internship_id,
                "student_id": _student_id(student_index),
                "task_sort_order": task,
                "task_name": f"容量岗位任务{task:02d}",
                "status": status,
                "student_note": "容量测试任务完成记录",
                "submitted_at": CURRENT_BATCH_START + timedelta(days=task * 10),
                "reviewed_by_name": None if status == "SUBMITTED" else "容量导师",
                "reviewed_at": None if status == "SUBMITTED" else CURRENT_BATCH_START + timedelta(days=task * 10 + 1),
            }


def _process_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 50_000_000
    months = max(1, math.ceil(args.days / 30))
    for student_index in range(1, args.active_interns + 1):
        internship_id = _current_record_id(args, student_index)
        for month in range(months):
            row += 1
            period_date = CURRENT_BATCH_START + timedelta(days=month * 30)
            pending = (student_index + month) % 6 == 0
            yield {
                **_common(row, args.tenant_id),
                "internship_id": internship_id,
                "report_type": "MONTHLY",
                "period_key": period_date.strftime("%Y-%m"),
                "content": "容量测试月度过程报告，记录岗位任务、问题、收获与下月计划。",
                "word_count": 180,
                "submitted_at": period_date + timedelta(days=25),
                "status": "PENDING_REVIEW" if pending else "APPROVED",
                "review_action": None if pending else "APPROVE",
                "reviewed_by_name": None if pending else "容量导师",
            }


def _risk_student_indexes(args: argparse.Namespace) -> list[int]:
    count = build_expected(args)["risks"]
    if count <= 0:
        return []
    return [min(args.active_interns, 1 + (i * args.active_interns // count)) for i in range(count)]


def _risk_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 60_000_000
    for seq, student_index in enumerate(_risk_student_indexes(args), start=1):
        row += 1
        internship_id = _current_record_id(args, student_index)
        yield {
            **_common(row, args.tenant_id),
            "internship_id": internship_id,
            "risk_code": "INT-CAPACITY",
            "risk_title": "容量测试风险样本",
            "risk_level": "HIGH" if seq % 5 == 0 else "MEDIUM",
            "source_module": "system",
            "source_type": "CAPACITY_FIXTURE",
            "source_id": internship_id,
            "source_version": 0,
            "owner_name": "容量导师",
            "deadline_at": FIXTURE_NOW + timedelta(days=7),
            "status": "PENDING_HANDLE" if seq % 3 else "PROCESSING",
        }


def _exception_rows(args: argparse.Namespace) -> Iterator[dict]:
    row = ID_BASE + 61_000_000
    for seq, student_index in enumerate(_risk_student_indexes(args), start=1):
        row += 1
        internship_id = _current_record_id(args, student_index)
        yield {
            **_common(row, args.tenant_id),
            "internship_id": internship_id,
            "exception_type": "OUT_OF_RANGE",
            "exception_date": CURRENT_BATCH_START + timedelta(days=(seq * 13) % max(1, args.days)),
            "distance_km": 2.5,
            "gps_accuracy": 20.0,
            "device_risk_flag": "normal",
            "address": "容量测试异常位置",
            "streak_days": 1,
            "status": "PENDING_HANDLE",
        }


SEEDED_MODELS = [
    AttendanceException,
    RiskRecord,
    InternshipPlanTaskProgress,
    InternshipProcessReport,
    InternshipBatchPlan,
    InternshipGuidance,
    WeeklyReport,
    InternshipCheckin,
    InternshipRecord,
    InternshipBatch,
    StudentProfile,
]

COUNT_MODELS = {
    "students": StudentProfile,
    "batches": InternshipBatch,
    "internshipRecords": InternshipRecord,
    "checkins": InternshipCheckin,
    "weeklyReports": WeeklyReport,
    "guidances": InternshipGuidance,
    "batchPlans": InternshipBatchPlan,
    "planTaskProgress": InternshipPlanTaskProgress,
    "processReports": InternshipProcessReport,
    "risks": RiskRecord,
    "attendanceExceptions": AttendanceException,
}


def cleanup(db, args: argparse.Namespace) -> None:
    for model in SEEDED_MODELS:
        db.execute(delete(model).where(model.tenant_id == args.tenant_id))
        db.commit()
    db.execute(delete(Tenant).where(Tenant.id == args.tenant_id))
    db.commit()


def _tenant_exists(db, tenant_id: int) -> bool:
    return db.scalar(select(func.count()).select_from(Tenant).where(Tenant.id == tenant_id)) > 0


def seed(args: argparse.Namespace) -> dict:
    _assert_safe_environment()
    started = time.perf_counter()
    db = get_sessionmaker()()
    try:
        if _tenant_exists(db, args.tenant_id):
            if not args.replace:
                raise SystemExit("capacity tenant already exists; use --replace or --cleanup")
            cleanup(db, args)

        db.execute(
            insert(Tenant),
            [{
                "id": args.tenant_id,
                "tenant_code": args.tenant_code,
                "school_name": "岗位实习容量测试学校",
                "short_name": "容量学校",
                "deploy_mode": "SAAS",
                "db_mode": "SHARED",
                "status": "ACTIVE",
                "created_at": FIXTURE_NOW,
                "updated_at": FIXTURE_NOW,
                "is_deleted": False,
                "version": 0,
            }],
        )
        db.commit()

        _bulk(db, StudentProfile, _student_rows(args))
        _bulk(db, InternshipBatch, _batch_rows(args))
        _bulk(db, InternshipRecord, _record_rows(args))
        _bulk(db, InternshipCheckin, _checkin_rows(args))
        _bulk(db, WeeklyReport, _weekly_rows(args))
        _bulk(db, InternshipGuidance, _guidance_rows(args))
        _bulk(db, InternshipBatchPlan, _plan_rows(args))
        _bulk(db, InternshipPlanTaskProgress, _task_rows(args))
        _bulk(db, InternshipProcessReport, _process_rows(args))
        _bulk(db, RiskRecord, _risk_rows(args))
        _bulk(db, AttendanceException, _exception_rows(args))

        actual = {"tenants": 1}
        for key, model in COUNT_MODELS.items():
            actual[key] = int(
                db.scalar(select(func.count()).select_from(model).where(model.tenant_id == args.tenant_id)) or 0
            )
        expected = build_expected(args)
        if actual != expected:
            raise SystemExit(f"seed row count mismatch: expected={expected} actual={actual}")
        duration = time.perf_counter() - started
        return build_manifest(args, seeded=True, actual=actual, duration_seconds=duration)
    finally:
        db.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed deterministic internship school-scale capacity data")
    parser.add_argument("--students", type=int, default=20_000)
    parser.add_argument("--active-interns", type=int, default=8_000)
    parser.add_argument("--history-batches", type=int, default=5)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--weeks", type=int, default=26)
    parser.add_argument("--tasks", type=int, default=10)
    parser.add_argument("--guidance-per-student", type=int, default=12)
    parser.add_argument("--risk-ratio", type=float, default=0.03)
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_TENANT_ID)
    parser.add_argument("--tenant-code", default=DEFAULT_TENANT_CODE)
    parser.add_argument("--manifest", type=Path, default=ROOT / "performance/results/internship-fixture.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args(argv)

    args.students = _positive("students", args.students)
    args.active_interns = _positive("active-interns", args.active_interns)
    args.history_batches = _positive("history-batches", args.history_batches, allow_zero=True)
    args.days = _positive("days", args.days)
    args.weeks = _positive("weeks", args.weeks)
    args.tasks = _positive("tasks", args.tasks)
    args.guidance_per_student = _positive("guidance-per-student", args.guidance_per_student)
    args.risk_ratio = _ratio(args.risk_ratio)
    if args.active_interns > args.students:
        raise SystemExit("active-interns must be <= students")
    if args.cleanup and (args.dry_run or args.replace):
        raise SystemExit("--cleanup cannot be combined with --dry-run/--replace")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        manifest = build_manifest(args, seeded=False)
    elif args.cleanup:
        _assert_safe_environment()
        db = get_sessionmaker()()
        try:
            cleanup(db, args)
        finally:
            db.close()
        manifest = build_manifest(args, seeded=False, actual={})
        manifest["cleaned"] = True
    else:
        manifest = seed(args)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "fixture": manifest["fixture"],
        "seeded": manifest["seeded"],
        "tenantId": manifest["tenantId"],
        "currentBatchId": manifest["currentBatchId"],
        "expected": manifest["expected"],
        "actual": manifest["actual"],
        "seedDurationSeconds": manifest["seedDurationSeconds"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
