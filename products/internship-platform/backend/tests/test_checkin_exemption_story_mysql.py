"""Original exemption return/resubmit and calendar facts with normal roles on isolated MySQL."""
import os
from datetime import datetime
import pytest
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipRecord,InternshipBatch,InternshipCheckinExemption,InternshipAuditTrail,UnifiedTodo
from test_plan_allocation_story_mysql import seed_plan_story,login,ok,ROOT,context
from app.internship_attendance_worker import run_cycle
from app.core.context import get_tenant,set_tenant
from app.models import InternshipLeave,RiskRecord
from app.core.exceptions import AppException
from app.internship_attendance_worker import _checkin_notices
from app.services.message_event_outbox_service import process_pending_outbox
from app.models import InternshipCheckin, InternshipMakeup, MessageEventOutbox, UnifiedMessage, UserRole

STUDENT='/api/v1/mobile/internship/context/checkin-exemptions'
TEACHER='/api/v1/mobile/teacher/internship/context/checkin-exemptions'

@pytest.fixture
def story():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE')!='1':pytest.skip('isolated MySQL opt-in required')
    s=seed_plan_story()
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(s['recordId']));record.status='ONBOARD';record.intern_start_date=datetime(2026,10,1);record.intern_end_date=datetime(2026,10,31)
        batch=db.get(InternshipBatch,int(s['batchId']));batch.start_date=datetime(2026,10,1);batch.end_date=datetime(2026,10,31);db.commit()
    with login(s) as school:
        record=ok(school.get(ROOT+'/intern-students/'+s['recordId']))
        ok(school.post(ROOT+'/intern-students/'+s['recordId']+'/advisor',json={'advisorUserId':str(s['users']['INTERN_MENTOR']),'expectedVersion':record['version']}))
    return s

def body(s,**extra):return {**context(s),'startDate':'2026-10-14','endDate':'2026-10-14','reason':'虚构联调：按批准安排免于本日签到',**extra}

def test_exemption_return_resubmit_same_original_and_calendar_readback(story):
    with login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher:
        first=ok(student.post(STUDENT,json=body(story)))
        rejected=ok(teacher.post(TEACHER+'/'+first['id']+'/review',json={'batchId':story['batchId'],'expectedVersion':first['version'],'action':'REJECT','comment':'请沿原单补充免签安排和责任说明'}))
        assert student.post(STUDENT,json=body(story,id=first['id'],expectedVersion=first['version'])).json()['code']!=0
        revised=ok(student.post(STUDENT,json=body(story,id=first['id'],expectedVersion=rejected['version'],reason='虚构联调：按指导教师意见补充安排与责任说明')))
        assert revised['id']==first['id'] and revised['version']>rejected['version']
        with get_sessionmaker()() as db:
            pending=db.scalars(select(UnifiedTodo).where(UnifiedTodo.tenant_id==int(story['tenantId']),UnifiedTodo.source_biz_id==int(first['id']),UnifiedTodo.source_biz_type=='INTERN_CHECKIN_EXEMPTION',UnifiedTodo.status=='PENDING')).all()
            assert len(pending)==1
        approved=ok(teacher.post(TEACHER+'/'+first['id']+'/review',json={'batchId':story['batchId'],'expectedVersion':revised['version'],'action':'APPROVE','comment':'合成免签安排核对通过'}))
        assert approved['id']==first['id'] and approved['status']=='APPROVED'
        calendar=ok(student.get('/api/v1/mobile/internship/checkin/calendar',params={'batchId':story['batchId'],'month':'2026-10'}))
        assert next(day for day in calendar['days'] if day['date']=='2026-10-14')['status']=='EXEMPT'
        with get_sessionmaker()() as db:
            trails=db.scalars(select(InternshipAuditTrail).where(InternshipAuditTrail.tenant_id==int(story['tenantId']),InternshipAuditTrail.target_id==int(first['id']),InternshipAuditTrail.target_type=='CHECKIN_EXEMPTION').order_by(InternshipAuditTrail.id)).all()
            assert [row.action for row in trails]==['EXEMPTION_APPLY','EXEMPTION_REJECT','EXEMPTION_RESUBMIT','EXEMPTION_APPROVE']
            assert trails[2].detail_json['previous']['reviewComment']=='请沿原单补充免签安排和责任说明'
            assert db.scalar(select(InternshipCheckinExemption).where(InternshipCheckinExemption.id==int(first['id']))).version==approved['version']

