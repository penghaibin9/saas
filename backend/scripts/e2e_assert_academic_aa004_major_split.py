"""Direct MySQL seal for AA-004 major split."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaMajorSplitBatch,
    AaMajorSplitOption,
    AaMajorSplitVolunteer,
    AffairsAuditTrail,
    SchoolClass,
    StudentAcademicFact,
    StudentProfile,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend/tmp/e2e_academic_aa004_state.local.json"
OUTCOME_PATH = ROOT / "e2e/academic-aa004-browser-outcome.json"
SEAL_PATH = ROOT / "e2e/academic-aa004-mysql-seal.json"


def req(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    outcome = json.loads(OUTCOME_PATH.read_text(encoding="utf-8"))
    tid = int(state["tenantId"])
    sid = int(state["studentId"])
    bid = int(outcome["batchId"])
    vid = int(outcome["volunteerId"])
    target = int(state["targetMajorBId"])
    baseline_id = int(state["baselineFactId"])
    baseline_version = int(state["baselineFactVersion"])

    db = get_sessionmaker()()
    try:
        batch = db.get(AaMajorSplitBatch, bid)
        req(batch is not None and int(batch.tenant_id) == tid, "AA-004 batch missing")
        req(batch.status == "CONFIRMED", f"AA-004 batch status={batch.status}")
        req(batch.grade == state["grade"], f"AA-004 batch grade={batch.grade}")

        volunteer = db.get(AaMajorSplitVolunteer, vid)
        req(volunteer is not None, "AA-004 volunteer missing")
        req(int(volunteer.batch_id) == bid and int(volunteer.student_id) == sid, "AA-004 volunteer ownership drift")
        req(volunteer.status == "CONFIRMED", f"AA-004 volunteer status={volunteer.status}")
        choices = [int(x) for x in json.loads(volunteer.choices_json or "[]")]
        req(choices == [target], f"AA-004 final choices={choices}, expected={[target]}")
        req(int(volunteer.result_major_id or 0) == target, f"AA-004 result major={volunteer.result_major_id}")
        req(int(volunteer.result_choice_rank or 0) == 1, f"AA-004 result rank={volunteer.result_choice_rank}")

        options = db.scalars(select(AaMajorSplitOption).where(
            AaMajorSplitOption.tenant_id == tid,
            AaMajorSplitOption.batch_id == bid,
            AaMajorSplitOption.is_deleted.is_(False),
        ).order_by(AaMajorSplitOption.id)).all()
        req(len(options) == 2, f"AA-004 option count={len(options)}")
        by_major = {int(row.major_id): row for row in options}
        req(int(by_major[target].allocated_count or 0) == 1, f"AA-004 target allocated={by_major[target].allocated_count}")
        req(all(int(row.allocated_count or 0) <= int(row.capacity) for row in options), "AA-004 capacity exceeded")

        student = db.get(StudentProfile, sid)
        req(student is not None, "AA-004 student missing")
        req(int(student.major_id or 0) == target, f"AA-004 StudentProfile major={student.major_id}")
        req(int(student.version or 0) == int(state["studentBaseVersion"]) + 1,
            f"AA-004 StudentProfile version base={state['studentBaseVersion']} final={student.version}")
        klass = db.get(SchoolClass, int(student.class_id or 0))
        req(klass is not None and int(klass.major_id or 0) == target, "AA-004 target class not bound to result major")
        req(klass.grade == state["grade"], f"AA-004 target class grade={klass.grade}")

        baseline = db.get(StudentAcademicFact, baseline_id)
        req(baseline is not None, "AA-004 baseline fact missing")
        req(int(baseline.version_no) == baseline_version, "AA-004 baseline version drift")
        req(baseline.valid_to is not None, "AA-004 baseline fact must be closed")
        applied = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid,
            StudentAcademicFact.student_id == sid,
            StudentAcademicFact.source_type == "MAJOR_SPLIT",
            StudentAcademicFact.source_ref_id == bid,
        )).all()
        req(len(applied) == 1, f"AA-004 applied fact count={len(applied)}")
        fact = applied[0]
        req(int(fact.version_no) == baseline_version + 1, f"AA-004 fact version={fact.version_no}")
        req(int(fact.major_id or 0) == target, f"AA-004 fact major={fact.major_id}")
        req(int(fact.class_id or 0) == int(student.class_id or 0), "AA-004 fact/profile class drift")
        req(fact.valid_to is None, "AA-004 applied fact must be current")
        active = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid,
            StudentAcademicFact.student_id == sid,
            StudentAcademicFact.valid_to.is_(None),
        )).all()
        req(len(active) == 1 and int(active[0].id) == int(fact.id), "AA-004 must leave exactly one current fact")

        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid,
            AffairsAuditTrail.biz_type == "AA_MAJOR_SPLIT",
            AffairsAuditTrail.biz_id == bid,
        ).order_by(AffairsAuditTrail.id)).all()
        counts = Counter(str(row.action or "") for row in audits)
        expected = {
            "SPLIT_BATCH_CREATE": 1,
            "SPLIT_OPTION_ADD": 2,
            "SPLIT_OPEN": 1,
            "SPLIT_VOLUNTEER_SUBMIT": 2,
            "SPLIT_CLOSE": 1,
            "SPLIT_ALLOCATE": 1,
            "SPLIT_APPLY_STUDENT": 1,
            "SPLIT_CONFIRM": 1,
        }
        for action, count in expected.items():
            req(counts[action] == count, f"AA-004 audit {action}={counts[action]} all={dict(counts)}")
        req(outcome.get("studentManageForbidden") is True, "AA-004 student management negative evidence missing")
        req(outcome.get("studentPcSubmitted") is True and outcome.get("studentMiniUpdated") is True,
            "AA-004 cross-surface submit/update evidence missing")
        req(outcome.get("staffConfirmed") is True and outcome.get("studentFinalProjection") is True,
            "AA-004 final Browser projection evidence missing")

        seal = {
            "tenantId": str(tid),
            "batchId": str(bid),
            "studentId": str(sid),
            "volunteerId": str(vid),
            "batchStatus": batch.status,
            "volunteerStatus": volunteer.status,
            "choices": choices,
            "resultMajorId": str(volunteer.result_major_id),
            "resultChoiceRank": volunteer.result_choice_rank,
            "studentMajorId": str(student.major_id),
            "studentClassId": str(student.class_id),
            "academicFactId": str(fact.id),
            "academicFactVersion": int(fact.version_no),
            "auditCounts": dict(counts),
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
