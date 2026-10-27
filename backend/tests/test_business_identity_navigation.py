from datetime import datetime
from sqlalchemy import select


def seed_relations(db, tenant_id, teacher_id=None):
    from app.models import (User, College, Major, SchoolClass, StudentProfile, AaTerm, AaCourse,
        AaTeachingTaskBatch, AaTeachingTask, AaTeachingClass, AaTeachingClassTeacher,
        GraduationBatch, GraduationMentor, GraduationStudent, InternshipBatch, InternshipRecord)
    def add(model, **fields):
        row=model(tenant_id=tenant_id,**fields);db.add(row);db.flush();return row
    teacher=db.get(User,teacher_id) if teacher_id else add(User,login_name='D606-T001',real_name='四域验收教师甲',password_hash='fixture-not-login',user_type='TEACHER',status='ACTIVE')
    assert teacher.tenant_id==tenant_id
    other=add(User,login_name='D606-T002',real_name='四域验收教师乙',password_hash='fixture-not-login',user_type='TEACHER',status='ACTIVE')
    college=add(College,college_name='D606四域验收学院',status='ACTIVE')
    major=add(Major,college_id=college.id,major_name='D606验收专业',status='ACTIVE')
    group=add(SchoolClass,major_id=major.id,class_name='D606关系验收班',grade='2026',status='ACTIVE',class_status='NORMAL',counselor_id=teacher.id,head_teacher_id=other.id)
    a=add(StudentProfile,student_no='D606-S001',real_name='四域虚构学生甲',college_id=college.id,major_id=major.id,class_id=group.id)
    b=add(StudentProfile,student_no='D606-S002',real_name='四域虚构学生乙',college_id=college.id,major_id=major.id,class_id=group.id)
    term=add(AaTerm,year_code='2026-2027',term_no=1,term_name='D606验收学期',start_date=datetime(2026,9,1),end_date=datetime(2027,1,31),teaching_weeks=20,status='DRAFT')
    course=add(AaCourse,course_code='D606-COURSE',course_name='D606跨域验收课程')
    academic=add(AaTeachingTaskBatch,term_id=term.id,batch_name='D606教务批次',status='DRAFT')
    task=add(AaTeachingTask,batch_id=academic.id,course_id=course.id,course_name=course.course_name,class_id=group.id,
        teacher_key=teacher.login_name,teacher_id=teacher.id,teacher_name=teacher.real_name,teaching_class_code='D606-TC',teaching_class_name='D606正式教学班',status='ASSIGNED')
    tc=add(AaTeachingClass,teaching_task_id=task.id,term_id=term.id,course_id=course.id,class_code='D606-TC',class_name='D606正式教学班',status='ACTIVE')
    add(AaTeachingClassTeacher,teaching_class_id=tc.id,teacher_key=teacher.login_name,teacher_id=None,teacher_name=teacher.real_name,status='ACTIVE')
    gd_batch=add(GraduationBatch,batch_name='D606毕设批次',batch_no='D606-GD',status='DRAFT')
    mentor=add(GraduationMentor,teacher_no=teacher.login_name,teacher_name=teacher.real_name)
    gd=add(GraduationStudent,batch_id=gd_batch.id,student_id=a.id,student_no=a.student_no,name=a.real_name,
        class_id=str(group.id),class_name=group.class_name,college_id=str(college.id),major_id=str(major.id),mentor_id=mentor.id,advisor_name=teacher.real_name,record_status='ACTIVE')
    internship=add(InternshipBatch,batch_name='D606实习批次',batch_no='D606-INTERN',status='DRAFT')
    ia=add(InternshipRecord,student_id=a.id,batch_id=internship.id,advisor_user_id=other.id,advisor_name=other.real_name,status='PREPARING')
    ib=add(InternshipRecord,student_id=b.id,batch_id=internship.id,advisor_user_id=teacher.id,advisor_name=teacher.real_name,status='PREPARING')
    missing=add(SchoolClass,major_id=major.id,class_name='D606待补辅导员班',grade='2026',status='ACTIVE',class_status='NORMAL')
    return {'teacherId':teacher.id,'otherTeacherId':other.id,'classId':group.id,'missingClassId':missing.id,
        'majorId':major.id,'studentA':a.id,'studentB':b.id,'teachingClassId':tc.id,'taskId':task.id,
        'academicBatchId':academic.id,'gdStudentId':gd.id,'gdBatchId':gd_batch.id,
        'internshipA':ia.id,'internshipB':ib.id,'internBatchId':internship.id}


