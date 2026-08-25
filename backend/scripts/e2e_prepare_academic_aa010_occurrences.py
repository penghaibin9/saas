"""Prepare AA-010 browser occurrence facts from the current published schedule truth.

This helper is audit-only. It does not create attendance sessions or mutate academic product
rows. It reads the authoritative C-W2 fixture, asks the production formal-occurrence consumer
to prove three executable occurrences, then writes those proven tuples back to the local E2E
state file for Playwright to consume through Teacher Mini real UI clicks.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import _mysql_env  # noqa: F401

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm
from app.modules.academic_affairs.services.academic_affairs_attendance_occurrence_consumer import (
    formal_schedule_patterns,
    resolve_formal_occurrence,
)

STATE_PATH = Path(__file__).resolve().parents[1] / "tmp" / "e2e_academic_c_teacher_today_state.local.json"


def assert_safe_target() -> None:
    env_name = str(os.getenv("APP_ENV") or "").lower()
    deploy_mode = str(os.getenv("DEPLOYMENT_MODE") or "").lower()
    if env_name in {"prod", "production"} or deploy_mode in {"prod", "production"}:
        raise SystemExit("refusing AA-010 occurrence preparation in production")
    db_url = str(os.getenv("DATABASE_URL") or "")
    lowered = db_url.lower()
    if not db_url or not any(marker in lowered for marker in ("e2e", "test")):
        raise SystemExit("DATABASE_URL must contain e2e or test")
    if any(marker in lowered for marker in ("prod", "production", "staging")):
        raise SystemExit("DATABASE_URL looks like production/staging")
    parsed = urlparse(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("AA-010 occurrence preparation only accepts a local database")


def _date_value(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise SystemExit("AA-010 term is missing a valid date boundary")


def _parity_allows(parity: str, week_no: int) -> bool:
    value = str(parity or "ALL").upper()
    if value == "ALL":
        return True
    if value == "ODD":
        return week_no % 2 == 1
    if value == "EVEN":
        return week_no % 2 == 0
    raise SystemExit(f"AA-010 formal pattern has unknown week parity: {value}")


def main() -> int:
    assert_safe_target()
    if not STATE_PATH.exists():
        raise SystemExit("AA-010 C-W2 state is missing; run e2e_seed_academic_c_teacher_today.py first")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    tenant_id = int(state.get("tenantId") or 0)
    term_id = int(state.get("termId") or 0)
    task_id = int(state.get("teachingTaskId") or 0)
    expected_item_id = int(state.get("scheduleItemId") or 0)
    expected_slot_no = int(state.get("slotNo") or 0)
    target_date = date.fromisoformat(str(state.get("targetDate") or ""))
    if not all((tenant_id, term_id, task_id, expected_item_id, expected_slot_no)):
        raise SystemExit("AA-010 C-W2 state is missing formal schedule identity")

    db = get_sessionmaker()()
    try:
        set_tenant({"tenantId": str(tenant_id)})
        term = db.get(AaTerm, term_id)
        task = db.get(AaTeachingTask, task_id)
        if not term or term.is_deleted or int(term.tenant_id) != tenant_id:
            raise SystemExit("AA-010 current term is missing from isolated MySQL")
        if not task or task.is_deleted or int(task.tenant_id) != tenant_id:
            raise SystemExit("AA-010 teaching task is missing from isolated MySQL")
        task_batch = db.get(AaTeachingTaskBatch, int(task.batch_id or 0))
        if not task_batch or task_batch.is_deleted or int(task_batch.tenant_id) != tenant_id:
            raise SystemExit("AA-010 teaching task batch is missing from isolated MySQL")
        if int(task_batch.term_id or 0) != int(term.id):
            raise SystemExit("AA-010 teaching task batch does not belong to the fixture term")

        projection = formal_schedule_patterns(db, task, task_batch, term)
        if projection.get("status") != "READY":
            raise SystemExit(f"AA-010 published schedule is not executable: {projection}")
        patterns = [
            row for row in projection.get("patterns") or []
            if int(row.get("scheduleItemId") or 0) == expected_item_id
            and int(row.get("slotNo") or 0) == expected_slot_no
        ]
        if len(patterns) != 1:
            raise SystemExit(
                "AA-010 expected exactly one active published pattern for the seeded schedule item; "
                f"got {patterns}"
            )
        pattern = patterns[0]

        term_start = _date_value(term.start_date)
        term_end = _date_value(term.end_date)
        if not (term_start <= target_date <= term_end):
            raise SystemExit("AA-010 target date is outside the fixture term")

        occurrences = []
        cursor = target_date
        while cursor >= term_start and len(occurrences) < 3:
            week_no = ((cursor - term_start).days // 7) + 1
            matches_pattern = (
                cursor.isoweekday() == int(pattern["weekday"])
                and int(pattern["startWeek"] or 0) <= week_no
                and (not int(pattern["endWeek"] or 0) or week_no <= int(pattern["endWeek"]))
                and _parity_allows(pattern.get("weekParity"), week_no)
            )
            if matches_pattern:
                resolved = resolve_formal_occurrence(
                    db,
                    task,
                    task_batch,
                    term,
                    session_date=cursor.isoformat(),
                    slot_no=expected_slot_no,
                    expected_schedule_item_id=expected_item_id,
                    lock=False,
                )
                if resolved.get("sourceType") != "FORMAL_TEACHING":
                    raise SystemExit(f"AA-010 occurrence is not formal teaching truth: {resolved}")
                occurrences.append({
                    "label": "current" if not occurrences else f"previous-{len(occurrences)}",
                    "sessionDate": str(resolved["sessionDate"]),
                    "scheduleItemId": int(resolved["scheduleItemId"]),
                    "slotNo": int(resolved["slotNo"]),
                    "weekNo": int(resolved["weekNo"]),
                    "activeBatchId": int(resolved["activeBatchId"]),
                    "scopeHeadVersion": int(resolved["scopeHeadVersion"]),
                    "changeId": int(resolved["changeId"]) if resolved.get("changeId") else None,
                    "changeType": resolved.get("changeType"),
                })
            cursor -= timedelta(days=1)

        if len(occurrences) != 3:
            raise SystemExit(f"AA-010 could not prove three published formal occurrences: {occurrences}")
        if occurrences[0]["sessionDate"] != target_date.isoformat():
            raise SystemExit("AA-010 current Teacher Today occurrence is not the first proven occurrence")
        if len({row["sessionDate"] for row in occurrences}) != 3:
            raise SystemExit("AA-010 proven occurrence dates are not unique")
        if any(row["scheduleItemId"] != expected_item_id for row in occurrences):
            raise SystemExit("AA-010 proven occurrences changed schedule item identity")
        if any(row["slotNo"] != expected_slot_no for row in occurrences):
            raise SystemExit("AA-010 proven occurrences changed slot identity")

        state["attendanceOccurrences"] = occurrences
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "teachingTaskId": task_id,
            "formalPattern": pattern,
            "attendanceOccurrences": occurrences,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
