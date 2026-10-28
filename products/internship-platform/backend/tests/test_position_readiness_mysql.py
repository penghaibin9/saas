"""School publication previews and writes share the same daily-check-in gate."""
from datetime import datetime, timedelta
import os

import pytest
from uuid import uuid4
from types import SimpleNamespace
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import EmpCompany, InternshipBatch, InternshipPosition, InternshipEnterpriseEval, InternshipRecord, InternshipCheckin, InternshipFinalScore
from app.modules.internship.services.internship_student_catalog_facade_service import _public_row
from app.modules.internship.services.internship_enterprise_eval_service import _row as evaluation_row
from test_plan_allocation_story_mysql import seed_plan_story, login, ok, ROOT


def test_midnight_exception_reads_same_local_day_evidence_and_completed_audit():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':pytest.skip('explicit isolated MySQL opt-in required')
    from app.models import AttendanceException
    story=seed_plan_story();stamp=datetime(2026,10,18,23,46)
    with get_sessionmaker()() as db:
        db.add(InternshipCheckin(tenant_id=int(story['tenantId']),internship_id=int(story['recordId']),checkin_date='2026-10-19',checkin_at=stamp,result='OUT_OF_RANGE',lat=28.5,lng=112.3,gps_accuracy=15))
        exc=AttendanceException(tenant_id=int(story['tenantId']),internship_id=int(story['recordId']),exception_type='OUT_OF_RANGE',exception_date=stamp,distance_km=1,status='PENDING_HANDLE')
        db.add(exc);db.commit();exc_id=str(exc.id)
    path=ROOT+'/exceptions/'+exc_id
    with login(story) as school:
        before=ok(school.get(path));assert before['locationEvidence']['available'] and before['locationEvidence']['checkinLat']==28.5
        comment='纯虚构联调：按学校日期核对同一原始打卡，不伪造现场证据'
        ok(school.post(path+'/handle',json={'action':'REASONABLE','comment':comment,'expectedVersion':before['version']}))
        after=ok(school.get(path));trail=after['trail'][-1]
        assert after['status']=='COMPLETED' and trail['title']=='标记合理' and trail['resultLabel']=='已标记合理' and trail['desc']==comment and trail['actor']


@pytest.mark.parametrize('elapsed,expected_week,approved',[(0,1,True),(3,1,True),(7,2,False)])
def test_approved_weekly_home_only_advances_when_school_week_advances(monkeypatch,elapsed,expected_week,approved):
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':pytest.skip('explicit isolated MySQL opt-in required')
    from app.models import WeeklyReport
    from app.modules.internship.services import internship_student_dashboard_service as service
    day=datetime(2026,10,19,8);monkeypatch.setattr(service,'local_now',lambda:day)
    story=seed_plan_story()
    with get_sessionmaker()() as db:
        rec=db.get(InternshipRecord,int(story['recordId']));rec.status='ONBOARD';rec.intern_start_date=day-timedelta(days=elapsed);rec.intern_end_date=day+timedelta(days=14)
        db.add(WeeklyReport(tenant_id=int(story['tenantId']),internship_id=rec.id,week_number=1,status='APPROVED',work_content='虚构本周报告',harvest_content='虚构收获',plan_content='虚构计划'))
        db.commit()
    with login(story,'STUDENT') as student:
        row=ok(student.get('/api/v1/mobile/internship/context/my',params={'batchId':story['batchId']}))
        assert row['weekly']['weekNumber']==expected_week and row['weekly'].get('approved') is approved