def test_withdrawn_original_resubmits_without_duplicate_pending(story):
    with login(story,'STUDENT') as student:
        first=ok(student.post(STUDENT,json=body(story)))
        withdrawn=ok(student.post(STUDENT+'/'+first['id']+'/withdraw',json={**context(story),'expectedVersion':first['version']}))
        revised=ok(student.post(STUDENT,json=body(story,id=first['id'],expectedVersion=withdrawn['version'])))
        assert revised['id']==first['id']
        assert student.post(STUDENT,json=body(story)).json()['code']!=0
        assert len(ok(student.get(STUDENT,params=context(story))))==1

def test_exemption_ownership_batch_length_and_teacher_scope_are_independent(story):
    foreign=seed_plan_story()
    with login(story,'STUDENT') as student,login(story,'OTHER_MENTOR') as unrelated,login(foreign,'STUDENT') as outsider:
        first=ok(student.post(STUDENT,json=body(story)))
        assert unrelated.post(TEACHER+'/'+first['id']+'/review',json={'batchId':story['batchId'],'expectedVersion':first['version'],'action':'APPROVE'}).json()['code']!=0
        assert outsider.post(STUDENT,json=body(story,id=first['id'],expectedVersion=0)).json()['code']!=0
        assert student.post(STUDENT,json=body(story,reason='长'*501)).json()['code']!=0
        assert student.post(STUDENT,json=body(story,batchId=story['batches'][1]['id'],id=first['id'],expectedVersion=0)).json()['code']!=0
        assert ok(student.get(STUDENT,params=context(story)))[0]['status']=='PENDING'


def test_teacher_todo_locates_exact_exemption_and_never_crosses_batch_or_scope(story):
    with login(story,'STUDENT') as student, login(story,'INTERN_MENTOR') as teacher, login(story,'OTHER_MENTOR') as unrelated:
        another=ok(student.post(STUDENT,json=body(story)))
        ok(teacher.post(TEACHER+'/'+another['id']+'/review',json={'batchId':story['batchId'],'expectedVersion':another['version'],'action':'APPROVE','comment':'已核对合成免签安排'}))
        original=ok(student.post(STUDENT,json=body(story,startDate='2026-10-15',endDate='2026-10-15')))
        todos=ok(teacher.get('/api/v1/teacher-mobile/internship/workbench/todos',params={'group':'ATTENDANCE'}))['items']
        target=next(row for row in todos if row['sourceBizId']==original['id'])
        assert target['actionPath']==f'/pages/teacher-internship/checkin-exemption/index?batchId={story["batchId"]}&exemptionId={original["id"]}'
        focused={'batchId':story['batchId'],'status':'ALL','exemptionId':original['id']}
        result=ok(teacher.get(TEACHER,params=focused))
        assert result['total']==1 and [row['id'] for row in result['items']]==[original['id']]
        assert another['id'] not in [row['id'] for row in result['items']]
        assert ok(unrelated.get(TEACHER,params=focused))['total']==0
        wrong=ok(teacher.get(TEACHER,params={**focused,'batchId':story['batches'][1]['id']}))
        assert wrong['total']==0 and wrong['items']==[]
        assert teacher.get(TEACHER,params={**focused,'exemptionId':'wrong'}).status_code==422

