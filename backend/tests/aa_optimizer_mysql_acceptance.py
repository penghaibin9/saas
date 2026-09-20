"""Real Alembic/MySQL integration; isolated rows retained, no create_all or schema reset.

Run with --noconftest against a dedicated yueke_optimizer_test_* database.
"""
import json
from datetime import datetime, timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, func, text, update
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.context import set_tenant, set_current_user
from app.db.session import get_sessionmaker, get_engine
from app.models import (Tenant, PlatformConfig, Role, Permission, RolePermission, User, UserRole,
                        AaTerm, AaTimeSlot, AaClassroom, AaCourse, AaTeachingTaskBatch, AaTeachingTask,
                        AaScheduleBatch, AaScheduleItem, AaScheduleRule, AaTeachingClass,
                        AaTeachingClassTeacher, AaTeachingClassRosterVersion, AaTeachingClassMember, StudentProfile)
from app.modules.academic_affairs.services import schedule_optimizer_jobs_service as service
from app.modules.academic_affairs.services.schedule_optimizer_apply_service import apply_candidate
from app.modules.academic_affairs.services.schedule_optimizer_worker_service import run_pending
from app.modules.academic_affairs.optimizer.persistence import jobs, snapshots
from app.modules.academic_affairs.services.academic_affairs_roster_consumer_service import roster_hash
from app.core.exceptions import AppException


