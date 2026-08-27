from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import (
    AffairsAuditTrail,
    CsDormRecord,
    CsServiceStudent,
    DormBed,
    DormBuilding,
    DormTransfer,
    StudentProfile,
    UnifiedTodo,
    User,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "app" / "e2e" / "student-affairs-sa009-browser-v3-evidence.json"
DORM_MANAGER_LOGIN = "e2e_sa009_dorm"
STUDENT_NO = "E2E20260911"


def main() -> None:
    assert EVIDENCE.exists(), f"missing Browser evidence: {EVIDENCE}"
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    building_id = int(evidence["buildingId"])
    transfer_id = int(evidence["transferId"])
    old_bed_id = int(evidence["oldBedId"])
    new_bed_id = int(evidence["newBedId"])

    with get_sessionmaker()() as db:
        building = db.get(DormBuilding, building_id)
        assert building and not building.is_deleted, building_id
        manager = db.scalars(select(User).where(
            User.tenant_id == building.tenant_id,
            User.login_name == DORM_MANAGER_LOGIN,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )).first()
        assert manager, DORM_MANAGER_LOGIN
        assert str(building.manager_teacher_key or "") == str(manager.id), {
            "buildingId": building_id,
            "managerTeacherKey": building.manager_teacher_key,
            "expectedUserId": int(manager.id),
        }

        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == building.tenant_id,
            StudentProfile.student_no == STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        )).first()
        assert student, STUDENT_NO

        transfer = db.get(DormTransfer, transfer_id)
        assert transfer and transfer.tenant_id == building.tenant_id, transfer_id
        assert transfer.status == "EXECUTED", transfer.status
        assert transfer.current_node == "EXECUTED", transfer.current_node
        assert int(transfer.student_id) == int(student.id)
        assert int(transfer.from_bed_id) == old_bed_id
        assert int(transfer.to_bed_id) == new_bed_id

        old_bed = db.get(DormBed, old_bed_id)
        new_bed = db.get(DormBed, new_bed_id)
        assert old_bed and new_bed
        assert int(old_bed.building_id) == building_id == int(new_bed.building_id)
        for label, bed in (("old", old_bed), ("new", new_bed)):
            assert bed.status == "VACANT", {"label": label, "status": bed.status, "bedId": int(bed.id)}
            assert bed.student_id is None, {"label": label, "studentId": bed.student_id}
            assert bed.cs_dorm_record_id is None, {"label": label, "recordId": bed.cs_dorm_record_id}

        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == building.tenant_id,
            CsServiceStudent.student_id == int(student.id),
            CsServiceStudent.is_deleted.is_(False),
        )).first()
        cs_student_id = int(cs.id) if cs else int(student.id)
        dorm_records = db.scalars(select(CsDormRecord).where(
            CsDormRecord.tenant_id == building.tenant_id,
            CsDormRecord.cs_student_id == cs_student_id,
            CsDormRecord.is_deleted.is_(False),
        ).order_by(CsDormRecord.id)).all()
        assert dorm_records, "SA-009 Browser journey must leave a dorm ledger record"
        active_in = [row for row in dorm_records if row.status == "IN" and row.record_status == "ACTIVE"]
        assert not active_in, [int(row.id) for row in active_in]
        latest = dorm_records[-1]
        assert latest.status == "OUT" and latest.record_status == "INACTIVE", {
            "recordId": int(latest.id), "status": latest.status, "recordStatus": latest.record_status,
        }
        assert latest.building == building.building_name
        assert latest.bed == new_bed.bed_no

        audits = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == building.tenant_id,
        ).order_by(AffairsAuditTrail.id)).all()
        audit_keys = {(row.biz_type, int(row.biz_id or 0), row.action) for row in audits}
        required = {
            ("DORM_BUILDING", building_id, "CREATE"),
            ("DORM_BUILDING", building_id, "GENERATE"),
            ("DORM_BED", old_bed_id, "CHECKIN"),
            ("DORM_TRANSFER", transfer_id, "SUBMIT"),
            ("DORM_TRANSFER", transfer_id, "EXECUTED"),
            ("DORM_BED", new_bed_id, "CHECKOUT"),
        }
        missing = sorted(required - audit_keys)
        assert not missing, {"missingAuditFacts": missing}

        pending = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == building.tenant_id,
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.source_biz_type == "DORM_TRANSFER",
            UnifiedTodo.source_biz_id == transfer_id,
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        )).all()
        assert not pending, [int(row.id) for row in pending]

        sealed = {
            "sa": "SA-009",
            "result": "REAL_PASS",
            "buildingId": building_id,
            "managerTeacherKey": str(building.manager_teacher_key),
            "managerUserId": int(manager.id),
            "studentId": int(student.id),
            "transferId": transfer_id,
            "transferStatus": transfer.status,
            "oldBed": {"id": old_bed_id, "status": old_bed.status},
            "newBed": {"id": new_bed_id, "status": new_bed.status},
            "latestDormRecord": {
                "id": int(latest.id), "status": latest.status, "recordStatus": latest.record_status,
                "building": latest.building, "room": latest.room, "bed": latest.bed,
            },
            "requiredAuditFacts": sorted([list(item) for item in required]),
            "pendingTransferTodos": 0,
        }
        print("[sa009-mysql-seal] " + json.dumps(sealed, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
