"""Direct MySQL seal for AA-001 term/calendar Browser chain."""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import AaCalendarEvent, AaTerm, AffairsAuditTrail

ROOT = Path(__file__).resolve().parents[2]
OUTCOME_PATH = ROOT / "e2e/academic-aa001-browser-outcome.json"
SEAL_PATH = ROOT / "e2e/academic-aa001-mysql-seal.json"


def req(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    outcome = json.loads(OUTCOME_PATH.read_text(encoding="utf-8"))
    source_term_id = int(outcome["sourceTermId"])
    target_term_id = int(outcome["targetTermId"])
    expected_sha = str(outcome.get("productSha") or "")
    holiday_remark = str(outcome["holidayRemark"])
    exam_remark = str(outcome["examRemark"])

    req(outcome.get("browserPass") is True, "AA-001 Browser outcome is not PASS")
    req(expected_sha, "AA-001 Browser outcome missing exact product SHA")

    db = get_sessionmaker()()
    try:
        source = db.get(AaTerm, source_term_id)
        target = db.get(AaTerm, target_term_id)
        req(source is not None and target is not None, "AA-001 source/target term missing")
        req(not source.is_deleted and not target.is_deleted, "AA-001 source/target term deleted")
        req(source.tenant_id == target.tenant_id, "AA-001 source/target tenant drift")
        tid = int(target.tenant_id)
        req(source.term_name == outcome["sourceName"], f"AA-001 source term name drift={source.term_name}")
        req(target.term_name == outcome["targetName"], f"AA-001 target term name drift={target.term_name}")
        req(source.year_code == outcome["sourceYearCode"], f"AA-001 source year drift={source.year_code}")
        req(target.year_code == outcome["targetYearCode"], f"AA-001 target year drift={target.year_code}")
        req(source.status == "DRAFT" and target.status == "DRAFT",
            f"AA-001 term state drift source={source.status} target={target.status}")

        source_events = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == tid,
            AaCalendarEvent.term_id == source_term_id,
            AaCalendarEvent.is_deleted.is_(False),
        ).order_by(AaCalendarEvent.id)).all()
        target_events = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == tid,
            AaCalendarEvent.term_id == target_term_id,
            AaCalendarEvent.is_deleted.is_(False),
        ).order_by(AaCalendarEvent.id)).all()

        req(len(source_events) == 2, f"AA-001 source event count={len(source_events)}")
        req(len(target_events) == 2, f"AA-001 target event count={len(target_events)}")
        source_by_remark = {str(row.remark or ""): row for row in source_events}
        target_by_remark = {str(row.remark or ""): row for row in target_events}
        req(set(source_by_remark) == {holiday_remark, exam_remark},
            f"AA-001 source remarks={list(source_by_remark)}")
        req(set(target_by_remark) == {holiday_remark, exam_remark},
            f"AA-001 target remarks={list(target_by_remark)}")
        req(source_by_remark[holiday_remark].event_type == "HOLIDAY", "AA-001 source HOLIDAY type drift")
        req(source_by_remark[exam_remark].event_type == "EXAM", "AA-001 source EXAM type drift")
        req(target_by_remark[holiday_remark].event_type == "HOLIDAY", "AA-001 target HOLIDAY type drift")
        req(target_by_remark[exam_remark].event_type == "EXAM", "AA-001 target EXAM type drift")
        req(target_by_remark[holiday_remark].start_date.date().isoformat() == outcome["mappedHoliday"],
            f"AA-001 mapped holiday={target_by_remark[holiday_remark].start_date}")

        target_ids = [int(row.id) for row in target_events]
        target_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_type == "AA_CALENDAR",
            AffairsAuditTrail.biz_id.in_(target_ids),
        ).order_by(AffairsAuditTrail.id)).all()
        req(len(target_audits) == 2,
            f"AA-001 target canonical audit count={len(target_audits)} shape={[(r.biz_id,r.action,r.detail) for r in target_audits]}")
        req(all(row.action == "ADD" for row in target_audits),
            f"AA-001 target audit action drift={[(r.biz_id,r.action) for r in target_audits]}")
        audit_by_id = {int(row.biz_id): row for row in target_audits}
        for event in target_events:
            audit = audit_by_id.get(int(event.id))
            req(audit is not None, f"AA-001 missing audit for event {event.id}")
            req(str(audit.detail or "") == str(event.event_type),
                f"AA-001 audit detail mismatch event={event.id} detail={audit.detail} type={event.event_type}")

        term_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_type == "AA_TERM",
            AffairsAuditTrail.biz_id.in_([source_term_id, target_term_id]),
        ).order_by(AffairsAuditTrail.id)).all()
        req(len(term_audits) == 2 and all(row.action == "CREATE" for row in term_audits),
            f"AA-001 term audit shape={[(r.biz_id,r.action) for r in term_audits]}")

        browser_ids = sorted(int(row["eventId"]) for row in outcome.get("targetEvents", []))
        db_ids = sorted(target_ids)
        req(browser_ids == db_ids, f"AA-001 Browser/MySQL event IDs drift browser={browser_ids} db={db_ids}")

        seal = {
            "productSha": expected_sha,
            "tenantId": str(tid),
            "sourceTermId": str(source_term_id),
            "targetTermId": str(target_term_id),
            "sourceEventIds": [str(row.id) for row in source_events],
            "targetEventIds": [str(row.id) for row in target_events],
            "targetRemarks": [str(row.remark or "") for row in target_events],
            "targetAudit": [
                {"bizId": str(row.biz_id), "action": row.action, "detail": str(row.detail or "")}
                for row in target_audits
            ],
            "termAudit": [
                {"bizId": str(row.biz_id), "action": row.action}
                for row in term_audits
            ],
            "browserMysqlIdsMatch": True,
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