@pytest.fixture()
def scenario():
    url=make_url(settings.effective_database_url)
    assert url.host in {'127.0.0.1','localhost'} and url.database.startswith('yueke_optimizer_test_')
    assert get_engine().dialect.name=='mysql'
    with get_engine().connect() as db:
        assert db.execute(text('select version_num from alembic_version')).scalar()=='20260914_aa_opt_candidates'
    suffix=uuid4().hex[:10]
    tid=8000000000000000000+int(suffix,16)
    set_tenant(tid)
    with get_sessionmaker()() as db:
        db.add(Tenant(id=tid,tenant_code='opt-'+suffix,school_name='智能排课隔离验收学校',status='ACTIVE'))
        db.add(PlatformConfig(tenant_id=tid,config_type='TENANT_META',config_key='-',
                              config_json={'status':'trial','packageCode':'trial','expireAt':'2030-01-01T00:00:00'}))
        role=Role(tenant_id=tid,role_code='ACADEMIC_ADMIN',role_name='教务管理员',role_type='CUSTOM',status='ACTIVE')
        db.add(role);db.flush()
        for code in ['academicAffairs.schedule.view','academicAffairs.schedule.edit',
                     'academicAffairs.schedule.rule.manage','academicAffairs.schedule.publish']:
            perm=db.scalar(select(Permission).where(Permission.permission_code==code))
            if perm is None:
                perm=Permission(permission_code=code,permission_name='排课验收权限',module_code='academicAffairs',action='MANAGE')
                db.add(perm);db.flush()
            db.add(RolePermission(tenant_id=tid,role_id=role.id,permission_id=perm.id,status='ACTIVE'))
        accounts=[]
        for n in [1,2]:
            user=User(tenant_id=tid,login_name=f'opt-admin-{n}',real_name=f'验收教务员{n}',
                      user_type='TEACHER',password_hash='unusable-fixture-password',status='ACTIVE')
            db.add(user);db.flush()
            db.add(UserRole(tenant_id=tid,user_id=user.id,role_id=role.id,status='ACTIVE'))
            accounts.append({'userId':f'db-{user.id}','tenantId':str(tid),'currentRoleCode':'ACADEMIC_ADMIN',
                             'activeContextId':f'role:{role.id}','loginName':user.login_name,'userType':'TEACHER'})
        term=AaTerm(tenant_id=tid,year_code='2026-2027',term_no=1,term_name='排课验收学期',
                    start_date=datetime(2026,9,14),end_date=datetime(2026,9,27),teaching_weeks=2,status='PUBLISHED',is_current=True)
        db.add(term);db.flush()
        for no,start,end in [(1,'08:00','08:45'),(2,'08:55','09:40'),(3,'10:00','10:45'),(4,'10:55','11:40')]:
            db.add(AaTimeSlot(tenant_id=tid,slot_no=no,start_time=start,end_time=end,campus_code='MAIN',enabled=True,status='ENABLED'))
        room=AaClassroom(tenant_id=tid,room_name='验收实训室',building_code='A',building_name='实训楼',room_code='101',
                         room_type='LAB',capacity=30,campus_code='MAIN',status='AVAILABLE',allow_schedule=True,is_exclusive=False)
        course=AaCourse(tenant_id=tid,course_code='OPT101',course_name='实训课',status='ENABLED')
        db.add_all([room,course]);db.flush()
        task_batch=AaTeachingTaskBatch(tenant_id=tid,term_id=term.id,batch_name='验收教学任务',status='APPROVED')
        batch=AaScheduleBatch(tenant_id=tid,term_id=term.id,batch_name='验收课表草稿',status='DRAFT')
        db.add_all([task_batch,batch]);db.flush()
        task=AaTeachingTask(tenant_id=tid,batch_id=task_batch.id,course_id=course.id,course_name='实训课',
                            teaching_class_name='验收教学班',teacher_key='opt-teacher',teacher_name='验收教师',
                            expected_students=2,weekly_hours=4,total_hours=8,start_week=1,end_week=2,
                            required_room_type='LAB',formation_mode='ADMIN_FIXED',status='READY',no_auto_schedule=False)
        db.add(task);db.flush()
        tc=AaTeachingClass(tenant_id=tid,teaching_task_id=task.id,term_id=term.id,course_id=course.id,
                           class_code='OPT01',class_name='验收教学班',class_type='ADMIN',roster_status='LOCKED',status='ACTIVE')
        db.add(tc);db.flush()
        students=[StudentProfile(tenant_id=tid,student_no=f'OPT{n}',real_name=f'验收学生{n}',status='ACTIVE') for n in [1,2]]
        db.add_all(students);db.flush()
        from app.models import StudentAccountLink
        readers={}
        for role_code,login,user_type in [('ACADEMIC_TEACHER','opt-teacher','TEACHER'),('STUDENT','OPT1','STUDENT')]:
            reader_role=Role(tenant_id=tid,role_code=role_code,role_name=role_code,role_type='CUSTOM',status='ACTIVE')
            reader=User(tenant_id=tid,login_name=login,real_name='验收教师' if user_type=='TEACHER' else '验收学生1',
                        user_type=user_type,password_hash='unusable-fixture-password',status='ACTIVE')
            db.add_all([reader_role,reader]);db.flush()
            db.add(UserRole(tenant_id=tid,user_id=reader.id,role_id=reader_role.id,status='ACTIVE'))
            perm=db.scalar(select(Permission).where(Permission.permission_code=='academicAffairs.schedule.view'))
            db.add(RolePermission(tenant_id=tid,role_id=reader_role.id,permission_id=perm.id,status='ACTIVE'))
            readers[user_type.lower()]={'userId':f'db-{reader.id}','tenantId':str(tid),'currentRoleCode':role_code,
                'activeContextId':f'role:{reader_role.id}','loginName':login,'userType':user_type}
            if user_type=='STUDENT':
                db.add(StudentAccountLink(tenant_id=tid,student_id=students[0].id,user_id=reader.id,
                                          link_status='ACTIVE',bound_login_name=login))
        version=AaTeachingClassRosterVersion(tenant_id=tid,teaching_class_id=tc.id,version_no=1,
                    source_type='ADMIN_CLASS',member_count=2,roster_hash=roster_hash([s.id for s in students]),status='LOCKED')
        db.add(version);db.flush()
        tc.current_roster_version_id=version.id;tc.current_roster_version_no=1
        for sid in [s.id for s in students]:
            db.add(AaTeachingClassMember(tenant_id=tid,teaching_class_id=tc.id,roster_version_id=version.id,
                                         student_id=sid,source_type='ADMIN_CLASS',status='ACTIVE'))
        db.add(AaTeachingClassTeacher(tenant_id=tid,teaching_class_id=tc.id,teacher_key='opt-teacher',
                                      teacher_name='验收教师',role_type='PRIMARY',start_week=1,end_week=2,status='ACTIVE'))
        db.add(AaScheduleRule(tenant_id=tid,term_id=term.id,batch_id=batch.id,rule_key='AUTO_WEEKDAYS',
                              rule_value_json='[1,2,3,4,5]',status='ENABLED'))
        db.commit()
        result={'tid':tid,'user':accounts[0],'other':accounts[1],'batch':str(batch.id),
                'task':str(task.id),'term':term.id,'room':room.id,'studentId':str(students[0].id),**readers}
    set_current_user(accounts[0])
    return result