@pytest.mark.parametrize('existing',[None,datetime(2026,10,17)])
def test_onboarding_uses_school_calendar_day_after_utc_midnight_boundary(monkeypatch,existing):
    from contextlib import nullcontext
    from app.modules.internship.services import internship_student_service as service, internship_student_age
    class Clock(datetime):
        @classmethod
        def utcnow(cls): return cls(2026,10,18,16,30)
    record=SimpleNamespace(id=1,status='READY',intern_start_date=existing,version=0)
    db=SimpleNamespace(commit=lambda:None)
    monkeypatch.setattr(service,'datetime',Clock)
    monkeypatch.setattr(internship_student_age,'policy_today',lambda:datetime(2026,10,19).date())
    monkeypatch.setattr(service,'session',lambda:nullcontext(db))
    monkeypatch.setattr(service,'_get_for_update',lambda *args:record)
    monkeypatch.setattr(service,'_assert_write_scope',lambda *args:None)
    monkeypatch.setattr(service,'_require_record_version',lambda *args:None)
    monkeypatch.setattr(service,'_onboard_blockers',lambda *args:([],{'ruleVersion':'test','blockers':[]}))
    monkeypatch.setattr(service,'_trail',lambda *args:None)
    monkeypatch.setattr(service,'_row_of',lambda *args:record)
    saved=service.set_status('1','ONBOARD',expected_version=0)
    assert saved.intern_start_date==(existing or datetime(2026,10,19))
    assert saved.status=='ONBOARD' and saved.version==1


def test_school_can_correct_start_while_preserving_existing_planned_end_but_cannot_set_new_future_dates():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    from app.modules.internship.services.internship_student_age import policy_today
    day=policy_today();story=seed_plan_story();planned=datetime.combine(day+timedelta(days=10),datetime.min.time())
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(story['recordId']));record.status='ONBOARD'
        record.intern_start_date=datetime.combine(day-timedelta(days=1),datetime.min.time());record.intern_end_date=planned
        batch=db.get(InternshipBatch,record.batch_id);batch.start_date=record.intern_start_date;batch.end_date=planned
        version=int(record.version or 0);db.commit()
    path=ROOT+'/intern-students/'+story['recordId']
    payload={'expectedVersion':version,'internStartDate':day.isoformat(),'internEndDate':planned.date().isoformat(),'periodReason':'纯虚构联调：核对学校业务日期，保留既有计划结束日期'}
    with login(story) as school:
        saved=ok(school.put(path,json=payload))
        assert saved['internStartDate']==day.isoformat() and saved['internEndDate']==planned.date().isoformat()
        for fields in [{'internStartDate':(day+timedelta(days=1)).isoformat()}, {'internEndDate':(day+timedelta(days=9)).isoformat()}]:
            rejected=school.put(path,json={**payload,'expectedVersion':saved['version'],**fields})
            assert rejected.status_code in (400,422)
        assert ok(school.get(path))['version']==saved['version']
    with get_sessionmaker()() as db:
        assert db.get(InternshipRecord,int(story['recordId'])).intern_end_date==planned


@pytest.mark.parametrize('start,end',[(None,None),(None,datetime(2026,12,31)),(datetime(2026,10,18),None),(datetime(2026,10,18),datetime(2026,12,30))])
def test_agreement_period_before_onboarding_uses_explicit_batch_plan_without_writing_actual_dates(monkeypatch,start,end):
    from app.modules.internship.services import internship_agreement_service as service
    batch=SimpleNamespace(start_date=datetime(2026,10,1),end_date=datetime(2026,12,31))
    record=SimpleNamespace(intern_start_date=start,intern_end_date=end,batch_id=10,advisor_name='',enterprise_mentor_name='',enterprise_name='虚构企业',position_name='虚构新岗')
    agreement=SimpleNamespace(enterprise_name='虚构企业',position_name='虚构新岗')
    db=SimpleNamespace(get=lambda *args:SimpleNamespace(school_name='虚构学校'))
    monkeypatch.setattr(service,'_tid',lambda:11)
    monkeypatch.setattr(service,'tenant_get',lambda *args:batch)
    body=service._render_body(db,SimpleNamespace(body='{{internStartDate}}|{{internEndDate}}|{{internPeriod}}'),record,None,agreement)
    first,last,period=body.split('|')
    assert first.endswith(service._cn_date(start or batch.start_date)) and last.endswith(service._cn_date(end or batch.end_date))
    assert ('批次计划' in period)==(start is None or end is None)
    assert (record.intern_start_date,record.intern_end_date)==(start,end)