def test_four_domain_sources_pagination_and_names_stay_separate(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, AaTeachingTask
    from app.services.business_identity_service import list_business_identities,list_identity_objects
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        ids=seed_relations(db,tid)
        # A stale task snapshot must not override a formal teaching-class relationship.
        task=db.get(AaTeachingTask,ids['taskId']);task.teacher_key='D606-T002';task.teacher_id=ids['otherTeacherId']
        for index in range(21):
            db.add(SchoolClass(tenant_id=tid,major_id=ids['majorId'],class_name=f'分页虚构班{index}',status='ACTIVE',counselor_id=ids['teacherId']))
        db.commit()
    rows=list_business_identities(tenant_id=tid,user_id=ids['teacherId'])['list']
    by_type={row['identityType']:row for row in rows}
    assert {'COUNSELOR_CLASS','COURSE_TEACHER','GD_MENTOR','INTERNSHIP_ADVISOR'} <= set(by_type)
    assert len({row['identityKey'] for row in rows})==len(rows)
    assert by_type['COURSE_TEACHER']['objects']==[f"teachingClass:{ids['teachingClassId']}"]
    gd=by_type['GD_MENTOR']['objectItems'][0];intern=by_type['INTERNSHIP_ADVISOR']['objectItems'][0]
    assert gd['route']['path'].endswith('/graduation/students/'+str(ids['gdStudentId']))
    assert intern['route']['path'].endswith('/internship/students/'+str(ids['internshipB']))
    assert gd['batchName']=='D606毕设批次' and intern['batchName']=='D606实习批次'
    other=list_business_identities(tenant_id=tid,user_id=ids['otherTeacherId'])['list']
    assert not any(row['identityType']=='COURSE_TEACHER' for row in other)
    assert next(row for row in other if row['identityType']=='INTERNSHIP_ADVISOR')['objects']==[f"internship:{ids['internshipA']}"]
    page=list_identity_objects(tenant_id=tid,user_id=ids['teacherId'],identity_type='COUNSELOR_CLASS',
        subject_key=f"user:{ids['teacherId']}",page=2,page_size=20)
    assert page['total']==22 and len(page['list'])==2


def test_relation_object_from_other_school_has_no_label_or_destination(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College,Major,SchoolClass
    from app.services.business_identity_objects import describe_objects
    tid=1000000000000000001
    with get_sessionmaker()() as db:
        c=College(tenant_id=tid+1,college_name='不可泄露学院');db.add(c);db.flush()
        m=Major(tenant_id=tid+1,college_id=c.id,major_name='不可泄露专业');db.add(m);db.flush()
        group=SchoolClass(tenant_id=tid+1,major_id=m.id,class_name='不可泄露班级');db.add(group);db.commit()
        row=describe_objects(db,tid,[f'class:{group.id}'])[f'class:{group.id}']
        assert row['available'] is False and row['route'] is None
        assert '不可泄露' not in row['label']


def test_formal_affairs_duties_take_priority_and_expired_duties_do_not_revive_legacy_fields(db_mode):
    from datetime import timedelta
    from app.db.session import get_sessionmaker
    from app.models import AffairsCounselorAssignment
    from app.services.business_identity_service import list_business_identities
    from app.core.timeutil import utc_now_naive
    tid=1000000000000000001;now=utc_now_naive()
    with get_sessionmaker()() as db:
        ids=seed_relations(db,tid)
        primary=AffairsCounselorAssignment(tenant_id=tid,class_id=ids['classId'],user_id=ids['otherTeacherId'],
            duty_type='PRIMARY',status='ACTIVE',effective_from=now-timedelta(days=1))
        db.add(primary)
        for duty,start,end in [('CO',now-timedelta(days=1),None),('TEMP',now+timedelta(days=1),now+timedelta(days=2)),
                               ('TEMP',now-timedelta(days=2),now-timedelta(days=1))]:
            db.add(AffairsCounselorAssignment(tenant_id=tid,class_id=ids['classId'],user_id=ids['teacherId'],
                duty_type=duty,status='ACTIVE',effective_from=start,effective_to=end))
        db.commit();primary_id=primary.id
    mine=list_business_identities(tenant_id=tid,user_id=ids['teacherId'])['list']
    assert not any(row['identityType'] in ('COUNSELOR_CLASS','COUNSELOR_TEMP') for row in mine)
    assert next(row for row in mine if row['identityType']=='COUNSELOR_CO')['objectItems'][0]['relationSource']=='学工正式责任台账'
    other=list_business_identities(tenant_id=tid,user_id=ids['otherTeacherId'])['list']
    assert any(row['identityType']=='COUNSELOR_CLASS' for row in other)
    with get_sessionmaker()() as db:
        db.get(AffairsCounselorAssignment,primary_id).status='ENDED';db.commit()
    for uid in (ids['teacherId'],ids['otherTeacherId']):
        assert not any(row['identityType']=='COUNSELOR_CLASS' for row in list_business_identities(tenant_id=tid,user_id=uid)['list'])