def enqueue(s, plan_updates=None):
    context=service.context(s['user'],s['batch'])
    assert context.get('sourceRevision'),context
    body={'expectedSourceRevision':context['sourceRevision'],'idempotencyKey':uuid4().hex,'reason':'可靠排课真实验收',
          'plan':{'version':1,'week1Monday':'2026-09-14','defaultCampus':'MAIN',
                  'slotBlocks':{'MAIN':{str(n):'上午' for n in range(1,5)}},
                  'taskPatterns':{s['task']:[2,2]},'minDayGap':{s['task']:1}},'options':{'time_limit':2}}
    body['plan'].update(plan_updates or {})
    return service.enqueue(s['user'],s['batch'],body)


def candidate(s):
    job=enqueue(s)
    run_pending(s['tid'])
    finished=service.get_job(s['user'],s['batch'],job['jobId'])
    assert finished['state']=='SUCCEEDED',finished
    return finished


def item_count(s):
    with get_sessionmaker()() as db:
        return db.scalar(select(func.count()).select_from(AaScheduleItem).where(
            AaScheduleItem.tenant_id==s['tid'],AaScheduleItem.batch_id==int(s['batch']),AaScheduleItem.is_deleted.is_(False)))


def test_candidate_apply_and_duplicate_receipt(scenario):
    s=scenario;j=candidate(s)
    assert item_count(s)==0
    receipt=apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    assert receipt['status']=='DRAFT' and receipt['writtenItems']==4
    assert apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])['idempotent']
    assert item_count(s)==4


def test_changed_source_cannot_apply(scenario):
    s=scenario;j=candidate(s)
    with get_sessionmaker()() as db:
        db.get(AaClassroom,s['room']).capacity=1;db.commit()
    with pytest.raises(AppException,match='学校数据已变化'):
        apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    assert item_count(s)==0


def test_audit_failure_rolls_back_draft(scenario,monkeypatch):
    s=scenario;j=candidate(s)
    from app.modules.academic_affairs.optimizer.persistence import Repository
    original=Repository._audit
    def failing(self,db,action,*args):
        if action=='CANDIDATE_APPLY':raise RuntimeError('injected audit failure')
        return original(self,db,action,*args)
    monkeypatch.setattr(Repository,'_audit',failing)
    with pytest.raises(RuntimeError,match='injected audit failure'):
        apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    assert item_count(s)==0
    assert service.get_job(s['user'],s['batch'],j['jobId'])['state']=='SUCCEEDED'


def test_two_admins_competing_candidates(scenario):
    s=scenario;a=candidate(s);b=candidate(s)
    def adopt(pair):
        user,job=pair;set_tenant(s['tid']);set_current_user(user)
        try:return apply_candidate(user,s['batch'],job['jobId'],job['version'])['status']
        except AppException as e:return e.http_status
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(adopt,[(s['user'],a),(s['other'],b)]))
    assert sorted(map(str,results))==['409','DRAFT']
    assert item_count(s)==4