def test_student_catalog_preserves_declared_rest_days_and_false_overtime():
    for days in [0, 2]:
        position = InternshipPosition(id=1, rest_days_per_week=days, overtime_allowed=False)
        row = _public_row(position, EmpCompany(id=2, name='虚构企业'), {}, major_matched=True)
        assert row['restDaysPerWeek'] == days and row['overtime'] is False


def test_evaluation_exposes_actual_record_phase_and_string_batch_context():
    for status in ['ONBOARD', 'ASSESSING']:
        row = evaluation_row(InternshipEnterpriseEval(id=94, internship_id=13045),
            InternshipRecord(batch_id=9007199254741001, status=status), None)
        assert row['internshipStatus'] == status and row['batchId'] == '9007199254741001'


def test_formal_document_read_model_carries_utc_without_changing_stored_timestamp():
    from app.models import InternshipFormalDocument
    from app.modules.internship.services.internship_formal_document_service import _view
    stored=datetime(2026,10,18,13,47,29)
    row=InternshipFormalDocument(id=1,internship_id=2,student_id=3,batch_id=4,document_version=1,generated_at=stored)
    value=datetime.fromisoformat(_view(row)['generatedAt'])
    assert value.utcoffset()==timedelta(0) and value.hour==13
    assert row.generated_at==stored and row.generated_at.tzinfo is None


@pytest.mark.parametrize('path',['/api/v1/portal/internship/context/agreements','/api/v1/mobile/internship/context/agreements'])
def test_pc_agreement_list_uses_explicit_record_when_one_student_has_two_batches(path):
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    story = seed_plan_story()
    with get_sessionmaker()() as db:
        second = InternshipRecord(tenant_id=int(story['tenantId']), student_id=int(story['studentId']),
            batch_id=int(story['batches'][1]['id']), status='PREPARING', eligibility_status='QUALIFIED')
        db.add(second); db.commit(); second_id = str(second.id)
        other = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id==int(story['tenantId']),
            InternshipRecord.student_id!=int(story['studentId'])))
        other_id = str(other.id)
    contexts = [{'batchId':story['batchId'],'internshipId':story['recordId']},
        {'batchId':story['batches'][1]['id'],'internshipId':second_id}]
    with login(story) as school:
        ids = [ok(school.post(ROOT+'/agreements',json={'internshipId':ctx['internshipId']}))['id'] for ctx in contexts]
    with login(story,'STUDENT') as student:
        for ctx, agreement_id in zip(contexts, ids):
            rows = ok(student.get(path,params=ctx))
            assert [row['id'] for row in rows] == [agreement_id]
            assert rows[0]['internId']==ctx['internshipId'] and rows[0]['batchId']==ctx['batchId']
        assert student.get(path).status_code == 400
        assert student.get(path,params={'batchId':contexts[0]['batchId']}).status_code == 400
        assert student.get(path,params={**contexts[0],'internshipId':other_id}).status_code in (403,404,409)
        assert student.get(path,params={**contexts[0],'internshipId':second_id}).status_code in (403,404,409)


