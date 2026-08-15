"""A01-13 real-MySQL placement evidence: H1 survives position edits; switch creates seq+1."""
from __future__ import annotations

import os

import pytest

from app.core.context import set_current_user, set_tenant
from app.models import EmpCompany, InternshipPosition, InternshipRecord
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.modules.internship.services.internship_assignment_snapshot_authority import install_assignment_snapshot_authority
from app.modules.internship.services import internship_student_service as student_svc
from app.services.db_service import session as db_session
from tests.test_internship_p1_acceptance import _credit, _mk_running_batch, _mk_student, _uniq, ENT, IST, POS, TID

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or "").startswith("mysql"),
    reason="MySQL-only placement evidence",
)


def _position(client, headers, batch_id: str, company_id: str, title: str, amount: float, address: str):
    result = client.post(POS, headers=headers, json={
        "companyId": company_id, "title": title, "headcount": 2, "batchId": batch_id,
        "workAddress": address, "workLocation": address, "workContent": "生产线设备维护与质量巡检",
        "dailyHours": 8, "weeklyHours": 40, "nightShift": False, "overtimeAllowed": False,
        "restDaysPerWeek": 2, "remunerationType": "MONTHLY", "remunerationAmount": amount,
        "remunerationCycle": "MONTHLY", "accommodationProvided": True, "mealProvided": True,
        "hazardousFlag": False,
    }).json()
    assert result["code"] == 0, result
    pid = result["data"]["id"]
    submitted = client.post(f"{POS}/{pid}/status", headers=headers, json={"action": "SUBMIT"}).json()
    assert submitted["code"] == 0, submitted
    published = client.post(f"{POS}/{pid}/status", headers=headers, json={"action": "PUBLISH"}).json()
    assert published["code"] == 0, published
    return pid


def test_mysql_placement_snapshot_survives_position_edit_and_switches_with_new_seq(client, auth_headers, db_mode):
    install_assignment_snapshot_authority()
    batch_id = _mk_running_batch(client, auth_headers)
    student_id, _ = _mk_student(client, auth_headers)
    rec = client.post(IST, headers=auth_headers, json={"studentId": student_id, "batchId": batch_id}).json()
    assert rec["code"] == 0, rec
    record_id = int(rec["data"]["id"])

    company = client.post(ENT, headers=auth_headers, json={"name": _uniq("快照企"), "creditCode": _credit()}).json()
    assert company["code"] == 0, company
    company_id = company["data"]["id"]
    reviewed = client.post(f"{ENT}/{company_id}/review", headers=auth_headers, json={"action": "APPROVE"}).json()
    assert reviewed["code"] == 0, reviewed

    p1 = _position(client, auth_headers, batch_id, company_id, _uniq("设备岗A"), 3500, "长沙A园区")
    p2 = _position(client, auth_headers, batch_id, company_id, _uniq("设备岗B"), 4200, "长沙B园区")

    admin={"userId":"1","realName":"school_admin01","loginName":"school_admin01","currentRoleCode":"SCHOOL_ADMIN","userType":"TEACHER"}
    set_tenant({"tenantId":TID}); set_current_user(admin)
    try:
        first = student_svc.assign_position(record_id, p1, expected_version=0, user=admin)
        assert str(first["positionId"]) == str(p1)
        with db_session() as db:
            record = db.get(InternshipRecord, record_id)
            assert record.current_placement_snapshot_id
            h1 = db.get(InternshipPlacementSnapshot, record.current_placement_snapshot_id)
            assert h1 and h1.placement_seq == 1 and len(h1.snapshot_sha256) == 64
            original_hash = h1.snapshot_sha256
            original_amount = h1.remuneration_amount
            original_address = h1.work_address
            position = db.get(InternshipPosition, int(p1))
            position.remuneration_amount = 4500
            position.work_address = "长沙A园区-新地址"
            position.version = int(position.version or 0) + 1
            db.commit()
        with db_session() as db:
            h1_again = db.scalar(db.query(InternshipPlacementSnapshot).filter_by(tenant_id=int(TID), record_id=record_id, placement_seq=1).statement)
            assert h1_again.snapshot_sha256 == original_hash
            assert h1_again.remuneration_amount == original_amount
            assert h1_again.work_address == original_address
            record = db.get(InternshipRecord, record_id)
            expected = int(record.version or 0)
        second = student_svc.assign_position(record_id, p2, expected_version=expected, user=admin)
        assert str(second["positionId"]) == str(p2)
        with db_session() as db:
            snapshots = list(db.scalars(
                db.query(InternshipPlacementSnapshot)
                .filter_by(tenant_id=int(TID), record_id=record_id)
                .order_by(InternshipPlacementSnapshot.placement_seq.asc()).statement
            ).all())
            assert [s.placement_seq for s in snapshots] == [1, 2]
            assert snapshots[0].snapshot_sha256 == original_hash
            assert snapshots[1].snapshot_sha256 != original_hash
            record = db.get(InternshipRecord, record_id)
            assert record.current_placement_snapshot_id == snapshots[1].id
    finally:
        set_current_user(None); set_tenant(None)