def test_attendance_worker_is_scoped_idempotent_and_restores_context(story):
    other=seed_plan_story()
    with get_sessionmaker()() as db:
        # Historical approved leaves are initial fixtures; the worker produces overdue/risk facts.
        selected=InternshipLeave(tenant_id=int(story['tenantId']),internship_id=int(story['recordId']),student_id=int(story['studentId']),leave_type='PERSONAL',start_date='2026-10-13',end_date='2026-10-13',days=1,reason='虚构历史请假，等待自动超期核验',status='APPROVED')
        sibling=db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id==int(story['tenantId']),InternshipRecord.batch_id==int(story['batches'][1]['id'])))
        unrelated=InternshipLeave(tenant_id=int(story['tenantId']),internship_id=sibling.id,student_id=sibling.student_id,leave_type='PERSONAL',start_date='2026-10-13',end_date='2026-10-13',days=1,reason='其他批次虚构历史请假',status='APPROVED')
        db.add_all([selected,unrelated]);db.commit();selected_id,unrelated_id=selected.id,unrelated.id
    previous=get_tenant();set_tenant({'tenantId':'preserved-context'})
    try:
        first=run_cycle(int(story['tenantId']),int(story['batchId']));second=run_cycle(int(story['tenantId']),int(story['batchId']))
        assert first['markedOverdue']==1 and first['risksCreated']==1
        assert first['notificationsProcessed']==1 and first['unassignedRiskIds']==[]
        assert second['markedOverdue']==0 and second['risksCreated']==0
        assert second['notificationsProcessed']==0
        assert get_tenant()=={'tenantId':'preserved-context'}
        with pytest.raises(AppException) as denied:run_cycle(int(other['tenantId']),int(story['batchId']))
        assert denied.value.code == 'NO_PERMISSION'
        with get_sessionmaker()() as db:
            assert db.get(InternshipLeave,selected_id).status=='OVERDUE'
            assert db.get(InternshipLeave,unrelated_id).status=='APPROVED'
            risks=db.scalars(select(RiskRecord).where(RiskRecord.tenant_id==int(story['tenantId']),RiskRecord.source_type=='LEAVE',RiskRecord.source_id==selected_id)).all();assert len(risks)==1
    finally:set_tenant(previous)


def test_attendance_worker_command_runs_once_or_at_explicit_interval(monkeypatch, capsys):
    from app import internship_attendance_worker as worker
    targets = []
    def cycle(tenant_id, batch_id):
        targets.append((tenant_id, batch_id))
        return {'tenantId': str(tenant_id), 'batchId': str(batch_id)}
    monkeypatch.setattr(worker, 'run_cycle', cycle)
    assert worker.main(['--tenant-id', '7', '--batch-id', '8', '--once']) == 0
    assert targets == [(7, 8)]
    intervals = []
    def pause(seconds):
        intervals.append(seconds)
        if len(intervals) == 2:
            raise KeyboardInterrupt
    monkeypatch.setattr(worker.time, 'sleep', pause)
    with pytest.raises(KeyboardInterrupt):
        worker.main(['--tenant-id', '7', '--batch-id', '8', '--interval', '3'])
    assert targets == [(7, 8)] * 3 and intervals == [3, 3]
    assert len(capsys.readouterr().out.splitlines()) == 3


