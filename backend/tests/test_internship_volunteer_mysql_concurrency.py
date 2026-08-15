"""A01-13 real-MySQL concurrency: two stale writers cannot partially overwrite 1/2/3 slots."""
from __future__ import annotations

import os
import threading

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import InternshipApplication, InternshipRecord, InternshipPosition
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_volunteer_service as svc

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or "").startswith("mysql"),
    reason="MySQL-only volunteer row-lock concurrency",
)

TID = 1000000000000000001


def _session():
    return get_sessionmaker()()


def _seed():
    db=_session()
    try:
        record=InternshipRecord(
            tenant_id=TID, student_id=900001, batch_id=800001,
            eligibility_status="QUALIFIED", destination_type="NONE", status="READY", version=0,
        )
        campaign=InternshipRecruitmentCampaign(
            tenant_id=TID, batch_id=800001, campaign_code="RACE-A01-10",
            campaign_name="A01并发选岗", round_no=1, status="OPEN", teacher_confirm_sla_hours=48,
        )
        db.add_all([record,campaign]); db.flush()
        positions=[]
        for idx in range(1,5):
            row=InternshipPosition(
                tenant_id=TID, company_id=700000+idx, company_name=f"并发企业{idx}",
                batch_id=800001, campaign_id=campaign.id, source_type="SCHOOL",
                title=f"并发岗位{idx}", headcount=10, allocated_count=0, status="PUBLISHED",
            )
            db.add(row); positions.append(row)
        db.flush(); ids=(record.id,campaign.id,[p.id for p in positions]); db.commit(); return ids
    finally:
        db.close()


def test_mysql_two_stale_writers_single_winner_no_duplicate_or_half_slots(db_mode):
    record_id,campaign_id,position_ids=_seed()
    original=svc.eligibility_svc.evaluate_position_for_student_in_tx
    svc.eligibility_svc.evaluate_position_for_student_in_tx=lambda *args, **kwargs: {"eligible":True}
    barrier=threading.Barrier(2)
    lock=threading.Lock()
    results=[]

    plans=[position_ids[:3],[position_ids[3],position_ids[1],position_ids[2]]]

    def _run(plan):
        db=_session()
        try:
            barrier.wait(timeout=30)
            rows=[{"volunteerNo":i+1,"positionId":pid,"applicationStatement":f"志愿{i+1}"} for i,pid in enumerate(plan)]
            group,apps=svc.save_or_submit_in_tx(
                db,tenant_id=TID,student_id=900001,record_id=record_id,campaign_id=campaign_id,
                volunteers=rows,expected_group_version=0,submit=False,
            )
            db.commit()
            with lock: results.append(("ok",[a.position_id for a in apps],group.version))
        except AppException as exc:
            db.rollback()
            with lock: results.append(("err",exc.http_status,exc.code))
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            with lock: results.append(("boom",repr(exc)))
        finally:
            db.close()

    try:
        threads=[threading.Thread(target=_run,args=(plan,)) for plan in plans]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=90)
    finally:
        svc.eligibility_svc.evaluate_position_for_student_in_tx=original

    oks=[r for r in results if r[0]=="ok"]
    errs=[r for r in results if r[0]=="err"]
    assert len(oks)==1, results
    assert len(errs)==1, results
    assert errs[0][1]==409, results

    db=_session()
    try:
        groups=list(db.scalars(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id==TID,
            InternshipVolunteerGroup.record_id==record_id,
            InternshipVolunteerGroup.campaign_id==campaign_id,
            InternshipVolunteerGroup.is_deleted.is_(False),
        )).all())
        assert len(groups)==1
        apps=list(db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id==TID,
            InternshipApplication.record_id==record_id,
            InternshipApplication.application_type=="POSITION",
            InternshipApplication.is_deleted.is_(False),
        ).order_by(InternshipApplication.volunteer_no.asc())).all())
        assert [a.volunteer_no for a in apps]==[1,2,3]
        assert len({a.position_id for a in apps})==3
        assert [a.position_id for a in apps]==oks[0][1]
        assert db.scalar(select(func.count()).select_from(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.tenant_id==TID,
            InternshipVolunteerGroup.record_id==record_id,
            InternshipVolunteerGroup.campaign_id==campaign_id,
        ))==1
    finally:
        db.close()
