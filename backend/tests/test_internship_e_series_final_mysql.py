"""E-series final MySQL seal: hot capacity, cross-authority placement, and 20K applicant reads."""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipApplication, InternshipPosition, InternshipRecord
from app.models.internship_application_material_snapshot import InternshipApplicationMaterialSnapshot
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_enterprise_application_decision_service as decision_svc
from app.modules.internship.services import internship_position_rights as rights_svc
from app.modules.internship.services import internship_student_service as student_svc
from app.modules.internship.services.internship_assignment_snapshot_authority import install_assignment_snapshot_authority

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").startswith("mysql"),
    reason="E-series final seal requires real MySQL",
)


def _session():
    return get_sessionmaker()()


def _base() -> int:
    return 8_500_000_000 + (uuid4().int % 1_000_000_000)


def _tenant() -> int:
    return 7_500_000_000 + (uuid4().int % 1_000_000_000)


def _allow_assignment(monkeypatch):
    monkeypatch.setattr(student_svc, "_assert_write_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        rights_svc,
        "evaluate_position_publishability",
        lambda *_args, **_kwargs: {"passed": True, "blockers": [], "unknowns": [], "ruleVersion": "E-FINAL"},
    )


def test_mysql_hot_position_headcount_one_has_exactly_one_winner(monkeypatch, db_mode):
    """Two students race for one slot; the canonical conditional UPDATE must never oversubscribe."""
    tenant_id, base = _tenant(), _base()
    _allow_assignment(monkeypatch)
    db = _session()
    try:
        company = EmpCompany(
            tenant_id=tenant_id,
            name=f"E-FINAL-HOT-{base}",
            credit_code=f"HOT{base}",
            coop_status="ACTIVE",
            qualification_status="PASSED",
            blacklist=False,
        )
        db.add(company)
        db.flush()
        position = InternshipPosition(
            tenant_id=tenant_id,
            company_id=company.id,
            company_name=company.name,
            title="热点单名额岗位",
            headcount=1,
            allocated_count=0,
            status="PUBLISHED",
        )
        db.add(position)
        db.flush()
        records = [
            InternshipRecord(
                tenant_id=tenant_id,
                student_id=base + idx,
                batch_id=base + 100,
                eligibility_status="QUALIFIED",
                destination_type="NONE",
                status="READY",
                version=0,
            )
            for idx in (1, 2)
        ]
        db.add_all(records)
        db.flush()
        position_id = position.id
        record_ids = [row.id for row in records]
        db.commit()
    finally:
        db.close()

    barrier = threading.Barrier(2)
    output: list[tuple] = []
    output_lock = threading.Lock()

    def _worker(record_id: int):
        set_tenant({"tenantId": str(tenant_id)})
        local = _session()
        try:
            assert local.bind.dialect.name == "mysql"
            record = local.scalar(select(InternshipRecord).where(
                InternshipRecord.id == record_id,
                InternshipRecord.tenant_id == tenant_id,
            ).with_for_update())
            barrier.wait(timeout=30)
            student_svc.assign_position_in_tx(local, record, position_id, 0, user={"userId": "db-1"})
            local.commit()
            with output_lock:
                output.append(("ok", record_id))
        except AppException as exc:
            local.rollback()
            with output_lock:
                output.append(("err", record_id, exc.code, exc.http_status))
        finally:
            local.close()
            set_tenant(None)

    threads = [threading.Thread(target=_worker, args=(record_id,)) for record_id in record_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)
    assert all(not thread.is_alive() for thread in threads), "hot-position worker deadlock"

    winners = [item for item in output if item[0] == "ok"]
    losers = [item for item in output if item[0] == "err"]
    assert len(winners) == 1, output
    assert len(losers) == 1, output

    db = _session()
    try:
        position = db.get(InternshipPosition, position_id)
        records = list(db.scalars(select(InternshipRecord).where(InternshipRecord.id.in_(record_ids))).all())
        assigned = [row for row in records if row.position_id == position_id]
        assert position.allocated_count == 1
        assert position.headcount == 1
        assert position.status == "FULL"
        assert len(assigned) == 1
        assert assigned[0].id == winners[0][1]
    finally:
        db.close()


