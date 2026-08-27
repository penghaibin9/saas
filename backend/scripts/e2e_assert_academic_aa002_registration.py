"""Direct MySQL + audit seal for AA-002 real XLSX roster/register chain."""
from __future__ import annotations

import json
from pathlib import Path

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AaRegistration, AaRegistrationBatch, AaStatusChange, AffairsAuditTrail,
    ExcelImportJob, StudentAcademicFact, StudentProfile, StudentStageEvent,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend/tmp/e2e_academic_aa002_state.local.json"
OUTCOME_PATH = ROOT / "e2e/academic-aa002-browser-outcome.json"
SEAL_PATH = ROOT / "e2e/academic-aa002-mysql-seal.json"


def req(value, message):
    if not value: raise AssertionError(message)


def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    outcome = json.loads(OUTCOME_PATH.read_text(encoding="utf-8"))
    expected_nos = [r["studentNo"] for r in state["rows"]]
    batch_id = int(outcome["batchId"])
    req(outcome.get("xlsxUploadPass") is True and outcome.get("browserPass") is True, "AA-002 Browser/XLSX not PASS")
    req(outcome.get("productSha"), "AA-002 missing exact product SHA")

    db = get_sessionmaker()()
    try:
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.student_no.in_(expected_nos), StudentProfile.is_deleted.is_(False)
        ).order_by(StudentProfile.student_no)).all()
        req(len(students) == 2, f"AA-002 student rows={[(s.id,s.student_no) for s in students]}")
        tids = {int(s.tenant_id) for s in students}
        req(len(tids) == 1, f"AA-002 tenant drift={tids}")
        tid = tids.pop()
        by_no = {s.student_no: s for s in students}
        req(set(by_no) == set(expected_nos), f"AA-002 studentNo drift={set(by_no)}")
        req(all(s.student_status == "REGISTERED" for s in students),
            f"AA-002 final profile status={[(s.student_no,s.student_status) for s in students]}")

        batch = db.get(AaRegistrationBatch, batch_id)
        req(batch is not None and int(batch.tenant_id) == tid and not batch.is_deleted, "AA-002 batch missing")
        req(batch.register_type == "ENROLL" and batch.status == "OPEN", f"AA-002 batch={batch.register_type}/{batch.status}")

        regs = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == tid, AaRegistration.batch_id == batch_id,
            AaRegistration.student_id.in_([int(s.id) for s in students]), AaRegistration.is_deleted.is_(False)
        ).order_by(AaRegistration.id)).all()
        req(len(regs) == 2 and all(r.status == "REGISTERED" for r in regs),
            f"AA-002 registrations={[(r.id,r.student_id,r.status) for r in regs]}")
        req(set(str(r.id) for r in regs) == set(outcome.get("registrationIds") or []),
            f"AA-002 Browser/MySQL registration IDs drift db={[r.id for r in regs]} browser={outcome.get('registrationIds')}")

        roster_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid, AffairsAuditTrail.biz_type == "AA_ROSTER",
            AffairsAuditTrail.biz_id.in_([int(s.id) for s in students])
        )).all()
        req(len(roster_audits) == 2 and all(a.action == "IMPORT" for a in roster_audits),
            f"AA-002 roster audits={[(a.biz_id,a.action,a.detail) for a in roster_audits]}")
        batch_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid, AffairsAuditTrail.biz_type == "AA_REG_BATCH",
            AffairsAuditTrail.biz_id == batch_id
        )).all()
        req(len(batch_audits) == 1 and batch_audits[0].action == "CREATE", f"AA-002 batch audits={[(a.action,a.detail) for a in batch_audits]}")
        reg_audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == tid, AffairsAuditTrail.biz_type == "AA_REGISTRATION",
            AffairsAuditTrail.biz_id.in_([int(r.id) for r in regs])
        )).all()
        req(len(reg_audits) == 2 and all(a.action == "REGISTER" and a.detail == "ENROLL_REGISTER" for a in reg_audits),
            f"AA-002 registration audits={[(a.biz_id,a.action,a.detail) for a in reg_audits]}")

        changes = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == tid, AaStatusChange.student_id.in_([int(s.id) for s in students]),
            AaStatusChange.change_type == "ENROLL_REGISTER", AaStatusChange.is_deleted.is_(False)
        )).all()
        req(len(changes) == 2 and all(c.status == "EFFECTIVE" and c.to_status == "REGISTERED" for c in changes),
            f"AA-002 status changes={[(c.student_id,c.status,c.to_status) for c in changes]}")

        facts = db.scalars(select(StudentAcademicFact).where(
            StudentAcademicFact.tenant_id == tid, StudentAcademicFact.student_id.in_([int(s.id) for s in students]),
            StudentAcademicFact.valid_to.is_(None)
        )).all()
        req(len(facts) == 2 and all(f.student_status == "REGISTERED" and f.source_type == "ENROLL_REGISTER" for f in facts),
            f"AA-002 current facts={[(f.student_id,f.student_status,f.source_type) for f in facts]}")
        stages = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == tid, StudentStageEvent.student_id.in_([int(s.id) for s in students]),
            StudentStageEvent.source_module == "academic-affairs"
        )).all()
        req(len([s for s in stages if s.to_stage == "REGISTERED"]) == 2,
            f"AA-002 stage events={[(s.student_id,s.from_stage,s.to_stage,s.reason) for s in stages]}")

        jobs = db.scalars(select(ExcelImportJob).where(
            ExcelImportJob.tenant_id == tid, ExcelImportJob.module_key == "academicAffairs",
            ExcelImportJob.biz_type == "roster", ExcelImportJob.is_deleted.is_(False)
        ).order_by(ExcelImportJob.id.desc())).all()
        req(len(jobs) == 1, f"AA-002 Excel import jobs={[(j.id,j.status,j.total_rows,j.success_rows) for j in jobs]}")
        job = jobs[0]
        req(job.status == "IMPORTED" and job.total_rows == 2 and job.valid_rows == 2 and job.invalid_rows == 0 and job.success_rows == 2,
            f"AA-002 Excel job={job.status}/{job.total_rows}/{job.valid_rows}/{job.invalid_rows}/{job.success_rows}")

        seal = {
            "productSha": outcome["productSha"], "tenantId": str(tid), "batchId": str(batch_id),
            "studentIds": [str(s.id) for s in students], "studentNos": expected_nos,
            "registrationIds": [str(r.id) for r in regs], "excelImportJobId": str(job.id),
            "excelImportJob": {"status": job.status, "total": job.total_rows, "valid": job.valid_rows, "invalid": job.invalid_rows, "success": job.success_rows},
            "rosterAuditCount": len(roster_audits), "registrationAuditCount": len(reg_audits),
            "statusChangeCount": len(changes), "currentFactCount": len(facts), "browserMysqlIdsMatch": True,
        }
        SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(seal, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__": raise SystemExit(main())