def test_queue_lease_cancel_retry_and_tenant_scope(scenario):
    from app.modules.academic_affairs.optimizer.contracts import InputError
    s=scenario;j=enqueue(s)
    repository=service._repository(s['user'])
    def claim(_):
        set_tenant(s['tid']);return repository.claim(str(s['tid']))
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed=[c for c in pool.map(claim,[1,2]) if c]
    assert len(claimed)==1
    first=claimed[0]
    with get_sessionmaker()() as db:
        db.execute(update(jobs).where(jobs.c.tenant_id==s['tid'],jobs.c.id==int(j['jobId'])).values(
            lease_until=datetime.utcnow()-timedelta(seconds=1)))
        db.commit()
    second=repository.claim(str(s['tid']))
    assert second['leaseToken']!=first['leaseToken']
    assert not repository.heartbeat(str(s['tid']),j['jobId'],first['leaseToken'])
    current=repository.get(str(s['tid']),j['jobId'])
    assert current['attempts']==2
    cancelled=service.cancel_job(s['user'],s['batch'],j['jobId'],current['version'])
    assert cancelled['state']=='CANCELLED'
    assert not repository.heartbeat(str(s['tid']),j['jobId'],second['leaseToken'])
    with pytest.raises(InputError,match='TENANT_SCOPE_MISMATCH'):
        repository.get(str(s['tid']+1),j['jobId'])
    assert item_count(s)==0


def test_revoked_creator_does_not_solve(scenario):
    s=scenario;j=enqueue(s)
    with get_sessionmaker()() as db:
        db.execute(update(UserRole).where(UserRole.tenant_id==s['tid'],UserRole.user_id==int(s['user']['userId'][3:])).values(status='DISABLED'))
        db.commit()
    run_pending(s['tid'])
    result=service._repository(s['user']).get(str(s['tid']),j['jobId'])
    assert result['state']=='REJECTED'
    assert item_count(s)==0


def test_apply_then_original_publish_gate(scenario):
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as canonical
    s=scenario;j=candidate(s);other=candidate(s)
    with pytest.raises(AppException):canonical.publish(s['batch'],s['user'])
    apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    assert canonical.pre_publish(s['batch'],s['user'])['status']=='PRE_PUBLISHED'
    result=canonical.publish(s['batch'],s['user'])
    assert result['status']=='PUBLISHED'
    assert not service.get_job(s['user'],s['batch'],other['jobId'])['canApply']
    from app.models import AaScheduleScopeHead
    with get_sessionmaker()() as db:
        head=db.scalar(select(AaScheduleScopeHead).where(AaScheduleScopeHead.tenant_id==s['tid'],AaScheduleScopeHead.term_id==s['term']))
        assert str(head.active_batch_id)==s['batch']


def test_four_end_published_reader_same_items(scenario):
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as canonical
    from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile
    s=scenario;j=candidate(s)
    apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    set_current_user(s['student'])
    assert mobile.schedule_my(s['student'])['items']==[]
    set_current_user(s['teacher'])
    assert mobile.teacher_schedule_my(s['teacher'])['items']==[]
    set_current_user(s['user'])
    canonical.pre_publish(s['batch'],s['user']);canonical.publish(s['batch'],s['user'])
    set_current_user(s['student'])
    student=mobile.schedule_my(s['student'])
    from app.student_portal import router as portal
    student_pc=portal.academic_schedule(s['student'])['data']
    set_current_user(s['teacher'])
    teacher=mobile.teacher_schedule_my(s['teacher'])
    teacher_pc=canonical.teacher_schedule(s['teacher'],'opt-teacher',str(s['term']))
    ids=lambda rows:{str(r.get('scheduleItemId') or r.get('itemId')) for r in rows}
    expected=ids(student['items'])
    assert len(expected)==4
    assert ids(student_pc['items'])==ids(teacher_pc['items'])==ids(teacher['items'])==expected
    assert {str(r.get('activeBatchId')) for r in teacher['items']}=={s['batch']}