def test_leave_risk_closes_only_through_original_return_confirmation(story):
    with get_sessionmaker()() as db:
        leave=InternshipLeave(tenant_id=int(story['tenantId']),internship_id=int(story['recordId']),
            student_id=int(story['studentId']),leave_type='PERSONAL',start_date='2026-10-13',end_date='2026-10-13',
            days=1,reason='虚构历史请假前置，正式调度与销假仍走权威命令',status='APPROVED')
        db.add(leave);db.commit();leave_id=str(leave.id)
    run_cycle(int(story['tenantId']),int(story['batchId']))
    with get_sessionmaker()() as db:
        risk=db.scalar(select(RiskRecord).where(RiskRecord.tenant_id==int(story['tenantId']),
            RiskRecord.source_type=='LEAVE',RiskRecord.source_id==int(leave_id)))
        risk_id=str(risk.id)
    path='/api/v1/mobile/internship/context/leaves/'+leave_id
    with login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher:
        risk=ok(teacher.get(ROOT+'/risks/'+risk_id))
        assert not risk['closeAllowed'] and risk['sourceStatus']=='OVERDUE'
        handled=ok(teacher.post(ROOT+'/risks/'+risk_id+'/handle',json={'expectedVersion':risk['version'],'comment':'已联系学生核实返岗'}))
        denied=teacher.post(ROOT+'/risks/'+risk_id+'/close',json={'expectedVersion':handled['version'],'result':'RESOLVED','comment':'尝试提前关闭应被拒绝'})
        assert denied.json()['bizCode']=='DATA_CONFLICT'
        leave=ok(student.get(path,params=context(story)))
        returned=ok(student.post(path+'/return',json={**context(story),'expectedVersion':leave['version'],'note':'虚构学生已返岗，提交原单销假'}))
        assert not ok(teacher.get(ROOT+'/risks/'+risk_id))['closeAllowed']
        ok(teacher.post('/api/v1/mobile/teacher/internship/context/leaves/'+leave_id+'/ack-return',
            json={'batchId':story['batchId'],'expectedVersion':returned['version'],'evidenceFileId':'','note':'已核实本人返岗并确认原单销假'}))
        assert ok(teacher.get(ROOT+'/risks/'+risk_id))['status']=='CLOSED'
        with get_sessionmaker()() as db:
            row=db.get(RiskRecord,int(risk_id));row.source_id=int(leave_id)+1000000;db.commit()
        assert ok(teacher.get(ROOT+'/risks/'+risk_id))['sourceIntegrity']=='BROKEN'


def prepare_attendance(story,monkeypatch):
    from zoneinfo import ZoneInfo
    from app import internship_attendance_worker as worker
    now=datetime(2026,10,16,12,tzinfo=ZoneInfo('Asia/Shanghai'))
    monkeypatch.setattr(worker,'local_now',lambda:now)
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,int(story['batchId']))
        batch.rules_config={**(batch.rules_config or {}),'checkin':{'requireDaily':True,'reminderTime':'11:00'}}
        db.commit()
    return now


@pytest.mark.parametrize('covered',['NONE','LEAVE','EXEMPT','SIGNED','MAKEUP'])
def test_unsigned_messages_match_calendar_exclusions_and_are_deduplicated(story,monkeypatch,covered):
    prepare_attendance(story,monkeypatch)
    with get_sessionmaker()() as db:
        fields={'tenant_id':int(story['tenantId']),'internship_id':int(story['recordId']),'student_id':int(story['studentId'])}
        if covered=='LEAVE':db.add(InternshipLeave(**fields,leave_type='PERSONAL',start_date='2026-10-14',end_date='2026-10-14',days=1,reason='历史批准事假前置',status='APPROVED'))
        if covered=='EXEMPT':db.add(InternshipCheckinExemption(**fields,batch_id=int(story['batchId']),start_date='2026-10-14',end_date='2026-10-14',reason='历史批准免签前置',status='APPROVED'))
        if covered in ('SIGNED','MAKEUP'):db.add(InternshipCheckin(tenant_id=fields['tenant_id'],internship_id=fields['internship_id'],checkin_date='2026-10-14',result='RECORDED'))
        if covered=='MAKEUP':db.add(InternshipMakeup(**fields,checkin_date='2026-10-14',makeup_type='OTHER',reason='历史已批准补卡前置',status='APPROVED'))
        db.commit()
    set_tenant(int(story['tenantId']))
    with get_sessionmaker()() as db:
        first=_checkin_notices(db,int(story['tenantId']),int(story['batchId']));db.commit()
    process_pending_outbox(limit=len(first),outbox_ids=first)
    with get_sessionmaker()() as db:
        second=_checkin_notices(db,int(story['tenantId']),int(story['batchId']));db.commit()
    assert set(first)==set(second)
    assert process_pending_outbox(limit=len(second),outbox_ids=second)==0
    with get_sessionmaker()() as db:
        events=db.scalars(select(MessageEventOutbox).where(MessageEventOutbox.tenant_id==int(story['tenantId']))).all()
        assert sum(e.event_code=='INTERNSHIP.CHECKIN_REMIND' for e in events)==1
        assert sum(e.event_code=='INTERNSHIP.CHECKIN_STREAK' for e in events)==(covered=='NONE')
        messages=db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id==int(story['tenantId']))).all()
        assert len(messages)==1+(covered=='NONE')
    with login(story,'STUDENT') as student:
        calendar=ok(student.get('/api/v1/mobile/internship/checkin/calendar',params={'batchId':story['batchId'],'month':'2026-10'}))
        status=next(d['status'] for d in calendar['days'] if d['date']=='2026-10-14')
        assert status=={'NONE':'ABSENT','LEAVE':'LEAVE','EXEMPT':'EXEMPT','SIGNED':'CHECKIN','MAKEUP':'MAKEUP'}[covered]