@pytest.mark.parametrize('checkin_result', ['NO_LOCATION','NORMAL','RECORDED','LEAVE','MOCK_LOCATION','OUT_OF_RANGE'])
def test_no_location_can_reach_makeup_approval_without_rewriting_original_location(checkin_result):
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    story=seed_plan_story();today=datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(story['recordId']));record.status='ONBOARD'
        record.intern_start_date=today;record.intern_end_date=today+timedelta(days=1)
        batch=db.get(InternshipBatch,record.batch_id);batch.rules_config={**(batch.rules_config or {}),'checkin':{'requiredDays':1}}
        checkin=InternshipCheckin(tenant_id=int(story['tenantId']),internship_id=record.id,
            checkin_date=today.date().isoformat(),checkin_at=datetime.utcnow(),result=checkin_result)
        db.add(checkin);db.commit();checkin_id=checkin.id
    context={'batchId':story['batchId'],'internshipId':story['recordId']}
    with login(story,'STUDENT') as student:
        response=student.post('/api/v1/portal/internship/context/makeups',json={**context,
            'checkinDate':today.date().isoformat(),'makeupType':'MISSING','reason':'纯虚构联调：电脑无定位留痕交学校人工核对出勤'})
        if checkin_result!='NO_LOCATION':
            assert response.status_code==400 and response.json()['bizCode']=='DATA_CONFLICT' and '不能重复' in response.json()['message']
            return
        pending=ok(response)
    with login(story) as school:
        approved=ok(school.post(ROOT+'/makeups/'+pending['id']+'/approve',json={'expectedVersion':pending['version'],'comment':'本地虚构联调核对通过'}))
        assert approved['status']=='APPROVED'
    from app.core.context import get_tenant,set_tenant
    from app.modules.internship.services.internship_compliance_facts import material_quantity_facts
    previous=get_tenant()
    try:
        set_tenant(int(story['tenantId']))
        with get_sessionmaker()() as db:
            assert db.get(InternshipCheckin,checkin_id).result=='NO_LOCATION'
            facts=material_quantity_facts(db,db.get(InternshipRecord,int(story['recordId'])),db.get(InternshipBatch,int(story['batchId'])))
            assert facts['checkin']['actual']==1
    finally:
        set_tenant(previous)


def test_scoped_audit_delivery_keeps_other_school_pending_and_replays_once():
    from app.modules.internship.services.internship_audit_service import process_pending
    for invalid in [0,-1,True,'1']:
        with pytest.raises(ValueError):
            process_pending(tenant_id=invalid)
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    from app.models.audit_outbox import AuditOutbox
    from app.models.audit import SecurityAuditLog
    schools=[seed_plan_story(),seed_plan_story()];events=[uuid4().hex,uuid4().hex]
    with get_sessionmaker()() as db:
        for story,event_id in zip(schools,events):
            db.add(AuditOutbox(tenant_id=int(story['tenantId']),event_id=event_id,
                event_type='INTERNSHIP_PAGE_TEST',payload_json={'tenantId':story['tenantId'],'targetType':'TEST_ONLY','targetId':'1'}))
        db.commit()
    target=int(schools[0]['tenantId'])
    assert process_pending(limit=1000,tenant_id=target)['failed']==0
    assert process_pending(limit=1000,tenant_id=target)['failed']==0
    with get_sessionmaker()() as db:
        own=db.scalar(select(AuditOutbox).where(AuditOutbox.event_id==events[0]))
        other=db.scalar(select(AuditOutbox).where(AuditOutbox.event_id==events[1]))
        assert own.status=='PROCESSED' and other.status=='PENDING'
        assert len(list(db.scalars(select(SecurityAuditLog.id).where(SecurityAuditLog.tenant_id==target,SecurityAuditLog.source_event_id==events[0]))))==1