def test_replan_preserves_manual_import_locked_and_replaces_auto(scenario):
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as canonical
    s=scenario
    with get_sessionmaker()() as db:
        batch=db.get(AaScheduleBatch,int(s['batch']));task=db.get(AaTeachingTask,int(s['task']))
        preserved=[]
        for no,source in enumerate(['MANUAL','IMPORT','LOCKED'],1):
            item=canonical._build_item(db,batch,task,{'taskId':s['task'],'weekday':1,'slotNo':no,
                'startWeek':1,'endWeek':2,'weekParity':'ALL','classroom':'验收实训室'},item_source=source)
            db.add(item);db.flush();preserved.append(item.id)
        db.commit()
    for replace in [False,True]:
        j=enqueue(s,{'replaceAuto':replace,'taskPatterns':{s['task']:[1]},'minDayGap':{s['task']:0}})
        run_pending(s['tid']);j=service.get_job(s['user'],s['batch'],j['jobId'])
        assert j['state']=='SUCCEEDED'
        apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
        assert item_count(s)==4
        with get_sessionmaker()() as db:
            assert all(not db.get(AaScheduleItem,i).is_deleted for i in preserved)


def test_odd_week_adoption_keeps_formal_parity(scenario):
    s=scenario
    with get_sessionmaker()() as db:
        db.get(AaTeachingTask,int(s['task'])).total_hours=4;db.commit()
    j=enqueue(s,{'taskParities':{s['task']:'ODD'}});run_pending(s['tid'])
    j=service.get_job(s['user'],s['batch'],j['jobId'])
    assert j['state']=='SUCCEEDED'
    apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    with get_sessionmaker()() as db:
        rows=db.scalars(select(AaScheduleItem).where(AaScheduleItem.tenant_id==s['tid'])).all()
        assert len(rows)==4 and all(r.week_parity=='ODD' for r in rows)


def test_invalid_current_roster_blocks_source_and_adoption(scenario):
    s=scenario;j=candidate(s)
    with get_sessionmaker()() as db:
        version=db.scalar(select(AaTeachingClassRosterVersion).where(AaTeachingClassRosterVersion.tenant_id==s['tid']))
        version.member_count+=1;db.commit()
    assert not service.context(s['user'],s['batch'])['canGenerate']
    with pytest.raises(AppException):apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    assert item_count(s)==0


def test_read_only_teacher_cannot_adopt_and_recovered_job_keeps_action(scenario):
    s=scenario;j=candidate(s)
    with get_sessionmaker()() as db:
        key=db.scalar(select(jobs.c.idempotency_key).where(jobs.c.id==int(j['jobId'])))
    recovered=service.lookup_job(s['user'],s['batch'],key)
    assert recovered['job']['canApply'] is True
    set_current_user(s['teacher'])
    with pytest.raises(AppException):apply_candidate(s['teacher'],s['batch'],j['jobId'],j['version'])
    with pytest.raises(AppException):service.cancel_job(s['teacher'],s['batch'],j['jobId'],j['version'])
    assert item_count(s)==0


def test_student_removed_from_formal_roster_cannot_use_old_class_fallback(scenario):
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as canonical
    from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile
    s=scenario;j=candidate(s);apply_candidate(s['user'],s['batch'],j['jobId'],j['version'])
    canonical.pre_publish(s['batch'],s['user']);canonical.publish(s['batch'],s['user'])
    set_current_user(s['student'])
    assert len(mobile.schedule_my(s['student'])['items'])==4
    with get_sessionmaker()() as db:
        member=db.scalar(select(AaTeachingClassMember).where(AaTeachingClassMember.tenant_id==s['tid'],AaTeachingClassMember.student_id==int(s['studentId'])))
        member.status='REMOVED';db.commit()
    assert mobile.schedule_my(s['student'])['items']==[]
