"""Real MySQL school handling, version races and authoritative placement side effects."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from threading import Barrier, Thread

import pytest
from sqlalchemy import select

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipApplication, InternshipPosition, InternshipRecord
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision as Decision
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.models.internship_placement_snapshot import InternshipPlacementSnapshot
from app.modules.internship.services import internship_school_volunteer_service as svc
from app.modules.internship.services import internship_enterprise_application_decision_service as enterprise
from tests.test_internship_school_volunteers import _seed, TID, ADMIN, MENTOR, BASE


def ready():
    ids = _seed()
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        group = db.get(InternshipVolunteerGroup, ids['0'])
        record = db.get(InternshipRecord, group.record_id)
        record.eligibility_status = 'QUALIFIED'
        campaign = db.get(InternshipRecruitmentCampaign, ids['campaign'])
        campaign.school_confirm_start_at = now-timedelta(days=1)
        campaign.school_confirm_end_at = now+timedelta(days=1)
        campaign.enterprise_decision_start_at = now-timedelta(days=1)
        campaign.enterprise_decision_end_at = now+timedelta(days=1)
        campaign.enterprise_confirm_required = True
        app = db.scalar(select(InternshipApplication).where(
            InternshipApplication.record_id == record.id, InternshipApplication.campaign_id == campaign.id))
        company = EmpCompany(tenant_id=TID, name='虚构办理测试企业', coop_status='ACTIVE', qualification_status='PASSED')
        db.add(company); db.flush()
        position = db.get(InternshipPosition, app.position_id)
        position.company_id = company.id
        for key, value in dict(work_content='设备记录与实训',daily_hours=8,weekly_hours=40,
            night_shift=False,overtime_allowed=False,rest_days_per_week=2,remuneration_type='MONTHLY',
            remuneration_amount=2400,remuneration_cycle='MONTHLY',accommodation_provided=False,
            meal_provided=True,hazardous_flag=False,mentor_name='虚构企业导师').items():
            setattr(position, key, value)
        decision = db.scalar(select(Decision).where(Decision.application_id == app.id,
            Decision.material_snapshot_id == group.current_material_snapshot_id))
        decision.company_id = company.id
        decision.decision_status = 'ACCEPT_INTENT'
        decision.valid_until = now+timedelta(hours=12)
        group.status = 'LOCKED'
        group.locked_application_id = app.id
        group.locked_by_decision_id = decision.id
        group.teacher_confirm_deadline = now+timedelta(hours=12)
        other_position = InternshipPosition(tenant_id=TID,company_id=company.id,batch_id=record.batch_id,
            campaign_id=campaign.id,title='虚构第二志愿岗位',status='PUBLISHED',headcount=3)
        db.add(other_position); db.flush()
        sibling = InternshipApplication(tenant_id=TID, record_id=record.id, student_id=record.student_id,
            batch_id=record.batch_id,campaign_id=campaign.id,application_type='POSITION',volunteer_no=2,
            position_id=other_position.id,material_snapshot_id=app.material_snapshot_id,status='PENDING_REVIEW')
        db.add(sibling); db.flush()
        sibling_decision = Decision(tenant_id=TID,application_id=sibling.id,volunteer_group_id=group.id,
            campaign_id=campaign.id,batch_id=record.batch_id,company_id=company.id,position_id=other_position.id,
            material_snapshot_id=app.material_snapshot_id,submission_version=group.submission_version,
            decision_status='INTERESTED',effect_status='ACTIVE')
        db.add(sibling_decision); db.flush()
        ids.update(record=record.id, app=app.id, position=position.id, decision=decision.id,
                   company=company.id, sibling=sibling.id, siblingDecision=sibling_decision.id)
        db.commit()
    return ids


def body(ids):
    return dict(applicationId=ids['app'],expectedGroupVersion=0,expectedRecordVersion=0,expectedApplicationVersion=0)


def test_confirmation_http_freezes_placement_consumes_intent_closes_siblings_and_rejects_replay(client, auth_headers, db_mode):
    ids = ready()
    root = f"{BASE}/{ids['campaign']}/volunteer-groups/{ids['0']}"
    denied = client.post(root+'/confirm',headers=auth_headers,json={**body(ids),'expectedGroupVersion':99})
    assert denied.status_code == 409, denied.json()
    success = client.post(root+'/confirm',headers=auth_headers,json=body(ids))
    assert success.status_code == 200, success.json()
    data = success.json()['data']
    assert data['status'] == 'APPROVED' and data['positionId'] == str(ids['position'])
    assert client.post(root+'/confirm',headers=auth_headers,json=body(ids)).status_code == 409
    assert client.post(root+'/return',headers=auth_headers,json={
        'reason':'已确认后不应普通退回','expectedGroupVersion':data['version'],
        'expectedRecordVersion':data['recordVersion']}).status_code == 409
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, ids['record'])
        snapshot = db.get(InternshipPlacementSnapshot,record.current_placement_snapshot_id)
        assert snapshot and snapshot.position_id == ids['position'] and len(snapshot.snapshot_sha256) == 64
        assert record.status == 'PREPARING'  # confirmation never implies onboard clearance
        assert db.get(InternshipPosition,ids['position']).allocated_count == 1
        assert db.get(Decision,ids['decision']).effect_status == 'CONSUMED'
        assert db.get(InternshipApplication,ids['app']).status == 'APPROVED'
        assert db.get(InternshipApplication,ids['sibling']).status == 'CANCELLED'
        assert db.get(Decision,ids['siblingDecision']).effect_status == 'SUPERSEDED'
        legacy = db.scalar(select(InternshipApplication).where(InternshipApplication.record_id == record.id,
            InternshipApplication.campaign_id.is_(None)))
        assert legacy.status == 'PENDING_REVIEW'


@pytest.mark.parametrize('failure', ['window','capacity','qualification','material','advisor'])
def test_confirmation_failures_leave_capacity_group_and_decision_unchanged(client, auth_headers, db_mode, failure):
    ids = ready()
    with get_sessionmaker()() as db:
        if failure == 'window': db.get(InternshipRecruitmentCampaign,ids['campaign']).school_confirm_end_at = datetime.utcnow()-timedelta(minutes=1)
        if failure == 'capacity': db.get(InternshipPosition,ids['position']).headcount = 0
        if failure == 'qualification': db.get(InternshipRecord,ids['record']).eligibility_status = 'DISQUALIFIED'
        if failure == 'material': db.get(InternshipApplication,ids['app']).material_snapshot_id = None
        if failure == 'advisor': db.get(InternshipRecord,ids['record']).advisor_user_id = None
        db.commit()
    response = client.post(f"{BASE}/{ids['campaign']}/volunteer-groups/{ids['0']}/confirm",
        headers=auth_headers,json=body(ids))
    assert response.status_code == 409, response.json()
    with get_sessionmaker()() as db:
        assert db.get(InternshipVolunteerGroup,ids['0']).status == 'LOCKED'
        assert db.get(Decision,ids['decision']).effect_status == 'ACTIVE'
        assert db.get(InternshipPosition,ids['position']).allocated_count == 0
        assert db.get(InternshipRecord,ids['record']).current_placement_snapshot_id is None


def test_return_versions_scope_and_expired_lock_keep_teacher_reason(client, auth_headers, db_mode):
    ids = ready()
    url = f"{BASE}/{ids['campaign']}/volunteer-groups/{ids['0']}/return"
    payload = {'reason':'请补充本人实训作品说明','expectedGroupVersion':0,'expectedRecordVersion':0}
    assert client.post(url,headers=auth_headers,json={'reason':'缺少版本'}).status_code == 400
    assert client.post(url,headers=auth_headers,json={**payload,'expectedRecordVersion':9}).status_code == 409
    set_tenant({'tenantId':str(TID)})
    try:
        with pytest.raises(AppException) as denied:
            svc.return_group(campaign_id=ids['campaign'],group_id=ids['1'],user=MENTOR,reason=payload['reason'],
                expected_group_version=0,expected_record_version=0)
        assert denied.value.http_status == 404
    finally: set_tenant(None)
    with get_sessionmaker()() as db:
        db.get(InternshipVolunteerGroup,ids['0']).teacher_confirm_deadline = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    result = client.post(url,headers=auth_headers,json=payload)
    assert result.status_code == 200, result.json()
    assert result.json()['data']['revisionReason'] == payload['reason']
    assert result.json()['data']['status'] == 'NEEDS_REVISION'
    with get_sessionmaker()() as db:
        assert db.get(Decision,ids['decision']).effect_status == 'EXPIRED'
        assert db.get(InternshipRecord,ids['record']).position_id is None


def test_enterprise_cannot_continue_handling_a_returned_submission(db_mode):
    ids = ready()
    set_tenant({'tenantId':str(TID)})
    try:
        svc.return_group(campaign_id=ids['campaign'],group_id=ids['0'],user=ADMIN,reason='请补充岗位材料',
            expected_group_version=0,expected_record_version=0)
        with get_sessionmaker()() as db:
            with pytest.raises(AppException) as denied:
                enterprise.set_decision_in_tx(db,context=SimpleNamespace(tenant_id=TID,batch_id=ids['batch'],
                    campaign_id=ids['campaign'],company_id=ids['company'],user_id=99118,member_id=None,
                    member_role='HR',claims={}),application_id=ids['sibling'],status='INTERVIEW',
                    interview_at=datetime.utcnow()+timedelta(days=1))
            assert '已退回或撤回' in denied.value.message
            db.rollback()
            assert db.get(Decision,ids['siblingDecision']).decision_status == 'INTERESTED'
            assert db.get(Decision,ids['siblingDecision']).effect_status == 'SUPERSEDED'
    finally: set_tenant(None)


def test_concurrent_school_confirmation_and_enterprise_withdrawal_have_one_consistent_result(db_mode):
    ids = ready(); barrier = Barrier(2); results = []
    def worker(kind):
        set_tenant({'tenantId':str(TID)})
        try:
            barrier.wait(timeout=10)
            if kind == 'school':
                svc.confirm_group(campaign_id=ids['campaign'],group_id=ids['0'],application_id=ids['app'],
                    user=ADMIN,expected_group_version=0,expected_record_version=0,expected_application_version=0)
            else:
                with get_sessionmaker()() as db:
                    enterprise.withdraw_accept_in_tx(db,context=SimpleNamespace(tenant_id=TID,batch_id=ids['batch'],
                        campaign_id=ids['campaign'],company_id=ids['company'],user_id=99118,member_id=None,
                        member_role='HR',claims={}),application_id=ids['app'],reason='企业撤回拟接收说明')
                    db.commit()
            results.append((kind,'ok'))
        except AppException: results.append((kind,'conflict'))
        except Exception as exc: results.append((kind,repr(exc)))
        finally: set_tenant(None)
    threads = [Thread(target=worker,args=(kind,)) for kind in ('school','enterprise')]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=20)
    assert not any(thread.is_alive() for thread in threads)
    assert sorted(result[1] for result in results) == ['conflict','ok'], results
    with get_sessionmaker()() as db:
        group = db.get(InternshipVolunteerGroup,ids['0'])
        record = db.get(InternshipRecord,ids['record'])
        decision = db.get(Decision,ids['decision'])
        if group.status == 'APPROVED':
            assert record.position_id == ids['position'] and decision.effect_status == 'CONSUMED'
        else:
            assert group.status == 'NEEDS_REVISION' and record.position_id is None
            assert decision.effect_status == 'SUPERSEDED'