def test_mysql_student_enterprise_school_chain_closes_one_canonical_placement(monkeypatch, db_mode):
    """Student submission -> enterprise ACCEPT_INTENT -> canonical school assignment closes all facts."""
    tenant_id, base = _tenant(), _base()
    now = datetime.utcnow()
    _allow_assignment(monkeypatch)
    install_assignment_snapshot_authority()

    db = _session()
    try:
        company = EmpCompany(
            tenant_id=tenant_id,
            name=f"E-FINAL-CROSS-{base}",
            credit_code=f"CROSS{base}",
            coop_status="ACTIVE",
            qualification_status="PASSED",
            blacklist=False,
        )
        db.add(company)
        db.flush()
        campaign = InternshipRecruitmentCampaign(
            tenant_id=tenant_id,
            batch_id=base + 200,
            campaign_code=f"E-FINAL-{base}",
            campaign_name="E系列最终跨端招聘季",
            round_no=1,
            status="OPEN",
            school_confirm_start_at=now - timedelta(hours=1),
            school_confirm_end_at=now + timedelta(hours=1),
            enterprise_access_end_at=now + timedelta(days=1),
            enterprise_confirm_required=True,
            teacher_confirm_sla_hours=48,
        )
        db.add(campaign)
        db.flush()
        position = InternshipPosition(
            tenant_id=tenant_id,
            company_id=company.id,
            company_name=company.name,
            batch_id=campaign.batch_id,
            campaign_id=campaign.id,
            source_type="ENTERPRISE",
            title="E系列跨端正式岗位",
            headcount=2,
            allocated_count=0,
            status="PUBLISHED",
        )
        record = InternshipRecord(
            tenant_id=tenant_id,
            student_id=base + 301,
            batch_id=campaign.batch_id,
            eligibility_status="QUALIFIED",
            destination_type="NONE",
            status="READY",
            version=0,
        )
        db.add_all([position, record])
        db.flush()
        group = InternshipVolunteerGroup(
            tenant_id=tenant_id,
            record_id=record.id,
            student_id=record.student_id,
            batch_id=campaign.batch_id,
            campaign_id=campaign.id,
            status="SUBMITTED",
            submission_version=1,
            submitted_at=now,
            version=0,
        )
        db.add(group)
        db.flush()
        snapshot = InternshipApplicationMaterialSnapshot(
            tenant_id=tenant_id,
            volunteer_group_id=group.id,
            student_id=record.student_id,
            campaign_id=campaign.id,
            batch_id=campaign.batch_id,
            submission_version=1,
            profile_version=1,
            profile_snapshot_json={"profile": {"headline": "E final"}, "items": []},
            school_fact_snapshot_json={"realName": "终审学生", "studentNo": str(record.student_id)},
            attachment_file_ids_json=[],
            material_policy_snapshot_json={"schemaVersion": "V1"},
            consent_version="INTERNSHIP_APPLICATION_PRIVACY_V1",
            consent_at=now,
            contact_sharing_policy={"mode": "MASKED_ONLY", "sharePhone": False, "shareEmail": False},
            snapshot_hash=(f"{base:064d}"[-64:]),
        )
        db.add(snapshot)
        db.flush()
        application = InternshipApplication(
            tenant_id=tenant_id,
            record_id=record.id,
            student_id=record.student_id,
            batch_id=campaign.batch_id,
            campaign_id=campaign.id,
            application_type="POSITION",
            volunteer_no=1,
            position_id=position.id,
            company_name=company.name,
            position_name=position.title,
            application_statement="E系列最终链路申请说明",
            material_snapshot_id=snapshot.id,
            status="PENDING_REVIEW",
            submitted_at=now,
            version=0,
        )
        db.add(application)
        db.flush()
        decision = InternshipEnterpriseApplicationDecision(
            tenant_id=tenant_id,
            application_id=application.id,
            volunteer_group_id=group.id,
            campaign_id=campaign.id,
            batch_id=campaign.batch_id,
            company_id=company.id,
            position_id=position.id,
            material_snapshot_id=snapshot.id,
            submission_version=1,
            decision_status="ACCEPT_INTENT",
            effect_status="ACTIVE",
            valid_until=now + timedelta(hours=2),
            decided_by_member_id=base + 401,
            decided_by_user_id=base + 402,
            decided_at=now,
            version=0,
        )
        db.add(decision)
        db.flush()
        group.status = "LOCKED"
        group.current_material_snapshot_id = snapshot.id
        group.locked_application_id = application.id
        group.locked_by_decision_id = decision.id
        group.locked_at = now
        group.teacher_confirm_deadline = now + timedelta(hours=1)
        ids = {
            "application": application.id,
            "record": record.id,
            "position": position.id,
            "group": group.id,
            "decision": decision.id,
        }
        db.commit()
    finally:
        db.close()

    set_tenant({"tenantId": str(tenant_id)})
    try:
        result = student_svc.assign_position(
            ids["record"],
            ids["position"],
            expected_version=0,
            user={"userId": "db-9901", "realName": "终审老师", "currentRoleCode": "SCHOOL_ADMIN"},
        )
        assert result["positionId"] == str(ids["position"])
    finally:
        set_tenant(None)

    db = _session()
    try:
        application = db.get(InternshipApplication, ids["application"])
        record = db.get(InternshipRecord, ids["record"])
        position = db.get(InternshipPosition, ids["position"])
        group = db.get(InternshipVolunteerGroup, ids["group"])
        decision = db.get(InternshipEnterpriseApplicationDecision, ids["decision"])
        snapshots = list(db.scalars(select(InternshipPlacementSnapshot).where(
            InternshipPlacementSnapshot.tenant_id == tenant_id,
            InternshipPlacementSnapshot.record_id == ids["record"],
        )).all())
        assert application.status == "APPROVED"
        assert record.position_id == ids["position"]
        assert record.current_placement_snapshot_id is not None
        assert position.allocated_count == 1
        assert group.status == "APPROVED"
        assert decision.effect_status == "CONSUMED"
        assert len(snapshots) == 1
        assert snapshots[0].application_id == ids["application"]
        assert snapshots[0].enterprise_decision_id == ids["decision"]
        assert snapshots[0].snapshot_sha256 and len(snapshots[0].snapshot_sha256) == 64
    finally:
        db.close()