def test_actual_period_updates_require_school_scope_current_version_and_unpublished_score():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    from app.modules.internship.services.internship_student_age import policy_today
    day=policy_today();story=seed_plan_story()
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(story['recordId']));record.status='ASSESSING'
        batch=db.get(InternshipBatch,record.batch_id)
        batch.start_date=datetime.combine(day-timedelta(days=1),datetime.min.time());batch.end_date=datetime.combine(day,datetime.min.time())
        version=int(record.version or 0);db.commit()
    path=ROOT+'/intern-students/'+story['recordId']
    payload={'expectedVersion':version,'internStartDate':day.isoformat(),'internEndDate':day.isoformat(),'periodReason':'纯虚构联调：学校核对当日实际实习日期'}
    with login(story,'INTERN_MENTOR') as teacher:
        assert teacher.put(path,json=payload).status_code==403
    with login(story) as school:
        saved=ok(school.put(path,json=payload))
        assert saved['internStartDate']==saved['internEndDate']==day.isoformat()
        assert saved['version']==version+1
        assert school.put(path,json=payload).json()['bizCode']=='DATA_CONFLICT'
        for fields in [{'internEndDate':(day+timedelta(days=1)).isoformat()},
                       {'internStartDate':(day+timedelta(days=1)).isoformat()},
                       {'internStartDate':(day-timedelta(days=2)).isoformat()}, {'periodReason':'短'}]:
            rejected=school.put(path,json={**payload,'expectedVersion':saved['version'],**fields})
            assert rejected.status_code in (400,422)
        with get_sessionmaker()() as db:
            grade=InternshipFinalScore(tenant_id=int(story['tenantId']),internship_id=int(story['recordId']),student_id=int(story['studentId']),batch_id=int(story['batchId']),status='PUBLISHED')
            db.add(grade);db.commit();grade_id=str(grade.id)
        blocked=school.put(path,json={**payload,'expectedVersion':saved['version']})
        assert blocked.json()['bizCode']=='DATA_CONFLICT' and blocked.json()['details']['scoreId']==grade_id
        assert ok(school.get(path))['version']==saved['version']
    other=seed_plan_story()
    with login(other) as foreign:
        assert foreign.put(path,json=payload).status_code in (403,404)


@pytest.mark.parametrize('daily', [True, False])
def test_publication_preview_matches_write_and_zero_coordinates_remain_valid(daily):
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    story = seed_plan_story()
    with get_sessionmaker()() as db:
        batch = db.get(InternshipBatch, int(story['batchId']))
        batch.rules_config = {**(batch.rules_config or {}), 'checkin': {'requireDaily': daily}}
        company = EmpCompany(tenant_id=int(story['tenantId']), name='发布检查虚构企业',
            status='ACTIVE', coop_status='ACTIVE', qualification_status='PASSED',
            blacklist=False, access_valid_until=datetime.utcnow()+timedelta(days=30))
        db.add(company); db.commit(); company_id = str(company.id)
    with login(story) as school:
        agreement = ok(school.post(ROOT+'/agreements', json={'internshipId': story['recordId']}))
        assert '批次计划：' in ok(school.get(ROOT+'/agreements/'+agreement['id']))['renderedBody']
        draft = ok(school.post(ROOT+'/positions', json={
            'companyId': company_id, 'batchId': story['batchId'], 'title': '发布预检合成岗位',
            'headcount': 1, 'workLocation': '虚构地点', 'workAddress': '虚构地点一号',
            'workContent': '按培养方向完成软件测试与实践记录', 'dailyHours': 8, 'weeklyHours': 40,
            'nightShift': False, 'overtimeAllowed': False, 'restDaysPerWeek': 2,
            'remunerationType': 'UNPAID', 'accommodationProvided': False,
            'mealProvided': False, 'hazardousFlag': False}))
        path = ROOT+'/positions/'+draft['id']
        preview = ok(school.get(path))
        assert preview['publishable'] is (not daily)
        assert any(item['code']=='CHECKIN_LOCATION_REQUIRED' for item in preview['compliance']['blockers']) is daily
        pending = ok(school.post(path+'/status', json={'action': 'SUBMIT', 'expectedVersion': draft['version']}))
        if daily:
            denied = school.post(path+'/status', json={'action': 'PUBLISH', 'expectedVersion': pending['version']})
            assert denied.json()['bizCode']=='DATA_CONFLICT'
            assert '打卡中心' in denied.json()['message']
            pending = ok(school.put(path, json={'expectedVersion': pending['version'],
                'geofenceLat': 0, 'geofenceLng': 0, 'geofenceRadiusM': 500}))
            preview = ok(school.get(path))
            assert preview['publishable'] is True and preview['geofenceLat']==0 and preview['geofenceLng']==0
        published = ok(school.post(path+'/status', json={'action': 'PUBLISH', 'expectedVersion': pending['version']}))
        assert published['status']=='PUBLISHED' and ok(school.get(path))['publishable'] is True