def test_unsigned_configuration_and_revoked_advisor_never_expand_delivery(story,monkeypatch):
    from app.modules.internship.schemas.internship import CheckinRule
    prepare_attendance(story,monkeypatch)
    assert CheckinRule().reminderTime is None and CheckinRule(reminderTime='00:00').reminderTime=='00:00'
    with pytest.raises(ValueError):CheckinRule(reminderTime='25:00')
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,int(story['batchId']))
        batch.rules_config={'checkin':{'requireDaily':False,'reminderTime':'00:00'}};db.commit()
    set_tenant(int(story['tenantId']))
    with get_sessionmaker()() as db:assert _checkin_notices(db,int(story['tenantId']),int(story['batchId']))==[]
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,int(story['batchId']));batch.rules_config={'checkin':{'requireDaily':True}}
        role=db.scalar(select(UserRole).where(UserRole.tenant_id==int(story['tenantId']),UserRole.user_id==story['users']['INTERN_MENTOR']))
        role.status='DISABLED';db.commit()
    with get_sessionmaker()() as db:assert _checkin_notices(db,int(story['tenantId']),int(story['batchId']))==[]


def test_parallel_attendance_cycles_deliver_each_target_once(story,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    prepare_attendance(story,monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:run_cycle(int(story['tenantId']),int(story['batchId'])),range(2)))
    assert sum(x['notificationsProcessed'] for x in outcomes)==2
    with get_sessionmaker()() as db:
        assert len(db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id==int(story['tenantId']))).all())==2


def test_reminder_waits_for_local_cutoff_and_does_not_count_today_as_an_absent_day(story,monkeypatch):
    from app import internship_attendance_worker as worker
    from datetime import timedelta
    now=prepare_attendance(story,monkeypatch)
    with get_sessionmaker()() as db:
        db.get(InternshipRecord,int(story['recordId'])).intern_start_date=datetime(2026,10,14);db.commit()
    set_tenant(int(story['tenantId']))
    monkeypatch.setattr(worker,'local_now',lambda:now.replace(hour=10,minute=59))
    with get_sessionmaker()() as db:assert _checkin_notices(db,int(story['tenantId']),int(story['batchId']))==[]
    monkeypatch.setattr(worker,'local_now',lambda:now.replace(hour=11,minute=0))
    with get_sessionmaker()() as db:
        events=_checkin_notices(db,int(story['tenantId']),int(story['batchId']));db.commit()
        assert len(events)==1 and db.get(MessageEventOutbox,events[0]).event_code=='INTERNSHIP.CHECKIN_REMIND'
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,int(story['recordId']));record.intern_end_date=now-timedelta(days=1);db.commit()
    with get_sessionmaker()() as db:assert _checkin_notices(db,int(story['tenantId']),int(story['batchId']))==[]