def test_mysql_enterprise_applicant_query_is_bounded_at_20k_rows(db_mode):
    """A 20K-company applicant workbench remains SQL-paginated and tenant/company scoped."""
    tenant_id, base = _tenant(), _base()
    now = datetime.utcnow()
    db = _session()
    try:
        company = EmpCompany(
            tenant_id=tenant_id,
            name=f"E-FINAL-20K-{base}",
            credit_code=f"SCALE{base}",
            coop_status="ACTIVE",
            qualification_status="PASSED",
            blacklist=False,
        )
        campaign = InternshipRecruitmentCampaign(
            tenant_id=tenant_id,
            batch_id=base + 500,
            campaign_code=f"E-SCALE-{base}",
            campaign_name="E系列20K报名规模招聘季",
            round_no=1,
            status="OPEN",
        )
        db.add_all([company, campaign])
        db.flush()
        position = InternshipPosition(
            tenant_id=tenant_id,
            company_id=company.id,
            company_name=company.name,
            batch_id=campaign.batch_id,
            campaign_id=campaign.id,
            source_type="ENTERPRISE",
            title="20K报名规模岗位",
            headcount=25_000,
            allocated_count=0,
            status="PUBLISHED",
        )
        db.add(position)
        db.flush()
        snapshot = InternshipApplicationMaterialSnapshot(
            tenant_id=tenant_id,
            volunteer_group_id=base + 501,
            student_id=base + 502,
            campaign_id=campaign.id,
            batch_id=campaign.batch_id,
            submission_version=1,
            profile_version=1,
            profile_snapshot_json={"profile": {"headline": "scale"}, "items": []},
            school_fact_snapshot_json={"realName": "规模学生", "studentNo": "SCALE"},
            attachment_file_ids_json=[],
            material_policy_snapshot_json={"schemaVersion": "V1"},
            consent_version="INTERNSHIP_APPLICATION_PRIVACY_V1",
            consent_at=now,
            contact_sharing_policy={"mode": "MASKED_ONLY", "sharePhone": False, "shareEmail": False},
            snapshot_hash=(f"{base + 1:064d}"[-64:]),
        )
        db.add(snapshot)
        db.flush()

        table = InternshipApplication.__table__
        for chunk_start in range(0, 20_000, 2_000):
            rows = []
            for offset in range(chunk_start, chunk_start + 2_000):
                rows.append({
                    "tenant_id": tenant_id,
                    "record_id": base + 100_000 + offset,
                    "student_id": base + 200_000 + offset,
                    "batch_id": campaign.batch_id,
                    "campaign_id": campaign.id,
                    "application_type": "POSITION",
                    "volunteer_no": 1,
                    "position_id": position.id,
                    "material_snapshot_id": snapshot.id,
                    "status": "PENDING_REVIEW",
                    "submitted_at": now,
                })
            db.execute(insert(table), rows)
        db.commit()

        context = SimpleNamespace(
            tenant_id=tenant_id,
            batch_id=campaign.batch_id,
            campaign_id=campaign.id,
            company_id=company.id,
        )
        page1, total1 = decision_svc.list_owned_applications_in_tx(
            db, context=context, page=1, page_size=100,
        )
        page200, total200 = decision_svc.list_owned_applications_in_tx(
            db, context=context, page=200, page_size=100,
        )
        assert total1 == total200 == 20_000
        assert len(page1) == len(page200) == 100
        assert {row["applicationId"] for row in page1}.isdisjoint(
            {row["applicationId"] for row in page200}
        )
    finally:
        db.close()
